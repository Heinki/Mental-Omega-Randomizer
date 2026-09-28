"""Exercise paired lobby and game handshakes over local TCP sockets."""

from pathlib import Path
import queue
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.direct import host_session, join_session
from randomizer.coop.lobby import Lobby
from randomizer.coop.prototype import build_manifest, build_shop_manifest
from randomizer.core.paths import GAME_ROOT
from randomizer.maps.ini import section_value_map_preserve


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def events_until(lobby, target):
    deadline = time.monotonic() + 15
    seen = []
    while time.monotonic() < deadline:
        try:
            event = lobby.events.get(timeout=0.5)
        except queue.Empty:
            continue
        seen.append(event)
        if event[0] in target:
            return event, seen
    raise AssertionError(f'Timed out waiting for {target}: {seen}')


def lobby_case(host_code, guest_code, expected):
    with TemporaryDirectory() as first, TemporaryDirectory() as second:
        port = free_port()
        host = Lobby(Path(first), 'host', 'Host', port=port, pairing_code=host_code)
        guest = Lobby(Path(second), 'guest', 'Guest', address='127.0.0.1',
                      port=port, pairing_code=guest_code)
        try:
            host.start()
            event, _ = events_until(host, {'listening'})
            assert event[1] == port
            guest.start()
            host_event, _ = events_until(host, {'connected', 'error'})
            guest_event, _ = events_until(guest, {'connected', 'error'})
            assert host_event[0] == expected, host_event
            assert guest_event[0] == expected, guest_event
            if expected == 'error':
                assert 'pairing' in host_event[1].lower()
                assert 'pairing' in guest_event[1].lower()
            else:
                host.send({'type': 'select', 'code': 'COOP_STHUNDER'})
                message, _ = events_until(guest, {'message'})
                assert message[1] == {'type': 'select', 'code': 'COOP_STHUNDER'}
                host.send({'type': 'shop_stage', 'data': {'stage': 1}})
                message, _ = events_until(guest, {'message'})
                assert message[1] == {'type': 'shop_stage', 'data': {'stage': 1}}
                guest.send({'type': 'shop_ready', 'digest': 'stage-check'})
                message, _ = events_until(host, {'message'})
                assert message[1] == {'type': 'shop_ready', 'digest': 'stage-check'}
                host.send({'type': 'shop_victory', 'seed': 'TEST',
                           'stage': 1, 'code': 'COOP_STHUNDER'})
                message, _ = events_until(guest, {'message'})
                assert message[1]['type'] == 'shop_victory'
                host.send({'type': 'shop_failure', 'seed': 'TEST',
                           'stage': 1, 'code': 'COOP_STHUNDER',
                           'revived': False,
                           'session_token': 'private-game-token-1234567890123456'})
                message, _ = events_until(guest, {'message'})
                assert message[1]['type'] == 'shop_failure'
        finally:
            host.close()
            guest.close()


def game_case(manifest, host_root, guest_root, host_token, guest_token, expected):
    port = free_port()
    output = queue.Queue()

    def run_host():
        try:
            output.put(('ready', host_session(
                host_root, manifest, name='Host', bind='127.0.0.1',
                control_port=port, session_token=host_token,
            )))
        except Exception as exc:
            output.put(('error', str(exc)))

    thread = threading.Thread(target=run_host, daemon=True)
    thread.start()
    try:
        guest_result = join_session(
            guest_root, '127.0.0.1', name='Guest', control_port=port,
            game_port=1235, session_token=guest_token,
        )
        guest_event = ('ready', guest_result)
    except Exception as exc:
        guest_event = ('error', str(exc))
    host_event = output.get(timeout=30)
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert host_event[0] == expected, host_event
    assert guest_event[0] == expected, guest_event
    if expected == 'error':
        assert 'token' in host_event[1].lower()
        assert 'token' in guest_event[1].lower()
    else:
        assert host_event[1]['map_sha256'] == guest_event[1]['map_sha256']
        assert (host_root / 'spawnmap.ini').read_bytes() == (
            guest_root / 'spawnmap.ini').read_bytes()


def shop_exchange_case(host_root, guest_root, *, guest_seed, guest_stage, expected,
                       guest_loadout=None, error_fragment='seed and stage'):
    port = free_port()
    output = queue.Queue()
    host_setup = {
        'seed': 'COOP-PAIR-SHOP', 'stage': 2, 'coop_name': 'coop_sthunder',
        'loadout': {'access_ids': ['FV'], 'buff_counts': {'FV': {'health': 2}}},
    }
    guest_setup = {
        'seed': guest_seed, 'stage': guest_stage,
        'loadout': (guest_loadout if guest_loadout is not None else
                    {'access_ids': ['HTNK'], 'buff_counts': {'HTNK': {'damage': 1}}}),
    }

    def run_host():
        try:
            output.put(('ready', host_session(
                host_root, None, name='Host', bind='127.0.0.1',
                control_port=port, shop_setup=host_setup,
            )))
        except Exception as exc:
            output.put(('error', str(exc)))

    thread = threading.Thread(target=run_host, daemon=True)
    thread.start()
    try:
        guest_result = join_session(
            guest_root, '127.0.0.1', name='Guest', control_port=port,
            game_port=1235, shop_setup=guest_setup,
        )
        guest_event = ('ready', guest_result)
    except Exception as exc:
        guest_event = ('error', str(exc))
    host_event = output.get(timeout=30)
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert host_event[0] == expected, host_event
    assert guest_event[0] == expected, guest_event
    if expected == 'error':
        assert error_fragment in host_event[1]
        assert error_fragment in guest_event[1]
    else:
        assert host_event[1]['map_sha256'] == guest_event[1]['map_sha256']
        map_bytes = (host_root / 'spawnmap.ini').read_bytes()
        assert map_bytes == (guest_root / 'spawnmap.ini').read_bytes()
        lines = map_bytes.decode('latin-1').splitlines()
        host_clone = section_value_map_preserve(lines, 'MORHFV')
        guest_clone = section_value_map_preserve(lines, 'MORGHTNK')
        assert host_clone['RequiredHouses'] != guest_clone['RequiredHouses']
        assert not section_value_map_preserve(lines, 'MORGFV')
        assert not section_value_map_preserve(lines, 'MORHHTNK')


def main():
    lobby_case('same-long-private-code', 'same-long-private-code', 'connected')
    lobby_case('first-long-private-code', 'other-long-private-code', 'error')
    host_root = GAME_ROOT / 'RandomizerLauncherData' / 'coop_local' / 'host'
    guest_root = GAME_ROOT / 'RandomizerLauncherData' / 'coop_local' / 'guest'
    if not host_root.is_dir() or not guest_root.is_dir():
        raise SystemExit('Prepare two private copies with tools/coop_local_test.py first.')
    state = {
        'seed': 'COOP-PAIR-CHECK', 'progression_mode': 'Grid Mode',
        'reward_mode': 'Chaos', 'coop_mode': True, 'starting_rewards': [],
        'mission_order': ['COOP_STHUNDER'], 'mission_checks': {},
    }
    manifest, _ = build_manifest(
        GAME_ROOT, state, 'coop_sthunder', unit_id='FV', allow_test_unit=True,
    )
    game_case(manifest, host_root, guest_root,
              'host-private-session-token', 'wrong-private-session-token', 'error')
    game_case(manifest, host_root, guest_root,
              'same-private-session-token', 'same-private-session-token', 'ready')
    shop_manifest, _ = build_shop_manifest(
        GAME_ROOT, 'COOP-PAIR-SHOP', 'coop_sthunder',
        {'access_ids': ['FV'], 'buff_counts': {'FV': {'health': 1}}},
        {'access_ids': ['HTNK'], 'buff_counts': {'HTNK': {'damage': 1}}},
    )
    game_case(shop_manifest, host_root, guest_root,
              'same-private-session-token', 'same-private-session-token', 'ready')
    shop_exchange_case(host_root, guest_root,
                       guest_seed='OTHER-SHOP-SEED', guest_stage=2, expected='error')
    shop_exchange_case(host_root, guest_root,
                       guest_seed='COOP-PAIR-SHOP', guest_stage=3, expected='error')
    shop_exchange_case(host_root, guest_root,
                       guest_seed='COOP-PAIR-SHOP', guest_stage=2, expected='error',
                       guest_loadout={'access_ids': ['ZZZZ'], 'buff_counts': {}},
                       error_fragment='absent from installed')
    shop_exchange_case(host_root, guest_root,
                       guest_seed='COOP-PAIR-SHOP', guest_stage=2, expected='ready')
    print('Paired lobby, wrong codes, Grid map, private Shop exchange: passed')


if __name__ == '__main__':
    main()
