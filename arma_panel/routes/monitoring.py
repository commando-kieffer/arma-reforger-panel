"""Read-only endpoints polled by the dashboard: status, metrics and logs."""

import time

from flask import Blueprint, jsonify, request

from ..security import ensure_csrf, login_required
from ..services import logs
from ..services.metrics import get_cpu_ram, get_system_ram
from ..services.process import format_uptime, get_process_uptime, get_server_pid
from ..services.scenarios import all_scenarios_cached, count_by_source, get_map_name
from ..services.server_config import read_config

bp = Blueprint("monitoring", __name__, url_prefix="/api")


@bp.get("/status")
@login_required
def status():
    pid = get_server_pid()
    cfg = read_config()
    cpu, ram = get_cpu_ram(pid) if pid else (0.0, 0.0)
    ram_used, ram_total = get_system_ram()
    uptime_sec = get_process_uptime(pid) if pid else 0
    missions = all_scenarios_cached()
    return jsonify({
        "running":        pid is not None,
        "pid":            pid,
        "map":            get_map_name(cfg),
        "players":        0,
        "uptime":         format_uptime(uptime_sec) if pid else "—",
        "uptime_sec":     uptime_sec,
        "server_name":    cfg.get("game", {}).get("name", "—"),
        "ip":             cfg.get("publicAddress", "—"),
        "port":           cfg.get("publicPort", "—"),
        "scenario_id":    cfg.get("game", {}).get("scenarioId", ""),
        "missions":       missions,
        "missions_count": count_by_source(missions),
        "password":       cfg.get("game", {}).get("password", ""),
        "password_admin": cfg.get("game", {}).get("passwordAdmin", ""),
        "cpu":            cpu,
        "ram_process":    ram,
        "ram_used":       ram_used,
        "ram_total":      ram_total,
        "mods":           cfg.get("game", {}).get("mods", []),
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


@bp.get("/logs")
@login_required
def server_logs():
    n = int(request.args.get("lines", 100))
    path = logs.get_latest_log()
    if not path:
        return jsonify({"lines": [], "path": None})
    try:
        return jsonify({"lines": logs.tail(path, n), "path": path})
    except Exception as e:
        return jsonify({"lines": [], "error": str(e)})
