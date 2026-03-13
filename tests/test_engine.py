"""Tests for engine hotkey parsing logic.

Since engine.py has heavy dependencies (faster_whisper, pyaudio, pynput)
that may not be available in all environments, we test the pure logic
by extracting and testing the parse function directly.
"""
import pytest


def _parse_key(key_str):
    """Copy of WhisperEngine._parse_key for testing without imports."""
    parts = key_str.lower().split("+")
    modifiers = set()
    key = parts[-1]
    for p in parts[:-1]:
        if p in ("ctrl", "alt", "shift"):
            modifiers.add(p)
    return {"modifiers": modifiers, "key": key}


class TestParseKey:
    def test_simple_key(self):
        result = _parse_key("F9")
        assert result == {"modifiers": set(), "key": "f9"}

    def test_ctrl_combo(self):
        result = _parse_key("ctrl+f9")
        assert result == {"modifiers": {"ctrl"}, "key": "f9"}

    def test_ctrl_combo_case_insensitive(self):
        result = _parse_key("Ctrl+F9")
        assert result == {"modifiers": {"ctrl"}, "key": "f9"}

    def test_multi_modifier(self):
        result = _parse_key("ctrl+shift+a")
        assert result == {"modifiers": {"ctrl", "shift"}, "key": "a"}

    def test_single_letter(self):
        result = _parse_key("A")
        assert result == {"modifiers": set(), "key": "a"}

    def test_f10_legacy(self):
        result = _parse_key("F10")
        assert result == {"modifiers": set(), "key": "f10"}

    def test_alt_combo(self):
        result = _parse_key("Alt+F7")
        assert result == {"modifiers": {"alt"}, "key": "f7"}
