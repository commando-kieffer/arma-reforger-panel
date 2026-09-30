"""Access to the server's console logs."""

import glob
import os
import subprocess

from .. import config


def get_latest_log():
    """Path of console.log in the newest `logs_*` directory, or None."""
    try:
        dirs = sorted(glob.glob(f"{config.LOG_DIR}/logs_*"), reverse=True)
        if not dirs:
            return None
        path = os.path.join(dirs[0], "console.log")
        return path if os.path.exists(path) else None
    except Exception:
        return None


def tail(path, lines):
    r = subprocess.run(["tail", "-n", str(lines), path], capture_output=True, text=True)
    return r.stdout.splitlines()
