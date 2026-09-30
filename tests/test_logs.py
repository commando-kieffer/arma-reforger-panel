import os
import tempfile
import unittest
import zipfile
from unittest import mock

from arma_panel import config
from arma_panel.services import logs


class LogSessionsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log_dir = os.path.join(tmp.name, "logs")
        os.makedirs(self.log_dir)
        patcher = mock.patch.object(config, "LOG_DIR", self.log_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_session(self, name, files):
        path = os.path.join(self.log_dir, name)
        os.makedirs(path)
        for file_name, text in files.items():
            with open(os.path.join(path, file_name), "w", encoding="utf-8") as f:
                f.write(text)
        return path

    def test_list_newest_first_and_ignores_other_entries(self):
        self.make_session("logs_2026-09-28_10-00-00", {"console.log": "abc"})
        self.make_session("logs_2026-09-29_23-59-10", {"console.log": "x" * 10, "error.log": "e", "other.txt": "?"})
        self.make_session("logs_backup", {"console.log": "?"})
        with open(os.path.join(self.log_dir, "logs_2026-09-30_00-00-00"), "w") as f:
            f.write("a file, not a session")

        sessions = logs.list_sessions()
        self.assertEqual([s["name"] for s in sessions], ["logs_2026-09-29_23-59-10", "logs_2026-09-28_10-00-00"])
        self.assertEqual(sessions[0]["started"], "2026-09-29 23:59:10")
        self.assertEqual(sessions[0]["files"], {"console.log": 10, "error.log": 1})
        self.assertEqual(sessions[0]["size"], 11)

    def test_missing_log_dir(self):
        with mock.patch.object(config, "LOG_DIR", os.path.join(self.log_dir, "nope")):
            self.assertEqual(logs.list_sessions(), [])

    def test_session_dir_rejects_other_names(self):
        self.make_session("logs_2026-09-29_23-59-10", {"console.log": "x"})
        self.assertIsNotNone(logs.session_dir("logs_2026-09-29_23-59-10"))
        for name in ("logs_2026-09-29_23-59-11", "../logs", "logs_2026-09-29_23-59-10/..", "console.log", ""):
            self.assertIsNone(logs.session_dir(name), name)

    def test_zip_contains_the_three_log_files_only(self):
        files = {"console.log": "console", "error.log": "errors", "script.log": "scripts", "crash.dmp": "?"}
        self.make_session("logs_2026-09-29_23-59-10", files)
        archive = logs.zip_session("logs_2026-09-29_23-59-10")
        self.addCleanup(archive.close)
        with zipfile.ZipFile(archive) as zf:
            self.assertEqual(sorted(zf.namelist()), ["console.log", "error.log", "script.log"])
            self.assertEqual(zf.read("error.log"), b"errors")

    def test_zip_of_empty_or_unknown_session(self):
        self.make_session("logs_2026-09-29_23-59-10", {})
        self.assertIsNone(logs.zip_session("logs_2026-09-29_23-59-10"))
        self.assertIsNone(logs.zip_session("logs_2020-01-01_00-00-00"))


if __name__ == "__main__":
    unittest.main()
