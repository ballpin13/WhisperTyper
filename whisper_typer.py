"""
WhisperTyper - Röstinmatning med Whisper
F9:  Håll ned för att diktera text (med smart interpunktion).
F10: Håll ned för att ge AI en instruktion att redigera senaste texten.
"""

import threading
import tempfile
import os
import sys
import time
import wave
import re

# Kontrollera beroenden
missing = []
try:
    import pyaudio
except ImportError:
    missing.append("pyaudio")
try:
    import whisper
except ImportError:
    missing.append("openai-whisper")
try:
    import keyboard
except ImportError:
    missing.append("keyboard")
try:
    import pyperclip
except ImportError:
    missing.append("pyperclip")

if missing:
    print(f"[FEL] Saknade paket: {', '.join(missing)}")
    print(f"Installera med: pip install {' '.join(missing)}")
    sys.exit(1)

import requests

# ── Konfiguration ────────────────────────────────────────────────────────────
HOTKEY          = "F9"
AI_HOTKEY       = "F10"
WHISPER_MODEL   = "medium"       # tiny/base/small/medium/large
LANGUAGE        = "sv"           # svenska
SAMPLE_RATE     = 16000
CHANNELS        = 1
CHUNK           = 1024
MAX_RECORD_SEC  = 60             # max inspelningstid i sekunder

# Ollama för AI-redigering (F10) — körs lokalt
OLLAMA_URL      = "http://localhost:11434"
OLLAMA_MODEL    = "mistral:7b"
# ─────────────────────────────────────────────────────────────────────────────

import torch
USE_CUDA = torch.cuda.is_available()
DEVICE = "cuda" if USE_CUDA else "cpu"

print(f"[WhisperTyper] Enhet: {DEVICE}" + (f" ({torch.cuda.get_device_name(0)})" if USE_CUDA else ""))
print(f"[WhisperTyper] Laddar Whisper-modell '{WHISPER_MODEL}'... (kan ta en stund första gången)")
model = whisper.load_model(WHISPER_MODEL, device=DEVICE)
print(f"[WhisperTyper] Modell laddad!")
print(f"[WhisperTyper]   {HOTKEY} = diktera text")

# Kontrollera att Ollama körs
ollama_available = False
try:
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
    if r.status_code == 200:
        ollama_available = True
        print(f"[WhisperTyper]   {AI_HOTKEY} = AI-redigering via Ollama ({OLLAMA_MODEL})")
except Exception:
    pass
if not ollama_available:
    print(f"[WhisperTyper]   {AI_HOTKEY} = ej tillgänglig (starta Ollama först)")

# ── Smart interpunktion ──────────────────────────────────────────────────────
# Ersätter uttalade skiljetecken med faktiska tecken.
# Bara entydiga ord som aldrig menar något annat i vanligt tal.
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
    """Ersätter uttalade skiljetecken med faktiska tecken."""
    result = text
    for pattern, symbol in PUNCTUATION_MAP:
        result = re.sub(pattern, symbol, result, flags=re.IGNORECASE)
    # Rensa mellanslag före skiljetecken (t.ex. "hej ?" → "hej?")
    result = re.sub(r"\s+([?.!,;:])", r"\1", result)
    return result


# ── Globalt state ────────────────────────────────────────────────────────────
is_recording    = False
recording_mode  = None           # "dictate" eller "ai"
audio_frames    = []
audio_lock      = threading.Lock()
pa              = pyaudio.PyAudio()
last_typed_text = ""


def record_audio():
    """Spelar in mikrofon till audio_frames tills is_recording = False."""
    global audio_frames
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )
    start = time.time()
    with audio_lock:
        audio_frames = []

    mode_text = "diktering" if recording_mode == "dictate" else "AI-instruktion"
    print(f"[●] Spelar in {mode_text}... (släpp för att stoppa)")
    while is_recording and (time.time() - start) < MAX_RECORD_SEC:
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_frames.append(data)

    stream.stop_stream()
    stream.close()
    duration = time.time() - start
    print(f"[■] Inspelning klar ({duration:.1f}s)")


def transcribe_audio():
    """Transkriberar inspelat ljud och returnerar text."""
    with audio_lock:
        frames = list(audio_frames)

    if not frames:
        print("[!] Inget ljud inspelat.")
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))

    print("[◎] Transkriberar med Whisper...")
    try:
        result = model.transcribe(
            tmp_path,
            language=LANGUAGE,
            fp16=USE_CUDA,
            condition_on_previous_text=True,
        )
        text = result["text"].strip()
    except Exception as e:
        print(f"[FEL] Whisper-fel: {e}")
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not text:
        print("[!] Inget tal kändes igen.")
        return None

    return text


def type_text(text):
    """Skriver in text i aktiv ruta via clipboard."""
    global last_typed_text
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
        keyboard.press_and_release("ctrl+v")
        time.sleep(0.15)
        pyperclip.copy(old_clipboard)
        last_typed_text = text
    except Exception as e:
        print(f"[FEL] Kunde inte skriva in text: {e}")


def replace_last_text(new_text):
    """Raderar senaste texten och ersätter med ny."""
    global last_typed_text
    if not new_text:
        return

    if last_typed_text:
        # Radera gamla texten med backspace
        for _ in range(len(last_typed_text)):
            keyboard.press_and_release("backspace")
        time.sleep(0.05)

    type_text(new_text)


def handle_dictation():
    """F9: Transkribera → smart interpunktion → skriv in."""
    text = transcribe_audio()
    if not text:
        return
    text = smart_punctuation(text)
    print(f"[✓] Text: {text}")
    type_text(text)


def handle_ai_edit():
    """F10: Transkribera instruktion → Ollama redigerar senaste texten → ersätt."""
    if not ollama_available:
        print("[!] AI-redigering ej tillgänglig. Starta Ollama först.")
        return

    instruction = transcribe_audio()
    if not instruction:
        return

    print(f"[AI] Instruktion: {instruction}")

    if not last_typed_text:
        print("[!] Ingen tidigare text att redigera. Diktera med F9 först.")
        return

    print(f"[AI] Redigerar: \"{last_typed_text}\"")

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Du är en textassistent. Användaren har dikterat en text och vill nu ändra den. "
                            "Returnera BARA den redigerade texten, inget annat. Ingen förklaring, inga citattecken. "
                            "Om användaren säger att du hörde fel, korrigera texten. "
                            "Om användaren ger en redigeringsinstruktion, utför den."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Ursprunglig text: \"{last_typed_text}\"\n\nInstruktion: {instruction}",
                    },
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        new_text = response.json()["message"]["content"].strip()
        print(f"[AI] Resultat: {new_text}")
        replace_last_text(new_text)
    except Exception as e:
        print(f"[FEL] AI-fel: {e}")


# ── Inspelning start/stopp ───────────────────────────────────────────────────

def start_recording(mode):
    global is_recording, recording_mode
    if not is_recording:
        is_recording = True
        recording_mode = mode
        t = threading.Thread(target=record_audio, daemon=True)
        t.start()


def stop_recording():
    global is_recording
    if is_recording:
        mode = recording_mode
        is_recording = False
        if mode == "dictate":
            t = threading.Thread(target=handle_dictation, daemon=True)
            t.start()
        elif mode == "ai":
            t = threading.Thread(target=handle_ai_edit, daemon=True)
            t.start()


# Registrera tangenter
keyboard.on_press_key("F9", lambda e: start_recording("dictate"))
keyboard.on_release_key("F9", lambda e: stop_recording())
keyboard.on_press_key("F10", lambda e: start_recording("ai"))
keyboard.on_release_key("F10", lambda e: stop_recording())

print(f"[WhisperTyper] Körs i bakgrunden. Avsluta med Ctrl+C.")
try:
    keyboard.wait()
except KeyboardInterrupt:
    print("\n[WhisperTyper] Avslutar.")
    pa.terminate()
