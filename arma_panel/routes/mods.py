"""Mod sets and the mods in each of them."""

import json

from flask import Blueprint, jsonify, request

from ..i18n import t, tn
from ..security import csrf_protected, login_required
from ..services import modsets
from ..services.mods import collect_import_entries, fill_versions, merge_mods, normalize_mod_entry
from ..services.process import get_server_pid
from ..services.server_config import ChangeRejected
from ..services.workshop import installed_versions
from .common import attempt

bp = Blueprint("mods", __name__, url_prefix="/api/modsets")


def _attempt(action):
    return attempt(action, write_failed="api.modset_write_failed")


@bp.get("")
@login_required
def overview():
    result, error = _attempt(modsets.overview)
    if error:
        return error
    return jsonify({"ok": True, **result})


@bp.post("")
@login_required
@csrf_protected
def create_set():
    data = request.get_json(silent=True) or {}
    set_id, error = _attempt(lambda: modsets.create(data.get("name"), data.get("copy_from")))
    if error:
        return error
    return jsonify({"ok": True, "id": set_id})


@bp.post("/<set_id>/rename")
@login_required
@csrf_protected
def rename_set(set_id):
    data = request.get_json(silent=True) or {}
    _, error = _attempt(lambda: modsets.rename(set_id, data.get("name")))
    if error:
        return error
    return jsonify({"ok": True})


@bp.post("/<set_id>/delete")
@login_required
@csrf_protected
def delete_set(set_id):
    _, error = _attempt(lambda: modsets.delete(set_id))
    if error:
        return error
    return jsonify({"ok": True})


@bp.post("/<set_id>/activate")
@login_required
@csrf_protected
def activate_set(set_id):
    _, error = _attempt(lambda: modsets.activate(set_id))
    if error:
        return error
    return jsonify({"ok": True, "restart_required": get_server_pid() is not None})


@bp.get("/<set_id>/export")
@login_required
def export_set(set_id):
    """The set's mods in the import format. Mods that don't name a version
    get the one the server has downloaded, when it is known."""
    data, error = _attempt(lambda: modsets.get(set_id))
    if error:
        return error
    mods, missing = fill_versions(data["mods"], installed_versions())
    return jsonify({
        "ok": True,
        "name": data["name"],
        "mods": mods,
        "unversioned": [m.get("name") or m.get("modId") for m in missing],
    })


def _restart_required(in_use):
    # Only the set in use is in config.json; editing another one doesn't
    # concern the server.
    return in_use and get_server_pid() is not None


@bp.post("/<set_id>/mods/add")
@login_required
@csrf_protected
def add_mod(set_id):
    data = request.get_json(silent=True) or {}
    norm = normalize_mod_entry({"modId": data.get("modId",""), "name": data.get("name",""), "version": data.get("version","")})
    if not norm:
        return jsonify({"ok": False, "error": t("api.invalid_mod_entry")})
    if "name" not in norm:
        return jsonify({"ok": False, "error": t("api.mod_name_required")})

    def add(mods):
        if any(str(m.get("modId", "")).upper() == norm["modId"] for m in mods):
            raise ChangeRejected(t("api.mod_exists"))
        return mods + [norm], None

    outcome, error = _attempt(lambda: modsets.change_mods(set_id, add))
    if error:
        return error
    _, in_use = outcome
    return jsonify({"ok": True, "restart_required": _restart_required(in_use)})


def _read_import_request():
    """Return (raw JSON text or None, mode) from either an uploaded file or a
    JSON body."""
    if request.files and "file" in request.files:
        f = request.files["file"]
        raw = f.read().decode("utf-8")  # UnicodeDecodeError handled by the caller
        mode = (request.form.get("mode") or "replace").strip().lower()
        return raw, mode
    body = request.get_json(silent=True) or {}
    payload = body.get("payload")
    raw = None
    if isinstance(payload, list):
        raw = json.dumps(payload)
    elif isinstance(payload, str):
        raw = payload
    mode = (body.get("mode") or "replace").strip().lower()
    return raw, mode


@bp.post("/<set_id>/mods/import")
@login_required
@csrf_protected
def import_mods(set_id):
    """Bulk-import mods into a set. Accepts either:
       - multipart/form-data with a 'file' part containing a JSON array, plus
         form fields 'mode' (replace|merge) and '_csrf'.
       - application/json with {payload: <text or array>, mode, _csrf}.
    """
    try:
        raw, mode = _read_import_request()
    except UnicodeDecodeError:
        return jsonify({"ok": False, "error": t("api.file_not_utf8")}), 400

    if mode not in ("replace", "merge"):
        return jsonify({"ok": False, "error": t("api.invalid_mode")}), 400
    if not raw or not raw.strip():
        return jsonify({"ok": False, "error": t("api.empty_payload")}), 400

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"ok": False, "error": t("api.invalid_json", reason=e.msg, line=e.lineno, col=e.colno)}), 400
    if not isinstance(data, list):
        return jsonify({"ok": False, "error": t("api.not_an_array")}), 400

    valid, skipped_entries = collect_import_entries(data)
    skipped = [
        t("api.skipped_duplicate", position=pos, mod_id=mod_id) if mod_id
        else t("api.skipped_invalid", position=pos)
        for pos, mod_id in skipped_entries
    ]

    def import_into(mods):
        if mode == "merge":
            merged, added = merge_mods(mods, valid)
            return merged, t("api.import_merged", added=added, present=len(valid) - added)
        return valid, tn("api.import_replaced", len(valid))

    outcome, error = _attempt(lambda: modsets.change_mods(set_id, import_into))
    if error:
        return error
    msg, in_use = outcome
    return jsonify({
        "ok": True,
        "message": msg,
        "imported": len(valid),
        "skipped": skipped,
        "restart_required": _restart_required(in_use),
    })


@bp.post("/<set_id>/mods/remove")
@login_required
@csrf_protected
def remove_mod(set_id):
    data   = request.get_json(silent=True) or {}
    mod_id = str(data.get("modId", "")).strip().upper()
    if not mod_id:
        return jsonify({"ok": False, "error": t("api.missing_mod_id")})

    def remove(mods):
        kept = [m for m in mods if str(m.get("modId", "")).upper() != mod_id]
        if len(kept) == len(mods):
            raise ChangeRejected(t("api.mod_not_found"))
        return kept, None

    outcome, error = _attempt(lambda: modsets.change_mods(set_id, remove))
    if error:
        return error
    _, in_use = outcome
    return jsonify({"ok": True, "restart_required": _restart_required(in_use)})
