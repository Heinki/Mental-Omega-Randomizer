"""Persistent, bounded diagnostics for support and play-session debugging."""
import json
import logging
import os
import sys

from randomizer_paths import FROZEN, GAME_ROOT, LAUNCHER_LOG


SESSION_ID = os.urandom(4).hex()
LOGGER = logging.getLogger('mental_omega_randomizer')
MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 4


def rotate_log_at_startup():
    """Bound diagnostics without importing logging.handlers and its network stack."""
    try:
        if not LAUNCHER_LOG.exists() or LAUNCHER_LOG.stat().st_size < MAX_LOG_BYTES:
            return
        for index in range(LOG_BACKUP_COUNT, 0, -1):
            source = (
                LAUNCHER_LOG
                if index == 1
                else LAUNCHER_LOG.with_name(f'{LAUNCHER_LOG.name}.{index - 1}')
            )
            target = LAUNCHER_LOG.with_name(f'{LAUNCHER_LOG.name}.{index}')
            if not source.exists():
                continue
            if target.exists():
                target.unlink()
            source.replace(target)
    except OSError:
        # Logging must never prevent the launcher from starting.
        pass


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
        rotate_log_at_startup()
        handler = logging.FileHandler(LAUNCHER_LOG, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | session=%(session)s | %(message)s'
        ))
        LOGGER.addHandler(handler)
    except OSError:
        LOGGER.addHandler(logging.NullHandler())
    event(
        'launcher_started',
        frozen=FROZEN,
        python=sys.version.split()[0],
        windows=str(sys.getwindowsversion()) if hasattr(sys, 'getwindowsversion') else sys.platform,
        executable=sys.executable,
        game_root=GAME_ROOT,
    )
    return LOGGER


setup_logging()
