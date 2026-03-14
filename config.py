import copy
import json
import os
import uuid
from pathlib import Path
from datetime import datetime
import platform

APP_NAME = "WhisperTyper"

DEFAULT_CONFIG = {
    "whisper_model": "medium",
    "whisper_device": "auto",
    "language": "sv",
    "hotkey_dictate": "F9",
    "hotkey_ai": "ctrl+f9",
    "ai_provider": "ollama",
    "ollama_model": "gemma3:12b",
    "cloud_provider": "openai",
    "cloud_model": "gpt-4o-mini",
    "cloud_api_key": "",
    "cloud_api_key_openai": "",
    "cloud_api_key_anthropic": "",
    "cloud_api_key_groq": "",
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
    "vocabulary": [],
}

BASE_SYSTEM_PROMPT = (
    "Returnera ENBART den bearbetade texten. "
    "Ingen förklaring, inga citattecken, inga inledande fraser, inget extra."
)

# Legacy prompt used for migration detection
_LEGACY_PROMPT = (
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
            "system_prompt": "",
            "auto_run": False,
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
        data = copy.deepcopy(default)
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
        changed = False
        for p in self._prompts["profiles"]:
            # Migration: add auto_run if missing
            if "auto_run" not in p:
                p["auto_run"] = False
                changed = True
            # Migration: clear legacy prompt
            if p["system_prompt"] == _LEGACY_PROMPT:
                p["system_prompt"] = ""
                changed = True
        if changed:
            self._save_json(self._prompts_path, self._prompts)
        return self._prompts["profiles"]

    def get_active_prompt(self):
        active_id = self.get("active_prompt_profile")
        for p in self.get_prompt_profiles():
            if p["id"] == active_id:
                return p["system_prompt"]
        return self._prompts["profiles"][0]["system_prompt"]

    def get_full_system_prompt(self):
        profile_prompt = self.get_active_prompt()
        if profile_prompt:
            return f"{BASE_SYSTEM_PROMPT}\n\n{profile_prompt}"
        return BASE_SYSTEM_PROMPT

    def get_active_auto_run(self):
        active_id = self.get("active_prompt_profile")
        for p in self.get_prompt_profiles():
            if p["id"] == active_id:
                return p.get("auto_run", False)
        return False

    def add_prompt_profile(self, profile_id, name, system_prompt, auto_run=False):
        self._prompts["profiles"].append({
            "id": profile_id,
            "name": name,
            "system_prompt": system_prompt,
            "auto_run": auto_run,
            "deletable": True,
        })
        self._save_json(self._prompts_path, self._prompts)

    def update_prompt_profile(self, profile_id, system_prompt, auto_run=None):
        for p in self._prompts["profiles"]:
            if p["id"] == profile_id:
                p["system_prompt"] = system_prompt
                if auto_run is not None:
                    p["auto_run"] = auto_run
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

    # ── Vocabulary ──
    def get_vocabulary(self):
        return self._config.get("vocabulary", [])

    def set_vocabulary(self, words):
        self._config["vocabulary"] = words
        self._save_json(self._config_path, self._config)

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
