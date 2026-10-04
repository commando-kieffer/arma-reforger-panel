"""Panel styles.

A theme is a folder holding three stylesheets, base.css (shared by every
page), login.css and panel.css, and a theme.json giving its name:

    {"name": "Retro 2000"}

The panel comes with the themes in static/css/<id>/. Themes uploaded from the
panel are kept in custom-themes/<id>/ in the panel directory. A folder that
is missing one of these files is skipped.
"""

import io
import json
import os
import re
import secrets
import shutil
import threading
import zipfile
from collections import namedtuple

from .. import config
from ..i18n import t
from ..log import logger
from .files import write_atomic
from .server_config import ChangeRejected

STYLESHEETS = ("base.css", "login.css", "panel.css")
MANIFEST = "theme.json"
DEFAULT_THEME = "zeus"
NAME_MAX_LENGTH = 60
STYLESHEET_MAX_BYTES = 512 * 1024

BUILT_IN_DIR = os.path.join(config.BASE_DIR, "static", "css")
_BUILT_IN_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")
_CUSTOM_ID_RE = re.compile(r"^[0-9a-f]{8}$")
_UNSAFE_FILE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# path: the folder holding the stylesheets. custom: uploaded from the panel.
Theme = namedtuple("Theme", "id name path custom")

# Covers the custom themes folder.
_lock = threading.Lock()


class NameTaken(Exception):
    """An uploaded theme has the name of a custom theme uploaded before."""


def all_themes():
    """The usable themes: the built-in ones, then the custom ones, each
    sorted by name."""
    themes = _scan(BUILT_IN_DIR, _BUILT_IN_ID_RE, custom=False)
    built_in = {theme.id for theme in themes}
    custom = _scan(config.CUSTOM_THEMES_DIR, _CUSTOM_ID_RE, custom=True)
    return themes + [theme for theme in custom if theme.id not in built_in]


def get(theme_id):
    """The theme with this id, or None."""
    return next((theme for theme in all_themes() if theme.id == theme_id), None)


def save(name, stylesheets, replace=False):
    """Add an uploaded theme and return its id.

    `stylesheets` maps each of STYLESHEETS to the uploaded bytes, or None when
    the file is missing. When a custom theme already has this name, NameTaken
    is raised, unless `replace` is set: its stylesheets are then replaced.
    """
    name = _check_name(name)
    texts = {file: _check_stylesheet(file, stylesheets.get(file)) for file in STYLESHEETS}
    with _lock:
        themes = all_themes()
        same = next((theme for theme in themes if theme.name.casefold() == name.casefold()), None)
        if same is not None and not same.custom:
            raise ChangeRejected(t("api.theme_name_built_in", name=same.name))
        if same is not None and not replace:
            raise NameTaken(t("api.theme_name_taken", name=same.name))
        if same is not None:
            for file, text in texts.items():
                write_atomic(os.path.join(same.path, file), text)
            write_atomic(os.path.join(same.path, MANIFEST), _manifest(name))
            return same.id

        # Written to a hidden folder first, so the theme only shows up once
        # all its files are there.
        theme_id = _new_id(themes)
        tmp = os.path.join(config.CUSTOM_THEMES_DIR, f".{theme_id}.tmp")
        try:
            os.makedirs(tmp)
            for file, text in texts.items():
                with open(os.path.join(tmp, file), "w", encoding="utf-8") as f:
                    f.write(text)
            with open(os.path.join(tmp, MANIFEST), "w", encoding="utf-8") as f:
                f.write(_manifest(name))
            os.replace(tmp, os.path.join(config.CUSTOM_THEMES_DIR, theme_id))
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return theme_id


def delete(theme_id):
    """Remove a custom theme. Whether it is in use is up to the caller."""
    with _lock:
        theme = _get_or_reject(theme_id)
        if not theme.custom:
            raise ChangeRejected(t("api.theme_built_in"))
        shutil.rmtree(theme.path)


def archive(theme_id):
    """The theme's stylesheets as a zip file: (file name, bytes)."""
    theme = _get_or_reject(theme_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in STYLESHEETS:
            zf.write(os.path.join(theme.path, file), file)
    file_name = _UNSAFE_FILE_NAME_RE.sub("_", theme.name).strip(" .") or theme.id
    return f"{file_name}.zip", buffer.getvalue()


def _scan(root, id_re, custom):
    try:
        names = os.listdir(root)
    except FileNotFoundError:
        return []
    themes = []
    for theme_id in names:
        path = os.path.join(root, theme_id)
        if not id_re.match(theme_id) or not os.path.isdir(path):
            continue
        missing = [file for file in STYLESHEETS + (MANIFEST,)
                   if not os.path.isfile(os.path.join(path, file))]
        if missing:
            logger.warning("ignoring theme %s: missing %s", path, ", ".join(missing))
            continue
        name = _read_name(path)
        if name is not None:
            themes.append(Theme(theme_id, name, path, custom))
    return sorted(themes, key=lambda theme: theme.name.casefold())


def _read_name(path):
    try:
        with open(os.path.join(path, MANIFEST), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("ignoring theme %s: %s", path, e)
        return None
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        logger.warning("ignoring theme %s: %s has no name", path, MANIFEST)
        return None
    return name.strip()


def _manifest(name):
    return json.dumps({"name": name}, indent="\t", ensure_ascii=False) + "\n"


def _get_or_reject(theme_id):
    theme = get(theme_id)
    if theme is None:
        raise ChangeRejected(t("api.theme_not_found"))
    return theme


def _new_id(themes):
    while True:
        theme_id = secrets.token_hex(4)
        # A folder skipped as broken still exists; don't overwrite it.
        if (all(theme.id != theme_id for theme in themes)
                and not os.path.exists(os.path.join(config.CUSTOM_THEMES_DIR, theme_id))):
            return theme_id


def _check_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ChangeRejected(t("api.theme_name_required"))
    name = name.strip()
    if len(name) > NAME_MAX_LENGTH or not name.isprintable():
        raise ChangeRejected(t("api.theme_name_invalid", max=NAME_MAX_LENGTH))
    return name


def _check_stylesheet(file, data):
    if data is None:
        raise ChangeRejected(t("api.theme_file_missing", file=file))
    if len(data) > STYLESHEET_MAX_BYTES:
        raise ChangeRejected(t("api.theme_file_too_large", file=file, max=STYLESHEET_MAX_BYTES // 1024))
    try:
        # utf-8-sig drops the byte order mark some editors add.
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ChangeRejected(t("api.theme_file_not_utf8", file=file)) from None
