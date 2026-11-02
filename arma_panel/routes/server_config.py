"""Editing config.json: the forms (server settings, gameplay, persistence)
and the config.json editor.

Everything is saved through POST /api/config/save, which the page's save bar
sends with every section that has changes. Each section is checked first,
then all of them are applied in a single write, so a save is all or nothing.
The editor's text replaces the whole file, so it can't be saved together
with form changes.
"""

from flask import Blueprint, jsonify, request

from ..i18n import t
from ..security import csrf_protected, login_required
from ..services import config_check, config_fields
from ..services.config_fields import (FAST_VALIDATION, GAMEPLAY_FIELDS, PERSISTENCE_FIELDS, SERVER_FIELDS,
                                      FieldError)
from ..services.persistence import MODES, set_persistence_mode
from ..services.process import get_server_pid
from ..services.scenarios import all_scenarios_cached
from ..services.server_config import (ChangeRejected, ConfigChanged, ConfigError, load_config, read_config_text,
                                      replace_config_text)
from .common import save_config

bp = Blueprint("server_config", __name__, url_prefix="/api")

NAME_MAX_LENGTH = 100  # limit given by the Bohemia wiki


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


@bp.get("/gameplay")
@login_required
def get_gameplay():
    try:
        cfg = load_config()
    except ConfigError as e:
        return jsonify({"ok": False, "error": t("api.config_unreadable", error=e)}), 500
    return jsonify({
        "ok": True,
        "fast_validation": FAST_VALIDATION.read(cfg),
        **config_fields.form_values(cfg, GAMEPLAY_FIELDS),
    })


@bp.get("/config/raw")
@login_required
def get_raw():
    """The file as stored, for the config.json editor, with its SHA-256 so a
    save can tell whether it changed in the meantime."""
    try:
        text, sha256 = read_config_text()
    except ConfigError as e:
        return jsonify({"ok": False, "error": t("api.config_unreadable", error=e)}), 500
    return jsonify({"ok": True, "text": text, "sha256": sha256})


@bp.post("/config/check")
@login_required
@csrf_protected
def check_raw():
    """Problems in the editor's text, without saving it."""
    text = (request.get_json(silent=True) or {}).get("text")
    if not isinstance(text, str):
        return jsonify({"ok": False, "error": t("api.invalid_request")}), 400
    return jsonify({"ok": True, "problems": config_check.check(text, _scenario_ids())})


def _string(data, key):
    value = data[key]
    if not isinstance(value, str):
        raise FieldError(t("api.not_a_string", field=key))
    return value


def _server_change(data):
    """Check the Server Configuration card's values and return the change to
    apply. Raises FieldError."""
    game_changes = {}
    if "server_name" in data:
        name = _string(data, "server_name").strip()
        if not name:
            raise FieldError(t("api.name_required"))
        if len(name) > NAME_MAX_LENGTH:
            raise FieldError(t("api.name_too_long", max=NAME_MAX_LENGTH))
        game_changes["name"] = name
    if "scenario_id" in data:
        sid = _string(data, "scenario_id").strip()
        if sid not in _scenario_ids():
            raise FieldError(t("api.unknown_scenario"))
        game_changes["scenarioId"] = sid
    if "password" in data:
        game_changes["password"] = _string(data, "password")
    if "password_admin" in data:
        password = _string(data, "password_admin").strip()
        if not password:
            raise FieldError(t("api.admin_password_required"))
        # The server doesn't support spaces here (wiki, passwordAdmin).
        if any(c.isspace() for c in password):
            raise FieldError(t("api.admin_password_spaces"))
        game_changes["passwordAdmin"] = password
    fields = config_fields.parse_form(SERVER_FIELDS, data)

    def change(cfg):
        game = cfg.setdefault("game", {})
        if not isinstance(game, dict):
            raise ChangeRejected(t("api.config_unexpected", path="game"))
        game.update(game_changes)
        written = config_fields.apply(cfg, SERVER_FIELDS, fields)
        # With crossPlatform set, the wiki recommends leaving supportedPlatforms
        # out: true then means every platform and false means PC only.
        if "cross_platform" in written:
            game.pop("supportedPlatforms", None)

    return change


def _gameplay_change(data):
    fields = config_fields.parse_form(GAMEPLAY_FIELDS, data)
    return lambda cfg: config_fields.apply(cfg, GAMEPLAY_FIELDS, fields)


def _persistence_change(data):
    mode = data.get("mode")
    if mode not in MODES:
        raise FieldError(t("api.invalid_persistence_mode"))
    # The settings only apply, and are only checked, in custom mode.
    fields = config_fields.parse_form(PERSISTENCE_FIELDS, data) if mode == "custom" else {}

    def change(cfg):
        set_persistence_mode(cfg, mode)
        config_fields.apply(cfg, PERSISTENCE_FIELDS, fields)

    return change


# Form sections the save bar can send, in the order they are applied.
SECTIONS = {
    "server": _server_change,
    "gameplay": _gameplay_change,
    "persistence": _persistence_change,
}


@bp.post("/config/save")
@login_required
@csrf_protected
def save():
    """Save the sections with changes: {"server": {...}, "gameplay": {...},
    "persistence": {...}} or {"raw": {"text": ..., "sha256": ...}}.
    An error names the section it comes from in "section"."""
    data = request.get_json(silent=True) or {}
    parts = {name: data[name] for name in SECTIONS if name in data}
    if "raw" in data:
        if parts:
            return jsonify({"ok": False, "error": t("api.save_mixed")}), 400
        return _save_raw(data["raw"])
    if not parts:
        return jsonify({"ok": False, "error": t("api.no_changes")}), 400

    changes = []
    for name, part in parts.items():
        try:
            if not isinstance(part, dict):
                raise FieldError(t("api.invalid_request"))
            changes.append(SECTIONS[name](part))
        except FieldError as e:
            return jsonify({"ok": False, "error": str(e), "section": name}), 400

    def change(cfg):
        for apply_section in changes:
            apply_section(cfg)

    _, error = save_config(change)
    if error:
        return error
    return jsonify({"ok": True, "saved": list(parts), "restart_required": get_server_pid() is not None})


def _save_raw(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or not isinstance(raw.get("sha256"), str):
        return jsonify({"ok": False, "error": t("api.invalid_request"), "section": "raw"}), 400
    problems = config_check.check(raw["text"], _scenario_ids())
    if config_check.has_errors(problems):
        return jsonify({"ok": False, "error": t("api.config_check_failed"), "section": "raw",
                        "problems": problems}), 400
    try:
        sha256 = replace_config_text(raw["text"], raw["sha256"])
    except ConfigChanged:
        return jsonify({"ok": False, "error": t("api.config_changed"), "section": "raw"}), 409
    except ConfigError as e:
        return jsonify({"ok": False, "error": t("api.config_unreadable", error=e), "section": "raw"}), 500
    except OSError as e:
        return jsonify({"ok": False, "error": t("api.config_write_failed", error=e), "section": "raw"}), 500
    return jsonify({"ok": True, "saved": ["raw"], "sha256": sha256, "problems": problems,
                    "restart_required": get_server_pid() is not None})


def _scenario_ids():
    return {m["id"] for m in all_scenarios_cached()}
