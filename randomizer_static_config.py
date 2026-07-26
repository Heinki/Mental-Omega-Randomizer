"""Load editable static configuration from source or packaged data."""

import json
import shutil
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from randomizer_config_schema import (
    REQUIRED_SECTIONS,
    StaticConfigError,
    validate_sections,
)
from randomizer_paths import APP_DIR, FROZEN, SOURCE_DIR


BUNDLED_CONFIG_DIR = SOURCE_DIR / 'configs'
STATIC_CONFIG_DIR = APP_DIR / 'configs'
SUPPORTED_SCHEMA_VERSION = 1
REQUIRED_STATIC_CONFIGS = tuple(REQUIRED_SECTIONS)


def _config_path(relative_path):
    relative_path = Path(relative_path)
    if relative_path.is_absolute() or '..' in relative_path.parts:
        raise StaticConfigError(f'Invalid static config path: {relative_path}')
    return STATIC_CONFIG_DIR / relative_path


def _ensure_visible_config(relative_path):
    """Expose bundled defaults beside a frozen launcher without overwriting."""
    target = _config_path(relative_path)
    if target.is_file() or not FROZEN:
        return target

    bundled = BUNDLED_CONFIG_DIR / relative_path
    if not bundled.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled, target)
    return target


def _load_static_config_sections(relative_path, path):
    """Read and validate one resolved static-config file."""
    if not path.is_file():
        raise StaticConfigError(f'Required static config is missing: {path}')
    try:
        document = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise StaticConfigError(f'Cannot load static config {path}: {exc}') from exc
    if not isinstance(document, dict):
        raise StaticConfigError(f'Static config root must be an object: {path}')

    version = document.get('schema_version')
    if version != SUPPORTED_SCHEMA_VERSION:
        raise StaticConfigError(
            f'Unsupported schema_version {version!r} in {path}; '
            f'expected {SUPPORTED_SCHEMA_VERSION}'
        )
    sections = document.get('sections')
    if not isinstance(sections, dict):
        raise StaticConfigError(f'Static config sections must be an object: {path}')
    validate_sections(relative_path, sections, path)
    return sections


@lru_cache(maxsize=None)
def _load_static_config_cached(relative_path):
    """Load one static JSON document and recover frozen stale overrides."""
    path = _ensure_visible_config(relative_path)
    try:
        return _load_static_config_sections(relative_path, path)
    except StaticConfigError:
        # Frozen upgrades keep editable configs in RandomizerLauncherData.
        # Preserve an invalid old/user copy, then recover from bundled defaults.
        bundled = BUNDLED_CONFIG_DIR / Path(relative_path)
        if not FROZEN or not bundled.is_file() or path == bundled:
            raise
        bundled_sections = _load_static_config_sections(relative_path, bundled)
        backup = path.with_name(path.name + '.invalid-backup')
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        shutil.copy2(bundled, path)
        return bundled_sections


def load_static_config(relative_path):
    """Return an isolated copy so runtime derivation cannot mutate cached data."""
    return deepcopy(_load_static_config_cached(relative_path))


load_static_config.cache_clear = _load_static_config_cached.cache_clear


def static_config_section(relative_path, section, expected_type):
    """Return one required section with a clear type-validation error."""
    sections = load_static_config(relative_path)
    if section not in sections:
        raise StaticConfigError(f'Missing section {section!r} in {relative_path}')
    value = sections[section]
    if not isinstance(value, expected_type):
        expected_name = getattr(expected_type, '__name__', str(expected_type))
        raise StaticConfigError(
            f'Section {section!r} in {relative_path} must be {expected_name}'
        )
    return value


def validate_static_configs(relative_paths):
    """Load required documents, returning their resolved visible paths."""
    paths = []
    for relative_path in relative_paths:
        load_static_config(relative_path)
        paths.append(_config_path(relative_path))
    return paths
