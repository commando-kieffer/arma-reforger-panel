"""Minimal client for the Steam server query protocol (A2S).

Used to read the player count (A2S_INFO) and the player list (A2S_PLAYER)
from the game server. Protocol: https://developer.valvesoftware.com/wiki/Server_queries

Anything unexpected in an answer raises A2SError, so callers show the data as
unavailable instead of showing a list that might be wrong.
"""

import math
import socket
import struct

SIMPLE_HEADER = b"\xff\xff\xff\xff"
SPLIT_HEADER = b"\xfe\xff\xff\xff"

INFO_REQUEST = b"TSource Engine Query\x00"
PLAYER_REQUEST = b"U"
NO_CHALLENGE = b"\xff\xff\xff\xff"

CHALLENGE_REPLY = b"A"
INFO_REPLY = b"I"
PLAYER_REPLY = b"D"

DEFAULT_TIMEOUT = 2.0
MAX_SPLIT_PACKETS = 32
COMPRESSED_FLAG = 0x80000000


class A2SError(Exception):
    """The server answered something this client doesn't understand."""


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, n):
        if self.pos + n > len(self.data):
            raise A2SError("truncated answer")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def byte(self):
        return self.take(1)[0]

    def short(self):
        return struct.unpack("<h", self.take(2))[0]

    def long(self):
        return struct.unpack("<l", self.take(4))[0]

    def ulong(self):
        return struct.unpack("<L", self.take(4))[0]

    def float(self):
        return struct.unpack("<f", self.take(4))[0]

    def string(self):
        end = self.data.find(b"\x00", self.pos)
        if end < 0:
            raise A2SError("unterminated string")
        raw = self.data[self.pos:end]
        self.pos = end + 1
        return raw.decode("utf-8", errors="replace")

    def rest(self):
        return self.data[self.pos:]


def parse_info(payload):
    """Parse an A2S_INFO answer (without the 4-byte header)."""
    r = _Reader(payload)
    if r.take(1) != INFO_REPLY:
        raise A2SError("not an A2S_INFO answer")
    r.byte()                # protocol version
    name = r.string()
    map_name = r.string()
    r.string()              # folder
    r.string()              # game
    r.short()               # Steam app ID
    players = r.byte()
    max_players = r.byte()
    bots = r.byte()
    # The remaining fields (server type, OS, VAC, version, extra data) aren't needed.
    return {"name": name, "map": map_name, "players": players, "max_players": max_players, "bots": bots}


def parse_players(payload):
    """Parse an A2S_PLAYER answer (without the 4-byte header).

    The number of entries must match the announced count exactly; a short or
    padded answer is rejected rather than shown as a partial list.
    """
    r = _Reader(payload)
    if r.take(1) != PLAYER_REPLY:
        raise A2SError("not an A2S_PLAYER answer")
    count = r.byte()
    players = []
    for _ in range(count):
        r.byte()            # index, always 0 on some servers
        name = r.string().strip()
        r.long()            # score
        duration = r.float()
        players.append({
            "name": name,
            "duration": int(duration) if math.isfinite(duration) and duration >= 0 else None,
        })
    if r.rest():
        raise A2SError("unexpected data after the player list")
    return players


def query_info(address, timeout=DEFAULT_TIMEOUT):
    with _connect(address, timeout) as sock:
        answer = _request(sock, INFO_REQUEST)
        if answer[:1] == CHALLENGE_REPLY:
            answer = _request(sock, INFO_REQUEST + _challenge(answer))
        return parse_info(answer)


def query_players(address, timeout=DEFAULT_TIMEOUT):
    with _connect(address, timeout) as sock:
        answer = _request(sock, PLAYER_REQUEST + NO_CHALLENGE)
        if answer[:1] == CHALLENGE_REPLY:
            answer = _request(sock, PLAYER_REQUEST + _challenge(answer))
        return parse_players(answer)


def _connect(address, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    # A connected UDP socket only receives packets from the server, and an
    # unreachable port fails right away instead of waiting for the timeout.
    sock.connect(address)
    return sock


def _request(sock, payload):
    sock.send(SIMPLE_HEADER + payload)
    return _read_answer(sock)


def _challenge(answer):
    if len(answer) < 5:
        raise A2SError("malformed challenge")
    return answer[1:5]


def _read_answer(sock):
    packet = sock.recv(65535)
    if packet.startswith(SIMPLE_HEADER):
        return packet[4:]
    if packet.startswith(SPLIT_HEADER):
        return _read_split_answer(sock, packet)
    raise A2SError("unknown packet header")


def _read_split_answer(sock, packet):
    """Reassemble an answer split over several packets (Source engine format:
    header, answer ID, packet count, packet number, max packet size)."""
    parts = {}
    answer_id = total = None
    while True:
        r = _Reader(packet)
        if r.take(4) != SPLIT_HEADER:
            raise A2SError("unexpected packet in a split answer")
        packet_id = r.ulong()
        count = r.byte()
        number = r.byte()
        r.short()           # max packet size
        if packet_id & COMPRESSED_FLAG:
            raise A2SError("compressed answers are not supported")
        if answer_id is None:
            answer_id, total = packet_id, count
        if packet_id != answer_id or count != total or not 0 < total <= MAX_SPLIT_PACKETS:
            raise A2SError("inconsistent split answer")
        if number >= total or number in parts:
            raise A2SError("inconsistent split answer")
        parts[number] = r.rest()
        if len(parts) == total:
            break
        packet = sock.recv(65535)
    payload = b"".join(parts[i] for i in range(total))
    # The reassembled payload starts with its own simple header; if it doesn't,
    # the server uses a split format this client doesn't know.
    if not payload.startswith(SIMPLE_HEADER):
        raise A2SError("unknown split answer format")
    return payload[4:]
