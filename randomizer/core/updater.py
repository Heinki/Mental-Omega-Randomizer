"""GitHub-only update discovery, persistent notices, and verified staging.

This module deliberately has no game/config imports: the copied update helper
must run before the normal launcher loads its bundled configuration.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .storage import atomic_write_json, read_json_object
from .update_profile import APWORLD_NAME, EXECUTABLE_NAME, REPOSITORY


MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 512 * 1024 * 1024


def version_key(value):
    """Compare dotted release versions numerically, including v-prefixed tags."""
    if not isinstance(value, str) or not re.fullmatch(r'[vV]?\d+(?:\.\d+){0,3}', value):
        raise ValueError(f'Unsupported release version: {value!r}')
    parts = tuple(int(part) for part in value.lstrip('vV').split('.'))
    return parts + (0,) * (4 - len(parts))


def _validate_transport_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host in {'api.github.com', 'github.com'}
                    or host.endswith('.githubusercontent.com'))):
        raise ValueError('Update URL must use GitHub HTTPS hosting.')


class _GitHubRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        _validate_transport_url(url)
        return super().redirect_request(request, response, code, message, headers, url)


def _open(url):
    _validate_transport_url(url)
    request = Request(url, headers={
        'User-Agent': f'{EXECUTABLE_NAME}-Updater',
        'Accept': 'application/vnd.github+json' if urlsplit(url).hostname == 'api.github.com'
                  else 'application/octet-stream',
    })
    return build_opener(_GitHubRedirect()).open(request, timeout=15)


def _json_from_url(url):
    with _open(url) as response:
        raw = response.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError('Release metadata exceeds the size limit.')
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Release metadata must be a JSON object.')
    return value


@dataclass(frozen=True)
class UpdateAsset:
    name: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    tag: str
    assets: tuple[UpdateAsset, ...]


def check_latest_release(installed_version):
    """Accept only complete, stable releases from this product's repository."""
    release = _json_from_url(f'https://api.github.com/repos/{REPOSITORY}/releases/latest')
    if release.get('draft') or release.get('prerelease'):
        return None
    tag = release.get('tag_name', '')
    if version_key(tag) <= version_key(installed_version):
        return None
    raw_assets = release.get('assets')
    if not isinstance(raw_assets, list):
        raise ValueError('Release has no asset list.')
    assets = {}
    prefix = f'https://github.com/{REPOSITORY}/releases/download/{quote(tag, safe="")}/'
    for asset in raw_assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get('name')
        if name not in {'release_manifest.json', EXECUTABLE_NAME, APWORLD_NAME}:
            continue
        if name in assets:
            raise ValueError('Release contains duplicate update assets.')
        url = asset.get('browser_download_url', '')
        if url != prefix + quote(name, safe=''):
            raise ValueError('Release asset does not belong to the selected release.')
        assets[name] = asset
    if not all(name in assets for name in ('release_manifest.json', EXECUTABLE_NAME, APWORLD_NAME)):
        raise ValueError('Release is missing its launcher, APWorld, or update manifest.')
    manifest = _json_from_url(assets['release_manifest.json']['browser_download_url'])
    version = manifest.get('launcher_version', '')
    if manifest.get('format') != 1 or version_key(version) != version_key(tag):
        raise ValueError('Release manifest version does not match its GitHub tag.')
    hashes = manifest.get('files')
    if not isinstance(hashes, dict):
        raise ValueError('Release manifest has no file checksums.')
    selected = []
    for name in (EXECUTABLE_NAME, APWORLD_NAME):
        checksum = hashes.get(name, '')
        size = assets[name].get('size')
        if not isinstance(checksum, str) or not re.fullmatch('[0-9a-fA-F]{64}', checksum):
            raise ValueError(f'Release has no valid SHA-256 for {name}.')
        if type(size) is not int or not 0 < size <= MAX_ASSET_BYTES:
            raise ValueError(f'Release asset size is invalid: {name}.')
        selected.append(UpdateAsset(name, assets[name]['browser_download_url'], size, checksum.lower()))
    return AvailableUpdate(version, tag, tuple(selected))


def update_state_path(app_dir):
    return Path(app_dir) / 'updates' / 'state.json'


def load_update_state(app_dir):
    try:
        return read_json_object(update_state_path(app_dir))
    except (OSError, ValueError):
        return {}


def notice_shown(app_dir, version):
    """Persist by numeric version, so retagging v1.2 as 1.2 cannot nag again."""
    key = '.'.join(map(str, version_key(version)))
    versions = load_update_state(app_dir).get('notified_versions', [])
    return isinstance(versions, list) and key in versions


def remember_notice(app_dir, version):
    state = load_update_state(app_dir)
    versions = state.get('notified_versions', [])
    if not isinstance(versions, list):
        versions = []
    key = '.'.join(map(str, version_key(version)))
    if key not in versions:
        versions.append(key)
    state['notified_versions'] = versions
    atomic_write_json(update_state_path(app_dir), state)


def file_sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage_update(update, app_dir, executable, progress=None):
    """Download complete files beside persistent data, without replacing anything."""
    executable = Path(executable).resolve()
    if executable.name != EXECUTABLE_NAME:
        raise ValueError(f'Automatic updates require the filename {EXECUTABLE_NAME}.')
    # Probe the actual installation directory before asking the launcher to exit.
    with tempfile.TemporaryFile(dir=executable.parent):
        pass
    root = Path(app_dir) / 'updates'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='update-', dir=root)).resolve()
    try:
        files = []
        total = sum(asset.size for asset in update.assets)
        completed = 0
        for asset in update.assets:
            destination = directory / asset.name
            digest = hashlib.sha256()
            count = 0
            deadline = time.monotonic() + 600
            with _open(asset.url) as response, destination.open('xb') as stream:
                while chunk := response.read(256 * 1024):
                    count += len(chunk)
                    if count > asset.size or time.monotonic() > deadline:
                        raise ValueError(f'Download exceeded its size or time limit: {asset.name}.')
                    stream.write(chunk)
                    digest.update(chunk)
                    if progress:
                        progress(f'Downloading {asset.name}', completed + count, total)
            if count != asset.size or digest.hexdigest() != asset.sha256:
                raise ValueError(f'Download verification failed: {asset.name}. Your installation is unchanged.')
            completed += count
            files.append({'name': asset.name, 'sha256': asset.sha256})
        request = directory / 'request.json'
        atomic_write_json(request, {
            'format': 1,
            'parent_pid': os.getpid(),
            'target': str(executable),
            'version': update.version,
            'files': files,
        })
        return request
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def fresh_process_environment():
    """A copied/restarted one-file executable needs a new extraction lifecycle."""
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith('_PYI_')}
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return environment


def start_update_helper(request):
    """Run a copy of the old launcher, independent of its locked executable."""
    request = Path(request)
    helper = request.parent / 'update-helper.exe'
    shutil.copy2(sys.executable, helper)
    return subprocess.Popen(
        [str(helper), '--apply-update', str(request)],
        cwd=Path(sys.executable).resolve().parent,
        env=fresh_process_environment(),
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        close_fds=True,
    )
