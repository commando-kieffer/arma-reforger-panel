"""Arma Reforger server management panel.

Layout:
  config.py    settings read from config.env
  security.py  authentication, CSRF and rate limiting
  services/    game server process, config.json, mods, saves, scenarios, logs
  routes/      Flask blueprints exposing the pages and the JSON API
"""

import os

from flask import Flask

from . import config
from .routes import register_blueprints
from .security import add_security_headers, load_or_create_secret


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(config.BASE_DIR, "static"),
        template_folder=os.path.join(config.BASE_DIR, "templates"),
    )
    app.secret_key = load_or_create_secret(config.SECRET_FILE)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=False,  # set True if you put HTTPS in front
        PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # 2 MB cap on uploads
    )
    app.after_request(add_security_headers)
    register_blueprints(app)
    return app
