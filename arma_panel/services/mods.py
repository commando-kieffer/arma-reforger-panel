"""Validation and merging of mod lists (mod sets and `game.mods` in config.json)."""

HEX_DIGITS = "0123456789ABCDEFabcdef"


def normalize_mod_entry(entry):
    """Validate one mod row. Returns canonical dict or None."""
    if not isinstance(entry, dict):
        return None
    mod_id = str(entry.get("modId", "")).strip()
    if not mod_id or len(mod_id) > 32:
        return None
    if not all(c in HEX_DIGITS for c in mod_id):
        return None
    out = {"modId": mod_id.upper()}
    name = str(entry.get("name", "")).strip()
    if name:
        if len(name) > 200 or any(c in name for c in "\n\r"):
            return None
        out["name"] = name
    version = str(entry.get("version", "")).strip()
    if version:
        if len(version) > 32 or any(c in version for c in '\n\r"\\'):
            return None
        out["version"] = version
    # Workshop exports can mark a mod as optional; keep that choice.
    required = entry.get("required")
    if isinstance(required, bool):
        out["required"] = required
    return out


def collect_import_entries(data):
    """Normalise an imported JSON array.

    Returns (valid, skipped). `skipped` holds (position, mod_id) tuples with a
    1-based position; mod_id is set when the entry was a duplicate and None
    when it was invalid.
    """
    valid = []
    skipped = []
    seen = set()
    for i, entry in enumerate(data):
        norm = normalize_mod_entry(entry)
        if not norm:
            skipped.append((i + 1, None))
            continue
        if norm["modId"] in seen:
            skipped.append((i + 1, norm["modId"]))
            continue
        seen.add(norm["modId"])
        valid.append(norm)
    return valid, skipped


def merge_mods(existing, incoming):
    """Append the `incoming` mods whose modId isn't in `existing` yet.
    Returns (merged list, number of mods added)."""
    merged = list(existing)
    existing_ids = {str(m.get("modId", "")).upper() for m in merged}
    added = 0
    for m in incoming:
        if m["modId"] not in existing_ids:
            merged.append(m)
            existing_ids.add(m["modId"])
            added += 1
    return merged, added
