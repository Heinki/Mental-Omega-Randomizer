"""Load editable static configuration from source or packaged data."""

import hashlib
import json
import shutil
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from randomizer.config.schema import (
    REQUIRED_SECTIONS,
    StaticConfigError,
    validate_sections,
)
from randomizer.core.paths import APP_DIR, FROZEN, SOURCE_DIR


BUNDLED_CONFIG_DIR = SOURCE_DIR / 'configs'
STATIC_CONFIG_DIR = APP_DIR / 'configs'
BUNDLED_CONFIG_MANIFEST = BUNDLED_CONFIG_DIR / 'bundle_manifest.json'
VISIBLE_CONFIG_MANIFEST = STATIC_CONFIG_DIR / '.bundle_manifest.json'
SUPPORTED_SCHEMA_VERSION = 1
REQUIRED_STATIC_CONFIGS = tuple(REQUIRED_SECTIONS)
_PACKAGED_CONFIGS_SYNCHRONIZED = False


def _config_path(relative_path):
    relative_path = Path(relative_path)
    if relative_path.is_absolute() or '..' in relative_path.parts:
        raise StaticConfigError(f'Invalid static config path: {relative_path}')
    return STATIC_CONFIG_DIR / relative_path


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_config_manifest(path):
    try:
        document = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise StaticConfigError(f'Cannot load config bundle manifest {path}: {exc}') from exc
    if not isinstance(document, dict) or document.get('format') != 1:
        raise StaticConfigError(f'Unsupported config bundle manifest: {path}')
    files = document.get('files')
    if not isinstance(files, dict) or not files:
        raise StaticConfigError(f'Config bundle manifest has no files: {path}')
    normalized = {}
    for relative_name, expected_hash in files.items():
        relative_path = Path(str(relative_name))
        if relative_path.is_absolute() or '..' in relative_path.parts:
            raise StaticConfigError(
                f'Invalid config bundle manifest path: {relative_name}'
            )
        expected_hash = str(expected_hash).lower()
        if len(expected_hash) != 64 or any(
            character not in '0123456789abcdef' for character in expected_hash
        ):
            raise StaticConfigError(
                f'Invalid config bundle manifest hash for {relative_name}'
            )
        normalized[relative_path.as_posix()] = expected_hash
    return normalized


def _next_backup_path(path):
    base = path.with_name(path.name + '.pre-bundle-sync-backup')
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = base.with_name(f'{base.name}.{suffix}')
        suffix += 1
    return candidate


def _write_visible_manifest(files):
    VISIBLE_CONFIG_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary = VISIBLE_CONFIG_MANIFEST.with_name(
        VISIBLE_CONFIG_MANIFEST.name + '.tmp'
    )
    document = {'format': 1, 'files': files}
    temporary.write_text(json.dumps(document, indent=2), encoding='utf-8')
    temporary.replace(VISIBLE_CONFIG_MANIFEST)


def _synchronize_packaged_configs():
    """Refresh untouched packaged defaults while preserving local edits."""
    global _PACKAGED_CONFIGS_SYNCHRONIZED
    if _PACKAGED_CONFIGS_SYNCHRONIZED or not FROZEN:
        return

    bundled_hashes = _load_config_manifest(BUNDLED_CONFIG_MANIFEST)
    previous_hashes = None
    if VISIBLE_CONFIG_MANIFEST.is_file():
        try:
            previous_hashes = _load_config_manifest(VISIBLE_CONFIG_MANIFEST)
        except StaticConfigError:
            backup = _next_backup_path(VISIBLE_CONFIG_MANIFEST)
            shutil.copy2(VISIBLE_CONFIG_MANIFEST, backup)

    for relative_name, bundled_hash in bundled_hashes.items():
        relative_path = Path(relative_name)
        bundled = BUNDLED_CONFIG_DIR / relative_path
        if not bundled.is_file():
            raise StaticConfigError(
                f'Packaged config listed but missing from EXE: {relative_name}'
            )
        if _file_sha256(bundled) != bundled_hash:
            raise StaticConfigError(
                f'Packaged config hash mismatch in EXE: {relative_name}'
            )

        target = STATIC_CONFIG_DIR / relative_path
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled, target)
            continue

        target_hash = _file_sha256(target)
        if previous_hashes is None:
            # One-time migration for launchers predating bundle manifests.
            # Preserve every differing visible file before activating the
            # complete, internally consistent bundled config set.
            if target_hash != bundled_hash:
                backup = _next_backup_path(target)
                shutil.copy2(target, backup)
                shutil.copy2(bundled, target)
            continue

        previous_hash = previous_hashes.get(relative_name)
        if previous_hash == target_hash and target_hash != bundled_hash:
            shutil.copy2(bundled, target)

    _write_visible_manifest(bundled_hashes)
    _PACKAGED_CONFIGS_SYNCHRONIZED = True


def _ensure_visible_config(relative_path):
    """Expose synchronized bundled defaults beside a frozen launcher."""
    _synchronize_packaged_configs()
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
