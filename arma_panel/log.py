"""Logger shared by the panel modules.

Messages go to stdout with a "[panel]" prefix so they end up in
`journalctl -u arma-panel` alongside the Flask request log.
"""

import logging
import sys

logger = logging.getLogger("arma_panel")

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[panel] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
