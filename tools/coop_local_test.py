"""Prepare two private Mental Omega installs for a same-computer LAN test."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.prototype import rebuild_from_manifest
from randomizer.core.paths import GAME_ROOT


DEFAULT_OUTPUT = GAME_ROOT / 'RandomizerLauncherData' / 'coop_local'
COPY_EXCLUDES = (
    '/.agents/', '/.codex/', '/.git/', '/RandomizerLauncher/',
    '/RandomizerLauncherData/', '/Saved Games/', '/Screenshots/',
    '/GLCache/', '/debug/', '/release/', '/mental_omega.apworld',
)
PLAYERS = {'host': 'CoopHost', 'guest': 'CoopGuest'}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_ini_value(path: Path, section: str, key: str, value: str) -> None:
    data = path.read_bytes()
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    lines = data.decode('latin-1').splitlines()
    current = ''
    changed = False
    for index, line in enumerate(lines):
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip().lower()
        elif current == section.lower() and '=' in line:
            existing_key, _ = line.split('=', 1)
            if existing_key.strip().lower() == key.lower():
                lines[index] = f'{existing_key}={value}'
                changed = True
                break
    if not changed:
        raise ValueError(f'Missing [{section}] {key} in {path}')
    path.write_bytes(newline.join(line.encode('latin-1') for line in lines) + newline)


def _source_and_output(source: Path, output: Path) -> tuple[Path, Path]:
    source, output = source.resolve(), output.resolve()
    if not (source / 'MentalOmegaRandomizer.exe').is_file() or not (source / 'gamemd.exe').is_file():
        raise ValueError(f'Not a Mental Omega install: {source}')
    if output == source or (output.is_relative_to(source) and
                            not output.is_relative_to(source / 'RandomizerLauncherData')):
        raise ValueError('Output inside game install must be under RandomizerLauncherData.')
    return source, output


def _prepare_one(source: Path, output: Path, player: str, manifest: dict) -> Path:
    target = output / player
    marker = target / '.mor-coop-local-test.json'
    if target.exists():
        if not marker.is_file():
            raise ValueError(f'Existing folder is not this tool\'s copy: {target}')
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if saved.get('source_key') != manifest.get('source_key'):
            raise ValueError(f'Existing copy uses another co-op source map: {target}')
        rebuild_from_manifest(target, manifest)
        if saved != manifest:
            marker.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        _copy_launcher_data(source, target)
        _verify_one(target, manifest, player)
        (target / 'Saved Games').mkdir(exist_ok=True)
        (target / 'debug').mkdir(exist_ok=True)
        return target

    staging = Path(tempfile.mkdtemp(prefix=f'.{player}-', dir=output))
    try:
        command = ['rsync', '-a', *[f'--exclude={item}' for item in COPY_EXCLUDES],
                   f'{source}/', f'{staging}/']
        subprocess.run(command, check=True)
        (staging / 'Saved Games').mkdir(exist_ok=True)
        (staging / 'debug').mkdir(exist_ok=True)
        (staging / 'Client' / 'client.log').unlink(missing_ok=True)
        rebuild_from_manifest(staging, manifest)
        _copy_launcher_data(source, staging)
        options = staging / 'RA2MO.ini'
        for section, key, value in (
            ('Options', 'CheckforUpdates', 'False'),
            ('MultiPlayer', 'Handle', PLAYERS[player]),
            ('MultiPlayer', 'CnCNet_Autologin', 'false'),
            ('MultiPlayer', 'AutomaticCnCNetLogin', 'False'),
            ('MultiPlayer', 'DiscordIntegration', 'False'),
        ):
            _set_ini_value(options, section, key, value)
        marker = staging / marker.name
        marker.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        staging.rename(target)
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _verify_one(target: Path, manifest: dict, player: str) -> None:
    if not target.is_dir() or not (target / '.mor-coop-local-test.json').is_file():
        raise ValueError(f'Private {player} copy missing: {target}')
    expected = rebuild_from_manifest(target, manifest)
    if hashlib.sha256(expected).hexdigest() != manifest['map_sha256']:
        raise ValueError(f'Map source differs in {player} copy')
    if not (target / 'MentalOmegaRandomizer.exe').is_file():
        raise ValueError(f'Randomizer executable missing in {player} copy')
    options = (target / 'RA2MO.ini').read_text(encoding='latin-1')
    if f'Handle={PLAYERS[player]}' not in options:
        raise ValueError(f'Player name differs in {player} copy')


def _copy_launcher_data(source: Path, target: Path) -> None:
    executable = source / 'MentalOmegaRandomizer.exe'
    if not executable.is_file():
        raise ValueError(f'Randomizer executable missing: {executable}')
    destination = target / executable.name
    if not destination.is_file() or _sha(destination) != _sha(executable):
        staging = destination.with_suffix('.exe.mor-new')
        shutil.copy2(executable, staging)
        staging.replace(destination)
    private_data = target / 'RandomizerLauncherData'
    for relative in (
        Path('randomizer_state.json'),
        Path('randomizer_coop_state.json'),
        Path('configs/player/mental_omega_randomizer.yaml'),
    ):
        source_file = source / 'RandomizerLauncherData' / relative
        if source_file.is_file():
            destination_file = private_data / relative
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify', 'launch'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--source', type=Path, default=GAME_ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--player', choices=tuple(PLAYERS), help='Required for launch')
    parser.add_argument('--guest-prefix', type=Path,
                        help='Wine prefix for guest; defaults to output/guest_prefix')
    args = parser.parse_args(argv)
    try:
        source, output = _source_and_output(args.source, args.output)
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        # Validate manifest against original install before creating either copy.
        rebuild_from_manifest(source, manifest)
        if args.command == 'prepare':
            output.mkdir(parents=True, exist_ok=True)
            for player in PLAYERS:
                print(f'{player}: {_prepare_one(source, output, player, manifest)}', flush=True)
        else:
            for player in PLAYERS:
                _verify_one(output / player, manifest, player)
            print(f'Both maps match SHA-256 {manifest["map_sha256"]}')
            if args.command == 'launch':
                if not args.player:
                    parser.error('--player is required for launch')
                if not shutil.which('wine'):
                    raise ValueError('wine not found. Open MentalOmegaRandomizer.exe in private copy manually.')
                game = output / args.player
                if args.player == 'guest':
                    prefix = (args.guest_prefix or output / 'guest_prefix').resolve()
                    host_prefix = Path(os.environ.get('WINEPREFIX', Path.home() / '.wine')).resolve()
                    if prefix == host_prefix:
                        raise ValueError('Guest Wine prefix must differ from host Wine prefix.')
                    if not (prefix / 'system.reg').is_file():
                        if not shutil.which('wineboot'):
                            raise ValueError('wineboot not found for guest Wine prefix.')
                        print(f'Creating guest Wine prefix: {prefix}', flush=True)
                        env = dict(os.environ, WINEPREFIX=str(prefix))
                        subprocess.run(['wineboot', '-u'], check=True, env=env)
                    os.environ['WINEPREFIX'] = str(prefix)
                print(f'Opening {PLAYERS[args.player]} from {game}', flush=True)
                os.chdir(game)
                os.execvp('wine', ['wine', str(game / 'MentalOmegaRandomizer.exe')])
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Local co-op test: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
