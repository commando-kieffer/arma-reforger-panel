import unittest

from arma_panel.services.mods import collect_import_entries, fill_versions, normalize_mod_entry


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


class FillVersionsTest(unittest.TestCase):
    def test_fills_only_missing_versions(self):
        mods = [{"modId": "AA", "name": "Pinned", "version": "1.0"},
                {"modId": "BB", "name": "Latest"},
                {"modId": "CC", "name": "Not downloaded"}]
        filled, missing = fill_versions(mods, {"AA": "2.0", "BB": "3.1"})
        self.assertEqual(filled, [{"modId": "AA", "name": "Pinned", "version": "1.0"},
                                  {"modId": "BB", "name": "Latest", "version": "3.1"},
                                  {"modId": "CC", "name": "Not downloaded"}])
        self.assertEqual(missing, [{"modId": "CC", "name": "Not downloaded"}])
        self.assertNotIn("version", mods[1])

    def test_keeps_other_fields(self):
        filled, _ = fill_versions([{"modId": "aa", "required": False}], {"AA": "1.2"})
        self.assertEqual(filled, [{"modId": "aa", "required": False, "version": "1.2"}])


if __name__ == "__main__":
    unittest.main()
