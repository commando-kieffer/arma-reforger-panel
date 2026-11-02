"""Workshop mods the server has downloaded.

The server downloads each mod to <WORKSHOP_DIR>/<Name>_<ID>/, next to a
`meta` file (JSON with a UTF-8 BOM) describing the copy on disk:

    {"meta": {"id": "<ID>", "name": "...", "versions": [{"version": "1.4.3", ...}], ...}}
"""

import json
import os
import shutil

from .. import config
from ..i18n import t
from ..log import logger
from .mods import valid_version
from .server_config import ChangeRejected


def installed_versions():
    """Map each downloaded mod id (upper case) to its version.

    Mods whose version isn't certain are left out: a `versions` list that
    doesn't hold exactly one entry, or two folders for the same id that
    disagree.
    """
    found = {}
    for _path, meta in _mod_folders():
        found.setdefault(meta["id"], set()).add(meta["version"])
    return {mod_id: versions.pop() for mod_id, versions in found.items()
            if len(versions) == 1 and None not in versions}


def installed_mods():
    """The downloaded mods, sorted by name: [{"id", "name", "version" (or
    None), "folders", "size"}], one entry per mod id even when the server
    has it in several folders."""
    mods = {}
    for path, meta in _mod_folders():
        mod = mods.setdefault(meta["id"], {"id": meta["id"], "name": meta["name"],
                                           "versions": set(), "folders": [], "size": 0})
        mod["versions"].add(meta["version"])
        mod["folders"].append(os.path.basename(path))
        mod["size"] += _folder_size(path)
    result = []
    for mod in mods.values():
        versions = mod.pop("versions")
        mod["version"] = versions.pop() if len(versions) == 1 else None
        result.append(mod)
    return sorted(result, key=lambda m: (m["name"].casefold(), m["id"]))


def uninstall(mod_id):
    """Delete every folder holding the mod. Returns the number of folders
    removed. Whether the mod may be removed is up to the caller."""
    mod_id = str(mod_id).strip().upper()
    paths = [path for path, meta in _mod_folders() if meta["id"] == mod_id]
    if not paths:
        raise ChangeRejected(t("api.workshop_mod_not_found"))
    for path in paths:
        # rmtree refuses a symlink, so a link pointing outside WORKSHOP_DIR is
        # never followed.
        shutil.rmtree(path)
    return len(paths)


def _mod_folders():
    """(path, {"id", "name", "version"}) for each folder of WORKSHOP_DIR
    that holds a mod's meta file. Symlinks are skipped."""
    if not config.WORKSHOP_DIR:
        return []
    try:
        entries = [e for e in os.scandir(config.WORKSHOP_DIR) if e.is_dir(follow_symlinks=False)]
    except OSError:
        return []
    folders = []
    for entry in entries:
        meta = _read_meta(os.path.join(entry.path, "meta"), entry.name)
        if meta:
            folders.append((entry.path, meta))
    return folders


def _read_meta(path, folder_name):
    """{"id", "name", "version" (or None)}, or None when the file doesn't
    describe a mod."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        logger.warning("could not read %s: %s", path, e)
        return None
    meta = data.get("meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not meta["id"].strip():
        return None
    mod_id = meta["id"].strip().upper()
    versions = meta.get("versions")
    entry = versions[0] if isinstance(versions, list) and len(versions) == 1 else None
    version = entry.get("version") if isinstance(entry, dict) else None
    version = version.strip() if isinstance(version, str) else ""
    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        # The folder is named <Name>_<ID>.
        suffix = "_" + mod_id
        name = folder_name[:-len(suffix)] if folder_name.upper().endswith(suffix) else folder_name
    return {"id": mod_id, "name": name.strip(), "version": version if valid_version(version) else None}


def _folder_size(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total
