"""Panel images that can be replaced from the panel, in two groups:

    banner  banner-logo.png, shown in the header and on the login page
    icons   icon-192.png and icon-512.png, used for the browser tab, the
            home screen and the installed app (see static/manifest.json)

The panel comes with default images under static/. Images uploaded from the
panel are kept in custom-branding/ in the panel directory and used instead.
The browser does the scaling and sends PNG files (static/js/panel/settings.js);
they are only checked here.
"""

import os
import struct
import threading

from .. import config
from ..i18n import t
from .files import write_atomic_bytes
from .server_config import ChangeRejected

GROUPS = {
    "banner": ("banner-logo.png",),
    "icons": ("icon-192.png", "icon-512.png"),
}
FILE_MAX_BYTES = 1536 * 1024
BANNER_MAX_SIZE = (1200, 300)

_STATIC_DIR = os.path.join(config.BASE_DIR, "static")
_DEFAULTS = {
    "banner-logo.png": os.path.join(_STATIC_DIR, "img"),
    "icon-192.png": _STATIC_DIR,
    "icon-512.png": _STATIC_DIR,
}
_ICON_SIZES = {"icon-192.png": 192, "icon-512.png": 512}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Covers the custom branding folder.
_lock = threading.Lock()


def location(name):
    """(folder, file name) of the image to serve, or None for an unknown name."""
    if name not in _DEFAULTS:
        return None
    if os.path.isfile(os.path.join(config.CUSTOM_BRANDING_DIR, name)):
        return config.CUSTOM_BRANDING_DIR, name
    return _DEFAULTS[name], name


def custom_groups():
    """{group: whether it uses uploaded images}"""
    return {group: all(os.path.isfile(os.path.join(config.CUSTOM_BRANDING_DIR, name)) for name in names)
            for group, names in GROUPS.items()}


def save(group, files):
    """Use uploaded images for `group`. `files` maps each of its file names to
    the PNG's bytes, or None when it is missing."""
    checked = {name: _check_png(name, files.get(name)) for name in _names(group)}
    with _lock:
        os.makedirs(config.CUSTOM_BRANDING_DIR, exist_ok=True)
        for name, data in checked.items():
            write_atomic_bytes(os.path.join(config.CUSTOM_BRANDING_DIR, name), data)


def reset(group):
    """Go back to the images the panel comes with."""
    names = _names(group)
    with _lock:
        for name in names:
            try:
                os.remove(os.path.join(config.CUSTOM_BRANDING_DIR, name))
            except FileNotFoundError:
                pass


def _names(group):
    if group not in GROUPS:
        raise ChangeRejected(t("api.branding_unknown"))
    return GROUPS[group]


def _check_png(name, data):
    if data is None:
        raise ChangeRejected(t("api.branding_file_missing", file=name))
    if len(data) > FILE_MAX_BYTES:
        raise ChangeRejected(t("api.branding_file_too_large", file=name, max=FILE_MAX_BYTES // 1024))
    # A PNG starts with its signature, then the IHDR chunk: length (13),
    # type, width and height as big-endian 32-bit integers.
    size = None
    if len(data) >= 24 and data.startswith(_PNG_SIGNATURE) and data[12:16] == b"IHDR":
        size = struct.unpack(">II", data[16:24])
    if name in _ICON_SIZES:
        side = _ICON_SIZES[name]
        if size != (side, side):
            raise ChangeRejected(t("api.branding_icon_invalid", file=name, size=side))
    else:
        max_width, max_height = BANNER_MAX_SIZE
        if size is None or not (0 < size[0] <= max_width and 0 < size[1] <= max_height):
            raise ChangeRejected(t("api.branding_banner_invalid", file=name, width=max_width, height=max_height))
    return data
