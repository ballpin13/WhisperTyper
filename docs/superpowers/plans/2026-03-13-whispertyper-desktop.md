# WhisperTyper Desktop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the WhisperTyper prototype (single-file terminal script) into a full PySide6 desktop app with system tray, dashboard UI, and configuration management.

**Architecture:** PySide6 GUI with engine running in QThread, communicating via Qt signals. Config stored as JSON in %APPDATA%. System tray provides always-on access. Dashboard has three tabs: Live, History, Settings.

**Tech Stack:** Python 3.9+, PySide6, OpenAI Whisper, PyAudio, pynput, pyperclip, requests, torch

**Spec:** `docs/superpowers/specs/2026-03-13-whispertyper-desktop-design.md`

---

## File Structure

```
WhisperTyper/
  main.py                # App entry point — QApplication, tray, dashboard
  engine.py              # QObject: recording, transcription, AI, hotkeys, sounds
  config.py              # Load/save config.json, history.json, prompts.json
  punctuation.py         # Smart punctuation post-processing (extracted from prototype)
  ui/
    __init__.py
    dashboard.py         # QMainWindow with QTabWidget
    tab_live.py          # Live tab widget
    tab_history.py       # History tab widget
    tab_settings.py      # Settings tab widget
  assets/
    icon_ready.png       # 64x64 green circle
    icon_recording.png   # 64x64 red circle
    icon_transcribing.png # 64x64 yellow circle
    icon_ai.png          # 64x64 blue circle
    icon_loading.png     # 64x64 grey circle
  tests/
    test_config.py
    test_punctuation.py
  requirements.txt
```

---

## Chunk 1: Foundation

### Task 1: config.py — Configuration management

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create tests/test_config.py with core tests**

```python
import pytest
import json
import os
import tempfile
from pathlib import Path


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary config directory."""
    return tmp_path


class TestConfigManager:
    def test_default_config_created_on_first_load(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        assert cm.get("whisper_model") == "medium"
        assert cm.get("language") == "sv"
        assert cm.get("hotkey_dictate") == "F9"
        assert cm.get("hotkey_ai") == "F10"

    def test_set_and_get(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.set("whisper_model", "large")
        assert cm.get("whisper_model") == "large"

    def test_config_persists_to_disk(self, tmp_config_dir):
        from config import ConfigManager
        cm1 = ConfigManager(config_dir=tmp_config_dir)
        cm1.set("whisper_model", "tiny")
        cm2 = ConfigManager(config_dir=tmp_config_dir)
        assert cm2.get("whisper_model") == "tiny"

    def test_default_prompts_created(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        profiles = cm.get_prompt_profiles()
        assert len(profiles) == 1
        assert profiles[0]["id"] == "standard"
        assert profiles[0]["deletable"] is False

    def test_add_prompt_profile(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.add_prompt_profile("test", "Test Profile", "You are a test assistant.")
        profiles = cm.get_prompt_profiles()
        assert len(profiles) == 2
        assert profiles[1]["name"] == "Test Profile"

    def test_cannot_delete_standard_profile(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        with pytest.raises(ValueError):
            cm.delete_prompt_profile("standard")

    def test_delete_custom_profile(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.add_prompt_profile("custom", "Custom", "prompt")
        cm.delete_prompt_profile("custom")
        assert len(cm.get_prompt_profiles()) == 1

    def test_add_history_entry(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.add_history_entry("Hej", 2.1, "dictate")
        history = cm.get_history()
        assert len(history) == 1
        assert history[0]["text"] == "Hej"
        assert history[0]["mode"] == "dictate"

    def test_history_max_limit(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.set("max_history", 3)
        for i in range(5):
            cm.add_history_entry(f"Text {i}", 1.0, "dictate")
        assert len(cm.get_history()) == 3

    def test_clear_history(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        cm.add_history_entry("Hej", 1.0, "dictate")
        cm.clear_history()
        assert len(cm.get_history()) == 0

    def test_get_active_prompt(self, tmp_config_dir):
        from config import ConfigManager
        cm = ConfigManager(config_dir=tmp_config_dir)
        prompt = cm.get_active_prompt()
        assert "textassistent" in prompt.lower()
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_config.py -v`
Expected: FAIL (config module not found)

- [ ] **Step 3: Implement config.py**

```python
import json
import uuid
from pathlib import Path
from datetime import datetime
import platform

APP_NAME = "WhisperTyper"

DEFAULT_CONFIG = {
    "whisper_model": "medium",
    "language": "sv",
    "hotkey_dictate": "F9",
    "hotkey_ai": "F10",
    "ai_provider": "ollama",
    "ollama_model": "mistral:7b",
    "cloud_provider": "openai",
    "cloud_model": "gpt-4o-mini",
    "cloud_api_key": "",
    "active_prompt_profile": "standard",
    "microphone": "default",
    "audio_output": "default",
    "sound_on_record_start": True,
    "sound_on_transcription_done": True,
    "sound_volume": 70,
    "show_notifications": True,
    "notification_duration_sec": 4,
    "max_record_sec": 60,
    "autostart": False,
    "max_history": 500,
}

DEFAULT_PROMPT = (
    "Du är en textassistent. Användaren har dikterat en text och vill nu ändra den. "
    "Returnera BARA den redigerade texten, inget annat. Ingen förklaring, inga citattecken. "
    "Om användaren säger att du hörde fel, korrigera texten. "
    "Om användaren ger en redigeringsinstruktion, utför den."
)

DEFAULT_PROMPTS = {
    "profiles": [
        {
            "id": "standard",
            "name": "Standard",
            "system_prompt": DEFAULT_PROMPT,
            "deletable": False,
        }
    ]
}


def _default_config_dir():
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


import os


class ConfigManager:
    def __init__(self, config_dir=None):
        self._dir = Path(config_dir) if config_dir else _default_config_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self._dir / "config.json"
        self._history_path = self._dir / "history.json"
        self._prompts_path = self._dir / "prompts.json"
        self._config = self._load_json(self._config_path, DEFAULT_CONFIG)
        self._history = self._load_json(self._history_path, [])
        self._prompts = self._load_json(self._prompts_path, DEFAULT_PROMPTS)

    def _load_json(self, path, default):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        data = default.copy() if isinstance(default, dict) else list(default)
        self._save_json(path, data)
        return data

    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Config ──
    def get(self, key):
        return self._config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self._config[key] = value
        self._save_json(self._config_path, self._config)

    # ── Prompts ──
    def get_prompt_profiles(self):
        return self._prompts["profiles"]

    def get_active_prompt(self):
        active_id = self.get("active_prompt_profile")
        for p in self._prompts["profiles"]:
            if p["id"] == active_id:
                return p["system_prompt"]
        return self._prompts["profiles"][0]["system_prompt"]

    def add_prompt_profile(self, profile_id, name, system_prompt):
        self._prompts["profiles"].append({
            "id": profile_id,
            "name": name,
            "system_prompt": system_prompt,
            "deletable": True,
        })
        self._save_json(self._prompts_path, self._prompts)

    def update_prompt_profile(self, profile_id, system_prompt):
        for p in self._prompts["profiles"]:
            if p["id"] == profile_id:
                p["system_prompt"] = system_prompt
                self._save_json(self._prompts_path, self._prompts)
                return
        raise ValueError(f"Profile '{profile_id}' not found")

    def delete_prompt_profile(self, profile_id):
        for p in self._prompts["profiles"]:
            if p["id"] == profile_id:
                if not p["deletable"]:
                    raise ValueError("Cannot delete standard profile")
                self._prompts["profiles"].remove(p)
                self._save_json(self._prompts_path, self._prompts)
                return
        raise ValueError(f"Profile '{profile_id}' not found")

    # ── History ──
    def get_history(self):
        return self._history

    def add_history_entry(self, text, duration_sec, mode, original_text=None):
        entry = {
            "id": str(uuid.uuid4()),
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "duration_sec": round(duration_sec, 1),
            "mode": mode,
            "ai_edited": mode == "ai_edit",
            "original_text": original_text,
        }
        self._history.insert(0, entry)
        max_h = self.get("max_history")
        if max_h and len(self._history) > max_h:
            self._history = self._history[:max_h]
        self._save_json(self._history_path, self._history)
        return entry

    def delete_history_entry(self, entry_id):
        self._history = [h for h in self._history if h["id"] != entry_id]
        self._save_json(self._history_path, self._history)

    def clear_history(self):
        self._history = []
        self._save_json(self._history_path, self._history)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add config manager with settings, history, and prompt profiles"
```

---

### Task 2: punctuation.py — Extract smart punctuation

**Files:**
- Create: `punctuation.py`
- Create: `tests/test_punctuation.py`

- [ ] **Step 1: Create tests/test_punctuation.py**

```python
from punctuation import smart_punctuation


def test_fragetecken():
    assert smart_punctuation("hur mår du frågetecken") == "hur mår du?"

def test_utropstecken():
    assert smart_punctuation("stopp utropstecken") == "stopp!"

def test_kommatecken():
    assert smart_punctuation("hej kommatecken hur mår du") == "hej, hur mår du"

def test_semikolon():
    assert smart_punctuation("först detta semikolon sedan det") == "först detta; sedan det"

def test_tre_punkter():
    assert smart_punctuation("jag vet inte tre punkter") == "jag vet inte..."

def test_ellips():
    assert smart_punctuation("hmm ellips") == "hmm..."

def test_ny_rad():
    assert smart_punctuation("rad ett ny rad rad två") == "rad ett\nrad två"

def test_citattecken():
    assert smart_punctuation("han sa citattecken hej citattecken") == 'han sa "hej"'

def test_case_insensitive():
    assert smart_punctuation("FRÅGETECKEN") == "?"

def test_cleans_spaces_before_punctuation():
    assert smart_punctuation("hej  ?") == "hej?"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_punctuation.py -v`

- [ ] **Step 3: Create punctuation.py**

```python
import re

PUNCTUATION_MAP = [
    (r"\bfrågetecken\b", "?"),
    (r"\butropstecken\b", "!"),
    (r"\bkommatecken\b", ","),
    (r"\bsemikolon\b", ";"),
    (r"\btre punkter\b", "..."),
    (r"\bellips\b", "..."),
    (r"\bny rad\b", "\n"),
    (r"\bnyrad\b", "\n"),
    (r"\bcitattecken\b", '"'),
]


def smart_punctuation(text):
    result = text
    for pattern, symbol in PUNCTUATION_MAP:
        result = re.sub(pattern, symbol, result, flags=re.IGNORECASE)
    result = re.sub(r"\s+([?.!,;:])", r"\1", result)
    return result
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_punctuation.py -v`

- [ ] **Step 5: Commit**

```bash
git add punctuation.py tests/test_punctuation.py
git commit -m "feat: extract smart punctuation into separate module"
```

---

### Task 3: Generate asset icons

**Files:**
- Create: `assets/icon_ready.png`
- Create: `assets/icon_recording.png`
- Create: `assets/icon_transcribing.png`
- Create: `assets/icon_ai.png`
- Create: `assets/icon_loading.png`
- Create: `assets/generate_icons.py`

- [ ] **Step 1: Create icon generator script**

```python
"""Generate simple colored circle icons for system tray."""
from PIL import Image, ImageDraw

ICONS = {
    "icon_ready": "#4CAF50",        # green
    "icon_recording": "#f44336",     # red
    "icon_transcribing": "#FFC107",  # yellow
    "icon_ai": "#2196F3",           # blue
    "icon_loading": "#9E9E9E",      # grey
}

SIZE = 64

for name, color in ICONS.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=color)
    img.save(f"assets/{name}.png")
    print(f"Generated assets/{name}.png")
```

- [ ] **Step 2: Run the generator**

Run: `cd /home/rober/Projects/Whisper && pip install Pillow -q && python assets/generate_icons.py`

- [ ] **Step 3: Verify icons exist**

Run: `ls -la assets/*.png`

- [ ] **Step 4: Commit**

```bash
git add assets/
git commit -m "feat: add tray status icons"
```

---

## Chunk 2: Engine

### Task 4: engine.py — Core engine as QObject

**Files:**
- Create: `engine.py`

This refactors all logic from `whisper_typer.py` into a QObject that emits signals. No tests for hardware-dependent code — tested manually.

- [ ] **Step 1: Create engine.py**

```python
"""WhisperTyper engine — recording, transcription, AI editing, hotkeys."""

import os
import re
import tempfile
import time
import wave
import threading

import pyaudio
import requests
import pyperclip
import torch
import whisper
from pynput import keyboard as pynput_keyboard
from PySide6.QtCore import QObject, Signal, QThread

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
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.use_cuda = torch.cuda.is_available()

        # Recording state
        self._is_recording = False
        self._recording_mode = None
        self._audio_frames = []
        self._audio_lock = threading.Lock()
        self._pa = pyaudio.PyAudio()

        # Text injection tracking
        self.last_typed_text = ""
        self._last_focused_window = None
        self._kb_controller = pynput_keyboard.Controller()

        # Hotkey listener
        self._hotkey_listener = None
        self._pressed_keys = set()

    def load_model(self):
        """Load Whisper model in current thread (call from QThread)."""
        self.model_loading.emit()
        model_name = self.config.get("whisper_model")
        self.model = whisper.load_model(model_name, device=self.device)
        self.model_ready.emit()

    def start_hotkey_listener(self):
        """Start global hotkey listener."""
        dictate_key = self._parse_key(self.config.get("hotkey_dictate"))
        ai_key = self._parse_key(self.config.get("hotkey_ai"))

        def on_press(key):
            if self.model is None:
                return
            normalized = self._normalize_key(key)
            if normalized == dictate_key and not self._is_recording:
                self._start_recording("dictate")
            elif normalized == ai_key and not self._is_recording:
                self._start_recording("ai")

        def on_release(key):
            normalized = self._normalize_key(key)
            dk = dictate_key
            ak = ai_key
            if normalized in (dk, ak) and self._is_recording:
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
        if hasattr(key, 'name'):
            return key.name.lower()
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        return str(key).lower()

    def _start_recording(self, mode):
        self._is_recording = True
        self._recording_mode = mode
        self.recording_started.emit(mode)
        self._play_sound("start")
        t = threading.Thread(target=self._record_audio, daemon=True)
        t.start()

    def _stop_recording(self):
        if not self._is_recording:
            return
        mode = self._recording_mode
        self._is_recording = False
        # Processing happens after recording thread finishes
        # We use a small delay to let the recording thread exit
        t = threading.Thread(target=self._process_recording, args=(mode,), daemon=True)
        t.start()

    def _record_audio(self):
        stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024,
            input_device_index=self._get_mic_index(),
        )
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
        # Small delay to ensure recording thread has written all frames
        time.sleep(0.1)

        with self._audio_lock:
            frames = list(self._audio_frames)

        if not frames:
            self.error.emit("Inget ljud inspelat.")
            return

        # Save WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b"".join(frames))

        # Transcribe
        self.transcription_started.emit()
        try:
            result = self.model.transcribe(
                tmp_path,
                language=self.config.get("language"),
                fp16=self.use_cuda,
                condition_on_previous_text=True,
            )
            text = result["text"].strip()
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
                    original_text=self.last_typed_text
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
                    {"role": "user", "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}'},
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

        if cloud_provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
        else:
            url = "https://api.anthropic.com/v1/messages"

        if cloud_provider == "openai":
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}'},
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            response = requests.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "system": self._get_system_prompt(),
                    "messages": [
                        {"role": "user", "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}'},
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
        # Sound playback will be implemented with QSound/QMediaPlayer
        # For now, this is a placeholder
        pass

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
```

- [ ] **Step 2: Commit**

```bash
git add engine.py
git commit -m "feat: add WhisperEngine QObject with signals, recording, transcription, AI"
```

---

## Chunk 3: UI

### Task 5: ui/tab_live.py — Live tab

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/tab_live.py`

- [ ] **Step 1: Create ui/__init__.py (empty)**

- [ ] **Step 2: Create ui/tab_live.py**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QFrame,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont


class LiveTab(QWidget):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Status indicator
        status_frame = QFrame()
        status_frame.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; }")
        status_layout = QHBoxLayout(status_frame)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #9E9E9E; font-size: 20px;")
        self._status_text = QLabel("Laddar modell...")
        self._status_text.setFont(QFont("Segoe UI", 12))
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_text)
        status_layout.addStretch()

        # Active prompt profile
        profile_label = QLabel("Profil:")
        profile_label.setFont(QFont("Segoe UI", 9))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(150)
        self._update_profile_combo()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        status_layout.addWidget(profile_label)
        status_layout.addWidget(self._profile_combo)

        layout.addWidget(status_frame)

        # Last transcription
        trans_frame = QFrame()
        trans_frame.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; }")
        trans_layout = QVBoxLayout(trans_frame)

        trans_header = QLabel("SENASTE TRANSKRIBERING")
        trans_header.setStyleSheet("color: #999; font-size: 11px;")
        trans_layout.addWidget(trans_header)

        self._trans_text = QLabel("Ingen transkribering ännu.")
        self._trans_text.setWordWrap(True)
        self._trans_text.setFont(QFont("Segoe UI", 13))
        self._trans_text.setStyleSheet("color: #333;")
        trans_layout.addWidget(self._trans_text)

        self._trans_meta = QLabel("")
        self._trans_meta.setStyleSheet("color: #aaa; font-size: 11px;")
        trans_layout.addWidget(self._trans_meta)

        # Buttons
        btn_layout = QHBoxLayout()
        self._copy_btn = QPushButton("Kopiera")
        self._copy_btn.setStyleSheet("""
            QPushButton { background: #e3f2fd; color: #1976D2; border: none;
                          border-radius: 6px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #bbdefb; }
        """)
        self._copy_btn.clicked.connect(self._copy_text)

        self._ai_btn = QPushButton("Redigera med AI")
        self._ai_btn.setStyleSheet("""
            QPushButton { background: #e8f5e9; color: #388E3C; border: none;
                          border-radius: 6px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #c8e6c9; }
        """)
        self._ai_btn.clicked.connect(self._toggle_ai_edit)

        btn_layout.addWidget(self._copy_btn)
        btn_layout.addWidget(self._ai_btn)
        btn_layout.addStretch()
        trans_layout.addLayout(btn_layout)

        # AI edit area (hidden by default)
        self._ai_frame = QFrame()
        self._ai_frame.setVisible(False)
        ai_layout = QHBoxLayout(self._ai_frame)
        ai_layout.setContentsMargins(0, 8, 0, 0)
        self._ai_input = QTextEdit()
        self._ai_input.setPlaceholderText("Skriv en instruktion, t.ex. 'gör texten mer formell'...")
        self._ai_input.setMaximumHeight(60)
        self._ai_send_btn = QPushButton("Skicka")
        self._ai_send_btn.setStyleSheet("""
            QPushButton { background: #388E3C; color: white; border: none;
                          border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background: #2E7D32; }
        """)
        self._ai_send_btn.clicked.connect(self._send_ai_edit)
        ai_layout.addWidget(self._ai_input)
        ai_layout.addWidget(self._ai_send_btn, alignment=Qt.AlignTop)
        trans_layout.addWidget(self._ai_frame)

        layout.addWidget(trans_frame)
        layout.addStretch()

    def _connect_signals(self):
        self.engine.model_loading.connect(self._on_model_loading)
        self.engine.model_ready.connect(self._on_model_ready)
        self.engine.recording_started.connect(self._on_recording_started)
        self.engine.transcription_started.connect(self._on_transcription_started)
        self.engine.transcription_done.connect(self._on_transcription_done)
        self.engine.ai_started.connect(self._on_ai_started)
        self.engine.ai_done.connect(self._on_ai_done)
        self.engine.error.connect(self._on_error)

    def _update_profile_combo(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        active = self.config.get("active_prompt_profile")
        for i, p in enumerate(self.config.get_prompt_profiles()):
            self._profile_combo.addItem(p["name"], p["id"])
            if p["id"] == active:
                self._profile_combo.setCurrentIndex(i)
        self._profile_combo.blockSignals(False)

    def _on_profile_changed(self, index):
        profile_id = self._profile_combo.currentData()
        if profile_id:
            self.config.set("active_prompt_profile", profile_id)

    @Slot()
    def _on_model_loading(self):
        self._status_dot.setStyleSheet("color: #9E9E9E; font-size: 20px;")
        self._status_text.setText("Laddar modell...")

    @Slot()
    def _on_model_ready(self):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 20px;")
        self._status_text.setText("Redo")

    @Slot(str)
    def _on_recording_started(self, mode):
        self._status_dot.setStyleSheet("color: #f44336; font-size: 20px;")
        mode_text = "Spelar in..." if mode == "dictate" else "Spelar in AI-instruktion..."
        self._status_text.setText(mode_text)

    @Slot()
    def _on_transcription_started(self):
        self._status_dot.setStyleSheet("color: #FFC107; font-size: 20px;")
        self._status_text.setText("Transkriberar...")

    @Slot(str, str)
    def _on_transcription_done(self, text, mode):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 20px;")
        self._status_text.setText("Redo")
        if mode == "dictate":
            self._trans_text.setText(text)
            from datetime import datetime
            self._trans_meta.setText(f"{datetime.now().strftime('%H:%M')} • F9 diktering")

    @Slot()
    def _on_ai_started(self):
        self._status_dot.setStyleSheet("color: #2196F3; font-size: 20px;")
        self._status_text.setText("AI bearbetar...")

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 20px;")
        self._status_text.setText("Redo")
        self._trans_text.setText(edited)
        from datetime import datetime
        self._trans_meta.setText(f"{datetime.now().strftime('%H:%M')} • AI-redigerad")

    @Slot(str)
    def _on_error(self, msg):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 20px;")
        self._status_text.setText("Redo")

    def _copy_text(self):
        text = self._trans_text.text()
        if text and text != "Ingen transkribering ännu.":
            import pyperclip
            pyperclip.copy(text)

    def _toggle_ai_edit(self):
        self._ai_frame.setVisible(not self._ai_frame.isVisible())

    def _send_ai_edit(self):
        instruction = self._ai_input.toPlainText().strip()
        if not instruction:
            return
        original = self._trans_text.text()
        if not original or original == "Ingen transkribering ännu.":
            return
        self._ai_input.clear()
        self._ai_frame.setVisible(False)
        # Run in thread to avoid blocking UI
        import threading
        threading.Thread(
            target=self.engine.ai_edit_text,
            args=(instruction, original),
            daemon=True,
        ).start()
```

- [ ] **Step 3: Commit**

```bash
git add ui/
git commit -m "feat: add Live tab with status, transcription display, AI edit"
```

---

### Task 6: ui/tab_history.py — History tab

**Files:**
- Create: `ui/tab_history.py`

- [ ] **Step 1: Create ui/tab_history.py**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QDialog, QTextEdit, QDialogButtonBox, QFrame,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QAction


class HistoryTab(QWidget):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()
        self._connect_signals()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Sök i historik...")
        self._search_input.setStyleSheet("""
            QLineEdit { background: white; border: 1px solid #e0e0e0;
                        border-radius: 6px; padding: 8px 12px; font-size: 13px; }
        """)
        self._search_input.textChanged.connect(self._filter_history)
        search_layout.addWidget(self._search_input)

        self._clear_btn = QPushButton("Rensa historik")
        self._clear_btn.setStyleSheet("""
            QPushButton { background: #ffebee; color: #c62828; border: none;
                          border-radius: 6px; padding: 8px 16px; font-size: 12px; }
            QPushButton:hover { background: #ffcdd2; }
        """)
        self._clear_btn.clicked.connect(self._clear_history)
        search_layout.addWidget(self._clear_btn)

        layout.addLayout(search_layout)

        # History list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget { background: white; border: 1px solid #e0e0e0;
                          border-radius: 8px; font-size: 13px; }
            QListWidget::item { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background: #e3f2fd; }
        """)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list)

    def _connect_signals(self):
        self.engine.transcription_done.connect(self._on_new_transcription)
        self.engine.ai_done.connect(self._on_ai_done)

    def _load_history(self):
        self._list.clear()
        for entry in self.config.get_history():
            self._add_item(entry)

    def _add_item(self, entry):
        text = entry["text"]
        truncated = text[:100] + "..." if len(text) > 100 else text
        timestamp = entry.get("timestamp", "")[:16].replace("T", " ")
        ai_marker = " [AI]" if entry.get("ai_edited") else ""
        display = f"{truncated}\n{timestamp}{ai_marker}"

        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, entry)
        self._list.insertItem(0, item)

    @Slot(str, str)
    def _on_new_transcription(self, text, mode):
        if mode == "dictate":
            self._load_history()

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self._load_history()

    def _filter_history(self, query):
        for i in range(self._list.count()):
            item = self._list.item(i)
            entry = item.data(Qt.UserRole)
            visible = query.lower() in entry["text"].lower() if query else True
            item.setHidden(not visible)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        entry = item.data(Qt.UserRole)

        menu = QMenu(self)
        copy_action = QAction("Kopiera", self)
        copy_action.triggered.connect(lambda: self._copy_entry(entry))
        menu.addAction(copy_action)

        ai_action = QAction("Redigera med AI", self)
        ai_action.triggered.connect(lambda: self._ai_edit_entry(entry))
        menu.addAction(ai_action)

        menu.addSeparator()
        delete_action = QAction("Ta bort", self)
        delete_action.triggered.connect(lambda: self._delete_entry(entry))
        menu.addAction(delete_action)

        menu.exec(self._list.mapToGlobal(pos))

    def _copy_entry(self, entry):
        import pyperclip
        pyperclip.copy(entry["text"])

    def _ai_edit_entry(self, entry):
        dialog = QDialog(self)
        dialog.setWindowTitle("Redigera med AI")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"Ursprunglig text: {entry['text'][:200]}"))

        instruction_input = QTextEdit()
        instruction_input.setPlaceholderText("Skriv instruktion...")
        instruction_input.setMaximumHeight(80)
        layout.addWidget(instruction_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            instruction = instruction_input.toPlainText().strip()
            if instruction:
                import threading
                threading.Thread(
                    target=self.engine.ai_edit_text,
                    args=(instruction, entry["text"]),
                    daemon=True,
                ).start()

    def _delete_entry(self, entry):
        self.config.delete_history_entry(entry["id"])
        self._load_history()

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Rensa historik",
            "Är du säker? Detta går inte att ångra.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.config.clear_history()
            self._load_history()
```

- [ ] **Step 2: Commit**

```bash
git add ui/tab_history.py
git commit -m "feat: add History tab with search, context menu, clear"
```

---

### Task 7: ui/tab_settings.py — Settings tab

**Files:**
- Create: `ui/tab_settings.py`

- [ ] **Step 1: Create ui/tab_settings.py**

Full settings tab with all sections from spec: Whisper, Hotkeys, AI, Prompt profiles, Microphone, Sound, Notifications, Other.

(Code is large — see implementation step. Key patterns:)
- Each section is a QFrame with styled border
- Dropdowns for model/language/provider/mic
- Key capture widget for hotkeys
- Editable prompt text area
- All changes saved immediately via config.set()

- [ ] **Step 2: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: add Settings tab with all configuration sections"
```

---

### Task 8: ui/dashboard.py — Main window

**Files:**
- Create: `ui/dashboard.py`

- [ ] **Step 1: Create ui/dashboard.py**

```python
from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.tab_live import LiveTab
from ui.tab_history import HistoryTab
from ui.tab_settings import SettingsTab


class Dashboard(QMainWindow):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self.setWindowTitle("WhisperTyper")
        self.setMinimumSize(500, 400)
        self.resize(550, 500)

        self.setStyleSheet("""
            QMainWindow { background: #f8f9fa; }
            QTabWidget::pane { border: none; background: #f8f9fa; }
            QTabBar::tab {
                background: #f0f0f0; border: none; padding: 10px 24px;
                font-size: 13px; color: #666;
            }
            QTabBar::tab:selected {
                background: #f8f9fa; color: #1976D2; font-weight: bold;
                border-bottom: 2px solid #1976D2;
            }
        """)

        self._tabs = QTabWidget()
        self._live_tab = LiveTab(config, engine)
        self._history_tab = HistoryTab(config, engine)
        self._settings_tab = SettingsTab(config, engine)

        self._tabs.addTab(self._live_tab, "Live")
        self._tabs.addTab(self._history_tab, "Historik")
        self._tabs.addTab(self._settings_tab, "Inställningar")

        self.setCentralWidget(self._tabs)

    def show_settings(self):
        self._tabs.setCurrentWidget(self._settings_tab)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
```

- [ ] **Step 2: Commit**

```bash
git add ui/dashboard.py
git commit -m "feat: add Dashboard main window with tabs"
```

---

## Chunk 4: Integration

### Task 9: main.py — System tray + app entry point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create main.py**

```python
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QThread, Slot

from config import ConfigManager
from engine import WhisperEngine
from ui.dashboard import Dashboard

ASSETS = Path(__file__).parent / "assets"


class ModelLoaderThread(QThread):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        self.engine.load_model()


class WhisperTyperApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.config = ConfigManager()
        self.engine = WhisperEngine(self.config)

        # Dashboard
        self.dashboard = Dashboard(self.config, self.engine)

        # System tray
        self._setup_tray()

        # Connect engine signals to tray
        self.engine.model_loading.connect(self._on_model_loading)
        self.engine.model_ready.connect(self._on_model_ready)
        self.engine.recording_started.connect(self._on_recording)
        self.engine.transcription_started.connect(self._on_transcribing)
        self.engine.transcription_done.connect(self._on_transcription_done)
        self.engine.ai_started.connect(self._on_ai)
        self.engine.ai_done.connect(self._on_ai_done)

        # Load model in background
        self._loader = ModelLoaderThread(self.engine)
        self._loader.finished.connect(self._on_model_loaded)
        self._loader.start()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self.app)
        self.tray.setIcon(QIcon(str(ASSETS / "icon_loading.png")))
        self.tray.setToolTip("WhisperTyper — Laddar...")
        self.tray.activated.connect(self._on_tray_activated)

        # Context menu
        menu = QMenu()

        self._last_text_action = QAction("(ingen transkribering)", menu)
        self._last_text_action.triggered.connect(self._copy_last_text)
        menu.addAction(self._last_text_action)

        menu.addSeparator()

        self._profile_menu = menu.addMenu("Promptprofil")
        self._update_profile_menu()

        menu.addSeparator()

        open_action = QAction("Öppna dashboard", menu)
        open_action.triggered.connect(self._show_dashboard)
        menu.addAction(open_action)

        settings_action = QAction("Inställningar", menu)
        settings_action.triggered.connect(self.dashboard.show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Avsluta", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _update_profile_menu(self):
        self._profile_menu.clear()
        active = self.config.get("active_prompt_profile")
        for p in self.config.get_prompt_profiles():
            action = QAction(p["name"], self._profile_menu)
            action.setCheckable(True)
            action.setChecked(p["id"] == active)
            pid = p["id"]
            action.triggered.connect(lambda checked, pid=pid: self._set_profile(pid))
            self._profile_menu.addAction(action)

    def _set_profile(self, profile_id):
        self.config.set("active_prompt_profile", profile_id)
        self._update_profile_menu()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Left click
            if self.dashboard.isVisible():
                self.dashboard.hide()
            else:
                self._show_dashboard()

    def _show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _copy_last_text(self):
        text = self.engine.last_typed_text
        if text:
            import pyperclip
            pyperclip.copy(text)

    @Slot()
    def _on_model_loading(self):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_loading.png")))
        self.tray.setToolTip("WhisperTyper — Laddar modell...")

    @Slot()
    def _on_model_ready(self):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_ready.png")))
        self.tray.setToolTip("WhisperTyper — Redo")
        if self.config.get("show_notifications"):
            self.tray.showMessage("WhisperTyper", "Redo att diktera!",
                                  QSystemTrayIcon.Information, 3000)

    def _on_model_loaded(self):
        self.engine.start_hotkey_listener()

    @Slot(str)
    def _on_recording(self, mode):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_recording.png")))
        self.tray.setToolTip("WhisperTyper — Spelar in...")

    @Slot()
    def _on_transcribing(self):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_transcribing.png")))
        self.tray.setToolTip("WhisperTyper — Transkriberar...")

    @Slot(str, str)
    def _on_transcription_done(self, text, mode):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_ready.png")))
        self.tray.setToolTip("WhisperTyper — Redo")
        truncated = text[:80] + "..." if len(text) > 80 else text
        self._last_text_action.setText(truncated)
        if self.config.get("show_notifications") and mode == "dictate":
            duration = self.config.get("notification_duration_sec") * 1000
            self.tray.showMessage("WhisperTyper", text,
                                  QSystemTrayIcon.Information, duration)

    @Slot()
    def _on_ai(self):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_ai.png")))
        self.tray.setToolTip("WhisperTyper — AI bearbetar...")

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self.tray.setIcon(QIcon(str(ASSETS / "icon_ready.png")))
        self.tray.setToolTip("WhisperTyper — Redo")
        truncated = edited[:80] + "..." if len(edited) > 80 else edited
        self._last_text_action.setText(truncated)

    def _quit(self):
        self.engine.cleanup()
        self.tray.hide()
        self.app.quit()

    def run(self):
        return self.app.exec()


def main():
    app = WhisperTyperApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create requirements.txt**

```
PySide6>=6.5
openai-whisper
torch
pyaudio
pynput
pyperclip
requests
Pillow
```

- [ ] **Step 3: Commit**

```bash
git add main.py requirements.txt
git commit -m "feat: add main.py with system tray, model loading, full integration"
```

---

### Task 10: Manual integration test

- [ ] **Step 1: Run the full app**

Run: `cd /home/rober/Projects/Whisper && python main.py`

Expected: Tray icon appears (grey → green), dashboard opens on left-click, F9 records and transcribes, F10 sends to AI.

- [ ] **Step 2: Fix any issues found during manual testing**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "fix: integration fixes from manual testing"
```

---

## Chunk 5: Installer (deferred)

### Task 11: PyInstaller build script

This task is deferred until the app is stable. Create `installer/build_installer.py` with PyInstaller spec for bundling as single `.exe`.

---
