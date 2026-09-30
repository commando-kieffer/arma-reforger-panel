"""Managing the server's mod list."""

import json

from flask import Blueprint, jsonify, request

from ..i18n import t, tn
from ..security import csrf_protected, login_required
from ..services.mods import collect_import_entries, merge_mods, normalize_mod_entry
from ..services.process import get_server_pid
from ..services.server_config import read_config, write_config

bp = Blueprint("mods", __name__, url_prefix="/api/mods")


@bp.post("/add")
@login_required
@csrf_protected
def add_mod():
    data = request.get_json(silent=True) or {}
    norm = normalize_mod_entry({"modId": data.get("modId",""), "name": data.get("name",""), "version": data.get("version","")})
    if not norm:
        return jsonify({"ok": False, "error": t("api.invalid_mod_entry")})
    if "name" not in norm:
        return jsonify({"ok": False, "error": t("api.mod_name_required")})
    cfg  = read_config()
    mods = cfg.setdefault("game", {}).setdefault("mods", [])
    if any(m.get("modId", "").upper() == norm["modId"] for m in mods):
        return jsonify({"ok": False, "error": t("api.mod_exists")})
    mods.append(norm)
    try:
        write_config(cfg)
        return jsonify({"ok": True, "restart_required": get_server_pid() is not None, "mods": mods})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


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


@bp.post("/import")
@login_required
@csrf_protected
def import_mods():
    """Bulk-import mods. Accepts either:
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

    cfg = read_config()
    g   = cfg.setdefault("game", {})

    if mode == "merge":
        g["mods"], added = merge_mods(g.get("mods", []), valid)
        msg = t("api.import_merged", added=added, present=len(valid) - added)
    else:
        g["mods"] = valid
        msg = tn("api.import_replaced", len(valid))

    try:
        write_config(cfg)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({
        "ok": True,
        "message": msg,
        "imported": len(valid),
        "skipped": skipped,
        "mods": g["mods"],
        "restart_required": get_server_pid() is not None,
    })


@bp.post("/remove")
@login_required
@csrf_protected
def remove_mod():
    data   = request.get_json(silent=True) or {}
    mod_id = data.get("modId", "").strip().upper()
    if not mod_id:
        return jsonify({"ok": False, "error": t("api.missing_mod_id")})
    cfg  = read_config()
    mods = cfg.get("game", {}).get("mods", [])
    new  = [m for m in mods if str(m.get("modId", "")).upper() != mod_id]
    if len(new) == len(mods):
        return jsonify({"ok": False, "error": t("api.mod_not_found")})
    cfg.setdefault("game", {})["mods"] = new
    try:
        write_config(cfg)
        return jsonify({"ok": True, "restart_required": get_server_pid() is not None, "mods": new})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
