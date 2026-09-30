"""Reading and writing the dedicated server's config.json.

Every change goes through update_config(): the file is read strictly, so a
config that can't be parsed is never overwritten with a partial one; the
previous version is copied to the backup folder; and the new content replaces
the file in a single rename, so the server never reads a half-written file.
"""

import copy
import json
import os
import shutil
import threading
from datetime import datetime

from .. import config
from ..log import logger

BACKUP_KEEP = 20

# Flask serves requests on several threads: two saves must not interleave
# their read-modify-write sequences.
_write_lock = threading.Lock()


class ConfigError(Exception):
    """config.json is missing, unreadable or not a JSON object."""


class ChangeRejected(Exception):
    """Raised by an update callback to cancel the change; nothing is written."""


def load_config():
    """Parse config.json, raising ConfigError instead of guessing."""
    try:
        with open(config.SERVER_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"{config.SERVER_CONFIG} not found") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}") from None
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(str(e)) from None
    if not isinstance(cfg, dict):
        raise ConfigError("the top-level value is not a JSON object")
    return cfg


def read_config():
    """Lenient read for display only. Never use the result to write the file."""
    try:
        return load_config()
    except ConfigError:
        return {}


def update_config(mutate):
    """Apply `mutate(cfg)` to config.json and save the result.

    Returns whatever `mutate` returns. Raises ConfigError if the current file
    can't be read, ChangeRejected if `mutate` refused the change, and OSError
    if writing failed; config.json is left untouched in all three cases. The
    file isn't rewritten when `mutate` changed nothing.
    """
    with _write_lock:
        cfg = load_config()
        before = copy.deepcopy(cfg)
        result = mutate(cfg)
        if cfg != before:
            _backup()
            _write_atomic(cfg)
        return result


def list_backups():
    try:
        names = os.listdir(config.CONFIG_BACKUP_DIR)
    except OSError:
        return []
    return sorted(n for n in names if n.startswith("config-") and n.endswith(".json"))


def _backup():
    # A failed backup is logged but doesn't block the save: the atomic write
    # below is what protects the file itself.
    try:
        os.makedirs(config.CONFIG_BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(config.SERVER_CONFIG, os.path.join(config.CONFIG_BACKUP_DIR, f"config-{stamp}.json"))
        for name in list_backups()[:-BACKUP_KEEP]:
            os.remove(os.path.join(config.CONFIG_BACKUP_DIR, name))
    except OSError as e:
        logger.warning("could not back up config.json: %s", e)


def _write_atomic(cfg):
    # Resolve a symlinked config.json so the link keeps pointing at the new file.
    path = os.path.realpath(config.SERVER_CONFIG)
    tmp = f"{path}.tmp"
    data = json.dumps(cfg, indent="\t", ensure_ascii=False) + "\n"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
