"""Panel settings: the panel's own preferences, shared by everyone using it.

Stored in panel-settings.json in the panel directory:

    {"theme": "zeus"}

Settings missing from the file, or holding a value the panel doesn't know,
fall back to their default.
"""

import json
import threading

from .. import config, themes
from ..i18n import t
from ..log import logger
from .files import write_atomic
from .server_config import ChangeRejected

DEFAULTS = {"theme": themes.DEFAULT_THEME}

_lock = threading.Lock()


def load():
    """The settings, with every key present and valid."""
    data = _read()
    theme = data.get("theme")
    return {"theme": theme if theme in themes.BY_ID else DEFAULTS["theme"]}


def set_theme(theme_id):
    if not isinstance(theme_id, str) or theme_id not in themes.BY_ID:
        raise ChangeRejected(t("api.unknown_theme"))
    with _lock:
        # Keys this version doesn't know are kept as they are.
        data = _read()
        data["theme"] = theme_id
        write_atomic(config.SETTINGS_FILE, json.dumps(data, indent="\t", ensure_ascii=False) + "\n")


def _read():
    try:
        with open(config.SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("ignoring %s: %s", config.SETTINGS_FILE, e)
        return {}
    if not isinstance(data, dict):
        logger.warning("ignoring %s: unexpected content", config.SETTINGS_FILE)
        return {}
    return data
