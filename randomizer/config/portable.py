"""Portable launcher-settings documents for sharing identical setups."""

from pathlib import Path

from randomizer.core.storage import atomic_write_json, read_json_object

from .player import (
    DEFAULT_CONFIG,
    deep_copy,
    deep_merge,
    migrate_loaded_config,
)


PORTABLE_SETTINGS_FORMAT = 'mental-omega-randomizer-settings'
PORTABLE_SETTINGS_VERSION = 1


def write_portable_settings(path, config):
    """Write all launcher options without active run/progress state."""
    document = {
        'format': PORTABLE_SETTINGS_FORMAT,
        'version': PORTABLE_SETTINGS_VERSION,
        'settings': deep_copy(config),
    }
    atomic_write_json(Path(path), document)


def read_portable_settings(path):
    """Load, migrate, and default-fill one portable settings document."""
    document = read_json_object(Path(path))
    if document.get('format') != PORTABLE_SETTINGS_FORMAT:
        raise ValueError('Not a Mental Omega Randomizer settings file.')
    if document.get('version') != PORTABLE_SETTINGS_VERSION:
        raise ValueError(
            'Unsupported settings file version: '
            f'{document.get("version")!r}.'
        )
    settings = document.get('settings')
    if not isinstance(settings, dict):
        raise ValueError('Portable settings payload must be an object.')
    settings = deep_copy(settings)
    migrate_loaded_config(settings)
    return deep_merge(DEFAULT_CONFIG, settings)
