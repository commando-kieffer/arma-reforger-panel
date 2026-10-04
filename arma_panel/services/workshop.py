"""Versions of the Workshop mods the server has downloaded.

The server downloads each mod to <WORKSHOP_DIR>/<Name>_<ID>/, next to a
`meta` file (JSON with a UTF-8 BOM) describing the copy on disk:

    {"meta": {"id": "<ID>", "versions": [{"version": "1.4.3", ...}], ...}}
"""

import json
import os

from .. import config
from ..log import logger
from .mods import valid_version


def installed_versions():
    """Map each downloaded mod id (upper case) to its version.

    Mods whose version isn't certain are left out: a `versions` list that
    doesn't hold exactly one entry, or two folders for the same id that
    disagree.
    """
    if not config.WORKSHOP_DIR:
        return {}
    try:
        folders = [e.path for e in os.scandir(config.WORKSHOP_DIR) if e.is_dir()]
    except OSError:
        return {}
    found = {}
    for folder in folders:
        mod_id, version = _read_meta(os.path.join(folder, "meta"))
        if mod_id:
            found.setdefault(mod_id, set()).add(version)
    return {mod_id: versions.pop() for mod_id, versions in found.items()
            if len(versions) == 1 and None not in versions}


def _read_meta(path):
    """Return (mod id, version or None), or (None, None) when the file
    doesn't describe a mod."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        logger.warning("could not read %s: %s", path, e)
        return None, None
    meta = data.get("meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
        return None, None
    versions = meta.get("versions")
    entry = versions[0] if isinstance(versions, list) and len(versions) == 1 else None
    version = entry.get("version") if isinstance(entry, dict) else None
    version = version.strip() if isinstance(version, str) else ""
    return meta["id"].strip().upper(), version if valid_version(version) else None
