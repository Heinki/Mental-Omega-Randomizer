"""Direct private co-op launch without the Mental Omega Client UI.

The launcher uses TCP only to agree on the map and launch settings. The game
spawner, injected by Syringe, owns the actual UDP game connection.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import time

from randomizer.coop.prototype import (
    SIDE_COUNTRIES, _map_config, build_shop_manifest, rebuild_from_manifest,
)
from randomizer.maps.ini import all_section_value_maps_preserve, merge_ini_section_values


CONTROL_PORT = 19421
GAME_PORT = 1234
PROTOCOL = 2
MAX_MESSAGE = 262_144
PLAYER_NAME = re.compile(r'[A-Za-z0-9_-]{1,14}\Z')
MODES = {'easy': ('Co-Op Easy', 2), 'normal': ('Co-Op Medium', 1),
         'hard': ('Co-Op Hard', 0)}
ALLY_KEYS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven')


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line(socket_file, message: dict) -> None:
    data = json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\n'
    if len(data) > MAX_MESSAGE:
        raise ValueError('Co-op control message is too large.')
    socket_file.write(data)
    socket_file.flush()


def _receive(socket_file) -> dict:
    data = socket_file.readline(MAX_MESSAGE + 1)
    if not data or len(data) > MAX_MESSAGE or not data.endswith(b'\n'):
        raise ValueError('Co-op peer closed connection or sent an invalid message.')
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError('Co-op peer sent an invalid message.')
    return result


def _name(value: str) -> str:
    if not PLAYER_NAME.fullmatch(value):
        raise ValueError('Player name must be 1–14 letters, numbers, _ or -.')
    return value


def _port(value: int) -> int:
    if not isinstance(value, int) or not 1024 <= value <= 65535:
        raise ValueError('Co-op port must be between 1024 and 65535.')
    return value


def _installation(game_root: Path) -> dict[str, str]:
    return {
        'machine': socket.gethostname().casefold(),
        'path': os.path.normcase(str(game_root.resolve())).casefold(),
    }


def _check_separate_install(local: dict, remote: dict) -> None:
    if local == remote:
        raise ValueError(
            'Both launchers use the same game folder. Co-op needs two separate '
            'Mental Omega folders because each game writes spawn.ini and '
            'spawnmap.ini. Use the local co-op test helper to prepare two copies.'
        )


def _mode_map(game_root: Path, manifest: dict, difficulty: str) -> bytes:
    if difficulty not in MODES:
        raise ValueError('Co-op difficulty must be easy, normal, or hard.')
    source = rebuild_from_manifest(game_root, manifest)
    mode_name, _ = MODES[difficulty]
    mode_file = game_root / 'INI' / 'Map Code' / f'{mode_name}.ini'
    mode_data = mode_file.read_bytes()
    lines = source.decode('latin-1').splitlines()
    merge_ini_section_values(lines, all_section_value_maps_preserve(mode_data.decode('latin-1').splitlines()))
    return ('\r\n'.join(lines) + '\r\n').encode('latin-1')


def _catalogue_settings(game_root: Path, manifest: dict) -> tuple[int, int, list[int], list[tuple[int, int, int]]]:
    coop_name = manifest['source_key'].rsplit('\\', 1)[-1]
    _, _, metadata, _, _ = _map_config(game_root, coop_name)
    denied_sides = {int(x) for x in re.findall(r'\d+', metadata.get('disallowedplayersides', ''))}
    sides = sorted(set(range(9)) - denied_sides)
    denied_colors = {int(x) for x in re.findall(r'\d+', metadata.get('disallowedplayercolors', ''))}
    colors = sorted(set(range(13)) - denied_colors)
    if len(sides) != 1 or len(colors) < 2:
        raise ValueError('Co-op map needs one player side and two allowed colors.')
    houses = []
    for key in sorted(k for k in metadata if re.fullmatch(r'enemyhouse\d+', k)):
        parts = metadata[key].split(',')
        if len(parts) != 3:
            raise ValueError(f'Invalid {key} in co-op catalogue.')
        houses.append(tuple(int(part.strip()) for part in parts))
    if not houses:
        raise ValueError('Co-op map has no enemy houses.')
    guest_side = sides[0]
    if manifest.get('schema') == 5:
        guest_country = manifest['guest_country']
        if guest_country not in SIDE_COUNTRIES:
            raise ValueError('Invalid guest Shop country.')
        guest_side = SIDE_COUNTRIES.index(guest_country)
        if guest_side // 3 != sides[0] // 3 or guest_side == sides[0]:
            raise ValueError('Guest Shop country must be another country of same faction.')
        if guest_side in {enemy[0] for enemy in houses}:
            raise ValueError('Guest Shop country is used by an enemy house.')
    return sides[0], guest_side, colors[:2], houses


def _spawn_data(game_root: Path, manifest: dict, *, role: str, name: str,
                peer_name: str, peer_ip: str, local_port: int, peer_port: int,
                game_id: int, difficulty: str, map_data: bytes) -> bytes:
    host_side, guest_side, colors, enemies = _catalogue_settings(game_root, manifest)
    host = role == 'host'
    own_side, other_side = ((host_side, guest_side) if host
                            else (guest_side, host_side))
    own_color, other_color = (colors if host else list(reversed(colors)))
    mode_name, handicap = MODES[difficulty]
    sections: dict[str, dict[str, str]] = {
        'Settings': {
            'Name': name, 'Scenario': 'spawnmap.ini', 'UIGameMode': mode_name,
            'UIMapName': manifest['description'], 'PlayerCount': '2',
            'AIPlayers': str(len(enemies)), 'Seed': str(game_id),
            'GameID': str(game_id), 'Host': 'Yes' if host else 'No',
            'IsSinglePlayer': 'No', 'Side': str(own_side), 'Color': str(own_color),
            'IsSpectator': 'No', 'Port': str(local_port), 'GameSpeed': '2',
            'ShortGame': 'No', 'AutoSurrender': 'No', 'BuildOffAlly': 'Yes',
            'FrameSendRate': '7', 'Protocol': '2', 'FogOfWar': 'No',
            'MultiEngineer': 'Yes', 'UnitCount': '0',
            'MapSHA1': hashlib.sha1(map_data).hexdigest(),
        },
        'Other1': {
            'Name': peer_name, 'Side': str(other_side), 'Color': str(other_color),
            'IsSpectator': 'No', 'Ip': peer_ip, 'Port': str(peer_port),
        },
        'SpawnLocations': {'Multi1': '0', 'Multi2': '1'},
        'Multi1_Alliances': {'HouseAllyOne': '1'},
        'Multi2_Alliances': {'HouseAllyOne': '0'},
    }
    if manifest.get('schema') == 4 and manifest.get('starting_credit_bonus', 0):
        # The CnCNet spawner reads Settings/Credits as real starting credits.
        # Source: CnCNet/yr-patches src/spawner/load_spawn.c.
        sections['Settings']['Credits'] = str(
            10000 + manifest['starting_credit_bonus']
        )
    for index, (enemy_side, enemy_color, location) in enumerate(enemies, 3):
        key = f'Multi{index}'
        sections.setdefault('HouseHandicaps', {})[key] = str(handicap)
        sections.setdefault('HouseCountries', {})[key] = str(enemy_side)
        sections.setdefault('HouseColors', {})[key] = str(enemy_color)
        sections['SpawnLocations'][key] = str(location)
        allies = [other - 1 for other in range(3, 3 + len(enemies)) if other != index]
        if allies:
            sections[f'{key}_Alliances'] = {
                f'HouseAlly{ALLY_KEYS[n]}': str(ally)
                for n, ally in enumerate(allies)
            }
    result = []
    for section, values in sections.items():
        result.extend([f'[{section}]', *(f'{key}={value}' for key, value in values.items()), ''])
    return '\r\n'.join(result).encode('latin-1')


def prepare_game(game_root: Path, manifest: dict, *, role: str, name: str,
                 peer_name: str, peer_ip: str, local_port: int, peer_port: int,
                 game_id: int, difficulty: str = 'normal') -> str:
    """Write only local runtime files after peers agree on the same map."""
    if role not in ('host', 'guest'):
        raise ValueError('Co-op role must be host or guest.')
    _name(name)
    _name(peer_name)
    _port(local_port)
    _port(peer_port)
    if not 1 <= game_id <= 2**31 - 1:
        raise ValueError('Invalid co-op game ID.')
    map_data = _mode_map(game_root, manifest, difficulty)
    spawn_data = _spawn_data(game_root, manifest, role=role, name=name,
                             peer_name=peer_name, peer_ip=peer_ip,
                             local_port=local_port, peer_port=peer_port,
                             game_id=game_id, difficulty=difficulty,
                             map_data=map_data)
    (game_root / 'spawnmap.ini').write_bytes(map_data)
    (game_root / 'spawn.ini').write_bytes(spawn_data)
    return _digest(map_data)


def _version_hash(game_root: Path) -> str:
    return _digest((game_root / 'version').read_bytes())


def host_session(game_root: Path, manifest: dict | None, *, name: str = 'CoopHost',
                 bind: str = '0.0.0.0', control_port: int = CONTROL_PORT,
                 game_port: int = GAME_PORT, difficulty: str = 'normal',
                 session_token: str = '', on_ready=None,
                 shop_setup: dict | None = None) -> dict:
    """Wait for one guest, verify setup, then signal both launchers to start."""
    _name(name)
    _port(control_port)
    _port(game_port)
    if (shop_setup is None) == (manifest is None):
        raise ValueError('Provide either a fixed co-op manifest or host Shop setup.')
    with socket.create_server((bind, control_port), backlog=1) as server:
        # Open the port before expensive map generation. A guest can now join
        # immediately after the host presses Start, even with a large Grid run.
        mode_hash = (_digest(_mode_map(game_root, manifest, difficulty))
                     if manifest is not None else '')
        version_hash = _version_hash(game_root)
        game_id = secrets.randbelow(2**31 - 1) + 1
        server.settimeout(120)
        connection, address = server.accept()
        with connection:
            connection.settimeout(180)
            with connection.makefile('rwb') as stream:
                hello = _receive(stream)
                if hello.get('type') != 'hello' or hello.get('protocol') != PROTOCOL:
                    raise ValueError('Incompatible co-op guest.')
                guest_name = _name(hello.get('name', ''))
                guest_port = _port(hello.get('game_port'))
                if session_token and not secrets.compare_digest(
                    str(hello.get('session_token', '')), session_token
                ):
                    _line(stream, {'type': 'reject', 'reason': 'Co-op game pairing token differs.'})
                    raise ValueError('Co-op game pairing token differs.')
                try:
                    _check_separate_install(
                        _installation(game_root), hello.get('installation'),
                    )
                except ValueError as exc:
                    _line(stream, {'type': 'reject', 'reason': str(exc)})
                    raise
                if guest_name == name:
                    raise ValueError('Both players need distinct names.')
                if shop_setup is not None:
                    guest_shop = hello.get('shop')
                    if (not isinstance(guest_shop, dict)
                            or guest_shop.get('seed') != shop_setup.get('seed')
                            or guest_shop.get('stage') != shop_setup.get('stage')):
                        reason = 'Shop players need the same seed and stage.'
                        _line(stream, {'type': 'reject', 'reason': reason})
                        raise ValueError(reason)
                    try:
                        manifest, _ = build_shop_manifest(
                            game_root, shop_setup['seed'], shop_setup['coop_name'],
                            shop_setup['loadout'], guest_shop['loadout'],
                            stage=shop_setup['stage'],
                        )
                        mode_hash = _digest(_mode_map(game_root, manifest, difficulty))
                    except (KeyError, TypeError, ValueError) as exc:
                        _line(stream, {'type': 'reject', 'reason': str(exc)})
                        raise
                _line(stream, {
                    'type': 'offer', 'protocol': PROTOCOL, 'manifest': manifest,
                    'name': name, 'game_port': game_port, 'game_id': game_id,
                    'difficulty': difficulty, 'map_sha256': mode_hash,
                    'version_sha256': version_hash,
                    'installation': _installation(game_root),
                })
                ready = _receive(stream)
                if ready.get('type') != 'ready' or ready.get('map_sha256') != mode_hash:
                    raise ValueError('Guest map differs or guest is not ready.')
                if ready.get('version_sha256') != version_hash:
                    raise ValueError('Guest Mental Omega patch differs.')
                local_hash = prepare_game(
                    game_root, manifest, role='host', name=name,
                    peer_name=guest_name, peer_ip=address[0],
                    local_port=game_port, peer_port=guest_port,
                    game_id=game_id, difficulty=difficulty,
                )
                if local_hash != mode_hash:
                    raise ValueError('Host map changed while preparing game.')
                _line(stream, {'type': 'start', 'game_id': game_id})
    result = {'role': 'host', 'peer': guest_name, 'peer_ip': address[0],
              'game_id': game_id, 'map_sha256': mode_hash}
    if on_ready:
        on_ready(result)
    return result


def join_session(game_root: Path, address: str, *, name: str = 'CoopGuest',
                 control_port: int = CONTROL_PORT, game_port: int = GAME_PORT,
                 session_token: str = '', on_ready=None,
                 shop_setup: dict | None = None) -> dict:
    _name(name)
    _port(control_port)
    _port(game_port)
    deadline = time.monotonic() + 20
    while True:
        try:
            connection = socket.create_connection((address, control_port), timeout=5)
            break
        except ConnectionRefusedError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)
    with connection:
        connection.settimeout(180)
        host_ip = connection.getpeername()[0]
        with connection.makefile('rwb') as stream:
            hello = {'type': 'hello', 'protocol': PROTOCOL,
                     'name': name, 'game_port': game_port,
                     'session_token': session_token,
                     'installation': _installation(game_root)}
            if shop_setup is not None:
                hello['shop'] = shop_setup
            _line(stream, hello)
            offer = _receive(stream)
            if offer.get('type') == 'reject':
                raise ValueError(str(offer.get('reason') or 'Co-op host rejected the guest.'))
            if offer.get('type') != 'offer' or offer.get('protocol') != PROTOCOL:
                raise ValueError('Incompatible co-op host.')
            _check_separate_install(_installation(game_root), offer.get('installation'))
            manifest = offer['manifest']
            if shop_setup is not None and (
                manifest.get('schema') != 5
                or manifest.get('seed') != shop_setup.get('seed')
                or manifest.get('shop_stage') != shop_setup.get('stage')
                or manifest.get('player_loadouts', {}).get('guest') != shop_setup.get('loadout')
            ):
                raise ValueError('Host Shop map differs from guest seed, stage, or loadout.')
            difficulty = offer['difficulty']
            host_name = _name(offer['name'])
            host_port = _port(offer['game_port'])
            game_id = offer['game_id']
            if host_name == name or _version_hash(game_root) != offer['version_sha256']:
                raise ValueError('Player names or Mental Omega patches differ.')
            if _digest(_mode_map(game_root, manifest, difficulty)) != offer['map_sha256']:
                raise ValueError('Generated co-op maps differ.')
            local_hash = prepare_game(
                game_root, manifest, role='guest', name=name,
                peer_name=host_name, peer_ip=host_ip,
                local_port=game_port, peer_port=host_port,
                game_id=game_id, difficulty=difficulty,
            )
            if local_hash != offer['map_sha256']:
                raise ValueError('Generated co-op maps differ.')
            _line(stream, {'type': 'ready', 'map_sha256': local_hash,
                           'version_sha256': _version_hash(game_root)})
            start = _receive(stream)
            if start.get('type') != 'start' or start.get('game_id') != game_id:
                raise ValueError('Host did not confirm co-op launch.')
    result = {'role': 'guest', 'peer': host_name, 'peer_ip': host_ip,
              'game_id': game_id, 'map_sha256': local_hash}
    if on_ready:
        on_ready(result)
    return result
