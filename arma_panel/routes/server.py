"""Start, stop, restart and force stop the dedicated server."""

import time

from flask import Blueprint, jsonify

from ..i18n import t, tn
from ..log import logger
from ..security import csrf_protected, login_required
from ..services.process import force_stop, get_server_pid, start_server, stop_server

bp = Blueprint("server", __name__, url_prefix="/api")


@bp.post("/start")
@login_required
@csrf_protected
def start():
    if get_server_pid():
        return jsonify({"ok": False, "error": t("api.server_running")})
    try:
        start_server()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.post("/stop")
@login_required
@csrf_protected
def stop():
    pid = get_server_pid()
    if not pid:
        return jsonify({"ok": False, "error": t("api.server_not_running")})
    try:
        stop_server(pid)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.post("/restart")
@login_required
@csrf_protected
def restart():
    pid = get_server_pid()
    if pid:
        try:
            stop_server(pid)
            time.sleep(3)
        except Exception as e:
            return jsonify({"ok": False, "error": t("api.stop_failed", error=e)})
    try:
        start_server()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.post("/force-stop")
@login_required
@csrf_protected
def force_stop_server():
    """For a server that a normal stop doesn't reach: every server process
    gets SIGINT, then SIGKILL if it's still there (services/process.py)."""
    result = force_stop()
    if not result["found"]:
        return jsonify({"ok": False, "error": t("api.force_stop_none")})
    logger.warning("force stop: processes %s, killed %s, still running %s, not allowed %s",
                   result["found"], result["killed"], result["remaining"], result["denied"])
    if result["remaining"]:
        message = tn("api.force_stop_remaining", len(result["remaining"]), pids=_pids(result["remaining"]))
        if result["denied"]:
            message += tn("api.force_stop_denied", len(result["denied"]), pids=_pids(result["denied"]))
        return jsonify({"ok": False, "error": message})
    message = tn("api.force_stopped", len(result["found"]))
    if result["killed"]:
        message += tn("api.force_stop_killed", len(result["killed"]), pids=_pids(result["killed"]))
    if result["systemd"]:
        message += t("api.force_stop_systemd")
    return jsonify({"ok": True, "message": message})


def _pids(pids):
    return ", ".join(str(pid) for pid in pids)
