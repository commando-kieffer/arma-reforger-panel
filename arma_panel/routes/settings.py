"""Panel settings, and the theme every page is rendered with."""

from flask import Blueprint, jsonify, request

from .. import themes
from ..security import csrf_protected, login_required
from ..services import panel_settings
from .common import attempt

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@bp.app_context_processor
def inject_theme():
    return {"theme": themes.BY_ID[panel_settings.load()["theme"]], "themes": themes.THEMES}


@bp.post("")
@login_required
@csrf_protected
def save_settings():
    # Any logged-in user for now; to be limited to admins once the panel has them.
    data = request.get_json(silent=True) or {}
    _, error = attempt(lambda: panel_settings.set_theme(data.get("theme")),
                       write_failed="api.settings_write_failed")
    if error:
        return error
    return jsonify({"ok": True})
