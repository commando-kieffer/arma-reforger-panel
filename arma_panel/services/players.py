"""Player count and player list, read from the running game server.

The count comes from A2S. A2S doesn't give the names on Reforger, so when
config.json has an `rcon` block the list (names and identity IDs) is read
over RCON instead.

The result is cached for a few seconds so several open panels don't multiply
the queries. A server that doesn't answer is reported as such, never as
"0 players", and a list that can't be trusted is left out.
"""

import threading
import time

from ..log import logger
from . import a2s, rcon

CACHE_SECONDS = 5
DEFAULT_PORT = 17777

_lock = threading.Lock()
_cache = {"key": None, "at": 0.0, "result": None}
_rcon = {"client": None, "problem": None}


def _local_address(block, default_port):
    """(host, port) of a config.json block with `address` and `port`, or None."""
    host = block.get("address")
    host = host.strip() if isinstance(host, str) else ""
    # The socket can be bound to all interfaces; the panel runs on the same host.
    if host in ("", "0.0.0.0"):
        host = "127.0.0.1"
    port = block.get("port", default_port)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return None
    return host, port


def a2s_address(cfg):
    """(host, port) to query, or None when config.json has no a2s block."""
    block = cfg.get("a2s")
    if not isinstance(block, dict):
        return None
    return _local_address(block, DEFAULT_PORT)


def rcon_settings(cfg):
    """((host, port), password) of the server's RCON port, or None when RCON
    isn't enabled in config.json. The server only starts RCON with a password."""
    block = cfg.get("rcon")
    if not isinstance(block, dict):
        return None
    password = block.get("password")
    if not isinstance(password, str) or not password:
        return None
    address = _local_address(block, rcon.DEFAULT_PORT)
    if address is None:
        return None
    return address, password


def get_players(running, cfg):
    """Returns {"state": ...} where state is:
      offline         the server process isn't running (nothing is queried)
      not_configured  config.json has no usable a2s block
      no_answer       the query failed (server starting, A2S unreachable, bad answer)
      ok              with "count", "max", "players" and "list_state"

    "players" is None when there is no list to show, and "list_state" says why:
      rcon_disabled   config.json has no usable rcon block
      rcon_no_answer  nothing answers on the RCON port
      rcon_refused    the server rejected the password
      rcon_bad_reply  the answer wasn't understood
      rcon_mismatch   the list doesn't have as many players as the A2S count
    """
    if not running:
        with _lock:
            _close_rcon()
        return {"state": "offline"}
    address = a2s_address(cfg)
    if address is None:
        return {"state": "not_configured"}
    settings = rcon_settings(cfg)
    key = (address, settings)
    with _lock:
        if _cache["key"] == key and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["result"]
        result = _query(address, settings)
        _cache.update(key=key, at=time.monotonic(), result=result)
        return result


def _query(address, settings):
    try:
        info = a2s.query_info(address)
    except (a2s.A2SError, OSError):
        return {"state": "no_answer"}
    result = {"state": "ok", "count": info["players"], "max": info["max_players"],
              "players": None, "list_state": "rcon_disabled"}
    if settings is not None:
        result["players"], result["list_state"] = _rcon_players(settings, info["players"])
        return result
    try:
        players = a2s.query_players(address)
    except (a2s.A2SError, OSError):
        return result
    # Entries without any name tell nothing useful: keep the count only.
    if players and not any(p["name"] for p in players):
        return result
    result["players"] = sorted(players, key=lambda p: p["duration"] or 0, reverse=True)
    result["list_state"] = "ok"
    # The count and the list come from two queries; show a count that matches the rows.
    result["count"] = len(players)
    return result


def _rcon_players(settings, count):
    """(players, "ok") read over RCON, or (None, reason) when there is no
    list that can be trusted. `count` is the number of players A2S reported."""
    # No need to ask who is connected when nobody is.
    if count == 0:
        return [], "ok"
    address, password = settings
    client = _rcon["client"]
    if client is None or (client.address, client.password) != settings:
        _close_rcon()
        client = _rcon["client"] = rcon.Client(address, password)
    reply = None
    try:
        reply = client.command(rcon.PLAYERS_COMMAND)
        players = rcon.parse_players(reply)
    except rcon.LoginRefused:
        return None, _problem("rcon_refused", "the server refused the RCON password of config.json")
    except rcon.RconError as e:
        return None, _problem("rcon_bad_reply", "%s (answer: %r, server messages: %r)"
                              % (e, reply if reply is None else reply[:1000], client.messages))
    except OSError as e:
        return None, _problem("rcon_no_answer", "no answer on RCON port %s:%d (%s)" % (*address, e))
    # The two counts come from the same server. When they differ, either a
    # player is joining or leaving, or the list isn't complete.
    if len(players) != count:
        return None, _problem("rcon_mismatch", "RCON lists %d players, A2S reports %d" % (len(players), count))
    _rcon["problem"] = None
    return players, "ok"


def _problem(reason, detail):
    """Log an RCON problem when it appears rather than at every poll."""
    if _rcon["problem"] != reason:
        _rcon["problem"] = reason
        logger.warning("player list unavailable: %s", detail)
    return reason


def _close_rcon():
    if _rcon["client"] is not None:
        _rcon["client"].close()
        _rcon["client"] = None
