"""Private LAN co-op prototype: build, rebuild, install, or remove one map."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.prototype import (
    available_units, build_manifest, install, rebuild_from_manifest, remove,
    write_bundle,
)
from randomizer.core.paths import APP_DIR, GAME_ROOT, STATE_PATH


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, default=GAME_ROOT)
    parser.add_argument('--output-dir', type=Path, default=APP_DIR / 'generated_coop')
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build', help='Build from current Classic/Grid seed')
    build.add_argument('--state', type=Path, default=STATE_PATH)
    build.add_argument('--coop', required=True, help='Installed co-op map stem, e.g. coop_sthunder')
    build.add_argument('--source-mission', default='', help='Required for Randomizer Arsenal')
    build.add_argument('--unit', default='', help='Earned or arsenal unit ID; defaults to first supported')
    listing = commands.add_parser('list-units', help='List saved access candidates')
    listing.add_argument('--state', type=Path, default=STATE_PATH)
    listing.add_argument('--source-mission', default='', help='Required for Randomizer Arsenal')
    for name in ('rebuild', 'install', 'remove'):
        commands.add_parser(name).add_argument('manifest', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {'build', 'list-units'}:
            state = json.loads(args.state.read_text(encoding='utf-8-sig'))
            if args.command == 'list-units':
                for unit_id, name in available_units(state, args.source_mission):
                    print(f'{unit_id}\t{name}')
                return 0
            manifest, map_data = build_manifest(
                args.game_root, state, args.coop,
                source_mission=args.source_mission, unit_id=args.unit,
                allow_test_unit=True,
            )
        else:
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            if args.command == 'remove':
                remove(args.game_root, manifest)
                print(f'Removed {manifest["map_key"]}')
                return 0
            map_data = rebuild_from_manifest(args.game_root, manifest)
        if args.command in {'build', 'rebuild'}:
            manifest_path, map_path = write_bundle(args.output_dir, manifest, map_data)
            print(f'Manifest: {manifest_path}')
            print(f'Map: {map_path}')
            print(f'SHA-256: {manifest["map_sha256"]}')
        elif args.command == 'install':
            if args.game_root.resolve() == GAME_ROOT.resolve():
                raise ValueError(
                    'Install only into a private Mental Omega copy: '
                    'pass --game-root PATH before install.'
                )
            destination = install(args.game_root, manifest, map_data)
            print(f'Installed: {destination}')
            print(f'LAN lobby map: {manifest["description"]}')
            print('Restart Mental Omega client. Select LAN, Co-Op, then this map.')
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f'Co-op prototype: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
