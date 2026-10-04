import os
import struct
import tempfile
import unittest
import zlib
from unittest import mock

from arma_panel import config
from arma_panel.services import branding
from arma_panel.services.server_config import ChangeRejected


def png(width, height):
    """A blank RGBA PNG of the given size."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b""))


ICONS = {"icon-192.png": png(192, 192), "icon-512.png": png(512, 512)}
BANNER = {"banner-logo.png": png(600, 150)}


class BrandingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.join(tmp.name, "custom-branding")
        patcher = mock.patch.object(config, "CUSTOM_BRANDING_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, name):
        folder, file = branding.location(name)
        with open(os.path.join(folder, file), "rb") as f:
            return folder, f.read()

    def test_defaults_exist_and_are_served_first(self):
        self.assertEqual(branding.custom_groups(), {"banner": False, "icons": False})
        for names in branding.GROUPS.values():
            for name in names:
                folder, data = self.read(name)
                self.assertNotEqual(folder, self.dir)
                self.assertTrue(data.startswith(b"\x89PNG"))
        self.assertIsNone(branding.location("../config.env"))
        self.assertIsNone(branding.location("manifest.json"))

    def test_groups_are_replaced_and_reset_separately(self):
        branding.save("icons", ICONS)
        self.assertEqual(branding.custom_groups(), {"banner": False, "icons": True})
        branding.save("banner", BANNER)
        self.assertEqual(branding.custom_groups(), {"banner": True, "icons": True})
        self.assertEqual(self.read("icon-512.png"), (self.dir, ICONS["icon-512.png"]))
        self.assertEqual(self.read("banner-logo.png"), (self.dir, BANNER["banner-logo.png"]))
        branding.reset("icons")
        self.assertEqual(branding.custom_groups(), {"banner": True, "icons": False})
        self.assertNotEqual(self.read("icon-192.png")[0], self.dir)
        branding.reset("icons")  # nothing left to remove

    def test_invalid_icons_are_rejected(self):
        cases = {
            "missing": None,
            "wrong size": png(192, 192),
            "not square": png(512, 511),
            "not a png": b"GIF89a" + b"\x00" * 40,
            "truncated": png(512, 512)[:20],
            "too large": png(512, 512) + b"\x00" * branding.FILE_MAX_BYTES,
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(ChangeRejected):
                branding.save("icons", {**ICONS, "icon-512.png": data})
        self.assertFalse(os.path.exists(self.dir))

    def test_banner_size_is_bounded(self):
        branding.save("banner", {"banner-logo.png": png(1200, 300)})
        branding.save("banner", {"banner-logo.png": png(1, 1)})
        for width, height in ((1201, 300), (1200, 301)):
            with self.subTest(size=(width, height)), self.assertRaises(ChangeRejected):
                branding.save("banner", {"banner-logo.png": png(width, height)})
        with self.assertRaises(ChangeRejected):
            branding.save("banner", {"banner-logo.png": b"not a png"})

    def test_unknown_group(self):
        with self.assertRaises(ChangeRejected):
            branding.save("favicon", {})
        with self.assertRaises(ChangeRejected):
            branding.reset("../static")


if __name__ == "__main__":
    unittest.main()
