"""Player count and player list, read from the game server over A2S.

The result is cached for a few seconds so several open panels don't multiply
the queries. A server that doesn't answer is reported as such, never as
"0 players".
"""

import threading
import time

from . import a2s

CACHE_SECONDS = 5
DEFAULT_PORT = 17777

_lock = threading.Lock()
_cache = {"address": None, "at": 0.0, "result": None}


def a2s_address(cfg):
    """(host, port) to query, or None when config.json has no a2s block."""
    block = cfg.get("a2s")
    if not isinstance(block, dict):
        return None
    host = block.get("address")
    host = host.strip() if isinstance(host, str) else ""
    # The socket can be bound to all interfaces; the panel runs on the same host.
    if host in ("", "0.0.0.0"):
        host = "127.0.0.1"
    port = block.get("port", DEFAULT_PORT)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return None
    return host, port


def get_players(running, cfg):
    """Returns {"state": ...} where state is:
      offline         the server process isn't running (nothing is queried)
      not_configured  config.json has no usable a2s block
      no_answer       the query failed (server starting, A2S unreachable, bad answer)
      ok              with "count", "max" and "players" (None when the server
                      doesn't provide a usable list)
    """
    if not running:
        return {"state": "offline"}
    address = a2s_address(cfg)
    if address is None:
        return {"state": "not_configured"}
    with _lock:
        if _cache["address"] == address and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["result"]
        result = _query(address)
        _cache.update(address=address, at=time.monotonic(), result=result)
        return result


def _query(address):
    try:
        info = a2s.query_info(address)
    except (a2s.A2SError, OSError):
        return {"state": "no_answer"}
    result = {"state": "ok", "count": info["players"], "max": info["max_players"], "players": None}
    try:
        players = a2s.query_players(address)
    except (a2s.A2SError, OSError):
        return result
    # Entries without any name tell nothing useful: keep the count only.
    if players and not any(p["name"] for p in players):
        return result
    result["players"] = sorted(players, key=lambda p: p["duration"] or 0, reverse=True)
    # The count and the list come from two queries; show a count that matches the rows.
    result["count"] = len(players)
    return result
