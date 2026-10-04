import json
import os
import tempfile
import unittest
from unittest import mock

from arma_panel import config
from arma_panel.services.workshop import installed_versions


class InstalledVersionsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        patcher = mock.patch.object(config, "WORKSHOP_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add_addon(self, folder, meta=None, text=None):
        path = os.path.join(self.dir, folder)
        os.makedirs(path)
        if text is None:
            text = json.dumps({"meta": meta})
        # The game writes `meta` with a BOM.
        with open(os.path.join(path, "meta"), "w", encoding="utf-8-sig") as f:
            f.write(text)

    def test_reads_the_version_of_each_addon(self):
        self.add_addon("ACECarrying_5DBD560C5148E1DA", {
            "id": "5DBD560C5148E1DA", "name": "ACE Carrying",
            "versions": [{"version": "1.4.3", "gameVersion": "1.7.0.41", "scenarios": []}],
        })
        self.add_addon("Lower_abcdef0123456789", {"id": "abcdef0123456789", "versions": [{"version": "2.0"}]})
        os.makedirs(os.path.join(self.dir, "saves"))
        self.assertEqual(installed_versions(),
                         {"5DBD560C5148E1DA": "1.4.3", "ABCDEF0123456789": "2.0"})

    def test_leaves_out_uncertain_versions(self):
        self.add_addon("Two_00000000000000AA", {"id": "00000000000000AA",
                                                "versions": [{"version": "1.0"}, {"version": "1.1"}]})
        self.add_addon("None_00000000000000BB", {"id": "00000000000000BB", "versions": []})
        self.add_addon("Bad_00000000000000CC", {"id": "00000000000000CC", "versions": [{"version": 'a"b'}]})
        self.add_addon("Broken_00000000000000DD", text="{")
        self.add_addon("NoId_00000000000000EE", {"versions": [{"version": "1.0"}]})
        self.assertEqual(installed_versions(), {})

    def test_folders_that_disagree_are_left_out(self):
        self.add_addon("Old_00000000000000AA", {"id": "00000000000000AA", "versions": [{"version": "1.0"}]})
        self.add_addon("New_00000000000000AA", {"id": "00000000000000AA", "versions": [{"version": "1.1"}]})
        self.add_addon("A_00000000000000BB", {"id": "00000000000000BB", "versions": [{"version": "2.0"}]})
        self.add_addon("B_00000000000000BB", {"id": "00000000000000BB", "versions": [{"version": "2.0"}]})
        self.add_addon("C_00000000000000CC", {"id": "00000000000000CC", "versions": [{"version": "3.0"}]})
        self.add_addon("D_00000000000000CC", {"id": "00000000000000CC", "versions": []})
        self.assertEqual(installed_versions(), {"00000000000000BB": "2.0"})

    def test_missing_directory(self):
        with mock.patch.object(config, "WORKSHOP_DIR", os.path.join(self.dir, "nope")):
            self.assertEqual(installed_versions(), {})
        with mock.patch.object(config, "WORKSHOP_DIR", ""):
            self.assertEqual(installed_versions(), {})


if __name__ == "__main__":
    unittest.main()
