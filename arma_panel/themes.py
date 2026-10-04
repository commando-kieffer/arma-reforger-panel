"""Panel styles.

Each theme has its own folder of stylesheets, static/css/<id>/, holding
base.css (shared by every page), login.css and panel.css. The theme in use is
a panel setting (see services/panel_settings.py): it is the same for
everyone.
"""

from collections import namedtuple

# fonts: Google Fonts stylesheet loaded before the theme's CSS, or None.
# color: browser UI color (<meta name="theme-color">).
Theme = namedtuple("Theme", "id name fonts color")

THEMES = (
    Theme(
        id="zeus",
        name="Commando Kieffer - Zeus",
        fonts="https://fonts.googleapis.com/css2?family=Spectral:wght@300;700"
              "&family=Roboto+Mono:wght@400;500&display=swap",
        color="#0F0E33",
    ),
)

DEFAULT_THEME = "zeus"

BY_ID = {theme.id: theme for theme in THEMES}
