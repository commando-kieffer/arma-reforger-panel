"""Helpers shared by the API routes."""

from flask import jsonify

from ..i18n import t
from ..services.server_config import ChangeRejected, ConfigError, update_config


def attempt(action, write_failed="api.config_write_failed"):
    """Run `action()` and turn the usual failures into a JSON error.

    Returns (result, None) on success and (None, response) otherwise:
        result, error = attempt(change)
        if error:
            return error
    `write_failed` is the message key used when a file couldn't be written.
    """
    try:
        return action(), None
    except ChangeRejected as e:
        return None, (jsonify({"ok": False, "error": str(e)}), 400)
    except ConfigError as e:
        return None, (jsonify({"ok": False, "error": t("api.config_not_saved", error=e)}), 500)
    except OSError as e:
        return None, (jsonify({"ok": False, "error": t(write_failed, error=e)}), 500)


def save_config(mutate):
    """attempt() for a single update_config(mutate) call."""
    return attempt(lambda: update_config(mutate))
