"""Session persistence settings and save file management."""

from flask import Blueprint, jsonify, request

from .. import config
from ..i18n import t
from ..security import csrf_protected, login_required
from ..services import config_fields
from ..services.config_fields import PERSISTENCE_FIELDS, FieldError
from ..services.persistence import MODES, flush_saves, persistence_mode, scan_saves, set_persistence_mode
from ..services.process import get_server_pid
from ..services.server_config import read_config
from .common import save_config

bp = Blueprint("persistence", __name__, url_prefix="/api/persistence")


@bp.get("")
@login_required
def get_persistence():
    cfg = read_config()
    return jsonify({
        "mode":        persistence_mode(cfg),
        **config_fields.form_values(cfg, PERSISTENCE_FIELDS),
        "saves":       scan_saves(),
        "profile_dir": config.PROFILE_DIR,
    })


@bp.post("")
@login_required
@csrf_protected
def update_persistence():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    if mode not in MODES:
        return jsonify({"ok": False, "error": t("api.invalid_persistence_mode")}), 400
    try:
        fields = config_fields.parse_form(PERSISTENCE_FIELDS, data) if mode == "custom" else {}
    except FieldError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    def change(cfg):
        set_persistence_mode(cfg, mode)
        config_fields.apply(cfg, PERSISTENCE_FIELDS, fields)
        return persistence_mode(cfg)

    new_mode, error = save_config(change)
    if error:
        return error
    return jsonify({
        "ok": True,
        "restart_required": get_server_pid() is not None,
        "mode":             new_mode,
    })


@bp.post("/flush")
@login_required
@csrf_protected
def flush():
    # Refuse to delete saves while the server is running — the game holds file
    # handles and may rewrite them mid-flush, which leaves us with partials.
    if get_server_pid():
        return jsonify({"ok": False, "error": t("api.stop_before_flush")})
    try:
        removed = flush_saves()
        return jsonify({"ok": True, "removed": removed, "saves": scan_saves()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
