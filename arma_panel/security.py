"""Authentication, CSRF protection, login rate limiting and response headers."""

import hmac
import os
import secrets
import time
from functools import wraps

import bcrypt
from flask import jsonify, request, session

from . import config
from .log import logger

LOGIN_WINDOW_SEC = 60.0
LOGIN_MAX_ATTEMPTS = 5

_login_buckets: dict[str, list[float]] = {}


def load_or_create_secret(path):
    """Persistent secret key so sessions survive panel restarts."""
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read().strip()
                if len(data) >= 32:
                    return data
    except OSError:
        pass
    data = secrets.token_bytes(48)
    try:
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, 0o600)
    except OSError as e:
        logger.warning("could not persist session secret (%s); using ephemeral one.", e)
    return data


def client_ip():
    # Honor X-Forwarded-For only when behind a reverse proxy; otherwise use remote_addr
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip() or "unknown"


def login_rate_ok(ip: str) -> bool:
    now = time.time()
    bucket = [t for t in _login_buckets.get(ip, []) if now - t < LOGIN_WINDOW_SEC]
    if len(bucket) >= LOGIN_MAX_ATTEMPTS:
        _login_buckets[ip] = bucket
        return False
    bucket.append(now)
    _login_buckets[ip] = bucket
    return True


def verify_password(plain: str) -> bool:
    if not plain:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), config.PANEL_PASSWORD_HASH.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def is_logged_in() -> bool:
    return bool(session.get("logged_in"))


def ensure_csrf() -> str:
    tok = session.get("csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["csrf"] = tok
    return tok


def login_required(view):
    """Answer 401 to API calls made without a logged-in session."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapper


def csrf_protected(view):
    """Check the CSRF token from the X-CSRF-Token header or the `_csrf` body
    field before running a state-changing view."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = session.get("csrf")
        supplied = (
            request.headers.get("X-CSRF-Token", "")
            or (request.get_json(silent=True) or {}).get("_csrf", "")
            or request.form.get("_csrf", "")
        )
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return jsonify({"ok": False, "error": "CSRF token invalid"}), 403
        return view(*args, **kwargs)
    return wrapper


def add_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp
