"""Start, stop and restart the dedicated server."""

import time

from flask import Blueprint, jsonify

from ..i18n import t
from ..security import csrf_protected, login_required
from ..services.process import get_server_pid, start_server, stop_server

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
