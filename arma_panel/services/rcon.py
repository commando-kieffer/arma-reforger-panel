"""Minimal client for the game server's RCON port (BattlEye RCon protocol).

Used to read the connected players with `#players` (their player number,
identity ID and name) and to kick one with `#kick <player number>`.
Protocol: https://www.battleye.com/downloads/BERConProtocol.txt
Commands: https://community.bistudio.com/wiki/Arma_Reforger:Server_Management
(`#kick` needs `"permission": "admin"` in the rcon block; `#players` works
with `monitor` too.)

The way Reforger answers a command isn't documented. As observed on a live
server, it acknowledges the command with an empty answer, then sends two
server messages: "Processing Command: <command>", and the output.

Anything else, in a packet or in the player list, raises RconError, so
callers show the list as unavailable instead of showing one that might be
wrong.
"""

import binascii
import re
import socket
import struct
import time

DEFAULT_PORT = 19999
DEFAULT_TIMEOUT = 2.0
# The server forgets a client that sent nothing for 45 seconds.
SESSION_SECONDS = 30

LOGIN = 0x00
COMMAND = 0x01
SERVER_MESSAGE = 0x02

PROCESSING_PREFIX = "Processing Command: "
PLAYERS_COMMAND = "#players"
PLAYERS_HEADER = "Players on server: [Player#] ; [Player UID] ; [Player Name]"
PLAYER_ROW_RE = re.compile(
    r"^(\d+) ; ([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}) ; ?(.*)$")
KICK_COMMAND = "#kick {}"


class RconError(Exception):
    """The server answered something this client doesn't understand."""


class LoginRefused(RconError):
    """The server rejected the password."""


def build_packet(payload):
    body = b"\xff" + payload
    return b"BE" + struct.pack("<L", binascii.crc32(body)) + body


def parse_packet(packet):
    """Payload of a packet, once its header and checksum have been checked."""
    if len(packet) < 8 or packet[:2] != b"BE" or packet[6:7] != b"\xff":
        raise RconError("unknown packet header")
    if struct.unpack("<L", packet[2:6])[0] != binascii.crc32(packet[6:]):
        raise RconError("wrong checksum")
    return packet[7:]


def parse_players(output):
    """Parse the output of `#players` into [{"id": ..., "uid": ..., "name": ...}],
    where "id" is the player number that `#kick` takes.

    Expected: the header line, then one "<number> ; <identity ID> ; <name>"
    line per player. Any other line rejects the whole output.
    """
    # Not splitlines(): it also splits on characters a player name may contain.
    lines = [line.strip() for line in output.split("\n")]
    lines = [line for line in lines if line]
    if not lines or lines.pop(0) != PLAYERS_HEADER:
        raise RconError("no player list header")
    players = []
    for line in lines:
        match = PLAYER_ROW_RE.match(line)
        if not match:
            raise RconError("unexpected line in the player list")
        players.append({"id": int(match.group(1)), "uid": match.group(2), "name": match.group(3)})
    return players


class Client:
    """One login on the RCON port, reused from one command to the next.

    The server keeps a slot (`rcon.maxClients`) for every client that logged
    in until it has been silent for a while, and a new socket is a new client.
    Keeping the socket open means the panel only ever takes one slot.
    """

    def __init__(self, address, password, timeout=DEFAULT_TIMEOUT):
        self.address = address
        self.password = password
        self.timeout = timeout
        # Server messages received since the last command that weren't part
        # of an output, such as "Logged In! Client ID: #0" after a login.
        self.messages = []
        self._sock = None
        self._sequence = 0
        self._last_sent = 0.0

    def command(self, text, output_wait=None):
        """Send a command and return its output.

        With `output_wait`, the command may have no output: when nothing
        follows the "Processing Command" message within that many seconds,
        "" is returned instead of raising a timeout.
        """
        if self._sock is not None and time.monotonic() - self._last_sent > SESSION_SECONDS:
            self.close()
        try:
            if self._sock is None:
                self._login()
            return self._command(text, output_wait)
        except (RconError, OSError):
            # Whatever went wrong, the next command starts from a new login.
            self.close()
            raise

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _login(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # A connected UDP socket only receives packets from the server, and an
        # unreachable port fails right away instead of waiting for the timeout.
        self._sock.connect(self.address)
        self._sequence = 0
        self.messages = []
        deadline = time.monotonic() + self.timeout
        self._send(bytes([LOGIN]) + self.password.encode("utf-8"))
        payload = self._receive(deadline)
        if payload[0] != LOGIN:
            raise RconError("unexpected packet during login")
        if payload[1:] != b"\x01":
            raise LoginRefused("the server refused the RCON password")

    def _command(self, text, output_wait):
        sequence = self._sequence
        self._sequence = (sequence + 1) % 256
        deadline = time.monotonic() + self.timeout
        self._send(bytes([COMMAND, sequence]) + text.encode("utf-8"))
        self.messages = []
        acknowledged = processing = False
        processed_at = 0.0
        while True:
            if processing and acknowledged and output_wait is not None:
                try:
                    payload = self._receive(min(deadline, processed_at + output_wait))
                except socket.timeout:
                    return ""
            else:
                payload = self._receive(deadline)
            if payload[0] == COMMAND:
                # The acknowledgement: the number of the command, nothing else.
                if acknowledged or payload[1:] != bytes([sequence]):
                    raise RconError("unexpected answer to the command")
                acknowledged = True
            elif payload[0] == SERVER_MESSAGE:
                message = self._server_message(payload)
                if processing:
                    if not acknowledged:
                        raise RconError("output received before the acknowledgement")
                    return message
                if message == PROCESSING_PREFIX + text:
                    processing = True
                    processed_at = time.monotonic()
                else:
                    self.messages.append(message)
            else:
                raise RconError("unexpected packet")

    def _server_message(self, payload):
        """Text of a server message. The server sends it again, then drops the
        client, unless it is acknowledged."""
        if len(payload) < 2:
            raise RconError("malformed server message")
        self._send(bytes([SERVER_MESSAGE, payload[1]]))
        return payload[2:].decode("utf-8", errors="replace")

    def _send(self, payload):
        self._sock.send(build_packet(payload))
        self._last_sent = time.monotonic()

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("no answer from the RCON port")
        self._sock.settimeout(remaining)
        return parse_packet(self._sock.recv(65535))
