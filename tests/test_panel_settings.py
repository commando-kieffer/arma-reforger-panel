import json
import os
import tempfile
import unittest
from unittest import mock

from arma_panel import config, themes
from arma_panel.services import panel_settings
from arma_panel.services.server_config import ChangeRejected


class PanelSettingsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "panel-settings.json")
        patcher = mock.patch.object(config, "SETTINGS_FILE", self.path)
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

    def test_every_theme_has_its_stylesheets(self):
        for theme in themes.THEMES:
            for name in ("base.css", "login.css", "panel.css"):
                path = os.path.join(config.BASE_DIR, "static", "css", theme.id, name)
                self.assertTrue(os.path.isfile(path), path)

    def test_set_theme_is_saved(self):
        for theme in themes.THEMES:
            panel_settings.set_theme(theme.id)
            self.assertEqual(panel_settings.load(), {"theme": theme.id})
            self.assertEqual(self.read(), {"theme": theme.id})

    def test_unknown_theme_is_rejected(self):
        for bad in ("nope", "", None, 3, ["zeus"]):
            with self.assertRaises(ChangeRejected):
                panel_settings.set_theme(bad)
        self.assertFalse(os.path.exists(self.path))

    def test_unknown_or_broken_values_fall_back_to_the_default(self):
        for text in ('{"theme": "gone"}', '{"theme": 1}', "[]", "{", ""):
            self.write(text)
            self.assertEqual(panel_settings.load(), {"theme": themes.DEFAULT_THEME}, text)

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
