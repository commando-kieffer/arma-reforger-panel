"""Access to the server's console logs.

The server writes one directory per start in LOG_DIR, named after the start
time (logs_2026-09-29_23-59-10), holding console.log, error.log and script.log.
"""

import glob
import os
import re
import subprocess
import tempfile
import zipfile

from .. import config

SESSION_NAME_RE = re.compile(r"^logs_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})$")
LOG_FILES = ("console.log", "error.log", "script.log")


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


def _is_regular_file(path):
    return os.path.isfile(path) and not os.path.islink(path)


def _log_files(session_path):
    """{file name: size} for the log files present in a session directory."""
    files = {}
    for name in LOG_FILES:
        path = os.path.join(session_path, name)
        try:
            if _is_regular_file(path):
                files[name] = os.path.getsize(path)
        except OSError:
            pass
    return files


def list_sessions():
    """Session directories, newest first. The names are zero-padded
    timestamps, so sorting them by name sorts them by date."""
    try:
        names = os.listdir(config.LOG_DIR)
    except OSError:
        return []
    sessions = []
    for name in sorted(names, reverse=True):
        match = SESSION_NAME_RE.match(name)
        path = os.path.join(config.LOG_DIR, name)
        if not match or not os.path.isdir(path) or os.path.islink(path):
            continue
        date, hours, minutes, seconds = match.groups()
        files = _log_files(path)
        sessions.append({
            "name": name,
            "started": f"{date} {hours}:{minutes}:{seconds}",
            "files": files,
            "size": sum(files.values()),
        })
    return sessions


def session_dir(name):
    """Path of the session directory `name`, or None if there is no such
    session. `name` has to appear in the directory listing, so a request can't
    point anywhere else."""
    if not SESSION_NAME_RE.match(name):
        return None
    try:
        if name not in os.listdir(config.LOG_DIR):
            return None
    except OSError:
        return None
    path = os.path.join(config.LOG_DIR, name)
    return path if os.path.isdir(path) and not os.path.islink(path) else None


def zip_session(name):
    """Zip the log files of session `name` into a temporary file.

    Returns the open file, positioned at the start, or None when the session
    doesn't exist or has none of the log files. Zipping first also takes a
    snapshot of logs the server is still writing to.
    """
    path = session_dir(name)
    if path is None:
        return None
    files = _log_files(path)
    if not files:
        return None
    archive = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_name in files:
                zf.write(os.path.join(path, file_name), arcname=file_name)
    except BaseException:
        archive.close()
        raise
    archive.seek(0)
    return archive
