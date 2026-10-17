"""Package an existing Windows launcher using an explicit, profile-free allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from randomizer.core.version import APP_VERSION


def sha256_file(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_windows_executable(path: Path) -> None:
    """Reject a missing/non-PE input without executing the supplied launcher."""
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise ValueError('The supplied launcher is not a Windows executable.')
        offset = struct.unpack_from('<I', header, 60)[0]
        if offset < 64 or offset + 24 > path.stat().st_size:
            raise ValueError('The supplied launcher has an invalid PE header.')
        stream.seek(offset)
        pe = stream.read(24)
        if pe[:4] != b'PE\0\0' or not struct.unpack_from('<H', pe, 22)[0] & 2:
            raise ValueError('The supplied launcher is not a PE executable image.')


def source_identity() -> dict:
    def git(*arguments):
        return subprocess.check_output(
            ['git', *arguments], cwd=ROOT, text=True, encoding='utf-8',
            errors='replace', stderr=subprocess.PIPE,
        ).strip()

    commit = git('rev-parse', 'HEAD')
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', commit):
        raise ValueError('Could not identify the source Git commit.')
    return {
        'source_git_sha': commit,
        'source_dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
    }


def package(executable: Path, output: Path, provenance: str, *, network_helper=True) -> dict:
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', APP_VERSION):
        raise ValueError('APP_VERSION must be a numeric launcher version.')
    if not provenance.strip():
        raise ValueError('Build provenance must describe the supplied launcher build.')
    executable, output = executable.expanduser().resolve(), output.expanduser().resolve()
    check_windows_executable(executable)
    inputs = {
        'MentalOmegaRandomizer.exe': executable,
        'START-HERE.txt': ROOT / 'tools' / 'CHALLENGES-START-HERE.txt',
        'CHALLENGES_TESTING.md': ROOT / 'CHALLENGES_TESTING.md',
        'COOP_CONNECTION_GUIDE.md': ROOT / 'COOP_CONNECTION_GUIDE.md',
        'LICENSE': ROOT / 'LICENSE',
    }
    if network_helper:
        inputs['Setup-Private-Network.ps1'] = ROOT / 'tools' / 'Setup-Private-Network.ps1'
    for name, source in inputs.items():
        if not source.is_file():
            raise ValueError(f'Missing package input: {name}')

    name = f'MentalOmegaRandomizer-{APP_VERSION}-windows'
    release_dir, archive_path = output / name, output / (name + '.zip')
    checksums_path = output / 'SHA256SUMS'
    for destination in (release_dir, archive_path, checksums_path):
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(
                f'Release output already exists: {destination}. Choose a fresh --output directory.'
            )
    identity = source_identity()
    output.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir()
    manifest = {
        'package_format': 1,
        'app_version': APP_VERSION,
        **identity,
        'build_provenance': provenance.strip(),
        'files': {},
    }
    # Never enumerate an installation or profile directory: only these named
    # inputs can enter the release, regardless of where the EXE was built.
    for filename, source in sorted(inputs.items()):
        target = release_dir / filename
        with source.open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        manifest['files'][filename] = {
            'sha256': sha256_file(target), 'size_bytes': target.stat().st_size,
        }
    manifest_name = 'RELEASE-MANIFEST.json'
    with (release_dir / manifest_name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted([*inputs, manifest_name]):
            # Neutral, deterministic ZIP metadata carries no source paths or
            # host filesystem timestamps/permissions. Files extract at root.
            entry = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0x20
            with (release_dir / filename).open('rb') as incoming, archive.open(entry, 'w') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    archive_sha256 = sha256_file(archive_path)
    with checksums_path.open('x', encoding='ascii', newline='\n') as stream:
        stream.write(f'{archive_sha256}  {archive_path.name}\n')
    return {
        'release_directory': str(release_dir), 'zip': str(archive_path),
        'sha256sums': str(checksums_path), 'zip_sha256': archive_sha256,
        'app_version': APP_VERSION, **identity,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True, help='Already built Windows launcher EXE.')
    parser.add_argument('--output', type=Path, required=True,
                        help='Parent directory for new release artifacts; SHA256SUMS must not exist.')
    parser.add_argument('--build-provenance', required=True,
                        help='Actual build mode/tool versions; omit personal paths and connection details.')
    parser.add_argument('--without-network-helper', action='store_true',
                        help='Omit the optional private-network firewall setup script.')
    args = parser.parse_args()
    try:
        result = package(args.exe, args.output, args.build_provenance,
                         network_helper=not args.without_network_helper)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Packaging failed: {exc}\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
