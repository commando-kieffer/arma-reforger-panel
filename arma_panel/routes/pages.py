"""The panel page and the PWA files that have to live at the site root."""

from flask import Blueprint, current_app, redirect, render_template, send_from_directory

from ..security import ensure_csrf, is_logged_in

bp = Blueprint("pages", __name__)


@bp.get("/manifest.json")
def manifest():
    return send_from_directory(current_app.static_folder, "manifest.json",
                               mimetype="application/manifest+json")


@bp.get("/service-worker.js")
def service_worker():
    # Served from the root rather than /static/ so the worker's scope is the whole panel.
    return send_from_directory(current_app.static_folder, "service-worker.js",
                               mimetype="application/javascript")


@bp.get("/")
def index():
    if not is_logged_in():
        return redirect("/login")
    ensure_csrf()
    return render_template("index.html")
