"""Checks run on a config.json written by hand, before it is saved.

The rules come from the Bohemia wiki (Arma_Reforger:Server_Config): the type
and range of each documented key, and the requirements it states, such as an
RCON password of at least 3 characters without spaces. Breaking one of them
is an error and the file isn't saved.

Keys the wiki doesn't document are only warned about: they can come from a
newer server version or from a mod (ACE settings in missionHeader, for
example), and the panel can't tell them from a typo. The server log has the
final word once it starts.
"""

import json
from dataclasses import dataclass

from ..i18n import t
from .mods import normalize_mod_entry

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Value:
    kind: str                # "string", "int", "bool", "object", "array" or "any"
    ranges: tuple = ()       # allowed (low, high) ranges for "int"; high None means no limit
    max_length: int = None   # for "string"
    choices: tuple = ()      # allowed values for "string", or for the items of an "array"
    items: str = None        # kind of the items of an "array"
    no_spaces: bool = False  # for "string"
    min_length: int = 0      # for "string"
    keys: dict = None        # documented keys of an "object"; None accepts any key
    required: tuple = ()     # keys an "object" must have
    any_of: tuple = ()       # other kinds accepted


def _obj(keys=None, required=()):
    return Value("object", keys=keys, required=required)


STRING = Value("string")
BOOL = Value("bool")
INT = Value("int")
PORT = Value("int", ranges=((1, 65535),))

GAME_PROPERTIES = _obj({
    "serverMaxViewDistance": Value("int", ranges=((500, 10000),)),
    "serverMinGrassDistance": Value("int", ranges=((0, 0), (50, 150))),
    "fastValidation": BOOL,
    "networkViewDistance": Value("int", ranges=((500, 5000),)),
    "battlEye": BOOL,
    "disableThirdPerson": BOOL,
    "VONDisableUI": BOOL,
    "VONDisableDirectSpeechUI": BOOL,
    "VONCanTransmitCrossFaction": BOOL,
    # Scenario and mod settings (ACE, for example): their content isn't checked.
    "missionHeader": _obj(),
    "persistence": _obj({
        "autoSaveInterval": Value("int", ranges=((0, 60),)),
        "saveRetention": Value("int", ranges=((1, 128),)),
        "keepSessionSave": BOOL,
        "hiveId": Value("int", ranges=((0, 16383),)),
        "databases": Value("any"),
        "storages": Value("any"),
    }),
})

SCHEMA = _obj({
    "bindAddress": STRING,
    "bindPort": PORT,
    "publicAddress": STRING,
    "publicPort": PORT,
    "a2s": _obj({"address": STRING, "port": PORT}, required=("address",)),
    "rcon": _obj({
        "address": STRING,
        "port": PORT,
        "password": Value("string", min_length=3, no_spaces=True),
        "maxClients": Value("int", ranges=((1, 16),)),
        "permission": Value("string", choices=("admin", "monitor")),
        "blacklist": Value("array", items="string"),
        "whitelist": Value("array", items="string"),
    }, required=("address", "password")),
    "game": _obj({
        "name": Value("string", max_length=100),
        "password": STRING,
        "passwordAdmin": Value("string", no_spaces=True),
        "admins": Value("array", items="string"),
        "scenarioId": STRING,
        "maxPlayers": Value("int", ranges=((1, 128),)),
        "visible": BOOL,
        "crossPlatform": BOOL,
        "supportedPlatforms": Value("array", items="string",
                                    choices=("PLATFORM_PC", "PLATFORM_XBL", "PLATFORM_PSN")),
        "gameProperties": GAME_PROPERTIES,
        "modsRequiredByDefault": BOOL,
        "mods": Value("array", items="object"),
    }, required=("scenarioId",)),
    "operating": _obj({
        "lobbyPlayerSynchronise": BOOL,
        "disableCrashReporter": BOOL,
        "disableNavmeshStreaming": Value("array", items="string", any_of=("bool",)),
        "disableServerShutdown": BOOL,
        "disableAI": BOOL,
        "playerSaveTime": INT,
        "aiLimit": INT,
        "slotReservationTimeout": Value("int", ranges=((5, 300),)),
        "joinQueue": _obj({"maxSize": Value("int", ranges=((0, 50),))}),
    }),
}, required=("game",))

DEFAULT_GAME_PORT = 2001
DEFAULT_A2S_PORT = 17777
DEFAULT_RCON_PORT = 19999


class _DuplicateKey(ValueError):
    pass


def check(text, scenario_ids=None):
    """Return the problems found in `text`: [{"level", "path", "message"}],
    errors first. `scenario_ids`, when given, are the scenarios the panel
    knows; another scenarioId is a warning."""
    try:
        cfg = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except _DuplicateKey as e:
        return [_problem(ERROR, "", t("check.duplicate_key", name=str(e)))]
    except json.JSONDecodeError as e:
        return [_problem(ERROR, "", t("check.syntax", line=e.lineno, col=e.colno, reason=e.msg))]
    except ValueError as e:
        return [_problem(ERROR, "", t("check.syntax_value", value=str(e)))]
    if not isinstance(cfg, dict):
        return [_problem(ERROR, "", t("check.not_an_object"))]

    problems = []
    _check_value(cfg, SCHEMA, (), problems)
    _check_mods(cfg, problems)
    _check_ports(cfg, problems)
    game = cfg.get("game")
    scenario = game.get("scenarioId") if isinstance(game, dict) else None
    if scenario_ids is not None and isinstance(scenario, str) and scenario not in scenario_ids:
        problems.append(_problem(WARNING, "game.scenarioId", t("check.unknown_scenario")))
    return sorted(problems, key=lambda p: p["level"] != ERROR)


def has_errors(problems):
    return any(p["level"] == ERROR for p in problems)


def _no_duplicates(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen.add(key)
    return dict(pairs)


def _no_constant(name):
    # NaN and Infinity aren't JSON, though Python accepts them by default.
    raise ValueError(name)


def _problem(level, path, message):
    return {"level": level, "path": path, "message": message}


def _path(parts):
    return ".".join(str(p) for p in parts)


def _kind_of(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "null"


def _check_value(value, spec, path, problems):
    kind = _kind_of(value)
    if spec.kind == "any":
        return
    if kind != spec.kind:
        if kind in spec.any_of:
            return
        problems.append(_problem(ERROR, _path(path), t("check.wrong_type", expected=t("check.kind_" + spec.kind))))
        return
    if kind == "object":
        _check_object(value, spec, path, problems)
    elif kind == "array":
        _check_array(value, spec, path, problems)
    elif kind == "int" and spec.ranges:
        if not any(low <= value and (high is None or value <= high) for low, high in spec.ranges):
            problems.append(_problem(ERROR, _path(path), t("check.out_of_range", allowed=_describe(spec.ranges))))
    elif kind == "string":
        _check_string(value, spec, path, problems)


def _check_object(value, spec, path, problems):
    for key in spec.required:
        if key not in value:
            problems.append(_problem(ERROR, _path(path + (key,)), t("check.required")))
    if spec.keys is None:
        return
    for key, item in value.items():
        if key in spec.keys:
            _check_value(item, spec.keys[key], path + (key,), problems)
        else:
            problems.append(_problem(WARNING, _path(path + (key,)), t("check.unknown_key")))


def _check_array(value, spec, path, problems):
    for i, item in enumerate(value):
        if spec.items and _kind_of(item) != spec.items:
            problems.append(_problem(ERROR, _path(path + (i,)), t("check.wrong_type", expected=t("check.kind_" + spec.items))))
        elif spec.choices and item not in spec.choices:
            problems.append(_problem(ERROR, _path(path + (i,)), t("check.not_a_choice", allowed=", ".join(spec.choices))))


def _check_string(value, spec, path, problems):
    if spec.choices and value not in spec.choices:
        problems.append(_problem(ERROR, _path(path), t("check.not_a_choice", allowed=", ".join(spec.choices))))
    if spec.max_length is not None and len(value) > spec.max_length:
        problems.append(_problem(ERROR, _path(path), t("check.too_long", max=spec.max_length)))
    if len(value) < spec.min_length:
        problems.append(_problem(ERROR, _path(path), t("check.too_short", min=spec.min_length)))
    if spec.no_spaces and any(c.isspace() for c in value):
        problems.append(_problem(ERROR, _path(path), t("check.spaces")))


def _describe(ranges):
    parts = []
    for low, high in ranges:
        if high is None:
            parts.append(f"≥ {low}")
        elif low == high:
            parts.append(str(low))
        else:
            parts.append(f"{low}–{high}")
    return ", ".join(parts)


def _check_mods(cfg, problems):
    game = cfg.get("game")
    mods = game.get("mods") if isinstance(game, dict) else None
    if not isinstance(mods, list):
        return
    seen = set()
    for i, entry in enumerate(mods):
        if not isinstance(entry, dict):
            continue  # already reported as a wrong type
        path = f"game.mods.{i}"
        normalized = normalize_mod_entry(entry)
        if normalized is None:
            problems.append(_problem(ERROR, path, t("check.invalid_mod")))
            continue
        if normalized["modId"] in seen:
            problems.append(_problem(WARNING, path, t("check.duplicate_mod", mod_id=normalized["modId"])))
        seen.add(normalized["modId"])


def _port(block, key, default):
    value = block.get(key, default) if isinstance(block, dict) else default
    return value if _kind_of(value) == "int" else None


def _check_ports(cfg, problems):
    """The game, A2S and RCON sockets are all UDP: two on the same port
    can't both open."""
    game_port = _port(cfg, "bindPort", None) or _port(cfg, "publicPort", DEFAULT_GAME_PORT)
    sockets = [("bindPort" if "bindPort" in cfg else "publicPort", game_port)]
    if isinstance(cfg.get("a2s"), dict):
        sockets.append(("a2s.port", _port(cfg["a2s"], "port", DEFAULT_A2S_PORT)))
    if isinstance(cfg.get("rcon"), dict):
        sockets.append(("rcon.port", _port(cfg["rcon"], "port", DEFAULT_RCON_PORT)))
    for i, (path, port) in enumerate(sockets):
        for other_path, other_port in sockets[:i]:
            if port is not None and port == other_port:
                problems.append(_problem(ERROR, path, t("check.port_taken", port=port, other=other_path)))
