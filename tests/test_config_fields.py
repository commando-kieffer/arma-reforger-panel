import unittest

from arma_panel.services import config_fields
from arma_panel.services.config_fields import Field, FieldError
from arma_panel.services.server_config import ChangeRejected

FIELDS = {
    "max_players": Field(("game", "maxPlayers"), int, 64, ((1, 128),)),
    "visible":     Field(("game", "visible"), bool, True),
    "grass":       Field(("game", "gameProperties", "serverMinGrassDistance"), int, 0, ((0, 0), (50, 150))),
    "ai_limit":    Field(("operating", "aiLimit"), int, -1, ((-1, None),)),
}


class ParseTest(unittest.TestCase):
    def test_types(self):
        with self.assertRaises(FieldError):
            FIELDS["max_players"].parse("64")
        with self.assertRaises(FieldError):
            FIELDS["max_players"].parse(True)
        with self.assertRaises(FieldError):
            FIELDS["max_players"].parse(12.5)
        with self.assertRaises(FieldError):
            FIELDS["visible"].parse(1)
        self.assertIs(FIELDS["visible"].parse(False), False)

    def test_ranges(self):
        self.assertEqual(FIELDS["max_players"].parse(128), 128)
        for bad in (0, 129):
            with self.assertRaises(FieldError):
                FIELDS["max_players"].parse(bad)
        for good in (0, 50, 150):
            self.assertEqual(FIELDS["grass"].parse(good), good)
        for bad in (1, 49, 151):
            with self.assertRaises(FieldError):
                FIELDS["grass"].parse(bad)
        self.assertEqual(FIELDS["ai_limit"].parse(5000), 5000)
        with self.assertRaises(FieldError):
            FIELDS["ai_limit"].parse(-2)

    def test_parse_form_ignores_absent_fields(self):
        self.assertEqual(config_fields.parse_form(FIELDS, {"visible": False, "other": 1}), {"visible": False})


class ApplyTest(unittest.TestCase):
    def test_defaults_are_not_written_for_missing_keys(self):
        cfg = {"game": {}}
        written = config_fields.apply(cfg, FIELDS, {"max_players": 64, "visible": True, "grass": 0})
        self.assertEqual(written, [])
        self.assertEqual(cfg, {"game": {}})

    def test_changed_values_are_written(self):
        cfg = {"game": {"maxPlayers": 32}}
        written = config_fields.apply(cfg, FIELDS, {"max_players": 40, "grass": 50, "ai_limit": 100})
        self.assertEqual(written, ["max_players", "grass", "ai_limit"])
        self.assertEqual(cfg, {"game": {"maxPlayers": 40, "gameProperties": {"serverMinGrassDistance": 50}},
                               "operating": {"aiLimit": 100}})

    def test_existing_value_set_back_to_default_is_written(self):
        cfg = {"game": {"visible": False}}
        self.assertEqual(config_fields.apply(cfg, FIELDS, {"visible": True}), ["visible"])
        self.assertIs(cfg["game"]["visible"], True)

    def test_unexpected_container_is_rejected(self):
        cfg = {"game": {"gameProperties": None}}
        with self.assertRaises(ChangeRejected):
            config_fields.apply(cfg, FIELDS, {"grass": 50})

    def test_form_values_fall_back_to_defaults(self):
        cfg = {"game": {"maxPlayers": "lots", "visible": False}}
        values = config_fields.form_values(cfg, FIELDS)
        self.assertEqual(values, {"max_players": 64, "visible": False, "grass": 0, "ai_limit": -1})


if __name__ == "__main__":
    unittest.main()
