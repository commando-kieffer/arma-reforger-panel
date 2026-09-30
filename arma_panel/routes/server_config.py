"""Editing the server settings: name, scenario, passwords and the
table-driven fields of services/config_fields.py."""

from flask import Blueprint, jsonify, request

from ..i18n import t
from ..security import csrf_protected, login_required
from ..services import config_fields
from ..services.config_fields import SERVER_FIELDS, FieldError
from ..services.process import get_server_pid
from ..services.scenarios import all_scenarios_cached
from ..services.server_config import ConfigError, load_config
from .common import save_config

bp = Blueprint("server_config", __name__, url_prefix="/api")

NAME_MAX_LENGTH = 100  # limit given by the Bohemia wiki


class InvalidValue(Exception):
    pass


@bp.get("/config")
@login_required
def get_config():
    """Current values for the configuration form. Loaded once by the page, not
    polled, so the passwords only travel when the form needs them."""
    try:
        cfg = load_config()
    except ConfigError as e:
        return jsonify({"ok": False, "error": t("api.config_unreadable", error=e)}), 500
    game = cfg.get("game", {})
    return jsonify({
        "ok":             True,
        "server_name":    game.get("name", ""),
        "scenario_id":    game.get("scenarioId", ""),
        "password":       game.get("password", ""),
        "password_admin": game.get("passwordAdmin", ""),
        **config_fields.form_values(cfg, SERVER_FIELDS),
    })


def _string(data, key):
    value = data[key]
    if not isinstance(value, str):
        raise InvalidValue(t("api.not_a_string", field=key))
    return value


def _game_changes(data):
    """Validate the request and return the game.* keys to set."""
    changes = {}
    if "server_name" in data:
        name = _string(data, "server_name").strip()
        if not name:
            raise InvalidValue(t("api.name_required"))
        if len(name) > NAME_MAX_LENGTH:
            raise InvalidValue(t("api.name_too_long", max=NAME_MAX_LENGTH))
        changes["name"] = name
    if "scenario_id" in data:
        sid = _string(data, "scenario_id").strip()
        if sid not in {m["id"] for m in all_scenarios_cached()}:
            raise InvalidValue(t("api.unknown_scenario"))
        changes["scenarioId"] = sid
    if "password" in data:
        changes["password"] = _string(data, "password")
    if "password_admin" in data:
        password = _string(data, "password_admin").strip()
        if not password:
            raise InvalidValue(t("api.admin_password_required"))
        # The server doesn't support spaces here (wiki, passwordAdmin).
        if any(c.isspace() for c in password):
            raise InvalidValue(t("api.admin_password_spaces"))
        changes["passwordAdmin"] = password
    return changes


@bp.post("/config")
@login_required
@csrf_protected
def update_config():
    data = request.get_json(silent=True) or {}
    try:
        changes = _game_changes(data)
        fields = config_fields.parse_form(SERVER_FIELDS, data)
    except (InvalidValue, FieldError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not changes and not fields:
        return jsonify({"ok": False, "error": t("api.no_changes")})

    def change(cfg):
        cfg.setdefault("game", {}).update(changes)
        written = config_fields.apply(cfg, SERVER_FIELDS, fields)
        # With crossPlatform set, the wiki recommends leaving supportedPlatforms
        # out: true then means every platform and false means PC only.
        if "cross_platform" in written:
            cfg["game"].pop("supportedPlatforms", None)

    _, error = save_config(change)
    if error:
        return error
    return jsonify({"ok": True, "restart_required": get_server_pid() is not None})
