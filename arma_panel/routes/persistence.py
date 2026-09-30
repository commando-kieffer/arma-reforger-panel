"""Session persistence settings and save file management."""

from flask import Blueprint, jsonify, request

from .. import config
from ..i18n import t
from ..security import csrf_protected, login_required
from ..services.persistence import (
    flush_saves,
    get_persistence_block,
    persistence_enabled,
    scan_saves,
    set_persistence_block,
)
from ..services.process import get_server_pid
from ..services.server_config import read_config, write_config

bp = Blueprint("persistence", __name__, url_prefix="/api/persistence")


@bp.get("")
@login_required
def get_persistence():
    cfg = read_config()
    block = get_persistence_block(cfg) or {}
    saves = scan_saves()
    return jsonify({
        "enabled":          persistence_enabled(cfg),
        "autoSaveInterval": block.get("autoSaveInterval", 10),
        "hiveId":           block.get("hiveId", 1),
        "saves":            saves,
        "profile_dir":      config.PROFILE_DIR,
    })


@bp.post("")
@login_required
@csrf_protected
def update_persistence():
    data = request.get_json(silent=True) or {}
    cfg  = read_config()
    enabled = bool(data.get("enabled"))
    if enabled:
        block = get_persistence_block(cfg) or {}
        if "autoSaveInterval" in data:
            try:
                v = int(data["autoSaveInterval"])
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": t("api.autosave_not_int")})
            if not 0 <= v <= 60:
                return jsonify({"ok": False, "error": t("api.autosave_range")})
            block["autoSaveInterval"] = v
        else:
            block.setdefault("autoSaveInterval", 10)
        if "hiveId" in data:
            try:
                v = int(data["hiveId"])
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": t("api.hive_not_int")})
            if not 0 <= v <= 16383:
                return jsonify({"ok": False, "error": t("api.hive_range")})
            block["hiveId"] = v
        else:
            block.setdefault("hiveId", 1)
        set_persistence_block(cfg, block)
    else:
        set_persistence_block(cfg, None)
    try:
        write_config(cfg)
        return jsonify({
            "ok": True,
            "restart_required": get_server_pid() is not None,
            "enabled":           persistence_enabled(cfg),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.post("/flush")
@login_required
@csrf_protected
def flush():
    # Refuse to delete saves while the server is running — the game holds file
    # handles and may rewrite them mid-flush, which leaves us with partials.
    if get_server_pid():
        return jsonify({"ok": False, "error": t("api.stop_before_flush")})
    try:
        removed = flush_saves()
        return jsonify({"ok": True, "removed": removed, "saves": scan_saves()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
