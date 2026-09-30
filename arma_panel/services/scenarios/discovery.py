"""Scenario discovery across installed addons, and the merged scenario list.

Scan results are cached per addon dir by `meta`/`.rdb` mtime so unchanged
addons are not re-read. /api/status only ever reads that cache; a real scan
happens when the user clicks "Rescan".
"""

import json
import os
import threading
import time

from ... import config
from ...log import logger
from ..server_config import read_config
from .addons import (
    addon_name_from_gproj,
    candidate_addon_roots,
    find_addons,
    scenarios_from_meta,
    scenarios_from_rdb,
)
from .catalog import SCENARIO_NAME_OVERRIDES, VANILLA_SCENARIOS, apply_name_override

_SCAN_LOCK = threading.Lock()
_LAST_SCAN_RESULT: dict = {"scenarios": [], "diag": None, "ts": 0.0}


def _scan_cache_load():
    try:
        with open(config.SCAN_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("mods", {}), data.get("mtimes", {})
    except (OSError, json.JSONDecodeError):
        return {}, {}


def _scan_cache_save(mods, mtimes):
    try:
        with open(config.SCAN_CACHE_FILE, "w") as f:
            json.dump({"mods": mods, "mtimes": mtimes, "saved_at": time.time()}, f)
    except OSError as e:
        logger.warning("could not write scenario cache: %s", e)


def _flatten(mods):
    flat = []
    for sids in mods.values():
        flat.extend(sids)
    return flat


def _discover_locked(force_rescan):
    """Actual scan work. Caller must hold _SCAN_LOCK."""
    diag = {"candidates_tried": [], "addons_scanned": 0,
            "mods_with_scenarios": 0, "scenarios_total": 0, "errors": []}

    cache_mods, cache_mtimes = ({}, {}) if force_rescan else _scan_cache_load()
    fresh_mods, fresh_mtimes = {}, {}

    seen_addon_dirs = set()
    addons_scanned = 0

    for root, is_vanilla in candidate_addon_roots():
        diag["candidates_tried"].append({"path": root, "vanilla": is_vanilla})
        for addon_dir, meta_path, rdb_path in find_addons(root):
            real_dir = os.path.realpath(addon_dir)
            if real_dir in seen_addon_dirs:
                continue
            seen_addon_dirs.add(real_dir)
            addons_scanned += 1

            # Cache key tracks both files so we re-scan if either changes.
            cache_key = real_dir
            try:
                meta_mtime = os.path.getmtime(meta_path) if meta_path else 0
                rdb_mtime  = os.path.getmtime(rdb_path) if rdb_path else 0
                mtime = max(meta_mtime, rdb_mtime)
            except OSError as e:
                diag["errors"].append(f"{cache_key}: stat failed ({e})")
                continue

            if cache_mtimes.get(cache_key) == mtime and cache_key in cache_mods:
                fresh_mods[cache_key] = cache_mods[cache_key]
                fresh_mtimes[cache_key] = mtime
                continue

            scenarios = []
            mod_name = None
            # 1. Try the workshop meta JSON first (gives us the publisher's
            #    display names + player counts when populated).
            if meta_path:
                scenarios, mod_name = scenarios_from_meta(meta_path)
            # 2. Fall back to the .rdb scan when the meta has no scenarios
            #    (Linux dedi strips them) or when there's no meta at all
            #    (Bohemia's bundled vanilla addons).
            if not scenarios and rdb_path:
                if not mod_name:
                    mod_name = addon_name_from_gproj(addon_dir) or os.path.basename(addon_dir)
                source = "vanilla" if is_vanilla else mod_name
                scenarios = scenarios_from_rdb(rdb_path, source)
            # 3. Force-tag everything found in the server install dir as vanilla.
            if is_vanilla:
                for s in scenarios:
                    s["source"] = "vanilla"
            # 4. Single-scenario mods are usually named after their scenario.
            #    The .rdb fallback only knows the filename (e.g.
            #    "MontfordFortress"), but the workshop name is the friendly
            #    one ("Fortress"). When a mod publishes exactly one scenario
            #    and we have an addon display name, prefer that — unless an
            #    explicit override is already in place.
            if len(scenarios) == 1 and not is_vanilla and mod_name:
                if scenarios[0]["id"] not in SCENARIO_NAME_OVERRIDES:
                    scenarios[0]["name"] = mod_name
            # 5. Apply our curated friendly-name overrides (mainly RHS).
            for s in scenarios:
                apply_name_override(s)

            if scenarios:
                fresh_mods[cache_key] = scenarios
            fresh_mtimes[cache_key] = mtime

    _scan_cache_save(fresh_mods, fresh_mtimes)

    flat = _flatten(fresh_mods)
    diag["addons_scanned"] = addons_scanned
    diag["mods_with_scenarios"] = len(fresh_mods)
    diag["scenarios_total"] = len(flat)
    # Back-compat fields the old UI knew about
    diag["workshop_dir"] = "; ".join(p for p, _ in candidate_addon_roots()) or None
    diag["metas_found"]  = addons_scanned
    return flat, diag


def discover_mod_scenarios(force_rescan=False):
    """Return (scenarios, diag).
       Lock-protected so concurrent /api/status polls or rescan clicks can't
       launch overlapping scans.  Non-rescan callers get the cached result
       without doing any disk I/O if a scan is already in progress."""
    if not force_rescan:
        # Cheap path: just read the on-disk cache.
        cache_mods, _mtimes = _scan_cache_load()
        if cache_mods:
            flat = _flatten(cache_mods)
            diag = {"workshop_dir": None, "paks_found": len(cache_mods),
                    "scenarios_total": len(flat), "from_cache": True}
            return flat, diag

    if not _SCAN_LOCK.acquire(blocking=force_rescan):
        # Scan in progress and we don't want to block — return whatever we have.
        return _LAST_SCAN_RESULT["scenarios"], (_LAST_SCAN_RESULT["diag"] or {"busy": True})
    try:
        scenarios, diag = _discover_locked(force_rescan)
        _LAST_SCAN_RESULT["scenarios"] = scenarios
        _LAST_SCAN_RESULT["diag"] = diag
        _LAST_SCAN_RESULT["ts"] = time.time()
        return scenarios, diag
    finally:
        _SCAN_LOCK.release()


def cached_scenarios():
    """Cheap read for /api/status — never triggers a fresh scan."""
    cache_mods, _mtimes = _scan_cache_load()
    return _flatten(cache_mods)


def _merge_with_vanilla(discovered):
    """Vanilla list + `discovered`, deduped by id (vanilla wins for naming)."""
    by_id = {}
    for s in VANILLA_SCENARIOS:
        by_id[s["id"]] = dict(s)
    for s in discovered:
        by_id.setdefault(s["id"], dict(s))
    out = list(by_id.values())
    out.sort(key=lambda s: (s["source"] != "vanilla", s["source"], s["name"]))
    return out


def all_scenarios(force_rescan=False):
    """Vanilla list + auto-discovered. Returns (list, diag)."""
    discovered, diag = discover_mod_scenarios(force_rescan=force_rescan)
    return _merge_with_vanilla(discovered), diag


def all_scenarios_cached():
    """Like all_scenarios() but never scans — used by /api/status hot path."""
    return _merge_with_vanilla(cached_scenarios())


def count_by_source(scenarios):
    return {"vanilla": sum(1 for m in scenarios if m.get("source") == "vanilla"),
            "from_mods": sum(1 for m in scenarios if m.get("source") != "vanilla")}


def get_map_name(cfg=None):
    try:
        if cfg is None:
            cfg = read_config()
        sid = cfg.get("game", {}).get("scenarioId", "")
        if not sid:
            return "Unknown"
        # Consult the full merged list (vanilla + discovered, with overrides
        # already applied) so the dashboard tile matches the dropdown.
        for m in all_scenarios_cached():
            if m["id"] == sid:
                return m["name"]
        return sid.split("/")[-1].replace(".conf", "")
    except Exception:
        return "Unknown"
