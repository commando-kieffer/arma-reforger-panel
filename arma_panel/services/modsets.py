"""Mod sets: named mod lists stored as JSON files in the panel directory.

    modsets/<id>.json   {"name": "...", "mods": [...]}
    modsets/active      id of the set in use

The server only reads game.mods in config.json, when it starts. Using a set
copies its mods there, and changes to the set in use are written to both
files.
"""

import json
import os
import re
import secrets
import threading

from .. import config
from ..i18n import t
from ..log import logger
from .files import write_atomic
from .server_config import ChangeRejected, ConfigError, load_config, update_config

ID_RE = re.compile(r"^[0-9a-f]{8}$")
NAME_MAX_LENGTH = 60
ACTIVE_FILE = "active"

# Covers the set files and the active pointer. config.json's own lock is
# always taken after this one.
_lock = threading.Lock()


def overview():
    """All the sets, sorted by name, the id of the one in use, and whether
    config.json's mod list still matches it."""
    with _lock:
        sets, active = _load()
        try:
            differs = active is not None and _config_mods(load_config()) != sets[active]["mods"]
        except ConfigError:
            differs = False  # already reported by the config banner
    return {
        "sets": sorted(({"id": set_id, **data} for set_id, data in sets.items()),
                       key=lambda s: s["name"].casefold()),
        "active": active,
        "config_differs": differs,
    }


def create(name, copy_from=None):
    """Create a set, empty or with the mods of `copy_from`. Returns its id."""
    with _lock:
        sets, _active = _load()
        name = _check_name(name, sets)
        mods = list(_get(sets, copy_from)["mods"]) if copy_from is not None else []
        set_id = _new_id(sets)
        _write_set(set_id, {"name": name, "mods": mods})
        return set_id


def rename(set_id, name):
    with _lock:
        sets, _active = _load()
        data = _get(sets, set_id)
        _write_set(set_id, {**data, "name": _check_name(name, sets, ignore=set_id)})


def delete(set_id):
    with _lock:
        sets, active = _load()
        _get(sets, set_id)
        if set_id == active:
            raise ChangeRejected(t("api.modset_in_use"))
        os.remove(_path(set_id))


def activate(set_id):
    """Copy the set's mods to config.json and mark it as in use."""
    with _lock:
        sets, _active = _load()
        mods = _get(sets, set_id)["mods"]
        update_config(lambda cfg: _set_config_mods(cfg, mods))
        _write_active(set_id)


def change_mods(set_id, change):
    """Replace the set's mods with `change(mods)`, which returns (new mods,
    result) or raises ChangeRejected. Returns (result, whether the set is in
    use, i.e. config.json was updated too)."""
    with _lock:
        sets, active = _load()
        data = _get(sets, set_id)
        mods, result = change(list(data["mods"]))
        in_use = set_id == active
        if in_use:
            # config.json first: it's the file that refuses writes when it
            # was broken by hand.
            update_config(lambda cfg: _set_config_mods(cfg, mods))
        _write_set(set_id, {**data, "mods": mods})
        return result, in_use


def _load():
    """Return (sets by id, active id or None). When there is no set yet, one
    is created from the mods in config.json and marked as in use."""
    sets = _read_sets()
    if sets:
        return sets, _read_active(sets)
    mods = _config_mods(load_config())
    set_id = _new_id(sets)
    sets[set_id] = {"name": t("modsets.default_name"),
                    "mods": [m for m in mods if isinstance(m, dict)] if isinstance(mods, list) else []}
    _write_set(set_id, sets[set_id])
    _write_active(set_id)
    return sets, set_id


def _read_sets():
    try:
        names = os.listdir(config.MODSETS_DIR)
    except FileNotFoundError:
        return {}
    sets = {}
    for name in names:
        set_id, ext = os.path.splitext(name)
        if ext == ".json" and ID_RE.match(set_id):
            data = _read_set(set_id)
            if data:
                sets[set_id] = data
    return sets


def _read_set(set_id):
    # Files edited by hand that don't have the expected shape are skipped
    # rather than guessed at.
    try:
        with open(_path(set_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("ignoring mod set %s: %s", set_id, e)
        return None
    if (not isinstance(data, dict) or not isinstance(data.get("name"), str)
            or not isinstance(data.get("mods"), list)
            or not all(isinstance(m, dict) for m in data["mods"])):
        logger.warning("ignoring mod set %s: unexpected content", set_id)
        return None
    return {"name": data["name"], "mods": data["mods"]}


def _read_active(sets):
    try:
        with open(os.path.join(config.MODSETS_DIR, ACTIVE_FILE), encoding="utf-8") as f:
            set_id = f.read().strip()
    except FileNotFoundError:
        return None
    return set_id if set_id in sets else None


def _write_set(set_id, data):
    os.makedirs(config.MODSETS_DIR, exist_ok=True)
    write_atomic(_path(set_id), json.dumps(data, indent="\t", ensure_ascii=False) + "\n")


def _write_active(set_id):
    write_atomic(os.path.join(config.MODSETS_DIR, ACTIVE_FILE), set_id + "\n")


def _path(set_id):
    return os.path.join(config.MODSETS_DIR, f"{set_id}.json")


def _new_id(sets):
    while True:
        set_id = secrets.token_hex(4)
        # A file skipped as unreadable still exists; don't overwrite it.
        if set_id not in sets and not os.path.exists(_path(set_id)):
            return set_id


def _get(sets, set_id):
    if not isinstance(set_id, str) or set_id not in sets:
        raise ChangeRejected(t("api.modset_not_found"))
    return sets[set_id]


def _check_name(name, sets, ignore=None):
    if not isinstance(name, str):
        raise ChangeRejected(t("api.modset_name_required"))
    name = name.strip()
    if not name:
        raise ChangeRejected(t("api.modset_name_required"))
    if len(name) > NAME_MAX_LENGTH or not name.isprintable():
        raise ChangeRejected(t("api.modset_name_invalid", max=NAME_MAX_LENGTH))
    if any(set_id != ignore and data["name"].casefold() == name.casefold()
           for set_id, data in sets.items()):
        raise ChangeRejected(t("api.modset_name_taken", name=name))
    return name


def _config_mods(cfg):
    game = cfg.get("game")
    return game.get("mods", []) if isinstance(game, dict) else []


def _set_config_mods(cfg, mods):
    game = cfg.setdefault("game", {})
    if not isinstance(game, dict):
        raise ChangeRejected(t("api.config_unexpected", path="game"))
    game["mods"] = mods
