"""Editing the basic server settings (name, scenario, passwords)."""

from flask import Blueprint, jsonify, request

from ..security import csrf_protected, login_required
from ..services.process import get_server_pid
from ..services.scenarios import all_scenarios_cached
from ..services.server_config import read_config, write_config

bp = Blueprint("server_config", __name__, url_prefix="/api")


@bp.post("/config")
@login_required
@csrf_protected
def update_config():
    data = request.get_json(silent=True) or {}
    cfg  = read_config()
    changed = False
    if "server_name" in data and data["server_name"].strip():
        cfg.setdefault("game", {})["name"] = data["server_name"].strip(); changed = True
    if "scenario_id" in data:
        sid = data["scenario_id"].strip()
        valid_ids = {m["id"] for m in all_scenarios_cached()}
        if sid not in valid_ids:
            return jsonify({"ok": False, "error": "Unknown scenario"})
        cfg.setdefault("game", {})["scenarioId"] = sid; changed = True
    if "password" in data:
        cfg.setdefault("game", {})["password"] = data["password"]; changed = True
    if "password_admin" in data and data["password_admin"].strip():
        cfg.setdefault("game", {})["passwordAdmin"] = data["password_admin"].strip(); changed = True
    if not changed:
        return jsonify({"ok": False, "error": "No changes"})
    try:
        write_config(cfg)
        return jsonify({"ok": True, "restart_required": get_server_pid() is not None})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
