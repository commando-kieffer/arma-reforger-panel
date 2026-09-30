"""Interface translations.

Catalogs live in translations/<lang>.json. Keys are dotted paths into the
JSON ("mods.added"), placeholders are written {name}, and messages that
depend on a count have `one` / `other` variants. The page embeds the catalog
of the active language so the front-end uses the same strings (see
static/js/i18n.js).

The language comes from the `lang` cookie set by the language switch and
defaults to English. Missing keys fall back to English, then to the key.
"""

import json
import os
import re

from flask import has_request_context, request

LANGUAGES = ("en", "fr")
DEFAULT_LANGUAGE = "en"
COOKIE_NAME = "lang"

_TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations")
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# CLDR plural categories for integers: French treats 0 as singular.
_PLURAL_RULES = {
    "en": lambda n: "one" if n == 1 else "other",
    "fr": lambda n: "one" if n in (0, 1) else "other",
}


def _flatten(tree, prefix=""):
    flat = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def _load_catalogs():
    catalogs = {}
    for lang in LANGUAGES:
        with open(os.path.join(_TRANSLATIONS_DIR, f"{lang}.json"), encoding="utf-8") as f:
            catalogs[lang] = _flatten(json.load(f))
    return catalogs


_catalogs = _load_catalogs()


def get_language():
    if not has_request_context():
        return DEFAULT_LANGUAGE
    lang = request.cookies.get(COOKIE_NAME, "")
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def _format(template, params):
    return _PLACEHOLDER_RE.sub(
        lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0),
        template,
    )


def t(key, **params):
    """Translate `key` into the request's language."""
    lang = get_language()
    template = _catalogs[lang].get(key) or _catalogs[DEFAULT_LANGUAGE].get(key) or key
    return _format(template, params)


def tn(key, count, **params):
    """Translate a count-dependent message; `count` is also available as {count}."""
    lang = get_language()
    plural_key = f"{key}.{_PLURAL_RULES[lang](count)}"
    if plural_key not in _catalogs[lang] and plural_key not in _catalogs[DEFAULT_LANGUAGE]:
        plural_key = f"{key}.other"
    return t(plural_key, count=count, **params)


def client_payload():
    """Data embedded in each page for static/js/i18n.js."""
    lang = get_language()
    messages = {**_catalogs[DEFAULT_LANGUAGE], **_catalogs[lang]}
    return {"lang": lang, "locale": messages["meta.locale"], "messages": messages}


def init_app(app):
    @app.context_processor
    def inject_i18n():
        return {
            "t": t,
            "lang": get_language(),
            "languages": LANGUAGES,
            "i18n_payload": client_payload(),
        }
