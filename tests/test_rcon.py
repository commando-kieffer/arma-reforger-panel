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

# Payloads sent by a real server for a login followed by `#players`, with one
# player connected (name and identity ID replaced).
CAPTURED_LOGIN = [
    b"\x00\x01",
    b"\x02\x00Logged In! Client ID: #0",
]
CAPTURED_PLAYERS = [
    b"\x01\x00",
    b"\x02\x01Processing Command: #players",
    b"\x02\x02Players on server: [Player#] ; [Player UID] ; [Player Name]\n"
    b"1 ; b6955d91-4749-4cdb-9a51-e69f630ec435 ; Cpt. Jerry - Fox",
]


def output(text, command="#players"):
    """Server messages a real server sends once it has run `command`."""
    return ["Processing Command: " + command, text]


class FakeServer:
    """RCON server on localhost behaving like the game server: a login is
    answered then followed by a "Logged In!" message, a command is
    acknowledged then followed by the messages `handler(command)` returns."""

    def __init__(self, handler, acknowledge=lambda sequence: bytes([rcon.COMMAND, sequence])):
        self.handler = handler
        self.acknowledge = acknowledge
        self.logins = 0
        self.acks = []
        self.messages = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.address = self.sock.getsockname()
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _message(self, text):
        self.messages += 1
        return bytes([rcon.SERVER_MESSAGE, self.messages - 1]) + text.encode("utf-8")

    def _serve(self):
        while self.running:
            try:
                packet, client = self.sock.recvfrom(65535)
            except OSError:
                continue
            payload = parse_packet(packet)
            if payload[0] == rcon.LOGIN:
                self.logins += 1
                self.messages = 0
                if payload[1:] == PASSWORD.encode():
                    answers = [b"\x00\x01", self._message("Logged In! Client ID: #0")]
                else:
                    answers = [b"\x00\x00"]
            elif payload[0] == rcon.COMMAND:
                answers = [self.acknowledge(payload[1])]
                answers += [self._message(text) for text in self.handler(payload[2:].decode())]
            else:
                self.acks.append(payload[1])
                answers = []
            for answer in answers:
                if answer:
                    self.sock.sendto(build_packet(answer), client)

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
    def test_captured_output(self):
        text = CAPTURED_PLAYERS[2][2:].decode()
        self.assertEqual(rcon.parse_players(text), [{"uid": UID_A, "name": "Cpt. Jerry - Fox"}])

    def test_list(self):
        text = HEADER + f"1 ; {UID_A} ; Jerry\r\n12 ; {UID_B} ; Orzeł ; 04 \n3 ; {UID_A} ; \n"
        self.assertEqual(rcon.parse_players(text), [
            {"uid": UID_A, "name": "Jerry"},
            {"uid": UID_B, "name": "Orzeł ; 04"},
            {"uid": UID_A, "name": ""},
        ])

    def test_no_players(self):
        self.assertEqual(rcon.parse_players(HEADER), [])

    def test_rejected(self):
        row = f"1 ; {UID_A} ; Jerry"
        for text in ("",
                     "Processing Command: #players",
                     row,
                     "Unknown command",
                     "Players on server:\n" + row,
                     HEADER + row + "\nsomething else",
                     HEADER + "1 ; 76561198000000000 ; Jerry",
                     HEADER + f"1;{UID_A};Jerry",
                     # Without line breaks the rows can't be told apart from the header.
                     HEADER.strip() + " " + row):
            with self.assertRaises(RconError, msg=text):
                rcon.parse_players(text)

    def test_line_separator_in_a_name(self):
        # U+2028 is a line break for str.splitlines(); it must not start a new row.
        text = HEADER + f"1 ; {UID_A} ; Jerry 2 ; {UID_B} ; Admin"
        self.assertEqual(len(rcon.parse_players(text)), 1)


class ClientTest(unittest.TestCase):
    def serve(self, handler, **kwargs):
        server = FakeServer(handler, **kwargs)
        self.addCleanup(server.close)
        return server

    def client(self, server, password=PASSWORD, timeout=1):
        client = rcon.Client(server.address, password, timeout=timeout)
        self.addCleanup(client.close)
        return client

    def test_captured_exchange(self):
        """Replay the packets of a real server, in the order it sent them."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        self.addCleanup(sock.close)
        received = []

        def replay():
            for answers in (CAPTURED_LOGIN, CAPTURED_PLAYERS):
                packet, client = sock.recvfrom(65535)
                received.append(parse_packet(packet))
                for answer in answers:
                    sock.sendto(build_packet(answer), client)
            sock.settimeout(1)
            for _ in range(3):
                received.append(parse_packet(sock.recvfrom(65535)[0]))

        thread = threading.Thread(target=replay, daemon=True)
        thread.start()
        client = self.client(mock.Mock(address=sock.getsockname()))
        text = client.command("#players")
        thread.join()
        self.assertEqual(rcon.parse_players(text), [{"uid": UID_A, "name": "Cpt. Jerry - Fox"}])
        self.assertEqual(client.messages, ["Logged In! Client ID: #0"])
        # Login, command, then one acknowledgement per server message.
        self.assertEqual(received, [b"\x00" + PASSWORD.encode(), b"\x01\x00#players",
                                    b"\x02\x00", b"\x02\x01", b"\x02\x02"])

    def test_command(self):
        server = self.serve(lambda command: output("you sent " + command, command))
        self.assertEqual(self.client(server).command("#players"), "you sent #players")

    def test_login_is_reused(self):
        server = self.serve(lambda command: output("list"))
        client = self.client(server)
        self.assertEqual([client.command("#players") for _ in range(3)], ["list"] * 3)
        self.assertEqual(server.logins, 1)

    def test_login_refused(self):
        server = self.serve(lambda command: output("list"))
        with self.assertRaises(rcon.LoginRefused):
            self.client(server, password="wrong").command("#players")

    def test_long_output(self):
        text = HEADER + "".join(f"{i} ; {UID_A} ; Player {i}\n" for i in range(128))
        server = self.serve(lambda command: output(text))
        self.assertEqual(self.client(server).command("#players"), text)

    def test_messages_before_the_output_are_set_aside(self):
        server = self.serve(lambda command: ["Something else"] + output("list"))
        client = self.client(server)
        self.assertEqual(client.command("#players"), "list")
        self.assertEqual(client.messages, ["Logged In! Client ID: #0", "Something else"])

    def test_server_messages_are_acknowledged(self):
        server = self.serve(lambda command: output("list"))
        client = self.client(server)
        client.command("#players")
        # The last acknowledgement was sent before command() returned; a
        # second exchange makes sure the server has read it.
        client.command("#players")
        self.assertEqual(server.acks[:3], [0, 1, 2])

    def test_no_output_times_out(self):
        for messages in ([], ["Processing Command: #players"], ["list"]):
            server = self.serve(lambda command: messages)
            with self.assertRaises(socket.timeout, msg=messages):
                self.client(server, timeout=0.3).command("#players")

    def test_processing_line_of_another_command(self):
        server = self.serve(lambda command: output("list", "#ban list"))
        with self.assertRaises(socket.timeout):
            self.client(server, timeout=0.3).command("#players")

    def test_unexpected_acknowledgement(self):
        for acknowledge in (lambda seq: bytes([rcon.COMMAND, seq + 1]),
                            lambda seq: bytes([rcon.COMMAND, seq]) + b"text",
                            lambda seq: b"\x07"):
            server = self.serve(lambda command: output("list"), acknowledge=acknowledge)
            with self.assertRaises(RconError):
                self.client(server).command("#players")

    def test_output_without_acknowledgement(self):
        server = self.serve(lambda command: output("list"), acknowledge=lambda seq: b"")
        with self.assertRaises(RconError):
            self.client(server).command("#players")

    def test_new_login_after_a_failure(self):
        commands = []

        def handler(command):
            commands.append(command)
            return [] if len(commands) == 1 else output("back")

        server = self.serve(handler)
        client = self.client(server, timeout=0.3)
        with self.assertRaises(socket.timeout):
            client.command("#players")
        self.assertEqual(client.command("#players"), "back")
        self.assertEqual(server.logins, 2)

    def test_new_login_after_a_long_silence(self):
        server = self.serve(lambda command: output("list"))
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
        self.server = FakeServer(lambda command: output(text) if command == "#players" else [])
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
        cfg = self.serve(HEADER + f"1 ; {UID_A} ; Jerry\n2 ; {UID_B} ; Hubert")
        self.assertEqual(self.query(cfg, 2), {"state": "ok", "count": 2, "max": 64, "list_state": "ok", "players": [
            {"uid": UID_A, "name": "Jerry"}, {"uid": UID_B, "name": "Hubert"}]})
        self.warning.assert_not_called()

    def test_nobody_connected(self):
        result = self.query(self.serve("not asked"), 0)
        self.assertEqual((result["players"], result["list_state"]), ([], "ok"))
        self.assertEqual(self.server.logins, 0)

    def test_list_shorter_than_the_count(self):
        result = self.query(self.serve(HEADER + f"1 ; {UID_A} ; Jerry"), 2)
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
        cfg = self.serve(HEADER + f"1 ; {UID_A} ; Jerry")
        self.assertEqual(self.query(cfg, 2)["list_state"], "rcon_mismatch")
        self.assertEqual(self.query(cfg, 1)["players"], [{"uid": UID_A, "name": "Jerry"}])
        self.assertEqual(self.server.logins, 1)

    def test_client_closed_when_the_server_stops(self):
        self.query(self.serve(HEADER + f"1 ; {UID_A} ; Jerry"), 1)
        self.assertIsNotNone(players._rcon["client"])
        self.assertEqual(players.get_players(False, {}), {"state": "offline"})
        self.assertIsNone(players._rcon["client"])


if __name__ == "__main__":
    unittest.main()
