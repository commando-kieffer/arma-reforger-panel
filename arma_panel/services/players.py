"""Player count and player list, read from the running game server, and
kicking a player.

The count comes from A2S. A2S doesn't give the names on Reforger, so when
config.json has an `rcon` block the list (player numbers, identity IDs and
names) is read over RCON instead. Kicking also goes through RCON, and needs
`"permission": "admin"` in that block.

The result is cached for a few seconds so several open panels don't multiply
the queries. A server that doesn't answer is reported as such, never as
"0 players", and a list that can't be trusted is left out.
"""

import threading
import time

from ..i18n import t
from ..log import logger
from . import a2s, rcon
from .server_config import ChangeRejected

CACHE_SECONDS = 5
DEFAULT_PORT = 17777

# After `#kick`: how long to wait for an output, then how long the player
# list is watched for the player to leave.
KICK_OUTPUT_WAIT = 1.0
KICK_CHECK_SECONDS = 5.0
KICK_CHECK_INTERVAL = 0.5

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


def rcon_can_kick(cfg):
    """Whether the rcon block allows kicking. The wiki doesn't say which
    permission applies when the key is left out, so only an explicit
    "admin" counts."""
    block = cfg.get("rcon")
    return isinstance(block, dict) and block.get("permission") == "admin"


def get_players(running, cfg):
    """Returns {"state": ...} where state is:
      offline         the server process isn't running (nothing is queried)
      not_configured  config.json has no usable a2s block
      no_answer       the query failed (server starting, A2S unreachable, bad answer)
      ok              with "count", "max", "players" and "list_state"

    With state "ok", "can_kick" says whether the rcon block allows kicking.
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
    can_kick = settings is not None and rcon_can_kick(cfg)
    key = (address, settings, can_kick)
    with _lock:
        if _cache["key"] == key and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["result"]
        result = _query(address, settings)
        if result["state"] == "ok":
            result["can_kick"] = can_kick
        _cache.update(key=key, at=time.monotonic(), result=result)
        return result


def kick(cfg, player_id, uid):
    """Kick player number `player_id`, once the list confirms the number
    still belongs to identity `uid` (numbers are reused when players leave
    and join). Returns the player's name. Raises ChangeRejected with a
    message ready to show.

    The server's answer to `#kick` isn't documented, so the kick only counts
    as done once the player is gone from `#players`.
    """
    settings = rcon_settings(cfg)
    if settings is None:
        raise ChangeRejected(t("api.kick_rcon_disabled"))
    if not rcon_can_kick(cfg):
        raise ChangeRejected(t("api.kick_needs_admin"))
    with _lock:
        _cache["key"] = None
        client = _client(settings)
        try:
            listed = rcon.parse_players(client.command(rcon.PLAYERS_COMMAND))
        except rcon.LoginRefused:
            raise ChangeRejected(t("api.kick_rcon_refused")) from None
        except (rcon.RconError, OSError):
            raise ChangeRejected(t("api.kick_rcon_failed")) from None
        target = next((p for p in listed
                       if p["id"] == player_id and p["uid"].lower() == str(uid).lower()), None)
        if target is None:
            raise ChangeRejected(t("api.kick_player_gone"))

        answer = None
        try:
            answer = client.command(rcon.KICK_COMMAND.format(player_id), output_wait=KICK_OUTPUT_WAIT)
        except (rcon.RconError, OSError) as e:
            logger.warning("no answer to #kick %d: %s", player_id, e)

        deadline = time.monotonic() + KICK_CHECK_SECONDS
        while time.monotonic() < deadline:
            time.sleep(KICK_CHECK_INTERVAL)
            try:
                listed = rcon.parse_players(client.command(rcon.PLAYERS_COMMAND))
            except (rcon.RconError, OSError):
                continue
            if not any(p["uid"].lower() == target["uid"].lower() for p in listed):
                logger.info("kicked player %d (%s, %s)", player_id, target["name"], target["uid"])
                return target["name"]
        logger.warning("player %d (%s) still connected after #kick; server answer: %r",
                       player_id, target["uid"], answer)
        raise ChangeRejected(t("api.kick_failed", answer=answer or "—"))


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
    address = settings[0]
    client = _client(settings)
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


def _client(settings):
    """The RCON client for `settings`, kept from one call to the next."""
    client = _rcon["client"]
    if client is None or (client.address, client.password) != settings:
        _close_rcon()
        client = _rcon["client"] = rcon.Client(*settings)
    return client


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
