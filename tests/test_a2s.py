import socket
import struct
import threading
import unittest
from unittest import mock

from arma_panel.services import a2s, players
from arma_panel.services.a2s import A2SError

HEADER = b"\xff\xff\xff\xff"
CHALLENGE = b"\x0a\x0b\x0c\x0d"


def info_payload(count=3, max_players=64):
    return (b"I\x11" + b"My Server\x00" + b"Everon\x00" + b"ArmaReforger\x00" + b"Arma Reforger\x00"
            + struct.pack("<h", 0) + bytes([count, max_players, 0]) + b"dl\x00\x001.6.0\x00")


def players_payload(entries, announced=None):
    out = b"D" + bytes([len(entries) if announced is None else announced])
    for name, duration in entries:
        out += b"\x00" + name.encode("utf-8") + b"\x00" + struct.pack("<l", 0) + struct.pack("<f", duration)
    return out


def split(payload, size):
    """Split HEADER + payload into Source-format split packets."""
    data = HEADER + payload
    chunks = [data[i:i + size] for i in range(0, len(data), size)]
    return [b"\xfe\xff\xff\xff" + struct.pack("<LBBh", 1234, len(chunks), n, 1248) + chunk
            for n, chunk in enumerate(chunks)]


class FakeServer:
    """UDP server on localhost answering each request with `handler(request)`."""

    def __init__(self, handler):
        self.handler = handler
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.address = self.sock.getsockname()
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while self.running:
            try:
                request, client = self.sock.recvfrom(65535)
            except OSError:
                continue
            for packet in self.handler(request):
                self.sock.sendto(packet, client)

    def close(self):
        self.running = False
        self.thread.join()
        self.sock.close()


def challenging(answer):
    """Handler that asks for a challenge first, then sends `answer` packets."""
    def handle(request):
        if request.endswith(CHALLENGE):
            return answer
        return [HEADER + b"A" + CHALLENGE]
    return handle


class A2SClientTest(unittest.TestCase):
    def serve(self, handler):
        server = FakeServer(handler)
        self.addCleanup(server.close)
        return server.address

    def test_info_without_challenge(self):
        address = self.serve(lambda req: [HEADER + info_payload(count=5, max_players=32)])
        info = a2s.query_info(address, timeout=1)
        self.assertEqual((info["players"], info["max_players"], info["map"]), (5, 32, "Everon"))

    def test_info_with_challenge(self):
        address = self.serve(challenging([HEADER + info_payload(count=2)]))
        self.assertEqual(a2s.query_info(address, timeout=1)["players"], 2)

    def test_players_with_challenge(self):
        answer = players_payload([("Orzeł_04", 125.7), ("Hubert", 30.0)])
        address = self.serve(challenging([HEADER + answer]))
        result = a2s.query_players(address, timeout=1)
        self.assertEqual(result, [{"name": "Orzeł_04", "duration": 125}, {"name": "Hubert", "duration": 30}])

    def test_split_answer_out_of_order(self):
        answer = players_payload([(f"Player {i}", 60.0) for i in range(40)])
        packets = split(answer, 300)
        self.assertGreater(len(packets), 2)
        address = self.serve(challenging(list(reversed(packets))))
        self.assertEqual(len(a2s.query_players(address, timeout=1)), 40)

    def test_truncated_player_list_is_rejected(self):
        answer = players_payload([("A", 1.0), ("B", 2.0)], announced=3)
        address = self.serve(lambda req: [HEADER + answer])
        with self.assertRaises(A2SError):
            a2s.query_players(address, timeout=1)

    def test_extra_data_is_rejected(self):
        answer = players_payload([("A", 1.0)]) + b"garbage"
        address = self.serve(lambda req: [HEADER + answer])
        with self.assertRaises(A2SError):
            a2s.query_players(address, timeout=1)

    def test_unknown_split_format_is_rejected(self):
        # Split packets without the "max packet size" field.
        data = HEADER + players_payload([("A", 1.0)])
        packets = [b"\xfe\xff\xff\xff" + struct.pack("<LBB", 7, 2, n) + chunk
                   for n, chunk in enumerate((data[:8], data[8:]))]
        address = self.serve(lambda req: packets)
        with self.assertRaises(A2SError):
            a2s.query_players(address, timeout=1)

    def test_no_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        address = sock.getsockname()
        sock.close()
        with self.assertRaises(OSError):
            a2s.query_info(address, timeout=0.3)


class GetPlayersTest(unittest.TestCase):
    CFG = {"a2s": {"address": "0.0.0.0", "port": 17777}}

    def setUp(self):
        players._cache.update(key=None, at=0.0, result=None)

    def test_address(self):
        self.assertEqual(players.a2s_address(self.CFG), ("127.0.0.1", 17777))
        self.assertEqual(players.a2s_address({"a2s": {"address": "1.2.3.4", "port": 2302}}), ("1.2.3.4", 2302))
        self.assertIsNone(players.a2s_address({}))
        self.assertIsNone(players.a2s_address({"a2s": {"address": "1.2.3.4", "port": "17777"}}))

    def test_offline_and_not_configured(self):
        self.assertEqual(players.get_players(False, self.CFG), {"state": "offline"})
        self.assertEqual(players.get_players(True, {}), {"state": "not_configured"})

    def test_no_answer(self):
        with mock.patch.object(a2s, "query_info", side_effect=socket.timeout()):
            self.assertEqual(players.get_players(True, self.CFG), {"state": "no_answer"})

    def test_count_only_when_list_fails(self):
        with mock.patch.object(a2s, "query_info", return_value={"players": 4, "max_players": 32}), \
             mock.patch.object(a2s, "query_players", side_effect=A2SError("bad")):
            result = players.get_players(True, self.CFG)
        self.assertEqual(result, {"state": "ok", "count": 4, "max": 32, "players": None, "list_state": "rcon_disabled"})

    def test_count_only_when_no_names(self):
        with mock.patch.object(a2s, "query_info", return_value={"players": 2, "max_players": 32}), \
             mock.patch.object(a2s, "query_players", return_value=[{"name": "", "duration": 5}] * 2):
            result = players.get_players(True, self.CFG)
        self.assertEqual((result["players"], result["list_state"]), (None, "rcon_disabled"))

    def test_list_sorted_and_cached(self):
        entries = [{"name": "A", "duration": 10}, {"name": "B", "duration": 300}]
        with mock.patch.object(a2s, "query_info", return_value={"players": 2, "max_players": 32}) as info, \
             mock.patch.object(a2s, "query_players", return_value=entries):
            first = players.get_players(True, self.CFG)
            second = players.get_players(True, self.CFG)
        self.assertEqual([p["name"] for p in first["players"]], ["B", "A"])
        self.assertEqual(first["list_state"], "ok")
        self.assertIs(first, second)
        self.assertEqual(info.call_count, 1)


if __name__ == "__main__":
    unittest.main()
