import os
import signal
import tempfile
import unittest
from unittest import mock

from arma_panel.services import process

SERVER = b"/home/arma/server/ArmaReforgerServer\0-config\0/home/arma/server/config.json\0"


class FakeProc:
    """A /proc tree holding fake processes, and an os.kill that ends them:
    `stubborn` pids ignore SIGINT, `immortal` ones ignore SIGKILL too."""

    def __init__(self, test):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = tmp.name
        self.signals = []
        self.stubborn = set()
        self.immortal = set()
        self.denied = set()
        for name, value in (("PROC_DIR", self.root), ("INTERRUPT_WAIT", 0.2), ("KILL_WAIT", 0.2),
                            ("POLL_INTERVAL", 0.01)):
            patcher = mock.patch.object(process, name, value)
            patcher.start()
            test.addCleanup(patcher.stop)
        patcher = mock.patch.object(process.os, "kill", self.kill)
        patcher.start()
        test.addCleanup(patcher.stop)
        # The panel runs on Linux; Windows has no SIGKILL.
        patcher = mock.patch.object(signal, "SIGKILL", getattr(signal, "SIGKILL", 9), create=True)
        patcher.start()
        test.addCleanup(patcher.stop)

    def add(self, pid, cmdline, cgroup="0::/user.slice\n"):
        folder = os.path.join(self.root, str(pid))
        os.makedirs(folder)
        with open(os.path.join(folder, "cmdline"), "wb") as f:
            f.write(cmdline)
        with open(os.path.join(folder, "cgroup"), "w") as f:
            f.write(cgroup)

    def end(self, pid):
        # An exited process waiting to be reaped keeps its pid but no command line.
        with open(os.path.join(self.root, str(pid), "cmdline"), "wb"):
            pass

    def kill(self, pid, sig):
        if not os.path.isdir(os.path.join(self.root, str(pid))):
            raise ProcessLookupError()
        if pid in self.denied:
            raise PermissionError()
        self.signals.append((pid, sig))
        if pid in self.immortal or (sig == signal.SIGINT and pid in self.stubborn):
            return
        self.end(pid)


class FindServerTest(unittest.TestCase):
    def test_only_the_server_binary_counts(self):
        proc = FakeProc(self)
        proc.add(120, SERVER)
        proc.add(130, b"./ArmaReforgerServer\0-config\0config.json\0")
        proc.add(140, b"tail\0-f\0/home/arma/server/ArmaReforgerServer.log\0")
        proc.add(150, b"nano\0ArmaReforgerServer\0")
        proc.add(160, b"/usr/bin/python3\0/home/arma/panel/app.py\0")
        proc.add(170, b"")
        os.makedirs(os.path.join(proc.root, "self"))
        self.assertEqual(process.find_server_pids(), [120, 130])
        self.assertEqual(process.get_server_pid(), 120)

    def test_no_proc(self):
        with mock.patch.object(process, "PROC_DIR", os.path.join(tempfile.gettempdir(), "no-such-proc")):
            self.assertEqual(process.find_server_pids(), [])
            self.assertIsNone(process.get_server_pid())


class ForceStopTest(unittest.TestCase):
    def setUp(self):
        self.proc = FakeProc(self)

    def test_nothing_to_stop(self):
        self.assertEqual(process.force_stop()["found"], [])
        self.assertEqual(self.proc.signals, [])

    def test_sigint_is_enough(self):
        self.proc.add(120, SERVER)
        result = process.force_stop()
        self.assertEqual((result["found"], result["killed"], result["remaining"]), ([120], [], []))
        self.assertEqual(self.proc.signals, [(120, signal.SIGINT)])

    def test_every_instance_then_sigkill_for_the_stubborn(self):
        self.proc.add(120, SERVER)
        self.proc.add(121, SERVER)
        self.proc.stubborn.add(121)
        result = process.force_stop()
        self.assertEqual((result["found"], result["killed"], result["remaining"]), ([120, 121], [121], []))
        self.assertEqual(self.proc.signals, [(120, signal.SIGINT), (121, signal.SIGINT), (121, signal.SIGKILL)])

    def test_still_running_is_reported(self):
        self.proc.add(120, SERVER)
        self.proc.immortal.add(120)
        self.assertEqual(process.force_stop()["remaining"], [120])

    def test_process_of_another_user(self):
        self.proc.add(120, SERVER)
        self.proc.denied.add(120)
        result = process.force_stop()
        self.assertEqual((result["denied"], result["remaining"]), ([120], [120]))

    def test_systemd_unit_is_detected(self):
        self.proc.add(120, SERVER, cgroup="0::/system.slice/arma-server.service\n")
        self.assertTrue(process.force_stop()["systemd"])
        self.proc.add(121, SERVER)
        self.assertFalse(process.force_stop()["systemd"])


if __name__ == "__main__":
    unittest.main()
