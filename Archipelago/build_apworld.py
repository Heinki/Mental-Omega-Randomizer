"""Build the deterministic Mental Omega APWorld on any desktop platform."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ARCHIPELAGO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ARCHIPELAGO_DIR.parent
MODULE_NAME = 'mental_omega'
SOURCE_DIR = ARCHIPELAGO_DIR / 'APWorld' / MODULE_NAME
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)


def archive_info(name: str) -> ZipInfo:
    info = ZipInfo(name, FIXED_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build(output_directory: Path) -> Path:
    sys.path.insert(0, str(PROJECT_ROOT))
    from Archipelago.generate_catalogue import main as generate_catalogue
    from Archipelago.bundle_generation import generation_files
    from randomizer.core.paths import BATTLE_CLIENT_INI
    from randomizer.core.version import release_versions
    from randomizer.missions.catalogue import parse_missions

    manifest_path = SOURCE_DIR / 'archipelago.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'APWorld manifest not found: {manifest_path}')
    versions = release_versions()

    generate_catalogue()
    bundled_files = generation_files()
    missions_data = json.dumps(
        parse_missions(BATTLE_CLIENT_INI), sort_keys=True,
    ).encode('utf-8')
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f'{MODULE_NAME}.apworld'

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({
        'minimum_ap_version': versions['archipelago_version'],
        'world_version': versions['apworld_version'],
        'compatible_version': versions['apworld_container_version'],
        'version': versions['apworld_container_version'],
        'maximum_ap_version': versions['archipelago_version'],
    })
    manifest_data = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')

    files = sorted(
        path for path in SOURCE_DIR.rglob('*')
        if path.is_file()
        and path != manifest_path
        and path.name != '_generated_version.py'
        and path.suffix != '.pyc'
        and '__pycache__' not in path.parts
    )
    generated_version_data = (
        '"""Generated from randomizer.core.version; do not edit."""\n\n'
        f'RANDOMIZER_VERSION = {versions["app_version"]!r}\n'
    ).encode('utf-8')
    with ZipFile(output_path, 'w') as archive:
        for source in files:
            relative = source.relative_to(SOURCE_DIR).as_posix()
            archive.writestr(
                archive_info(f'{MODULE_NAME}/{relative}'),
                source.read_bytes(),
            )
        for name, data in bundled_files:
            archive.writestr(archive_info(name), data)
        archive.writestr(
            archive_info(f'{MODULE_NAME}/generation_missions.json'),
            missions_data,
        )
        archive.writestr(
            archive_info(f'{MODULE_NAME}/archipelago.json'),
            manifest_data,
        )
        archive.writestr(
            archive_info(f'{MODULE_NAME}/_generated_version.py'),
            generated_version_data,
        )

    print(output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output-directory',
        type=Path,
        default=ARCHIPELAGO_DIR,
    )
    arguments = parser.parse_args()
    build(arguments.output_directory)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
