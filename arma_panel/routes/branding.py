"""Banner logo and app icons: serving them, and replacing them from the panel."""

from flask import Blueprint, abort, jsonify, request, send_from_directory

from ..security import csrf_protected, login_required
from ..services import branding
from .common import attempt

bp = Blueprint("branding", __name__)


def _attempt(action):
    return attempt(action, write_failed="api.branding_write_failed")


@bp.get("/branding/<name>")
def image(name):
    # Public: the login page and the installed app need them too.
    found = branding.location(name)
    if found is None:
        abort(404)
    resp = send_from_directory(*found, mimetype="image/png")
    # An image can be replaced under the same URL: always revalidate.
    resp.cache_control.no_cache = True
    return resp


@bp.get("/api/branding")
@login_required
def state():
    return jsonify({"ok": True, "custom": branding.custom_groups()})


@bp.post("/api/branding/<group>")
@login_required
@csrf_protected
def upload(group):
    """multipart/form-data with one PNG per file of the group, each part
    named after its file (e.g. 'icon-192.png')."""
    files = {}
    for name in branding.GROUPS.get(group, ()):
        part = request.files.get(name)
        # One byte over the limit is enough to reject the file.
        files[name] = part.read(branding.FILE_MAX_BYTES + 1) if part else None
    _, error = _attempt(lambda: branding.save(group, files))
    if error:
        return error
    return jsonify({"ok": True})


@bp.post("/api/branding/<group>/reset")
@login_required
@csrf_protected
def reset(group):
    _, error = _attempt(lambda: branding.reset(group))
    if error:
        return error
    return jsonify({"ok": True})
