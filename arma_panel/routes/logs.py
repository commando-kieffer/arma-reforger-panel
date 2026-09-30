"""Server console logs: the live tail and the past sessions."""

import os

from flask import Blueprint, abort, jsonify, request, send_file

from .. import config
from ..security import login_required
from ..services import logs

bp = Blueprint("logs", __name__, url_prefix="/api/logs")

MAX_TAIL_LINES = 1000


@bp.get("")
@login_required
def live_tail():
    try:
        n = min(max(int(request.args.get("lines", 100)), 1), MAX_TAIL_LINES)
    except ValueError:
        n = 100
    path = logs.get_latest_log()
    if not path:
        return jsonify({"lines": [], "path": None})
    try:
        return jsonify({"lines": logs.tail(path, n), "path": path})
    except Exception as e:
        return jsonify({"lines": [], "error": str(e)})


@bp.get("/sessions")
@login_required
def sessions():
    return jsonify({"sessions": logs.list_sessions(), "log_dir": config.LOG_DIR})


@bp.get("/sessions/<name>/download")
@login_required
def download_session(name):
    archive = logs.zip_session(name)
    if archive is None:
        abort(404)
    size = archive.seek(0, os.SEEK_END)
    archive.seek(0)
    response = send_file(archive, mimetype="application/zip", as_attachment=True,
                         download_name=f"{name}.zip", conditional=False, etag=False)
    # send_file only knows the size of paths and BytesIO objects.
    response.content_length = size
    return response
