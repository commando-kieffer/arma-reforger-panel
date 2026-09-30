"""Helpers shared by the API routes."""

from flask import jsonify

from ..i18n import t
from ..services.server_config import ChangeRejected, ConfigError, update_config


def save_config(mutate):
    """Run update_config(mutate) and turn its failures into a JSON error.

    Returns (result, None) on success and (None, response) otherwise:
        result, error = save_config(change)
        if error:
            return error
    """
    try:
        return update_config(mutate), None
    except ChangeRejected as e:
        return None, (jsonify({"ok": False, "error": str(e)}), 400)
    except ConfigError as e:
        return None, (jsonify({"ok": False, "error": t("api.config_not_saved", error=e)}), 500)
    except OSError as e:
        return None, (jsonify({"ok": False, "error": t("api.config_write_failed", error=e)}), 500)
