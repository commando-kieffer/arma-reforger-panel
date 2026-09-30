"""Reforger session save/load.

The panel offers three modes (see the persistence section of the Bohemia wiki):
  default   no `persistence` block: the server's defaults apply, which
            already autosave in scenarios that support it
  custom    the `persistence` block under game.gameProperties
  disabled  game.gameProperties.missionHeader.m_eSaveTypes = 0, the documented
            way to turn saving off

`-loadSessionSave` is always passed at launch so any existing save loads on
start. Save files live under PROFILE_DIR/.save/ on Linux dedicated installs
(Conflict / Combat Ops layout). Subdirs underneath: game/ (world/session),
playersave/ (per-player), settings/.
"""

import os
import shutil

from .. import config
from ..i18n import t
from .server_config import ChangeRejected

MODES = ("default", "custom", "disabled")

SAVE_SUBDIRS = (".save", "save", "saves")

# Subdirs the flush button targets. `settings/` is intentionally preserved
# because it holds non-session config the server expects to regenerate from.
FLUSHABLE_SUBDIRS = ("game", "playersave")


def get_persistence_block(cfg):
    """Read the persistence block at its real schema location:
    `game.gameProperties.persistence`. Returns the block dict or None."""
    gp = (cfg.get("game") or {}).get("gameProperties") or {}
    block = gp.get("persistence")
    return block if isinstance(block, dict) else None


def set_persistence_block(cfg, block):
    """Write `block` (a dict) at game.gameProperties.persistence, or remove it
    if `block` is None. Also pops any legacy top-level `persistence` key — the
    1.6 server schema rejects it, so its presence is always a bug."""
    cfg.pop("persistence", None)
    gp = cfg.setdefault("game", {}).setdefault("gameProperties", {})
    if block is None:
        gp.pop("persistence", None)
    else:
        gp["persistence"] = block


def _game_properties(cfg):
    game = cfg.setdefault("game", {})
    props = game.setdefault("gameProperties", {}) if isinstance(game, dict) else None
    if not isinstance(props, dict):
        raise ChangeRejected(t("api.config_unexpected", path="game.gameProperties"))
    return props


def _saving_disabled(cfg):
    props = (cfg.get("game") or {}).get("gameProperties") or {}
    header = props.get("missionHeader")
    if not isinstance(header, dict):
        return False
    value = header.get("m_eSaveTypes")
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def persistence_mode(cfg):
    if _saving_disabled(cfg):
        return "disabled"
    return "custom" if get_persistence_block(cfg) is not None else "default"


def set_persistence_mode(cfg, mode):
    """Switch cfg to `mode`.

    Disabling keeps the `persistence` block, so going back to custom restores
    the previous settings. Leaving the disabled mode only removes the
    m_eSaveTypes value it set, and the missionHeader if nothing else is left
    in it, so other header overrides stay.
    """
    if mode == "disabled":
        header = _game_properties(cfg).setdefault("missionHeader", {})
        if not isinstance(header, dict):
            raise ChangeRejected(t("api.config_unexpected", path="game.gameProperties.missionHeader"))
        header["m_eSaveTypes"] = 0
        return

    if _saving_disabled(cfg):
        props = cfg["game"]["gameProperties"]
        del props["missionHeader"]["m_eSaveTypes"]
        if not props["missionHeader"]:
            del props["missionHeader"]
    if mode == "default":
        if get_persistence_block(cfg) is not None or "persistence" in cfg:
            set_persistence_block(cfg, None)
    elif get_persistence_block(cfg) is None:
        _game_properties(cfg)
        set_persistence_block(cfg, {})


def save_root():
    for sub in SAVE_SUBDIRS:
        p = os.path.join(config.PROFILE_DIR, sub)
        if os.path.isdir(p):
            return p
    return os.path.join(config.PROFILE_DIR, ".save")  # canonical Linux dedicated path


def _scan_dir(path):
    """Return {count, bytes, newest} for files under `path`, or zeros if absent."""
    if not os.path.isdir(path):
        return {"count": 0, "bytes": 0, "newest": None}
    count = 0
    total = 0
    newest = 0.0
    for dirpath, _dirs, files in os.walk(path):
        for fn in files:
            try:
                st = os.stat(os.path.join(dirpath, fn))
            except OSError:
                continue
            count += 1
            total += st.st_size
            if st.st_mtime > newest:
                newest = st.st_mtime
    return {"count": count, "bytes": total, "newest": newest or None}


def scan_saves():
    root = save_root()
    if not os.path.isdir(root):
        return {"path": root, "exists": False, "total": {"count": 0, "bytes": 0, "newest": None}, "buckets": {}}
    buckets = {name: _scan_dir(os.path.join(root, name)) for name in ("game", "playersave", "settings")}
    total_count = sum(b["count"] for b in buckets.values())
    total_bytes = sum(b["bytes"] for b in buckets.values())
    newest_vals = [b["newest"] for b in buckets.values() if b["newest"]]
    return {
        "path":    root,
        "exists":  True,
        "buckets": buckets,
        "total":   {
            "count":  total_count,
            "bytes":  total_bytes,
            "newest": max(newest_vals) if newest_vals else None,
        },
    }


def flush_saves():
    """Remove the contents of `.save/game/` and `.save/playersave/` (world
    session + per-player data). `.save/settings/` is left alone — it holds
    non-session config the server regenerates from. Returns the count of files
    deleted."""
    root = save_root()
    if not os.path.isdir(root):
        return 0
    removed = 0
    for sub in FLUSHABLE_SUBDIRS:
        bucket = os.path.join(root, sub)
        if not os.path.isdir(bucket):
            continue
        for name in os.listdir(bucket):
            full = os.path.join(bucket, name)
            try:
                if os.path.isdir(full) and not os.path.islink(full):
                    for _dp, _dn, files in os.walk(full):
                        removed += len(files)
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                    removed += 1
            except OSError:
                pass
    return removed
