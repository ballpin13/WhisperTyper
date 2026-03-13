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
