"""WhisperTyper engine — recording, transcription, AI editing, hotkeys."""

import os
import tempfile
import time
import wave
import threading

import pyaudio
import requests
import pyperclip
from faster_whisper import WhisperModel
from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QObject, Signal

from config import ConfigManager
from punctuation import smart_punctuation


class WhisperEngine(QObject):
    # Signals
    model_loading = Signal()
    model_ready = Signal()
    recording_started = Signal(str)           # mode: "dictate" | "ai"
    recording_stopped = Signal(float)         # duration_sec
    transcription_started = Signal()
    transcription_done = Signal(str, str)     # text, mode
    ai_started = Signal()
    ai_done = Signal(str, str)               # original, edited
    error = Signal(str)                       # error message

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.model = None
        self._update_device()

        # Recording state
        self._is_recording = False
        self._recording_mode = None
        self._audio_frames = []
        self._audio_lock = threading.Lock()
        self._recording_done = threading.Event()
        self._pa = pyaudio.PyAudio()

        # Text injection tracking
        self.last_typed_text = ""
        self._kb_controller = pynput_keyboard.Controller()

        # Hotkey listener
        self._hotkey_listener = None

    def _update_device(self):
        choice = self.config.get("whisper_device")
        if choice == "auto":
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = choice
        self.use_cuda = self.device == "cuda"
        self.compute_type = "float16" if self.use_cuda else "int8"

    def load_model(self):
        """Load Whisper model in current thread (call from QThread)."""
        self._update_device()
        self.model_loading.emit()
        model_name = self.config.get("whisper_model")
        self.model = WhisperModel(
            model_name, device=self.device, compute_type=self.compute_type
        )
        self.model_ready.emit()

    def start_hotkey_listener(self):
        """Start global hotkey listener."""
        dictate_key = self._parse_key(self.config.get("hotkey_dictate"))
        ai_key = self._parse_key(self.config.get("hotkey_ai"))

        def on_press(key):
            if self.model is None:
                return
            normalized = self._normalize_key(key)
            print(f"[DEBUG] press: {key!r} -> '{normalized}' (expect '{dictate_key}'/'{ai_key}', recording={self._is_recording})")
            if normalized == dictate_key and not self._is_recording:
                self._start_recording("dictate")
            elif normalized == ai_key and not self._is_recording:
                self._start_recording("ai")

        def on_release(key):
            normalized = self._normalize_key(key)
            print(f"[DEBUG] release: {key!r} -> '{normalized}' (recording={self._is_recording})")
            if normalized in (dictate_key, ai_key) and self._is_recording:
                self._stop_recording()

        self._hotkey_listener = pynput_keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
        )
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def stop_hotkey_listener(self):
        if self._hotkey_listener:
            self._hotkey_listener.stop()

    def _parse_key(self, key_str):
        """Convert config key string like 'F9' to comparable value."""
        return key_str.lower()

    def _normalize_key(self, key):
        """Normalize a pynput key to a comparable string."""
        if hasattr(key, "name"):
            return key.name.lower()
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return str(key).lower()

    def _start_recording(self, mode):
        self._is_recording = True
        self._recording_mode = mode
        self._recording_done.clear()
        self.recording_started.emit(mode)
        self._play_sound("start")
        print(f"[REC] Inspelning startad ({mode})")
        t = threading.Thread(target=self._record_audio, daemon=True)
        t.start()

    def _stop_recording(self):
        if not self._is_recording:
            return
        mode = self._recording_mode
        self._is_recording = False
        print(f"[REC] Inspelning stoppad ({mode}), väntar på ljudtråd...")
        t = threading.Thread(target=self._wait_and_process, args=(mode,), daemon=True)
        t.start()

    def _wait_and_process(self, mode):
        self._recording_done.wait(timeout=3)
        print(f"[REC] Ljudtråd klar, bearbetar...")
        self._process_recording(mode)

    def _record_audio(self):
        mic_index = self._get_mic_index()
        kwargs = dict(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
        )
        if mic_index is not None:
            kwargs["input_device_index"] = mic_index

        stream = self._pa.open(**kwargs)
        start = time.time()
        with self._audio_lock:
            self._audio_frames = []

        max_sec = self.config.get("max_record_sec")
        while self._is_recording and (time.time() - start) < max_sec:
            data = stream.read(1024, exception_on_overflow=False)
            self._audio_frames.append(data)

        stream.stop_stream()
        stream.close()
        duration = time.time() - start
        print(f"[REC] Ljudström stängd ({duration:.1f}s, {len(self._audio_frames)} frames)")
        self._recording_done.set()
        self.recording_stopped.emit(duration)

    def _get_mic_index(self):
        mic = self.config.get("microphone")
        if mic == "default":
            return None
        try:
            return int(mic)
        except (ValueError, TypeError):
            return None

    def _process_recording(self, mode):
        with self._audio_lock:
            frames = list(self._audio_frames)

        if not frames:
            print("[PROC] Inga frames inspelade!")
            self.error.emit("Inget ljud inspelat.")
            return

        print(f"[PROC] {len(frames)} frames, sparar WAV...")
        # Save WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b"".join(frames))

        # Transcribe
        print(f"[PROC] Transkriberar med {self.device}...")
        self.transcription_started.emit()
        t0 = time.time()
        try:
            lang = self.config.get("language")
            if lang == "auto":
                lang = None
            segments, info = self.model.transcribe(
                tmp_path,
                language=lang,
                beam_size=1,
                condition_on_previous_text=True,
            )
            text = "".join(s.text for s in segments).strip()
            print(f"[PROC] Klar på {time.time()-t0:.1f}s: {text[:60]}")
        except Exception as e:
            self.error.emit(f"Whisper-fel: {e}")
            return
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        if not text:
            self.error.emit("Inget tal kändes igen.")
            return

        self._play_sound("done")

        if mode == "dictate":
            text = smart_punctuation(text)
            self.transcription_done.emit(text, mode)
            self._type_text(text)
            self.config.add_history_entry(text, 0, mode)
        elif mode == "ai":
            self.transcription_done.emit(text, mode)
            self._handle_ai_edit(text)

    def _handle_ai_edit(self, instruction):
        if not self.last_typed_text:
            self.error.emit("Ingen tidigare text att redigera. Diktera med F9 först.")
            return

        self.ai_started.emit()
        provider = self.config.get("ai_provider")

        try:
            if provider == "ollama":
                new_text = self._ai_ollama(instruction)
            else:
                new_text = self._ai_cloud(instruction)

            if new_text:
                self.ai_done.emit(self.last_typed_text, new_text)
                self._replace_last_text(new_text)
                self.config.add_history_entry(
                    new_text, 0, "ai_edit",
                    original_text=self.last_typed_text,
                )
        except Exception as e:
            self.error.emit(f"AI-fel: {e}")

    def _get_system_prompt(self):
        return self.config.get_active_prompt()

    def _ai_ollama(self, instruction):
        url = "http://localhost:11434"
        model = self.config.get("ollama_model")
        response = requests.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": self._get_system_prompt()},
                    {
                        "role": "user",
                        "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}',
                    },
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    def _ai_cloud(self, instruction):
        cloud_provider = self.config.get("cloud_provider")
        api_key = self.config.get("cloud_api_key")
        model = self.config.get("cloud_model")

        if not api_key:
            raise ValueError("API-nyckel saknas. Ange den i inställningarna.")

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {
                "role": "user",
                "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}',
            },
        ]

        if cloud_provider == "openai":
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            # Anthropic
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "system": self._get_system_prompt(),
                    "messages": [
                        {
                            "role": "user",
                            "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}',
                        }
                    ],
                    "max_tokens": 1000,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"].strip()

    def _type_text(self, text):
        if not text:
            return
        old_clipboard = ""
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            pass
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            with self._kb_controller.pressed(pynput_keyboard.Key.ctrl):
                self._kb_controller.tap("v")
            time.sleep(0.15)
            pyperclip.copy(old_clipboard)
            self.last_typed_text = text
        except Exception as e:
            self.error.emit(f"Kunde inte skriva in text: {e}")

    def _replace_last_text(self, new_text):
        if self.last_typed_text:
            for _ in range(len(self.last_typed_text)):
                self._kb_controller.tap(pynput_keyboard.Key.backspace)
            time.sleep(0.05)
        self._type_text(new_text)

    def _play_sound(self, sound_type):
        """Play sound effect if enabled."""
        if sound_type == "start" and not self.config.get("sound_on_record_start"):
            return
        if sound_type == "done" and not self.config.get("sound_on_transcription_done"):
            return
        # TODO: Implement sound playback with QMediaPlayer

    def ai_edit_text(self, instruction, original_text):
        """AI edit triggered from UI (not via hotkey)."""
        self.last_typed_text = original_text
        self.ai_started.emit()
        try:
            provider = self.config.get("ai_provider")
            if provider == "ollama":
                new_text = self._ai_ollama(instruction)
            else:
                new_text = self._ai_cloud(instruction)
            if new_text:
                self.ai_done.emit(original_text, new_text)
                self.config.add_history_entry(
                    new_text, 0, "ai_edit", original_text=original_text
                )
                return new_text
        except Exception as e:
            self.error.emit(f"AI-fel: {e}")
        return None

    def get_microphones(self):
        """List available microphones."""
        mics = []
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                mics.append({"index": i, "name": info["name"]})
        return mics

    def cleanup(self):
        self.stop_hotkey_listener()
        self._pa.terminate()
