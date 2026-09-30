import unittest

from arma_panel.services import config_fields
from arma_panel.services.config_fields import PERSISTENCE_FIELDS
from arma_panel.services.persistence import persistence_mode, set_persistence_mode
from arma_panel.services.server_config import ChangeRejected


def config(props):
    return {"game": {"name": "x", "gameProperties": props}}


class PersistenceModeTest(unittest.TestCase):
    def test_detection(self):
        self.assertEqual(persistence_mode({}), "default")
        self.assertEqual(persistence_mode(config({"persistence": {}})), "custom")
        self.assertEqual(persistence_mode(config({"persistence": {}, "missionHeader": {"m_eSaveTypes": 0}})), "disabled")
        self.assertEqual(persistence_mode(config({"missionHeader": {"m_eSaveTypes": 3}})), "default")
        self.assertEqual(persistence_mode(config({"missionHeader": {"m_eSaveTypes": False}})), "default")

    def test_disable_keeps_block_and_other_header_keys(self):
        cfg = config({"persistence": {"autoSaveInterval": 5}, "missionHeader": {"m_sName": "Mine"}})
        set_persistence_mode(cfg, "disabled")
        props = cfg["game"]["gameProperties"]
        self.assertEqual(props["missionHeader"], {"m_sName": "Mine", "m_eSaveTypes": 0})
        self.assertEqual(props["persistence"], {"autoSaveInterval": 5})

    def test_back_to_custom_restores_settings(self):
        cfg = config({"persistence": {"autoSaveInterval": 5}, "missionHeader": {"m_eSaveTypes": 0}})
        set_persistence_mode(cfg, "custom")
        self.assertEqual(cfg["game"]["gameProperties"], {"persistence": {"autoSaveInterval": 5}})

    def test_leaving_disabled_keeps_other_header_keys(self):
        cfg = config({"missionHeader": {"m_eSaveTypes": 0, "m_sName": "Mine"}})
        set_persistence_mode(cfg, "default")
        self.assertEqual(cfg["game"]["gameProperties"], {"missionHeader": {"m_sName": "Mine"}})

    def test_default_removes_block_without_adding_anything(self):
        cfg = config({"persistence": {"hiveId": 1}})
        set_persistence_mode(cfg, "default")
        self.assertEqual(cfg["game"]["gameProperties"], {})
        cfg = {"game": {"name": "x"}}
        set_persistence_mode(cfg, "default")
        self.assertEqual(cfg, {"game": {"name": "x"}})

    def test_custom_creates_an_empty_block(self):
        cfg = {"game": {}}
        set_persistence_mode(cfg, "custom")
        self.assertEqual(cfg["game"]["gameProperties"]["persistence"], {})

    def test_unexpected_header_is_rejected(self):
        with self.assertRaises(ChangeRejected):
            set_persistence_mode(config({"missionHeader": "oops"}), "disabled")

    def test_custom_fields_write_only_changes(self):
        cfg = config({"persistence": {"autoSaveInterval": 10, "hiveId": 1}})
        written = config_fields.apply(cfg, PERSISTENCE_FIELDS, {
            "auto_save_interval": 10, "save_retention": 10, "keep_session_save": True, "hive_id": 1,
        })
        self.assertEqual(written, ["keep_session_save"])
        self.assertEqual(cfg["game"]["gameProperties"]["persistence"],
                         {"autoSaveInterval": 10, "hiveId": 1, "keepSessionSave": True})


if __name__ == "__main__":
    unittest.main()
