"""Endpoints polled by the dashboard (status, metrics and players), and
kicking a player from the list."""

import time

from flask import Blueprint, jsonify, request

from ..i18n import t
from ..security import csrf_protected, ensure_csrf, login_required
from ..services.metrics import get_cpu_ram, get_system_ram
from ..services.players import get_players, kick
from ..services.process import format_uptime, get_process_uptime, get_server_pid
from ..services.scenarios import all_scenarios_cached, count_by_source, get_map_name
from ..services.server_config import ChangeRejected, ConfigError, load_config, read_config

bp = Blueprint("monitoring", __name__, url_prefix="/api")


@bp.get("/status")
@login_required
def status():
    pid = get_server_pid()
    try:
        cfg, config_error = load_config(), None
    except ConfigError as e:
        cfg, config_error = {}, str(e)
    cpu, ram = get_cpu_ram(pid) if pid else (0.0, 0.0)
    ram_used, ram_total = get_system_ram()
    uptime_sec = get_process_uptime(pid) if pid else 0
    missions = all_scenarios_cached()
    return jsonify({
        "running":        pid is not None,
        "pid":            pid,
        "map":            get_map_name(cfg) or t("status.unknown_mission"),
        "uptime":         format_uptime(uptime_sec) if pid else "—",
        "uptime_sec":     uptime_sec,
        "server_name":    cfg.get("game", {}).get("name", "—"),
        "ip":             cfg.get("publicAddress", "—"),
        "port":           cfg.get("publicPort", "—"),
        "scenario_id":    cfg.get("game", {}).get("scenarioId", ""),
        "missions":       missions,
        "missions_count": count_by_source(missions),
        "config_error":   config_error,
        "cpu":            cpu,
        "ram_process":    ram,
        "ram_used":       ram_used,
        "ram_total":      ram_total,
        "csrf":           ensure_csrf(),
    })


@bp.get("/metrics")
@login_required
def metrics():
    pid = get_server_pid()
    cpu, ram = get_cpu_ram(pid) if pid else (0.0, 0.0)
    ram_used, ram_total = get_system_ram()
    return jsonify({
        "cpu": cpu, "ram_process": ram,
        "ram_used": ram_used, "ram_total": ram_total,
        "running": pid is not None, "ts": int(time.time()),
    })


@bp.get("/players")
@login_required
def players():
    return jsonify(get_players(get_server_pid() is not None, read_config()))


@bp.post("/players/kick")
@login_required
@csrf_protected
def kick_player():
    """{"id": player number, "uid": identity ID}, both from the list shown.
    The player can join again (#kick isn't a ban)."""
    data = request.get_json(silent=True) or {}
    player_id, uid = data.get("id"), data.get("uid")
    if isinstance(player_id, bool) or not isinstance(player_id, int) or player_id < 0 or not isinstance(uid, str):
        return jsonify({"ok": False, "error": t("api.invalid_request")}), 400
    if get_server_pid() is None:
        return jsonify({"ok": False, "error": t("api.server_not_running")}), 409
    try:
        name = kick(load_config(), player_id, uid)
    except ConfigError as e:
        return jsonify({"ok": False, "error": t("api.config_unreadable", error=e)}), 500
    except ChangeRejected as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    return jsonify({"ok": True, "name": name})
