import unittest

from arma_panel.services.mods import collect_import_entries, normalize_mod_entry


class NormalizeModEntryTest(unittest.TestCase):
    def test_keeps_required_flag(self):
        entry = normalize_mod_entry({"modId": "595f2bf2f44836fb", "name": "RHS", "required": False})
        self.assertEqual(entry, {"modId": "595F2BF2F44836FB", "name": "RHS", "required": False})

    def test_ignores_non_boolean_required(self):
        entry = normalize_mod_entry({"modId": "AB", "required": "no"})
        self.assertEqual(entry, {"modId": "AB"})

    def test_rejects_non_hex_id(self):
        self.assertIsNone(normalize_mod_entry({"modId": "not-hex"}))

    def test_import_skips_duplicates(self):
        valid, skipped = collect_import_entries([{"modId": "AB"}, {"modId": "ab"}, {"modId": "zz"}])
        self.assertEqual(valid, [{"modId": "AB"}])
        self.assertEqual(skipped, [(2, "AB"), (3, None)])


if __name__ == "__main__":
    unittest.main()
