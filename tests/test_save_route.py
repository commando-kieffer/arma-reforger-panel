"""POST /api/config/save, which the save bar sends with every card that has
changes."""

import json
import os
import tempfile
import unittest
from unittest import mock

from arma_panel import config, create_app
from arma_panel.routes import server_config as route

SCENARIO = "{ECC61978EDCC2B5A}Missions/23_Campaign.conf"
CSRF = "token"


class SaveRouteTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "config.json")
        for name, value in (("SERVER_CONFIG", self.path), ("CONFIG_BACKUP_DIR", os.path.join(tmp.name, "backups"))):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (("get_server_pid", lambda: None), ("_scenario_ids", lambda: {SCENARIO})):
            patcher = mock.patch.object(route, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.write({"game": {"name": "Old", "scenarioId": SCENARIO, "passwordAdmin": "admin", "mods": []},
                    "keep": {"me": True}})
        self.client = create_app().test_client()
        with self.client.session_transaction() as session:
            session["logged_in"] = True
            session["csrf"] = CSRF

    def write(self, cfg):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, body):
        r = self.client.post("/api/config/save", json=body, headers={"X-CSRF-Token": CSRF})
        return r.status_code, r.get_json()

    def test_sections_are_saved_together(self):
        status, d = self.save({
            "server": {"server_name": "New", "max_players": 32},
            "gameplay": {"disable_third_person": True},
            "persistence": {"mode": "custom", "auto_save_interval": 5},
        })
        self.assertEqual((status, d["ok"], d["saved"]), (200, True, ["server", "gameplay", "persistence"]))
        cfg = self.read()
        self.assertEqual(cfg["game"]["name"], "New")
        self.assertEqual(cfg["game"]["maxPlayers"], 32)
        self.assertTrue(cfg["game"]["gameProperties"]["disableThirdPerson"])
        self.assertEqual(cfg["game"]["gameProperties"]["persistence"], {"autoSaveInterval": 5})
        self.assertEqual(cfg["keep"], {"me": True})

    def test_one_invalid_section_saves_nothing(self):
        before = self.read()
        status, d = self.save({"server": {"server_name": "New"}, "gameplay": {"network_view_distance": 1}})
        self.assertEqual((status, d["ok"], d["section"]), (400, False, "gameplay"))
        self.assertEqual(self.read(), before)

    def test_editor_text(self):
        r = self.client.get("/api/config/raw")
        sha = r.get_json()["sha256"]
        text = json.dumps({"game": {"scenarioId": SCENARIO, "gameProperties": {
            "missionHeader": {"m_ACE_Settings": {"m_ACE_Medical_Core": {"m_fBleedingRateScale": 0.5}}}}}}, indent="\t")
        status, d = self.save({"raw": {"text": text, "sha256": sha}})
        self.assertEqual((status, d["ok"], d["saved"]), (200, True, ["raw"]))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), text + "\n")

    def test_editor_errors_block_the_save(self):
        sha = self.client.get("/api/config/raw").get_json()["sha256"]
        before = self.read()
        status, d = self.save({"raw": {"text": '{"game": {"scenarioId": 5}}', "sha256": sha}})
        self.assertEqual((status, d["section"]), (400, "raw"))
        self.assertEqual(d["problems"][0]["path"], "game.scenarioId")
        self.assertEqual(self.read(), before)

    def test_editor_refuses_a_file_changed_meanwhile(self):
        sha = self.client.get("/api/config/raw").get_json()["sha256"]
        self.save({"server": {"server_name": "Changed by a form"}})
        status, d = self.save({"raw": {"text": json.dumps({"game": {"scenarioId": SCENARIO}}), "sha256": sha}})
        self.assertEqual(status, 409)
        self.assertEqual(self.read()["game"]["name"], "Changed by a form")

    def test_editor_and_forms_are_not_mixed(self):
        sha = self.client.get("/api/config/raw").get_json()["sha256"]
        status, _ = self.save({"raw": {"text": "{}", "sha256": sha}, "server": {"server_name": "x"}})
        self.assertEqual(status, 400)

    def test_check_endpoint(self):
        r = self.client.post("/api/config/check", json={"text": "{"}, headers={"X-CSRF-Token": CSRF})
        self.assertEqual(r.get_json()["problems"][0]["level"], "error")

    def test_needs_csrf(self):
        r = self.client.post("/api/config/save", json={"server": {"server_name": "x"}})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
