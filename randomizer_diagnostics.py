"""Persistent, bounded diagnostics for support and play-session debugging."""
import json
import logging
import platform
import sys
import uuid
from logging.handlers import RotatingFileHandler

from randomizer_paths import FROZEN, GAME_ROOT, LAUNCHER_LOG


SESSION_ID = uuid.uuid4().hex[:8]
LOGGER = logging.getLogger('mental_omega_randomizer')


def event(name, level=logging.INFO, **details):
    payload = json.dumps(details, ensure_ascii=False, sort_keys=True, default=str)
    LOGGER.log(level, '%s | %s', name, payload, extra={'session': SESSION_ID})


def setup_logging():
    if LOGGER.handlers:
        return LOGGER
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    try:
        LAUNCHER_LOG.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            LAUNCHER_LOG,
            maxBytes=2 * 1024 * 1024,
            backupCount=4,
            encoding='utf-8',
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | session=%(session)s | %(message)s'
        ))
        LOGGER.addHandler(handler)
    except OSError:
        LOGGER.addHandler(logging.NullHandler())
    event(
        'launcher_started',
        frozen=FROZEN,
        python=platform.python_version(),
        windows=platform.platform(),
        executable=sys.executable,
        game_root=GAME_ROOT,
    )
    return LOGGER


setup_logging()
