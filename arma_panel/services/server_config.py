"""Reading and writing the dedicated server's config.json."""

import json

from .. import config


def read_config():
    try:
        with open(config.SERVER_CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def write_config(cfg):
    with open(config.SERVER_CONFIG, "w") as f:
        json.dump(cfg, f, indent="\t")
