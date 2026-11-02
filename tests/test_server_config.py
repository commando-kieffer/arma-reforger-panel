import json
import os
import tempfile
import threading
import unittest
from unittest import mock

from arma_panel import config
from arma_panel.services import server_config
from arma_panel.services.server_config import (ChangeRejected, ConfigChanged, ConfigError, load_config,
                                               read_config_text, replace_config_text, update_config)


class ConfigFileTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "config.json")
        self.backups = os.path.join(tmp.name, "backups")
        for name, value in (("SERVER_CONFIG", self.path), ("CONFIG_BACKUP_DIR", self.backups)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()


class UpdateConfigTest(ConfigFileTestCase):
    def test_missing_file_is_an_error(self):
        with self.assertRaises(ConfigError):
            load_config()

    def test_broken_json_is_never_overwritten(self):
        self.write('{"game": {"name": "x",')
        with self.assertRaises(ConfigError):
            update_config(lambda cfg: cfg.setdefault("game", {}).update(name="new"))
        self.assertEqual(self.read(), '{"game": {"name": "x",')

    def test_non_object_is_an_error(self):
        self.write("[]")
        with self.assertRaises(ConfigError):
            load_config()

    def test_update_keeps_other_keys(self):
        self.write(json.dumps({"bindPort": 2001, "game": {"name": "old", "mods": [{"modId": "AB"}]}}))
        update_config(lambda cfg: cfg["game"].update(name="Opération"))
        cfg = load_config()
        self.assertEqual(cfg["game"]["name"], "Opération")
        self.assertEqual(cfg["bindPort"], 2001)
        self.assertEqual(cfg["game"]["mods"], [{"modId": "AB"}])
        self.assertIn("Opération", self.read())  # written as UTF-8, not \u escapes
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_rejected_change_writes_nothing(self):
        self.write('{"game": {}}')

        def reject(cfg):
            cfg["game"]["name"] = "half done"
            raise ChangeRejected("no")

        with self.assertRaises(ChangeRejected):
            update_config(reject)
        self.assertEqual(self.read(), '{"game": {}}')
        self.assertEqual(server_config.list_backups(), [])

    def test_unchanged_config_is_not_rewritten(self):
        self.write('{"game": {"name": "same"}}')
        update_config(lambda cfg: cfg["game"].update(name="same"))
        self.assertEqual(self.read(), '{"game": {"name": "same"}}')
        self.assertEqual(server_config.list_backups(), [])

    def test_each_write_is_backed_up_and_old_backups_pruned(self):
        self.write('{"n": 0}')
        with mock.patch.object(server_config, "BACKUP_KEEP", 3):
            for i in range(1, 6):
                update_config(lambda cfg, i=i: cfg.update(n=i))
        backups = server_config.list_backups()
        self.assertEqual(len(backups), 3)
        with open(os.path.join(self.backups, backups[-1]), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"n": 4})  # the version before the last write

    def test_concurrent_updates_are_not_lost(self):
        self.write('{"counter": 0}')

        def bump():
            for _ in range(20):
                update_config(lambda cfg: cfg.update(counter=cfg["counter"] + 1))

        threads = [threading.Thread(target=bump) for _ in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(load_config()["counter"], 80)


class ReplaceConfigTextTest(ConfigFileTestCase):
    """The config.json editor: the whole text replaced, broken JSON included."""

    def test_round_trip(self):
        with open(self.path, "wb") as f:
            f.write(b'{"game": {"name": "x"}}\n')
        text, sha = read_config_text()
        self.assertEqual(text, '{"game": {"name": "x"}}\n')
        new_sha = replace_config_text('{\n\t"game": {"name": "y"}\n}', sha)
        # Written as sent, with a final line break.
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b'{\n\t"game": {"name": "y"}\n}\n')
        self.assertEqual(read_config_text()[1], new_sha)
        self.assertEqual(len(server_config.list_backups()), 1)

    def test_refused_when_the_file_changed(self):
        self.write('{"game": {}}')
        _, sha = read_config_text()
        self.write('{"game": {"name": "changed elsewhere"}}')
        with self.assertRaises(ConfigChanged):
            replace_config_text('{"game": {}}', sha)
        self.assertEqual(self.read(), '{"game": {"name": "changed elsewhere"}}')
        self.assertEqual(server_config.list_backups(), [])

    def test_repairs_a_broken_file(self):
        self.write('{"game": ')
        text, sha = read_config_text()
        self.assertEqual(text, '{"game": ')
        replace_config_text('{"game": {}}', sha)
        self.assertEqual(load_config(), {"game": {}})

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            read_config_text()


if __name__ == "__main__":
    unittest.main()
