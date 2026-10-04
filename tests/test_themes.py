import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from arma_panel import config
from arma_panel.services import themes
from arma_panel.services.server_config import ChangeRejected


def stylesheets(marker="body {}"):
    return {file: f"/* {file} */ {marker}".encode() for file in themes.STYLESHEETS}


class ThemesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.join(tmp.name, "custom-themes")
        patcher = mock.patch.object(config, "CUSTOM_THEMES_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, theme_id, file):
        with open(os.path.join(self.dir, theme_id, file), encoding="utf-8") as f:
            return f.read()

    def test_built_in_themes(self):
        found = {theme.id: theme for theme in themes.all_themes()}
        self.assertIn(themes.DEFAULT_THEME, found)
        self.assertIn("retro", found)
        self.assertEqual(found["zeus"].name, "Commando Kieffer - Zeus")
        self.assertFalse(any(theme.custom for theme in found.values()))

    def test_upload_adds_a_custom_theme_after_the_built_in_ones(self):
        theme_id = themes.save("  Night ops ", stylesheets())
        theme = themes.get(theme_id)
        self.assertEqual((theme.name, theme.custom), ("Night ops", True))
        self.assertEqual(themes.all_themes()[-1].id, theme_id)
        self.assertEqual(self.read(theme_id, "panel.css"), "/* panel.css */ body {}")
        self.assertEqual(json.loads(self.read(theme_id, "theme.json")), {"name": "Night ops"})
        self.assertEqual([n for n in os.listdir(self.dir)], [theme_id])

    def test_byte_order_mark_is_dropped(self):
        files = stylesheets()
        files["base.css"] = b"\xef\xbb\xbf:root {}"
        theme_id = themes.save("Bom", files)
        self.assertEqual(self.read(theme_id, "base.css"), ":root {}")

    def test_invalid_uploads_are_rejected(self):
        missing = stylesheets()
        missing["login.css"] = None
        too_large = stylesheets()
        too_large["panel.css"] = b"a" * (themes.STYLESHEET_MAX_BYTES + 1)
        not_utf8 = stylesheets()
        not_utf8["base.css"] = b"\xff\xfe"
        cases = [("", stylesheets()), (None, stylesheets()), ("x" * 61, stylesheets()),
                 ("two\nlines", stylesheets()), ("Ok", missing), ("Ok", too_large), ("Ok", not_utf8)]
        for name, files in cases:
            with self.subTest(name=name), self.assertRaises(ChangeRejected):
                themes.save(name, files)
        self.assertFalse(os.path.exists(self.dir) and os.listdir(self.dir))

    def test_built_in_names_are_reserved(self):
        with self.assertRaises(ChangeRejected):
            themes.save("retro 2000", stylesheets())
        with self.assertRaises(ChangeRejected):
            themes.save("Retro 2000", stylesheets(), replace=True)

    def test_same_name_needs_replace(self):
        theme_id = themes.save("Night", stylesheets("a {}"))
        with self.assertRaises(themes.NameTaken):
            themes.save("NIGHT", stylesheets("b {}"))
        self.assertEqual(themes.save("NIGHT", stylesheets("b {}"), replace=True), theme_id)
        self.assertEqual(self.read(theme_id, "base.css"), "/* base.css */ b {}")
        self.assertEqual(themes.get(theme_id).name, "NIGHT")
        self.assertEqual(len([t for t in themes.all_themes() if t.custom]), 1)

    def test_broken_folders_are_skipped(self):
        theme_id = themes.save("Night", stylesheets())
        os.remove(os.path.join(self.dir, theme_id, "login.css"))
        self.assertIsNone(themes.get(theme_id))
        other = themes.save("Other", stylesheets())
        with open(os.path.join(self.dir, other, "theme.json"), "w") as f:
            f.write("{")
        self.assertIsNone(themes.get(other))
        os.makedirs(os.path.join(self.dir, "not-an-id"))
        self.assertEqual([t for t in themes.all_themes() if t.custom], [])

    def test_delete(self):
        theme_id = themes.save("Night", stylesheets())
        themes.delete(theme_id)
        self.assertIsNone(themes.get(theme_id))
        self.assertEqual(os.listdir(self.dir), [])
        for bad in (themes.DEFAULT_THEME, theme_id, "../zeus", None):
            with self.subTest(theme_id=bad), self.assertRaises(ChangeRejected):
                themes.delete(bad)

    def test_archive_holds_the_three_stylesheets(self):
        theme_id = themes.save('Night: "ops"', stylesheets())
        file_name, data = themes.archive(theme_id)
        self.assertEqual(file_name, "Night_ _ops_.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            self.assertEqual(sorted(zf.namelist()), sorted(themes.STYLESHEETS))
            self.assertEqual(zf.read("login.css"), b"/* login.css */ body {}")
        built_in_name, _ = themes.archive("retro")
        self.assertEqual(built_in_name, "Retro 2000.zip")
        with self.assertRaises(ChangeRejected):
            themes.archive("deadbeef")


if __name__ == "__main__":
    unittest.main()
