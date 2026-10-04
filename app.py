"""
Arma Reforger Server Management Panel
https://github.com/mateuszgolebiewski-code/arma-reforger-panel

Local fork — modifications:
  - Bcrypt-hashed admin password + constant-time verification + rate limiting
  - CSRF protection on state-changing routes
  - Persistent SECRET_KEY (sessions survive panel restart)
  - Bulk mod import via pasted JSON array or uploaded JSON file
  - Auto-discovery of scenarios from installed mods (`.pak` strings scan, mtime-cached)

This file is the entry point systemd runs (see install.sh); the application
itself lives in the `arma_panel` package.
"""

from arma_panel import config, create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=config.PANEL_HOST, port=config.PANEL_PORT, threaded=True)
