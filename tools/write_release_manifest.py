"""Prepare GitHub update metadata for manually built Windows release assets."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from randomizer.core import version
from randomizer.core.storage import atomic_write_json, atomic_write_text, read_json_object
from randomizer.core.update_profile import APWORLD_NAME, EXECUTABLE_NAME
from randomizer.core.updater import file_sha256, version_key


SETUP_NAME = EXECUTABLE_NAME.removesuffix('.exe') + '-Archipelago-Setup.md'


def apworld_manifest(path):
    with ZipFile(path) as archive:
        return json.loads(archive.read(f'{Path(APWORLD_NAME).stem}/archipelago.json'))


def verify_release(output, tag=None):
    """Reject incomplete, mismatched, or damaged bundles before uploading them."""
    if tag is not None and version_key(tag) != version_key(version.APP_VERSION):
        raise ValueError(f'Release tag {tag!r} does not match APP_VERSION {version.APP_VERSION!r}.')
    manifest = read_json_object(output / 'release_manifest.json')
    if (manifest.get('format') != 1
            or version_key(manifest.get('launcher_version')) != version_key(version.APP_VERSION)
            or manifest.get('archipelago_version') != version.ARCHIPELAGO_VERSION):
        raise ValueError('Release metadata does not match the source versions.')
    hashes = manifest.get('files')
    if not isinstance(hashes, dict) or not {EXECUTABLE_NAME, APWORLD_NAME, SETUP_NAME} <= hashes.keys():
        raise ValueError('Release must include the launcher, matching APWorld, and setup guide.')
    for name, expected in hashes.items():
        if (not isinstance(name, str) or Path(name).name != name
                or '/' in name or '\\' in name
                or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)):
            raise ValueError(f'Invalid release checksum entry: {name!r}.')
        if file_sha256(output / name) != expected:
            raise ValueError(f'Release checksum mismatch: {name}.')
    checksums = {}
    for line in (output / 'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        expected, name = line.split(' *', 1)
        if name in checksums:
            raise ValueError(f'Duplicate SHA256SUMS entry: {name}.')
        checksums[name] = expected
    if checksums != {**hashes, 'release_manifest.json': file_sha256(output / 'release_manifest.json')}:
        raise ValueError('SHA256SUMS does not match the complete release manifest.')
    with (output / EXECUTABLE_NAME).open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('Launcher is not a Windows executable.')
    world = apworld_manifest(output / APWORLD_NAME)
    expected_world_version = getattr(version, 'APWORLD_VERSION', version.APP_VERSION)
    if (version_key(world.get('world_version')) != version_key(expected_world_version)
            or version_key(manifest.get('apworld_version')) != version_key(expected_world_version)
            or manifest.get('apworld_game') != world.get('game')):
        raise ValueError('APWorld archive does not match the release metadata/source versions.')
    print(f'Verified complete release v{version.APP_VERSION}: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--apworld', type=Path)
    parser.add_argument('--output-directory', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--tag', help='Require this GitHub tag to match APP_VERSION.')
    arguments = parser.parse_args()
    if arguments.verify_only:
        if arguments.output_directory is None:
            parser.error('--verify-only requires --output-directory')
        verify_release(arguments.output_directory.resolve(), arguments.tag)
        return
    if arguments.launcher is None or arguments.apworld is None:
        parser.error('creating release metadata requires --launcher and --apworld')
    if arguments.tag is not None and version_key(arguments.tag) != version_key(version.APP_VERSION):
        parser.error('--tag must match APP_VERSION')
    output = (arguments.output_directory or arguments.launcher.parent).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for source, name in ((arguments.launcher, EXECUTABLE_NAME), (arguments.apworld, APWORLD_NAME)):
        source = source.resolve(strict=True)
        destination = output / name
        if source != destination:
            shutil.copy2(source, destination)
    project = Path(__file__).resolve().parents[1]
    guide = project / 'Archipelago' / 'SETUP.md'
    if not guide.is_file():
        guide = project / 'Archipelago' / 'README.md'
    if guide.resolve() != (output / SETUP_NAME).resolve():
        shutil.copy2(guide, output / SETUP_NAME)
    world = apworld_manifest(output / APWORLD_NAME)
    hashes = {name: file_sha256(output / name) for name in (EXECUTABLE_NAME, APWORLD_NAME, SETUP_NAME)}
    manifest_path = output / 'release_manifest.json'
    atomic_write_json(manifest_path, {
        'format': 1,
        'launcher_version': version.APP_VERSION,
        'archipelago_version': version.ARCHIPELAGO_VERSION,
        'apworld_game': world['game'],
        'apworld_version': world['world_version'],
        'files': hashes,
    })
    hashes['release_manifest.json'] = file_sha256(manifest_path)
    atomic_write_text(output / 'SHA256SUMS.txt', ''.join(
        f'{checksum} *{name}\n' for name, checksum in hashes.items()
    ), encoding='ascii')
    verify_release(output, arguments.tag)


if __name__ == '__main__':
    main()
