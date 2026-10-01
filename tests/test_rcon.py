import socket
import threading
import unittest
from unittest import mock

from arma_panel.services import a2s, players, rcon
from arma_panel.services.rcon import RconError, build_packet, parse_packet

PASSWORD = "s3cret"
UID_A = "b6955d91-4749-4cdb-9a51-e69f630ec435"
UID_B = "0f3a1c22-9d4e-4b7a-8c1d-2e5f6a7b8c9d"
HEADER = "Players on server: [Player#] ; [Player UID] ; [Player Name]\n"


def reply(sequence, text):
    return build_packet(bytes([rcon.COMMAND, sequence]) + text.encode("utf-8"))


def split_reply(sequence, text, size):
    data = text.encode("utf-8")
    chunks = [data[i:i + size] for i in range(0, len(data), size)]
    return [build_packet(bytes([rcon.COMMAND, sequence, 0, len(chunks), n]) + chunk)
            for n, chunk in enumerate(chunks)]


class FakeServer:
    """RCON server on localhost. Logins are checked against PASSWORD and each
    command is answered with the packets `handler(sequence, command)` returns."""

    def __init__(self, handler):
        self.handler = handler
        self.logins = 0
        self.acks = []
        self.clients = set()
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
                packet, client = self.sock.recvfrom(65535)
            except OSError:
                continue
            payload = parse_packet(packet)
            if payload[0] == rcon.LOGIN:
                self.logins += 1
                self.clients.add(client)
                accepted = payload[1:] == PASSWORD.encode()
                answers = [build_packet(bytes([rcon.LOGIN, accepted]))]
            elif payload[0] == rcon.COMMAND:
                answers = self.handler(payload[1], payload[2:].decode())
            else:
                self.acks.append(payload[1])
                answers = []
            for answer in answers:
                self.sock.sendto(answer, client)

    def close(self):
        self.running = False
        self.thread.join()
        self.sock.close()


class PacketTest(unittest.TestCase):
    def test_layout(self):
        # Login packet for the password "a": 'B' 'E', CRC32 of the rest, 0xFF, payload.
        packet = build_packet(b"\x00a")
        self.assertEqual(packet[:2], b"BE")
        self.assertEqual(packet[6:], b"\xff\x00a")
        self.assertEqual(parse_packet(packet), b"\x00a")

    def test_rejected(self):
        packet = build_packet(b"\x01\x00hello")
        for bad in (packet[:-1], b"XX" + packet[2:], packet[:6] + b"\x00" + packet[7:], b"BE", b""):
            with self.assertRaises(RconError):
                parse_packet(bad)


class ParsePlayersTest(unittest.TestCase):
    def test_list(self):
        text = HEADER + f"1 ; {UID_A} ; Jerry\n12 ; {UID_B} ; Orzeł ; 04 \n"
        self.assertEqual(rcon.parse_players(text), [
            {"uid": UID_A, "name": "Jerry"},
            {"uid": UID_B, "name": "Orzeł ; 04"},
        ])

    def test_accepted_headers(self):
        row = f"3 ; {UID_A} ; Jerry"
        for header in ("Players on server:\n",
                       "Players on server:\r\n[Player#] ; [Player UID] ; [Player Name]\r\n",
                       "Processing Command: #players\n" + HEADER):
            self.assertEqual(len(rcon.parse_players(header + row)), 1, header)

    def test_no_players(self):
        self.assertEqual(rcon.parse_players(HEADER), [])

    def test_rejected(self):
        row = f"1 ; {UID_A} ; Jerry"
        for text in ("",
                     "Processing Command: #players",
                     row,
                     "Unknown command",
                     HEADER + row + "\nsomething else",
                     HEADER + "1 ; 76561198000000000 ; Jerry",
                     # Without line breaks the rows can't be told apart from the header.
                     HEADER.strip() + " " + row,
                     "Players on server: 2\n" + row):
            with self.assertRaises(RconError, msg=text):
                rcon.parse_players(text)

    def test_line_separator_in_a_name(self):
        # U+2028 is a line break for str.splitlines(); it must not start a new row.
        text = HEADER + f"1 ; {UID_A} ; Jerry 2 ; {UID_B} ; Admin"
        self.assertEqual(len(rcon.parse_players(text)), 1)


class ClientTest(unittest.TestCase):
    def serve(self, handler):
        server = FakeServer(handler)
        self.addCleanup(server.close)
        return server

    def client(self, server, password=PASSWORD, timeout=1):
        client = rcon.Client(server.address, password, timeout=timeout)
        self.addCleanup(client.close)
        return client

    def test_command(self):
        server = self.serve(lambda seq, command: [reply(seq, "you sent " + command)])
        self.assertEqual(self.client(server).command("#players"), "you sent #players")

    def test_login_is_reused(self):
        server = self.serve(lambda seq, command: [reply(seq, str(seq))])
        client = self.client(server)
        self.assertEqual([client.command("#players") for _ in range(3)], ["0", "1", "2"])
        self.assertEqual(server.logins, 1)
        self.assertEqual(len(server.clients), 1)

    def test_login_refused(self):
        server = self.serve(lambda seq, command: [reply(seq, "")])
        with self.assertRaises(rcon.LoginRefused):
            self.client(server, password="wrong").command("#players")

    def test_split_answer_out_of_order(self):
        text = HEADER + "".join(f"{i} ; {UID_A} ; Player {i}\n" for i in range(60))
        server = self.serve(lambda seq, command: list(reversed(split_reply(seq, text, 400))))
        self.assertEqual(self.client(server).command("#players"), text)

    def test_split_answer_cut_inside_a_character(self):
        text = "é" * 10
        server = self.serve(lambda seq, command: split_reply(seq, text, 3))
        self.assertEqual(self.client(server).command("#players"), text)

    def test_missing_part_times_out(self):
        server = self.serve(lambda seq, command: split_reply(seq, "x" * 100, 40)[:-1])
        with self.assertRaises(socket.timeout):
            self.client(server, timeout=0.3).command("#players")

    def test_inconsistent_split_answer(self):
        server = self.serve(lambda seq, command: [
            build_packet(bytes([rcon.COMMAND, seq, 0, 2, 0]) + b"a"),
            build_packet(bytes([rcon.COMMAND, seq, 0, 3, 1]) + b"b"),
        ])
        with self.assertRaises(RconError):
            self.client(server).command("#players")

    def test_server_message_is_acknowledged(self):
        server = self.serve(lambda seq, command: [
            build_packet(bytes([rcon.SERVER_MESSAGE, 7]) + b"Player connected"),
            reply(seq, "done"),
        ])
        client = self.client(server)
        self.assertEqual(client.command("#players"), "done")
        self.assertEqual(client.messages, ["Player connected"])
        # The acknowledgement was sent before the answer was read; let the server see it.
        client.command("#players")
        self.assertEqual(server.acks[:1], [7])

    def test_answer_to_another_command_is_rejected(self):
        server = self.serve(lambda seq, command: [reply(seq + 1, "stray")])
        with self.assertRaises(RconError):
            self.client(server).command("#players")

    def test_corrupted_packet_is_rejected(self):
        server = self.serve(lambda seq, command: [reply(seq, "hello")[:-1]])
        with self.assertRaises(RconError):
            self.client(server).command("#players")

    def test_new_login_after_a_failure(self):
        commands = []

        def handler(seq, command):
            commands.append(command)
            return [] if len(commands) == 1 else [reply(seq, "back")]

        server = self.serve(handler)
        client = self.client(server, timeout=0.3)
        with self.assertRaises(socket.timeout):
            client.command("#players")
        self.assertEqual(client.command("#players"), "back")
        self.assertEqual(server.logins, 2)

    def test_new_login_after_a_long_silence(self):
        server = self.serve(lambda seq, command: [reply(seq, "ok")])
        client = self.client(server)
        client.command("#players")
        with mock.patch.object(rcon, "SESSION_SECONDS", -1):
            client.command("#players")
        self.assertEqual(server.logins, 2)

    def test_no_server(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        address = sock.getsockname()
        sock.close()
        with self.assertRaises(OSError):
            rcon.Client(address, PASSWORD, timeout=0.3).command("#players")


class RconSettingsTest(unittest.TestCase):
    def test_enabled(self):
        cfg = {"rcon": {"address": "127.0.0.1", "port": 19998, "password": PASSWORD, "permission": "monitor"}}
        self.assertEqual(players.rcon_settings(cfg), (("127.0.0.1", 19998), PASSWORD))

    def test_defaults(self):
        self.assertEqual(players.rcon_settings({"rcon": {"password": PASSWORD}}), (("127.0.0.1", 19999), PASSWORD))
        cfg = {"rcon": {"address": "0.0.0.0", "password": PASSWORD}}
        self.assertEqual(players.rcon_settings(cfg), (("127.0.0.1", 19999), PASSWORD))

    def test_not_enabled(self):
        for cfg in ({}, {"rcon": None}, {"rcon": {"address": "127.0.0.1", "port": 19999}},
                    {"rcon": {"password": ""}}, {"rcon": {"password": 1234}},
                    {"rcon": {"password": PASSWORD, "port": "19999"}}):
            self.assertIsNone(players.rcon_settings(cfg), cfg)


class RconPlayersTest(unittest.TestCase):
    """get_players() with an rcon block: A2S for the count, RCON for the list."""

    def setUp(self):
        players._cache.update(key=None, at=0.0, result=None)
        players._rcon.update(problem=None)
        self.addCleanup(players._close_rcon)
        patcher = mock.patch.object(players.logger, "warning")
        self.warning = patcher.start()
        self.addCleanup(patcher.stop)

    def serve(self, text):
        """Start a server answering `#players` with `text`; returns a config.json pointing at it."""
        self.server = FakeServer(lambda seq, command: [reply(seq, text)] if command == "#players" else [])
        self.addCleanup(self.server.close)
        return self.config(self.server.address)

    def config(self, address, password=PASSWORD):
        return {"a2s": {"address": "127.0.0.1", "port": 17777},
                "rcon": {"address": address[0], "port": address[1], "password": password}}

    def query(self, cfg, count):
        players._cache.update(key=None)
        with mock.patch.object(a2s, "query_info", return_value={"players": count, "max_players": 64}):
            return players.get_players(True, cfg)

    def test_list(self):
        cfg = self.serve(HEADER + f"1 ; {UID_A} ; Jerry\n2 ; {UID_B} ; Hubert\n")
        self.assertEqual(self.query(cfg, 2), {"state": "ok", "count": 2, "max": 64, "list_state": "ok", "players": [
            {"uid": UID_A, "name": "Jerry"}, {"uid": UID_B, "name": "Hubert"}]})
        self.warning.assert_not_called()

    def test_nobody_connected(self):
        result = self.query(self.serve("not asked"), 0)
        self.assertEqual((result["players"], result["list_state"]), ([], "ok"))
        self.assertEqual(self.server.logins, 0)

    def test_list_shorter_than_the_count(self):
        result = self.query(self.serve(HEADER + f"1 ; {UID_A} ; Jerry\n"), 2)
        self.assertEqual((result["count"], result["players"], result["list_state"]), (2, None, "rcon_mismatch"))

    def test_answer_not_understood(self):
        result = self.query(self.serve("Unknown command"), 1)
        self.assertEqual((result["count"], result["players"], result["list_state"]), (1, None, "rcon_bad_reply"))
        self.assertIn("Unknown command", self.warning.call_args[0][1])

    def test_wrong_password(self):
        self.serve(HEADER)
        result = self.query(self.config(self.server.address, password="not-the-password"), 1)
        self.assertEqual((result["players"], result["list_state"]), (None, "rcon_refused"))
        self.assertNotIn("not-the-password", str(self.warning.call_args))

    def test_no_answer(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        address = sock.getsockname()
        sock.close()
        result = self.query(self.config(address), 1)
        self.assertEqual((result["count"], result["players"], result["list_state"]), (1, None, "rcon_no_answer"))

    def test_problem_logged_once(self):
        cfg = self.serve("Unknown command")
        self.query(cfg, 1)
        self.query(cfg, 1)
        self.assertEqual(self.warning.call_count, 1)

    def test_recovers_after_a_problem(self):
        cfg = self.serve(HEADER + f"1 ; {UID_A} ; Jerry\n")
        self.assertEqual(self.query(cfg, 2)["list_state"], "rcon_mismatch")
        self.assertEqual(self.query(cfg, 1)["players"], [{"uid": UID_A, "name": "Jerry"}])
        self.assertEqual(self.server.logins, 1)

    def test_client_closed_when_the_server_stops(self):
        self.query(self.serve(HEADER + f"1 ; {UID_A} ; Jerry\n"), 1)
        self.assertIsNotNone(players._rcon["client"])
        self.assertEqual(players.get_players(False, {}), {"state": "offline"})
        self.assertIsNone(players._rcon["client"])


if __name__ == "__main__":
    unittest.main()
