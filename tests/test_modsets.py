import json
import os
import tempfile
import unittest
from unittest import mock

from arma_panel import config
from arma_panel.services import modsets
from arma_panel.services.server_config import ChangeRejected, ConfigError, load_config

RHS = {"modId": "595F2BF2F44836FB", "name": "RHS"}
ACE = {"modId": "5DBD560C5148E1DA", "name": "ACE"}


def add(mod):
    return lambda mods: (mods + [mod], None)


class ModSetsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config_path = os.path.join(tmp.name, "config.json")
        self.dir = os.path.join(tmp.name, "modsets")
        for name, value in (("SERVER_CONFIG", self.config_path),
                            ("CONFIG_BACKUP_DIR", os.path.join(tmp.name, "backups")),
                            ("MODSETS_DIR", self.dir)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.write_config({"bindPort": 2001, "game": {"name": "x", "mods": [RHS]}})

    def write_config(self, cfg):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def read_set(self, set_id):
        with open(os.path.join(self.dir, f"{set_id}.json"), encoding="utf-8") as f:
            return json.load(f)

    def default(self):
        data = modsets.overview()
        return data["active"], data

    def test_first_use_creates_the_default_set_from_config(self):
        with open(self.config_path, "rb") as f:
            before = f.read()
        set_id, data = self.default()
        self.assertEqual(data["sets"], [{"id": set_id, "name": "Default", "mods": [RHS]}])
        self.assertFalse(data["config_differs"])
        with open(self.config_path, "rb") as f:
            self.assertEqual(f.read(), before)
        with open(os.path.join(self.dir, "active"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), set_id)

    def test_first_use_with_broken_config_creates_nothing(self):
        with open(self.config_path, "w") as f:
            f.write("{")
        with self.assertRaises(ConfigError):
            modsets.overview()
        self.assertFalse(os.path.exists(self.dir))

    def test_create_and_duplicate(self):
        default_id, _ = self.default()
        empty_id = modsets.create("  Vanilla ")
        copy_id = modsets.create("RHS night", copy_from=default_id)
        self.assertEqual(self.read_set(empty_id), {"name": "Vanilla", "mods": []})
        self.assertEqual(self.read_set(copy_id), {"name": "RHS night", "mods": [RHS]})
        names = [s["name"] for s in modsets.overview()["sets"]]
        self.assertEqual(names, ["Default", "RHS night", "Vanilla"])

    def test_names_are_checked(self):
        self.default()
        for bad in ("", "   ", None, 12, "a" * 61, "two\nlines", "DEFAULT"):
            with self.assertRaises(ChangeRejected, msg=repr(bad)):
                modsets.create(bad)
        self.assertEqual(len(modsets.overview()["sets"]), 1)

    def test_rename(self):
        set_id, _ = self.default()
        modsets.rename(set_id, "default")  # its own name with another case
        other = modsets.create("Other")
        with self.assertRaises(ChangeRejected):
            modsets.rename(other, "DEFAULT")
        self.assertEqual(self.read_set(set_id), {"name": "default", "mods": [RHS]})

    def test_unknown_ids_are_rejected(self):
        self.default()
        for bad in ("deadbeef", "../config", None, ["x"]):
            with self.assertRaises(ChangeRejected):
                modsets.rename(bad, "x")
        with self.assertRaises(ChangeRejected):
            modsets.create("x", copy_from="deadbeef")
        with self.assertRaises(ChangeRejected):
            modsets.get("deadbeef")

    def test_get(self):
        set_id, _ = self.default()
        self.assertEqual(modsets.get(set_id), {"name": "Default", "mods": [RHS]})

    def test_the_set_in_use_cannot_be_deleted(self):
        set_id, _ = self.default()
        with self.assertRaises(ChangeRejected):
            modsets.delete(set_id)
        other = modsets.create("Other")
        modsets.delete(other)
        self.assertEqual([s["id"] for s in modsets.overview()["sets"]], [set_id])

    def test_activate_writes_the_mods_to_config(self):
        self.default()
        other = modsets.create("ACE only")
        modsets.change_mods(other, add(ACE))
        modsets.activate(other)
        cfg = load_config()
        self.assertEqual(cfg["game"]["mods"], [ACE])
        self.assertEqual(cfg["bindPort"], 2001)
        data = modsets.overview()
        self.assertEqual(data["active"], other)
        self.assertFalse(data["config_differs"])

    def test_changing_the_set_in_use_updates_config(self):
        set_id, _ = self.default()
        _, in_use = modsets.change_mods(set_id, add(ACE))
        self.assertTrue(in_use)
        self.assertEqual(load_config()["game"]["mods"], [RHS, ACE])
        self.assertEqual(self.read_set(set_id)["mods"], [RHS, ACE])

    def test_changing_another_set_leaves_config_alone(self):
        self.default()
        other = modsets.create("Other")
        _, in_use = modsets.change_mods(other, add(ACE))
        self.assertFalse(in_use)
        self.assertEqual(load_config()["game"]["mods"], [RHS])

    def test_rejected_change_writes_nothing(self):
        set_id, _ = self.default()

        def reject(mods):
            raise ChangeRejected("no")

        with self.assertRaises(ChangeRejected):
            modsets.change_mods(set_id, reject)
        self.assertEqual(self.read_set(set_id)["mods"], [RHS])

    def test_broken_config_blocks_changes_to_the_set_in_use_only(self):
        set_id, _ = self.default()
        other = modsets.create("Other")
        with open(self.config_path, "w") as f:
            f.write("{")
        with self.assertRaises(ConfigError):
            modsets.change_mods(set_id, add(ACE))
        self.assertEqual(self.read_set(set_id)["mods"], [RHS])
        modsets.change_mods(other, add(ACE))
        self.assertEqual(self.read_set(other)["mods"], [ACE])

    def test_hand_edited_config_is_reported(self):
        set_id, _ = self.default()
        self.write_config({"game": {"mods": [ACE]}})
        self.assertTrue(modsets.overview()["config_differs"])
        modsets.activate(set_id)
        self.assertEqual(load_config()["game"]["mods"], [RHS])
        self.assertFalse(modsets.overview()["config_differs"])

    def test_malformed_set_files_are_skipped(self):
        set_id, _ = self.default()
        for name, text in (("0000000a.json", "{"), ("0000000b.json", '{"name": "x", "mods": [1]}'),
                           ("notes.json", '{"name": "n", "mods": []}')):
            with open(os.path.join(self.dir, name), "w") as f:
                f.write(text)
        self.assertEqual([s["id"] for s in modsets.overview()["sets"]], [set_id])

    def test_missing_active_set(self):
        self.default()
        with open(os.path.join(self.dir, "active"), "w") as f:
            f.write("deadbeef\n")
        data = modsets.overview()
        self.assertIsNone(data["active"])
        self.assertFalse(data["config_differs"])


if __name__ == "__main__":
    unittest.main()
