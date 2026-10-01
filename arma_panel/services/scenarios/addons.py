"""Locating Reforger addons on disk and reading the scenarios they ship.

Reforger workshop mods unpack to <WORKSHOP_DIR>/<Name>_<HEXID>/. Each addon
ships a `meta` file (UTF-8-with-BOM JSON) that contains the workshop
metadata, including a `versions[].scenarios[]` array. Each scenario entry
is a dict with at least `name` and `gameId` (the full {HEX16}Missions/...
.conf identifier we need). This is far more reliable than scanning the
binary .pak file — and the `meta` file is tiny, so the scan is instant.
"""

import json
import os
import re

from ... import config

SCENARIO_GAME_ID_RE = re.compile(r'^\{[0-9A-Fa-f]{16}\}.+\.conf$')
# Any printable ASCII after the prefix: file names can contain spaces
# ("Missions/Scenario CK.conf"). The length-prefix check in
# scenarios_from_rdb is what rejects false matches, not this character set.
RDB_PATH_RE = re.compile(rb'Missions/[\x20-\x7e]+\.conf')


def candidate_addon_roots():
    """Locations to scan for addons. Each entry is (path, is_vanilla).
    `is_vanilla=True` means anything found there is Bohemia-shipped game
    content (the dedicated server's bundled addons), not a workshop mod."""
    server_dir = config.SERVER_DIR
    home = os.path.dirname(server_dir.rstrip("/")) if server_dir else os.path.expanduser("~")
    if not home or home == "/":
        home = os.path.expanduser("~arma") if os.path.isdir("/home/arma") else os.path.expanduser("~")

    roots = []
    # Workshop mod dirs (downloaded via SteamCMD / the game)
    if config.WORKSHOP_DIR:
        roots.append((config.WORKSHOP_DIR, False))
    roots.extend([
        (os.path.join(home, ".local/share/Arma Reforger/profile/addons"), False),
        (os.path.join(home, ".local/share/Arma Reforger/addons"),         False),
        (os.path.join(home, ".config/Arma Reforger/addons"),              False),
        (os.path.join(home, ".config/ArmaReforger/addons"),               False),
    ])
    # Bohemia-shipped game content (Conflict, GM, CAH, Operation Omega, etc.)
    if server_dir:
        roots.extend([
            (os.path.join(server_dir, "Addons"), True),
            (os.path.join(server_dir, "addons"), True),
            (server_dir,                          True),  # falls back to walking server install
        ])
    seen, out = set(), []
    for path, vanilla in roots:
        if path and path not in seen and os.path.isdir(path):
            seen.add(path)
            out.append((path, vanilla))
    return out


def find_addons(root, max_depth=4):
    """Walk `root` up to `max_depth` levels and yield (addon_dir, meta_or_None,
    rdb_or_None) for every directory that looks like a Reforger addon (i.e.
    contains a `meta` JSON, a `resourceDatabase.rdb`, or an `addon.gproj`)."""
    if not root or not os.path.isdir(root):
        return
    root = os.path.abspath(root)
    base_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        depth = dirpath.rstrip("/").count("/") - base_depth
        if depth >= max_depth:
            dirnames[:] = []
        meta_file = os.path.join(dirpath, "meta") if "meta" in filenames else None
        rdb_file = os.path.join(dirpath, "resourceDatabase.rdb") if "resourceDatabase.rdb" in filenames else None
        gproj = "addon.gproj" in filenames
        if meta_file or rdb_file or gproj:
            # Don't descend into addon dirs further (their inner files aren't more addons)
            dirnames[:] = []
            if meta_file or rdb_file:
                yield dirpath, meta_file, rdb_file


def addon_name_from_gproj(addon_dir):
    """Pull a friendly display name from addon.gproj (TITLE or ID field)."""
    gproj = os.path.join(addon_dir, "addon.gproj")
    if not os.path.isfile(gproj):
        return None
    try:
        with open(gproj, encoding="utf-8", errors="replace") as f:
            text = f.read(2048)
    except OSError:
        return None
    m = re.search(r'TITLE\s+"([^"]+)"', text) or re.search(r'ID\s+"([^"]+)"', text)
    return m.group(1).strip() if m else None


def scenarios_from_rdb(rdb_path, source_label):
    """Fallback: parse `resourceDatabase.rdb` for scenario records.

    The dedicated-server workshop downloader strips `meta.versions[].scenarios`
    on Linux (just an empty list), so we can't rely on the JSON for those.
    The .rdb file ships next to data.pak in every addon and contains the
    asset directory in a simple length-prefixed binary format. Each scenario
    asset record looks like:
        <4-byte LE length>  <path bytes>  <\\0>  <6-byte padding>  <8-byte LE GUID>  …
    where the LE length equals len(path) + 1 (counting the null terminator).
    The 8-byte GUID is little-endian, so we reverse it for the {HEX16} display.

    We rely on the path-prefix `Missions/` to filter for scenarios, then
    validate each candidate by checking the length prefix matches; this
    rejects stray substring hits in unrelated records.
    """
    try:
        with open(rdb_path, "rb") as f:
            data = f.read()
    except OSError:
        return []

    out = []
    seen = set()
    for m in RDB_PATH_RE.finditer(data):
        ps, pe = m.start(), m.end()
        if ps < 4:
            continue
        path_len_field = int.from_bytes(data[ps - 4:ps], "little")
        if path_len_field != (pe - ps) + 1:
            continue  # not a length-prefixed record — likely a substring inside something else
        if pe >= len(data) or data[pe] != 0:
            continue
        guid_start = pe + 7  # 1 null byte + 6-byte padding
        if guid_start + 8 > len(data):
            continue
        guid_bytes = data[guid_start:guid_start + 8]
        # Reject obviously-bogus GUIDs (all-zero / all-0xFF fillers).
        if guid_bytes == b"\x00" * 8 or guid_bytes == b"\xff" * 8:
            continue
        guid_hex = guid_bytes[::-1].hex().upper()  # little-endian → big-endian display
        path_str = m.group(0).decode("ascii", errors="replace")
        sid = "{" + guid_hex + "}" + path_str
        if sid in seen:
            continue
        seen.add(sid)
        out.append({
            "id": sid,
            "name": path_str.split("/")[-1].replace(".conf", ""),
            "description": "",
            "player_count": None,
            "source": source_label or "mod",
        })
    return out


def scenarios_from_meta(meta_path):
    """Parse a workshop `meta` file and return (scenarios, mod_name) where
    scenarios is a list of {id, name, description, player_count, source}.
    The `meta` file is UTF-8 with BOM and contains the workshop publisher
    metadata. Scenarios appear under meta.versions[].scenarios[].
    """
    try:
        with open(meta_path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return [], None

    m = (data.get("meta") or {})
    mod_name = (m.get("name") or "").strip()

    # Pull scenarios from the latest version (versions[0]) — that's what's installed.
    versions = m.get("versions") or []
    raw_scenarios = []
    if versions and isinstance(versions, list):
        raw_scenarios = versions[0].get("scenarios") or []
    if not raw_scenarios:
        # Some older meta layouts have a top-level scenarios array.
        raw_scenarios = m.get("scenarios") or []
    if not isinstance(raw_scenarios, list):
        return [], mod_name

    out = []
    for s in raw_scenarios:
        if not isinstance(s, dict):
            continue
        sid = (s.get("gameId") or "").strip()
        if not sid or not SCENARIO_GAME_ID_RE.match(sid):
            continue
        out.append({
            "id":           sid,
            "name":         (s.get("name") or sid.split("/")[-1].replace(".conf", "")).strip(),
            "description":  (s.get("description") or "").strip()[:300],
            "player_count": s.get("playerCount") if isinstance(s.get("playerCount"), int) else None,
            "source":       mod_name or "mod",
        })
    return out, mod_name
