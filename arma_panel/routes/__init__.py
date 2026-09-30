"""Flask blueprints, one per area of the panel."""

from . import auth, monitoring, mods, pages, persistence, scenarios, server, server_config

BLUEPRINTS = (
    pages.bp,
    auth.bp,
    monitoring.bp,
    server.bp,
    server_config.bp,
    mods.bp,
    persistence.bp,
    scenarios.bp,
)


def register_blueprints(app):
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
