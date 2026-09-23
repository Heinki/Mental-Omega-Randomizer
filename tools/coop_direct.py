"""Host or join a direct co-op game without opening MentalOmegaClient.exe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.direct import CONTROL_PORT, GAME_PORT, host_session, join_session
from randomizer.core.paths import GAME_ROOT


def launch_game(game_root: Path) -> int:
    syringe = game_root / 'Syringe.exe'
    game = game_root / 'gamemd.exe'
    if not syringe.is_file() or not game.is_file():
        raise FileNotFoundError('Syringe.exe or gamemd.exe missing in game copy.')
    flags = ['-SPAWN', '-CD', '-SPEEDCONTROL', '-LOG']
    environment = os.environ.copy()
    if sys.platform == 'win32':
        # Syringe requires its host executable to remain quoted in the raw
        # Windows command line, including paths without spaces.
        command = (subprocess.list2cmdline([str(syringe)]) + ' "' +
                   str(game) + '" ' + subprocess.list2cmdline(flags))
        process = subprocess.Popen(command, executable=str(syringe),
                                   cwd=game_root, env=environment)
    else:
        wine = shutil.which('wine')
        winepath = shutil.which('winepath')
        if not wine or not winepath:
            raise FileNotFoundError('wine and winepath are required on Linux.')
        environment['WINEDEBUG'] = '-all'
        overrides = environment.get('WINEDLLOVERRIDES', '')
        if not any(x.strip().lower().startswith('ddraw=') for x in overrides.split(';')):
            environment['WINEDLLOVERRIDES'] = ';'.join(x for x in (overrides, 'ddraw=n,b') if x)
        host = subprocess.run([winepath, '-w', str(game)], cwd=game_root,
                              env=environment, capture_output=True, text=True,
                              check=True).stdout.strip()
        if not host:
            raise RuntimeError('winepath returned no game executable path.')
        process = subprocess.Popen([wine, str(syringe), host, *flags],
                                   cwd=game_root, env=environment,
                                   start_new_session=True)
    print(f'Started game PID {process.pid}', flush=True)
    return process.wait()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, default=GAME_ROOT)
    parser.add_argument('--control-port', type=int, default=CONTROL_PORT)
    parser.add_argument('--game-port', type=int, default=GAME_PORT)
    parser.add_argument('--name', default='')
    parser.add_argument('--dry-run', action='store_true',
                        help='Prepare both games and handshake, without starting Syringe')
    commands = parser.add_subparsers(dest='command', required=True)
    host = commands.add_parser('host')
    host.add_argument('manifest', type=Path)
    host.add_argument('--bind', default='0.0.0.0')
    host.add_argument('--difficulty', choices=('easy', 'normal', 'hard'), default='normal')
    join = commands.add_parser('join')
    join.add_argument('host_address')
    args = parser.parse_args(argv)
    root = args.game_root.resolve()
    try:
        if args.command == 'host':
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            print(f'Waiting for guest on TCP {args.bind}:{args.control_port}', flush=True)
            result = host_session(root, manifest, name=args.name or 'CoopHost',
                                  bind=args.bind, control_port=args.control_port,
                                  game_port=args.game_port, difficulty=args.difficulty)
        else:
            result = join_session(root, args.host_address,
                                  name=args.name or 'CoopGuest',
                                  control_port=args.control_port,
                                  game_port=args.game_port)
        print(f'Paired with {result["peer"]}; game ID {result["game_id"]}; '
              f'map SHA-256 {result["map_sha256"]}', flush=True)
        if args.dry_run:
            print('Dry run: game launch skipped.', flush=True)
            return 0
        return launch_game(root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Direct co-op: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
