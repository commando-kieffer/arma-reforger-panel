"""Theme stylesheets, and uploading, downloading and deleting themes."""

import io
import os

from flask import Blueprint, abort, jsonify, request, send_file, send_from_directory

from ..i18n import t
from ..security import csrf_protected, login_required
from ..services import panel_settings, themes
from ..services.server_config import ChangeRejected
from .common import attempt

bp = Blueprint("themes", __name__)


def _attempt(action):
    return attempt(action, write_failed="api.theme_write_failed")


@bp.get("/themes/<theme_id>/<name>")
def stylesheet(theme_id, name):
    # Public: the login page needs it too.
    theme = themes.get(theme_id)
    if theme is None or name not in themes.STYLESHEETS:
        abort(404)
    resp = send_from_directory(theme.path, name, mimetype="text/css")
    # A custom theme can be replaced under the same URL: always revalidate.
    resp.cache_control.no_cache = True
    return resp


@bp.get("/api/themes")
@login_required
def list_themes():
    return jsonify({
        "ok": True,
        "themes": [{"id": theme.id, "name": theme.name, "custom": theme.custom}
                   for theme in themes.all_themes()],
        "active": panel_settings.load()["theme"],
    })


@bp.post("/api/themes")
@login_required
@csrf_protected
def upload_theme():
    """multipart/form-data with 'name', one file part per stylesheet ('base',
    'login', 'panel'), and 'replace' set to 1 to replace the custom theme
    already holding that name."""
    stylesheets = {}
    for file in themes.STYLESHEETS:
        part = request.files.get(os.path.splitext(file)[0])
        # One byte over the limit is enough to reject the file.
        stylesheets[file] = part.read(themes.STYLESHEET_MAX_BYTES + 1) if part else None
    try:
        theme_id, error = _attempt(lambda: themes.save(
            request.form.get("name"), stylesheets, replace=request.form.get("replace") == "1"))
    except themes.NameTaken as e:
        return jsonify({"ok": False, "error": str(e), "exists": True}), 409
    if error:
        return error
    return jsonify({"ok": True, "id": theme_id})


@bp.get("/api/themes/<theme_id>/download")
@login_required
def download_theme(theme_id):
    result, error = _attempt(lambda: themes.archive(theme_id))
    if error:
        return error
    file_name, data = result
    return send_file(io.BytesIO(data), mimetype="application/zip",
                     as_attachment=True, download_name=file_name)


@bp.post("/api/themes/<theme_id>/delete")
@login_required
@csrf_protected
def delete_theme(theme_id):
    def delete():
        if panel_settings.load()["theme"] == theme_id:
            raise ChangeRejected(t("api.theme_in_use"))
        themes.delete(theme_id)

    _, error = _attempt(delete)
    if error:
        return error
    return jsonify({"ok": True})
