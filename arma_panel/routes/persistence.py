"""Session persistence settings and save file management. The settings
are saved with the other config.json sections (routes/server_config.py)."""

from flask import Blueprint, jsonify

from .. import config
from ..i18n import t
from ..security import csrf_protected, login_required
from ..services import config_fields
from ..services.config_fields import PERSISTENCE_FIELDS
from ..services.persistence import flush_saves, persistence_mode, scan_saves
from ..services.process import get_server_pid
from ..services.server_config import read_config

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
