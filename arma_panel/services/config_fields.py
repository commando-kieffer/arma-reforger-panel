"""Settings edited through the panel forms, with the types, ranges and
defaults given by the Bohemia wiki (Arma_Reforger:Server_Config).

A key missing from config.json is shown with its default and only written
once the user sets a different value, so saving a form doesn't fill the file
with defaults nobody chose.
"""

from dataclasses import dataclass

from ..i18n import t
from .server_config import ChangeRejected

_MISSING = object()


class FieldError(ValueError):
    """A value sent by a form is invalid; the message is ready to display."""


@dataclass(frozen=True)
class Field:
    path: tuple          # keys leading to the value in config.json
    kind: type           # bool or int
    default: object
    ranges: tuple = ()   # allowed (low, high) ranges for ints; high None means no limit

    @property
    def key(self):
        return self.path[-1]

    def read(self, cfg):
        """Value stored in cfg, or the default if it's missing or of the wrong type."""
        value = _get(cfg, self.path)
        return value if _has_kind(value, self.kind) else self.default

    def parse(self, raw):
        """Check a value sent by a form. Raises FieldError."""
        if not _has_kind(raw, self.kind):
            key = "api.field_not_bool" if self.kind is bool else "api.field_not_int"
            raise FieldError(t(key, field=self.key))
        if self.ranges and not any(low <= raw and (high is None or raw <= high) for low, high in self.ranges):
            raise FieldError(t("api.field_range", field=self.key, allowed=self._describe_ranges()))
        return raw

    def _describe_ranges(self):
        parts = []
        for low, high in self.ranges:
            if high is None:
                parts.append(f"≥ {low}")
            elif low == high:
                parts.append(str(low))
            else:
                parts.append(f"{low}–{high}")
        return ", ".join(parts)


# Server Configuration card.
SERVER_FIELDS = {
    "max_players":    Field(("game", "maxPlayers"), int, 64, ((1, 128),)),
    "visible":        Field(("game", "visible"), bool, True),
    "cross_platform": Field(("game", "crossPlatform"), bool, False),
}


def form_values(cfg, fields):
    return {name: field.read(cfg) for name, field in fields.items()}


def parse_form(fields, data):
    """{name: value} for the fields present in `data`. Raises FieldError."""
    return {name: field.parse(data[name]) for name, field in fields.items() if name in data}


def apply(cfg, fields, values):
    """Write the parsed `values` into cfg and return the names actually written.

    A value equal to what's already stored is skipped, and so is a default
    value for a key the file doesn't have.
    """
    written = []
    for name, value in values.items():
        field = fields[name]
        stored = _get(cfg, field.path)
        if stored is _MISSING and value == field.default:
            continue
        if stored is not _MISSING and type(stored) is type(value) and stored == value:
            continue
        _set(cfg, field.path, value)
        written.append(name)
    return written


def _has_kind(value, kind):
    # bool is a subclass of int, so check it explicitly both ways.
    if kind is bool:
        return isinstance(value, bool)
    return isinstance(value, int) and not isinstance(value, bool)


def _get(cfg, path):
    node = cfg
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _set(cfg, path, value):
    node = cfg
    for i, part in enumerate(path[:-1]):
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ChangeRejected(t("api.config_unexpected", path=".".join(path[:i + 1])))
    node[path[-1]] = value
