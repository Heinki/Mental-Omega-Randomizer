"""Atomic Shop profile/run persistence with write-ahead recovery."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import threading

from randomizer.core.paths import (
    BACKUP_DIR,
    SHOP_PROFILE_PATH,
    SHOP_RUN_PATH,
    SHOP_TRANSACTION_PATH,
)
from randomizer.core.storage import atomic_write_json, read_json_object

from .state import normalize_shop_profile, normalize_shop_run


SHOP_TRANSACTION_SCHEMA_VERSION = 1


class ShopPersistenceError(RuntimeError):
    """Raised when durable Shop state cannot be read or recovered safely."""


@dataclass(frozen=True)
class ShopPersistencePaths:
    profile: Path
    run: Path
    transaction: Path
    backup_dir: Path


DEFAULT_SHOP_PATHS = ShopPersistencePaths(
    profile=SHOP_PROFILE_PATH,
    run=SHOP_RUN_PATH,
    transaction=SHOP_TRANSACTION_PATH,
    backup_dir=BACKUP_DIR / 'shop',
)

# Permanent progression is personal; solo and co-op runs have separate journals.
COOP_SHOP_PATHS = ShopPersistencePaths(
    profile=SHOP_PROFILE_PATH,
    run=SHOP_RUN_PATH.with_name('shop_coop_run.json'),
    transaction=SHOP_TRANSACTION_PATH.with_name('shop_coop_transaction.json'),
    backup_dir=BACKUP_DIR / 'shop_coop',
)


def _next_backup_path(path, backup_dir, *, suffix='invalid-backup'):
    backup_dir.mkdir(parents=True, exist_ok=True)
    base = backup_dir / f'{path.name}.{suffix}'
    candidate = base
    number = 2
    while candidate.exists():
        candidate = backup_dir / f'{base.name}.{number}'
        number += 1
    return candidate


def _backup_invalid(path, backup_dir):
    if not path.is_file():
        return None
    backup = _next_backup_path(path, backup_dir)
    shutil.copy2(path, backup)
    return backup


class ShopRepository:
    """Own Shop files and replay interrupted two-file commits exactly."""

    def __init__(self, paths=DEFAULT_SHOP_PATHS):
        self.paths = paths
        self._lock = threading.RLock()

    def _raise_invalid(self, label, path, error):
        try:
            backup = _backup_invalid(path, self.paths.backup_dir)
        except OSError as backup_error:
            raise ShopPersistenceError(
                f'Cannot load {label} {path}: {error}. '
                f'Backup also failed: {backup_error}'
            ) from error
        backup_text = f' Backup preserved at {backup}.' if backup else ''
        raise ShopPersistenceError(
            f'Cannot load {label} {path}: {error}.{backup_text}'
        ) from error

    def _read_profile(self):
        if not self.paths.profile.is_file():
            return normalize_shop_profile()
        try:
            raw = read_json_object(self.paths.profile)
            profile = normalize_shop_profile(raw)
        except Exception as exc:
            self._raise_invalid('Shop profile', self.paths.profile, exc)
        normalized = profile.to_dict()
        if raw != normalized:
            atomic_write_json(self.paths.profile, normalized, indent=None)
        return profile

    def _read_run(self):
        if not self.paths.run.is_file():
            return None
        try:
            raw = read_json_object(self.paths.run)
            run = normalize_shop_run(raw)
        except Exception as exc:
            self._raise_invalid('Shop run', self.paths.run, exc)
        normalized = run.to_dict()
        if raw != normalized:
            atomic_write_json(self.paths.run, normalized, indent=None)
        return run

    def load_profile(self):
        with self._lock:
            self.recover_pending_transaction()
            return self._read_profile()

    def load_run(self):
        with self._lock:
            self.recover_pending_transaction()
            return self._read_run()

    def load(self):
        with self._lock:
            self.recover_pending_transaction()
            return self._read_profile(), self._read_run()

    def save_profile(self, profile):
        with self._lock:
            self.recover_pending_transaction()
            normalized = normalize_shop_profile(profile.to_dict())
            atomic_write_json(
                self.paths.profile, normalized.to_dict(), indent=None
            )

    def save_run(self, run):
        with self._lock:
            self.recover_pending_transaction()
            normalized = normalize_shop_run(run.to_dict())
            atomic_write_json(self.paths.run, normalized.to_dict(), indent=None)

    def prepare_commit(self, profile, run, transaction_id):
        """Durably record exact targets before either state file changes."""
        with self._lock:
            self.recover_pending_transaction()
            transaction_id = str(transaction_id or '')
            if not transaction_id:
                raise ValueError('Shop transaction_id must be non-empty')
            normalized_profile = normalize_shop_profile(profile.to_dict())
            normalized_run = (
                None if run is None else normalize_shop_run(run.to_dict())
            )
            document = {
                'schema_version': SHOP_TRANSACTION_SCHEMA_VERSION,
                'transaction_id': transaction_id,
                'profile': normalized_profile.to_dict(),
                'run': (
                    None if normalized_run is None else normalized_run.to_dict()
                ),
            }
            atomic_write_json(self.paths.transaction, document, indent=None)

    def recover_pending_transaction(self):
        """Replay one journal until both exact target documents are durable."""
        with self._lock:
            if not self.paths.transaction.is_file():
                return False
            try:
                document = read_json_object(self.paths.transaction)
                if document.get('schema_version') != SHOP_TRANSACTION_SCHEMA_VERSION:
                    raise ValueError(
                        'Unsupported Shop transaction schema_version '
                        f'{document.get("schema_version")!r}'
                    )
                if not isinstance(document.get('transaction_id'), str) or not document[
                    'transaction_id'
                ]:
                    raise ValueError('Shop transaction_id must be non-empty')
                if 'run' not in document:
                    raise ValueError('Shop transaction has no run target')
                profile = normalize_shop_profile(document.get('profile'))
                run_document = document['run']
                run = (
                    None
                    if run_document is None
                    else normalize_shop_run(run_document)
                )
            except Exception as exc:
                self._raise_invalid(
                    'Shop transaction', self.paths.transaction, exc
                )
            atomic_write_json(self.paths.profile, profile.to_dict(), indent=None)
            if run is None:
                self.paths.run.unlink(missing_ok=True)
            else:
                atomic_write_json(self.paths.run, run.to_dict(), indent=None)
            self.paths.transaction.unlink(missing_ok=True)
            return True

    def commit(self, profile, run, transaction_id):
        with self._lock:
            self.prepare_commit(profile, run, transaction_id)
            self.recover_pending_transaction()


def shop_repository_for_mode(*, coop_mode):
    """Select a run journal and preserve co-op saves from the shared-file era."""
    solo = ShopRepository()
    coop = ShopRepository(COOP_SHOP_PATHS)
    # Recover both journals before migrating a run or reading the shared profile.
    solo.recover_pending_transaction()
    coop.recover_pending_transaction()
    legacy_run = solo.load_run()
    if (legacy_run is not None and legacy_run.eligible_mission_codes
            and all(code.startswith('COOP_')
                    for code in legacy_run.eligible_mission_codes)):
        destination = coop.paths.run
        if destination.exists():
            destination = _next_backup_path(
                solo.paths.run, coop.paths.backup_dir,
                suffix='coop-migration-backup',
            )
        solo.paths.run.replace(destination)
    return coop if coop_mode else solo
