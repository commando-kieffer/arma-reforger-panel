"""Login, logout and CSRF token endpoints."""

import time

from flask import Blueprint, jsonify, render_template, request, session

from ..security import client_ip, ensure_csrf, login_rate_ok, login_required, verify_password

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login_page():
    return render_template("login.html")


@bp.post("/login")
def login():
    ip = client_ip()
    if not login_rate_ok(ip):
        return jsonify({"ok": False, "error": "Too many attempts. Wait a minute."}), 429
    data = request.get_json(silent=True) or {}
    # bcrypt is intentionally slow — even on a successful login it adds ~100ms,
    # which is also a natural defense against brute force.
    if verify_password(data.get("password", "")):
        session.clear()
        session.permanent = True
        session["logged_in"] = True
        session["login_at"] = int(time.time())
        ensure_csrf()
        return jsonify({"ok": True, "csrf": session["csrf"]})
    return jsonify({"ok": False, "error": "Invalid password"}), 401


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/api/csrf")
@login_required
def csrf_token():
    """Front-end fetches a CSRF token after login and on tab refresh."""
    return jsonify({"csrf": ensure_csrf()})
