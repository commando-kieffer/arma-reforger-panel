"""File helpers shared by the services."""

import os
import shutil


def write_atomic(path, text):
    """Replace `path` with `text` in a single rename, so readers see either the
    old or the new content, never a partial file. The file mode is kept."""
    _write_atomic(path, text, "w", "utf-8")


def write_atomic_bytes(path, data):
    """write_atomic() for binary content."""
    _write_atomic(path, data, "wb", None)


def _write_atomic(path, content, mode, encoding):
    tmp = f"{path}.tmp"
    try:
        with open(tmp, mode, encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
