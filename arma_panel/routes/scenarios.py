"""Rescanning installed addons for scenarios."""

from flask import Blueprint, jsonify

from ..security import csrf_protected, login_required
from ..services.scenarios import all_scenarios, count_by_source

bp = Blueprint("scenarios", __name__, url_prefix="/api/scenarios")


@bp.post("/rescan")
@login_required
@csrf_protected
def rescan():
    missions, diag = all_scenarios(force_rescan=True)
    return jsonify({
        "ok": True,
        "missions": missions,
        "missions_count": count_by_source(missions),
        "diag": diag,
    })
