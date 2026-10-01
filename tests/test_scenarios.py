import os
import tempfile
import unittest

from arma_panel.services.scenarios.addons import scenarios_from_rdb


def rdb_record(path, guid):
    """One asset record as laid out in resourceDatabase.rdb."""
    raw = path.encode("ascii")
    return (len(raw) + 1).to_bytes(4, "little") + raw + b"\0" + b"\0" * 6 + bytes.fromhex(guid)[::-1]


class ScenariosFromRdbTest(unittest.TestCase):
    def scan(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "resourceDatabase.rdb")
            with open(path, "wb") as f:
                f.write(data)
            return scenarios_from_rdb(path, "Mod")

    def test_reads_scenario(self):
        found = self.scan(rdb_record("Missions/Fortress.conf", "ECC61978EDCC2B5A"))
        self.assertEqual([s["id"] for s in found], ["{ECC61978EDCC2B5A}Missions/Fortress.conf"])

    def test_reads_scenario_with_space_in_name(self):
        found = self.scan(rdb_record("Missions/Scenario CK.conf", "6A45889850514D76"))
        self.assertEqual([s["id"] for s in found], ["{6A45889850514D76}Missions/Scenario CK.conf"])
        self.assertEqual(found[0]["name"], "Scenario CK")

    def test_ignores_path_without_length_prefix(self):
        self.assertEqual(self.scan(b"junk Missions/Fake.conf\0" + b"\0" * 14), [])


if __name__ == "__main__":
    unittest.main()
