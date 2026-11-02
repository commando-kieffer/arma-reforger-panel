"""Mods the server has downloaded, and removing them from disk."""

from flask import Blueprint, jsonify

from .. import config
from ..i18n import t
from ..log import logger
from ..security import csrf_protected, login_required
from ..services import modsets, workshop
from ..services.process import get_server_pid
from ..services.scenarios import refresh_scenarios
from ..services.server_config import ChangeRejected, ConfigError, load_config, read_config
from .common import attempt

bp = Blueprint("workshop", __name__, url_prefix="/api/workshop")


def _config_mod_ids(cfg):
    """Ids of the mods in config.json's game.mods: the ones the server loads."""
    game = cfg.get("game")
    mods = game.get("mods") if isinstance(game, dict) else None
    if not isinstance(mods, list):
        return set()
    return {str(m.get("modId", "")).strip().upper() for m in mods if isinstance(m, dict)}


def _sets_by_mod():
    """{mod id: [names of the mod sets holding it]}, empty when the sets
    can't be read."""
    try:
        sets = modsets.overview()["sets"]
    except (ConfigError, OSError):
        return {}
    found = {}
    for mod_set in sets:
        for mod in mod_set["mods"]:
            found.setdefault(str(mod.get("modId", "")).strip().upper(), []).append(mod_set["name"])
    return found


@bp.get("")
@login_required
def installed():
    in_config = _config_mod_ids(read_config())
    sets = _sets_by_mod()
    return jsonify({
        "ok": True,
        "dir": config.WORKSHOP_DIR,
        "running": get_server_pid() is not None,
        "mods": [{**mod, "in_use": mod["id"] in in_config, "sets": sets.get(mod["id"], [])}
                 for mod in workshop.installed_mods()],
    })


@bp.post("/<mod_id>/uninstall")
@login_required
@csrf_protected
def uninstall(mod_id):
    """Delete a downloaded mod. Refused while the server runs, since it may
    have the files loaded (dependencies included), and for a mod listed in
    config.json, which the server would download again at the next start."""
    if get_server_pid() is not None:
        return jsonify({"ok": False, "error": t("api.stop_before_uninstall")}), 409

    def remove():
        if mod_id.strip().upper() in _config_mod_ids(load_config()):
            raise ChangeRejected(t("api.workshop_mod_in_use"))
        return workshop.uninstall(mod_id)

    removed, error = attempt(remove, write_failed="api.workshop_remove_failed")
    if error:
        return error
    logger.info("removed mod %s from the workshop folder (%d folder(s))", mod_id, removed)
    # Its scenarios leave the scenario list.
    refresh_scenarios()
    return jsonify({"ok": True, "removed": removed})
