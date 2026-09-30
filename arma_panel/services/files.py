"""File helpers shared by the services."""

import os
import shutil


def write_atomic(path, text):
    """Replace `path` with `text` in a single rename, so readers see either the
    old or the new content, never a partial file. The file mode is kept."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
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
