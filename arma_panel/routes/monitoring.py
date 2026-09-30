"""Read-only endpoints polled by the dashboard: status and metrics."""

import time

from flask import Blueprint, jsonify

from ..i18n import t
from ..security import ensure_csrf, login_required
from ..services.metrics import get_cpu_ram, get_system_ram
from ..services.process import format_uptime, get_process_uptime, get_server_pid
from ..services.scenarios import all_scenarios_cached, count_by_source, get_map_name
from ..services.server_config import ConfigError, load_config

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
        "players":        0,
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
