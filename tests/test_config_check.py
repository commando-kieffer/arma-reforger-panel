import json
import unittest

from arma_panel.services import config_check

VALID = {
    "bindAddress": "0.0.0.0",
    "bindPort": 2001,
    "publicPort": 2001,
    "a2s": {"address": "1.2.3.4", "port": 17777},
    "rcon": {"address": "127.0.0.1", "port": 19999, "password": "s3cret", "permission": "admin"},
    "game": {
        "name": "Server",
        "password": "",
        "passwordAdmin": "admin",
        "scenarioId": "{ECC61978EDCC2B5A}Missions/23_Campaign.conf",
        "maxPlayers": 64,
        "visible": True,
        "crossPlatform": False,
        "supportedPlatforms": ["PLATFORM_PC"],
        "gameProperties": {
            "serverMaxViewDistance": 2500,
            "battlEye": True,
            "missionHeader": {
                "m_ACE_Settings": {"m_ACE_Medical_Core": {"m_bBleedOutForPlayersEnabled": 1}},
            },
            "persistence": {"autoSaveInterval": 10},
        },
        "mods": [{"modId": "595F2BF2F44836FB", "name": "RHS", "version": "1.0"}],
    },
    "operating": {"aiLimit": -1, "joinQueue": {"maxSize": 10}, "disableNavmeshStreaming": []},
}


def with_change(change):
    cfg = json.loads(json.dumps(VALID))
    change(cfg)
    return json.dumps(cfg)


class ConfigCheckTest(unittest.TestCase):
    def problems(self, text, **kwargs):
        return [(p["level"], p["path"]) for p in config_check.check(text, **kwargs)]

    def assertError(self, text, path):
        problems = self.problems(text)
        self.assertIn(("error", path), problems, problems)
        self.assertTrue(config_check.has_errors(config_check.check(text)))

    def test_valid_config(self):
        self.assertEqual(self.problems(json.dumps(VALID, indent="\t")), [])

    def test_syntax_errors(self):
        for text in ("{", '{"game": {}', "", "{'game': 1}", '{"a": NaN}', '{"a": 1,}'):
            with self.subTest(text=text):
                problems = config_check.check(text)
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0]["level"], "error")
        self.assertIn("line 2", config_check.check('{\n  "game": }')[0]["message"])

    def test_duplicate_key(self):
        self.assertTrue(config_check.has_errors(config_check.check('{"game": {"name": "a", "name": "b"}}')))

    def test_not_an_object(self):
        self.assertError("[]", "")

    def test_required_keys(self):
        self.assertError("{}", "game")
        self.assertError(with_change(lambda c: c["game"].pop("scenarioId")), "game.scenarioId")
        self.assertError(with_change(lambda c: c["rcon"].pop("password")), "rcon.password")
        self.assertError(with_change(lambda c: c["a2s"].pop("address")), "a2s.address")

    def test_types_and_ranges(self):
        cases = {
            "game.maxPlayers": lambda c: c["game"].update(maxPlayers="64"),
            "game.visible": lambda c: c["game"].update(visible=1),
            "bindPort": lambda c: c.update(bindPort=70000),
            "game.gameProperties.serverMaxViewDistance": lambda c: c["game"]["gameProperties"].update(serverMaxViewDistance=99),
            "game.gameProperties.missionHeader": lambda c: c["game"]["gameProperties"].update(missionHeader=[]),
            "rcon.permission": lambda c: c["rcon"].update(permission="root"),
            "rcon.password": lambda c: c["rcon"].update(password="a b"),
            "game.passwordAdmin": lambda c: c["game"].update(passwordAdmin="has space"),
            "game.name": lambda c: c["game"].update(name="x" * 101),
            "game.supportedPlatforms.1": lambda c: c["game"].update(supportedPlatforms=["PLATFORM_PC", "SWITCH"]),
            "operating.joinQueue.maxSize": lambda c: c["operating"]["joinQueue"].update(maxSize=51),
            "game.mods.0": lambda c: c["game"].update(mods=[{"modId": "not-hex"}]),
        }
        for path, change in cases.items():
            with self.subTest(path=path):
                self.assertError(with_change(change), path)

    def test_short_rcon_password(self):
        self.assertError(with_change(lambda c: c["rcon"].update(password="ab")), "rcon.password")

    def test_navmesh_streaming_accepts_a_bool(self):
        self.assertEqual(self.problems(with_change(lambda c: c["operating"].update(disableNavmeshStreaming=True))), [])

    def test_unknown_keys_are_warnings(self):
        text = with_change(lambda c: (c["game"].update(MaxPlayers=10), c.update(newRootKey={})))
        problems = self.problems(text)
        self.assertIn(("warning", "game.MaxPlayers"), problems)
        self.assertIn(("warning", "newRootKey"), problems)
        self.assertFalse(config_check.has_errors(config_check.check(text)))

    def test_mission_header_content_is_free(self):
        text = with_change(lambda c: c["game"]["gameProperties"]["missionHeader"].update(anything={"x": [1, "a"]}))
        self.assertEqual(self.problems(text), [])

    def test_ports_must_differ(self):
        self.assertError(with_change(lambda c: c["a2s"].update(port=2001)), "a2s.port")
        self.assertError(with_change(lambda c: c["rcon"].update(port=17777)), "rcon.port")
        # Default ports count too: no bindPort/publicPort means 2001.
        self.assertError(with_change(lambda c: (c.pop("bindPort"), c.pop("publicPort"), c["a2s"].update(port=2001))),
                         "a2s.port")

    def test_duplicate_mod_is_a_warning(self):
        mod = {"modId": "595F2BF2F44836FB"}
        problems = self.problems(with_change(lambda c: c["game"].update(mods=[mod, mod])))
        self.assertEqual(problems, [("warning", "game.mods.1")])

    def test_unknown_scenario_is_a_warning(self):
        text = json.dumps(VALID)
        self.assertEqual(self.problems(text, scenario_ids={"other"}), [("warning", "game.scenarioId")])
        self.assertEqual(self.problems(text, scenario_ids={VALID["game"]["scenarioId"]}), [])

    def test_errors_come_first(self):
        text = with_change(lambda c: (c.update(unknown=1), c["game"].update(maxPlayers=0)))
        self.assertEqual([p["level"] for p in config_check.check(text)], ["error", "warning"])


if __name__ == "__main__":
    unittest.main()
