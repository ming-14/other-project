import json
import os
import pytest
from unittest.mock import patch
from core.settings.manager import SettingsManager, SETTINGS_FILE, _DEFAULTS


class TestSettingsManagerLoad:
    def test_load_defaults_when_no_file(self, tmp_path):
        sm = SettingsManager()
        with patch("core.settings.manager.SETTINGS_FILE", str(tmp_path / "settings.json")):
            settings = sm.load()
        for key, val in _DEFAULTS.items():
            assert settings[key] == val

    def test_load_from_file(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        custom = {"theme": "DarkTheme", "auto_scroll": False}
        settings_file.write_text(json.dumps(custom))
        sm = SettingsManager()
        with patch("core.settings.manager.SETTINGS_FILE", str(settings_file)):
            settings = sm.load()
        assert settings["theme"] == "DarkTheme"
        assert settings["auto_scroll"] is False
        assert settings["url_history"] == []

    def test_load_corrupt_file_uses_defaults(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not json{{{")
        sm = SettingsManager()
        with patch("core.settings.manager.SETTINGS_FILE", str(settings_file)):
            settings = sm.load()
        assert settings["theme"] == _DEFAULTS["theme"]


class TestSettingsManagerSave:
    def test_save_creates_file(self, tmp_path):
        sm = SettingsManager()
        sm.set("theme", "TestTheme")
        with patch("core.settings.manager.SETTINGS_FILE", str(tmp_path / "settings.json")):
            with patch("core.settings.manager._DATA_DIR", str(tmp_path)):
                result = sm.save()
        assert result is True
        assert (tmp_path / "settings.json").exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        settings_file = str(tmp_path / "settings.json")
        sm1 = SettingsManager()
        sm1.set("theme", "MyTheme")
        sm1.set("auto_scroll", False)
        with patch("core.settings.manager.SETTINGS_FILE", settings_file):
            with patch("core.settings.manager._DATA_DIR", str(tmp_path)):
                sm1.save()
        sm2 = SettingsManager()
        with patch("core.settings.manager.SETTINGS_FILE", settings_file):
            sm2.load()
        assert sm2.get("theme") == "MyTheme"
        assert sm2.get("auto_scroll") is False


class TestSettingsManagerGetSet:
    def test_get_existing_key(self):
        sm = SettingsManager()
        sm.set("theme", "TestTheme")
        assert sm.get("theme") == "TestTheme"

    def test_get_missing_key_returns_default(self):
        sm = SettingsManager()
        assert sm.get("nonexistent", "fallback") == "fallback"

    def test_get_missing_key_returns_none(self):
        sm = SettingsManager()
        assert sm.get("nonexistent") is None

    def test_set_overwrites(self):
        sm = SettingsManager()
        sm.set("theme", "A")
        sm.set("theme", "B")
        assert sm.get("theme") == "B"


class TestSettingsManagerUpdate:
    def test_update_multiple_keys(self):
        sm = SettingsManager()
        sm.update({"theme": "X", "auto_scroll": False})
        assert sm.get("theme") == "X"
        assert sm.get("auto_scroll") is False

    def test_update_preserves_other_keys(self):
        sm = SettingsManager()
        sm.set("theme", "Original")
        sm.set("auto_scroll", True)
        sm.update({"theme": "New"})
        assert sm.get("theme") == "New"
        assert sm.get("auto_scroll") is True


class TestSettingsManagerGetAll:
    def test_get_all_returns_copy(self):
        sm = SettingsManager()
        sm.set("theme", "Test")
        all_settings = sm.get_all()
        all_settings["theme"] = "Modified"
        assert sm.get("theme") == "Test"


class TestSettingsManagerReplaceAll:
    def test_replace_all(self):
        sm = SettingsManager()
        sm.set("theme", "Old")
        sm.replace_all({"new_key": "new_value"})
        assert sm.get("new_key") == "new_value"
        assert sm.get("theme") is None