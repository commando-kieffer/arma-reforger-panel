"""Arma Reforger server management panel.

Layout:
  config.py    settings read from config.env
  i18n.py      interface translations (translations/*.json)
  security.py  authentication, CSRF and rate limiting
  themes.py    panel styles (static/css/<theme>/)
  services/    game server process, config.json, mods, saves, scenarios, logs,
               panel settings
  routes/      Flask blueprints exposing the pages and the JSON API
"""

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config, i18n
from .routes import register_blueprints
from .security import SessionInterface, add_security_headers, load_or_create_secret


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(config.BASE_DIR, "static"),
        template_folder=os.path.join(config.BASE_DIR, "templates"),
    )
    app.secret_key = load_or_create_secret(config.SECRET_FILE)
    app.session_interface = SessionInterface()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2 MB cap on uploads
    )
    if config.PANEL_BEHIND_PROXY:
        # One proxy (nginx) in front: trust the last address it added to
        # X-Forwarded-For, and the scheme the browser used.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.after_request(add_security_headers)
    i18n.init_app(app)
    register_blueprints(app)
    return app
