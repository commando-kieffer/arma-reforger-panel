import json
import os
import tempfile
import unittest
from unittest import mock

from arma_panel import config
from arma_panel.services import panel_settings, themes
from arma_panel.services.server_config import ChangeRejected


class PanelSettingsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "panel-settings.json")
        for name, value in (("SETTINGS_FILE", self.path),
                            ("CUSTOM_THEMES_DIR", os.path.join(tmp.name, "custom-themes"))):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_defaults_without_a_file(self):
        self.assertEqual(panel_settings.load(), {"theme": themes.DEFAULT_THEME})
        self.assertFalse(os.path.exists(self.path))

    def test_set_theme_is_saved(self):
        for theme in themes.all_themes():
            panel_settings.set_theme(theme.id)
            self.assertEqual(panel_settings.load(), {"theme": theme.id})
            self.assertEqual(self.read(), {"theme": theme.id})

    def test_unknown_theme_is_rejected(self):
        for bad in ("nope", "", None, 3, ["zeus"], "../zeus"):
            with self.assertRaises(ChangeRejected):
                panel_settings.set_theme(bad)
        self.assertFalse(os.path.exists(self.path))

    def test_unknown_or_broken_values_fall_back_to_the_default(self):
        for text in ('{"theme": "gone"}', '{"theme": 1}', "[]", "{", ""):
            self.write(text)
            self.assertEqual(panel_settings.load(), {"theme": themes.DEFAULT_THEME}, text)

    def test_deleted_custom_theme_falls_back_to_the_default(self):
        files = {file: b"" for file in themes.STYLESHEETS}
        theme_id = themes.save("Night", files)
        panel_settings.set_theme(theme_id)
        self.assertEqual(panel_settings.load(), {"theme": theme_id})
        themes.delete(theme_id)
        self.assertEqual(panel_settings.load(), {"theme": themes.DEFAULT_THEME})

    def test_other_keys_are_kept(self):
        self.write('{"theme": "gone", "later": true}')
        panel_settings.set_theme(themes.DEFAULT_THEME)
        self.assertEqual(self.read(), {"theme": themes.DEFAULT_THEME, "later": True})

    def test_broken_file_is_replaced(self):
        self.write("{")
        panel_settings.set_theme(themes.DEFAULT_THEME)
        self.assertEqual(self.read(), {"theme": themes.DEFAULT_THEME})


if __name__ == "__main__":
    unittest.main()
