"""Bounded Archipelago 0.6.7 handshake used by client smoke and UI layers."""

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
import ssl
import sys
import time
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import getproxies

from randomizer.core.version import APP_VERSION


GAME_NAME = 'Mental Omega'
SUPPORTED_SLOT_DATA_VERSIONS = frozenset({4, 5})
SUPPORTED_RANDOMIZER_VERSION = APP_VERSION
CLIENT_VERSION = (0, 6, 7)
ITEMS_HANDLING_ALL = 0b111
DEFAULT_PORT = 38281


class ArchipelagoHandshakeError(RuntimeError):
    """Base failure establishing a Mental Omega Archipelago session."""


class ArchipelagoProtocolError(ArchipelagoHandshakeError):
    """Server packets or slot data violate the supported contract."""


class ArchipelagoConnectionRefused(ArchipelagoHandshakeError):
    """Server rejected slot, game, version, password, or item handling."""

    def __init__(self, errors):
        self.errors = tuple(str(error) for error in (errors or ('Unknown',)))
        super().__init__('Archipelago connection refused: ' + ', '.join(self.errors))


class ArchipelagoTlsError(ArchipelagoHandshakeError):
    """TLS failed while certificate verification remained enabled."""

    def __init__(self, endpoint, error, diagnostics):
        self.endpoint = str(endpoint)
        self.diagnostics = dict(diagnostics)
        verify_message = str(
            getattr(error, 'verify_message', '') or error
        ).strip()
        verify_code = getattr(error, 'verify_code', None)
        detail = (
            f'certificate verify code {verify_code}: {verify_message}'
            if verify_code is not None
            else verify_message
        )
        super().__init__(
            f'TLS certificate verification failed for {self.endpoint}: '
            f'{detail}. System clock, Windows trusted roots, antivirus/proxy '
            'TLS inspection, or server certificate chain may be responsible.'
        )


@dataclass(frozen=True)
class HandshakeResult:
    endpoint: str
    seed_name: str
    team: int
    slot: int
    checked_locations: tuple[int, ...]
    missing_locations: tuple[int, ...]
    slot_data: dict[str, Any]
    slot_info: dict[int, dict[str, Any]] = field(default_factory=dict)


def normalize_server_uri(value):
    """Return a validated ws/wss endpoint with hosted rooms using TLS."""
    endpoint = str(value or '').strip()
    if not endpoint:
        raise ValueError('Archipelago server address is required.')
    if '://' not in endpoint:
        bare = urlsplit(f'//{endpoint}')
        scheme = (
            'wss'
            if str(bare.hostname or '').rstrip('.').casefold()
            == 'archipelago.gg'
            else 'ws'
        )
        endpoint = f'{scheme}://{endpoint}'
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'ws', 'wss'}:
        raise ValueError('Archipelago server must use ws:// or wss://.')
    if not parsed.hostname:
        raise ValueError('Archipelago server hostname is required.')
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError('Archipelago server port is invalid.') from exc
    if parsed.username or parsed.password:
        raise ValueError('Put slot and password in their dedicated fields.')
    scheme = parsed.scheme
    if parsed.hostname.rstrip('.').casefold() == 'archipelago.gg':
        scheme = 'wss'
    netloc = parsed.netloc
    if parsed.port is None:
        host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
        netloc = f'{host}:{DEFAULT_PORT}'
    return urlunsplit((scheme, netloc, parsed.path or '/', '', ''))


def _sanitized_proxies():
    result = {}
    try:
        values = getproxies()
    except Exception:
        return result
    for scheme, value in values.items():
        parsed = urlsplit(str(value or ''))
        if not parsed.hostname:
            continue
        try:
            port = parsed.port
        except ValueError:
            port = None
        result[str(scheme)] = {
            'scheme': parsed.scheme,
            'host': parsed.hostname,
            'port': port,
        }
    return result


def tls_diagnostics(endpoint, context=None, error=None):
    """Return support-safe TLS facts without weakening verification."""
    parsed = urlsplit(str(endpoint))
    paths = ssl.get_default_verify_paths()
    if context is None and parsed.scheme == 'wss':
        try:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        except Exception:
            context = None
    stats = {}
    if context is not None:
        try:
            stats = context.cert_store_stats()
        except Exception:
            pass
    return {
        'endpoint': str(endpoint),
        'hostname': parsed.hostname or '',
        'port': parsed.port,
        'python': sys.version.split()[0],
        'openssl': ssl.OPENSSL_VERSION,
        'utc_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'verify_mode': getattr(context, 'verify_mode', None),
        'check_hostname': getattr(context, 'check_hostname', None),
        'certificate_store': stats,
        'default_cafile': paths.cafile,
        'default_capath': paths.capath,
        'openssl_cafile': paths.openssl_cafile,
        'openssl_capath': paths.openssl_capath,
        'ssl_cert_file_override': bool(os.environ.get('SSL_CERT_FILE')),
        'ssl_cert_dir_override': bool(os.environ.get('SSL_CERT_DIR')),
        'proxies': _sanitized_proxies(),
        'error_type': error.__class__.__name__ if error is not None else '',
        'verify_code': getattr(error, 'verify_code', None),
        'verify_message': str(
            getattr(error, 'verify_message', '') or ''
        ),
    }


def _connect_websocket(connect, endpoint, **kwargs):
    """Open one verified WebSocket and preserve actionable TLS failure data."""
    context = None
    if urlsplit(endpoint).scheme == 'wss':
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        kwargs['ssl'] = context
    try:
        return connect(endpoint, **kwargs)
    except (ssl.SSLCertVerificationError, ssl.CertificateError) as exc:
        diagnostics = tls_diagnostics(endpoint, context=context, error=exc)
        raise ArchipelagoTlsError(endpoint, exc, diagnostics) from exc
    except ssl.SSLError as exc:
        diagnostics = tls_diagnostics(endpoint, context=context, error=exc)
        raise ArchipelagoTlsError(endpoint, exc, diagnostics) from exc


def _decode_commands(message):
    if isinstance(message, bytes):
        message = message.decode('utf-8')
    try:
        commands = json.loads(message)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchipelagoProtocolError('Server sent invalid JSON.') from exc
    if not isinstance(commands, list):
        raise ArchipelagoProtocolError('Server packet root must be a list.')
    if not all(
        isinstance(command, dict) and isinstance(command.get('cmd'), str)
        for command in commands
    ):
        raise ArchipelagoProtocolError('Server packet contains an invalid command.')
    return commands


def _send_commands(socket, *commands):
    socket.send(json.dumps(commands, separators=(',', ':')))


def _connect_command(slot_name, password, client_uuid):
    slot = str(slot_name or '').strip()
    if not slot:
        raise ValueError('Archipelago slot name is required.')
    uuid = str(client_uuid or '').strip()
    if not uuid:
        raise ValueError('Archipelago client UUID is required.')
    major, minor, build = CLIENT_VERSION
    return {
        'cmd': 'Connect',
        'password': str(password or ''),
        'game': GAME_NAME,
        'name': slot,
        'uuid': uuid,
        'version': {
            'major': major,
            'minor': minor,
            'build': build,
            'class': 'Version',
        },
        'items_handling': ITEMS_HANDLING_ALL,
        'tags': ['AP'],
        'slot_data': True,
    }


def validate_slot_data(value):
    """Validate data needed before launcher settings may be locked."""
    if not isinstance(value, Mapping):
        raise ArchipelagoProtocolError('Connected packet has no slot data.')
    slot_data = dict(value)
    slot_data_version = slot_data.get('slot_data_version')
    if slot_data_version not in SUPPORTED_SLOT_DATA_VERSIONS:
        raise ArchipelagoProtocolError(
            'Unsupported Mental Omega slot-data version: '
            f"{slot_data.get('slot_data_version')!r}."
        )
    if slot_data.get('randomizer_version') != SUPPORTED_RANDOMIZER_VERSION:
        raise ArchipelagoProtocolError(
            'Slot requires Mental Omega Randomizer '
            f"{slot_data.get('randomizer_version')!r}; "
            f'client is {SUPPORTED_RANDOMIZER_VERSION}.'
        )
    for checksum_name in ('catalogue_checksum', 'manifest_checksum'):
        checksum = slot_data.get(checksum_name)
        if (
            not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in '0123456789abcdef' for character in checksum)
        ):
            raise ArchipelagoProtocolError(
                f'Slot data {checksum_name} is invalid.'
            )
    run_manifest = slot_data.get('run_manifest')
    if not isinstance(run_manifest, Mapping):
        raise ArchipelagoProtocolError('Slot data has no run manifest.')
    unsigned_manifest = dict(run_manifest)
    unsigned_manifest.pop('manifest_checksum', None)
    calculated_manifest_checksum = sha256(json.dumps(
        unsigned_manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')).hexdigest()
    if calculated_manifest_checksum != slot_data['manifest_checksum']:
        raise ArchipelagoProtocolError('Slot data run-manifest checksum is invalid.')
    if run_manifest.get('manifest_checksum') != slot_data['manifest_checksum']:
        raise ArchipelagoProtocolError('Slot data manifest checksums disagree.')
    if run_manifest.get('catalogue_checksum') != slot_data['catalogue_checksum']:
        raise ArchipelagoProtocolError('Slot data catalogue checksums disagree.')
    mission_order = slot_data.get('mission_order')
    if not isinstance(mission_order, list) or not mission_order:
        raise ArchipelagoProtocolError('Slot data has no mission order.')
    if not all(isinstance(code, str) and code for code in mission_order):
        raise ArchipelagoProtocolError('Slot data mission order is invalid.')
    locations = slot_data.get('locations')
    if not isinstance(locations, Mapping) or not locations:
        raise ArchipelagoProtocolError('Slot data has no location mapping.')
    if set(locations) != set(mission_order):
        raise ArchipelagoProtocolError(
            'Slot data location missions do not match mission order.'
        )
    normalized_locations = {}
    all_location_ids = set()
    for code in mission_order:
        checks = locations[code]
        if not isinstance(checks, Mapping):
            raise ArchipelagoProtocolError(
                f'Slot data locations for {code} are invalid.'
            )
        normalized_checks = {}
        for check_id, location_ids in checks.items():
            if not isinstance(check_id, str) or not check_id:
                raise ArchipelagoProtocolError(
                    f'Slot data check ID for {code} is invalid.'
                )
            if (
                not isinstance(location_ids, list)
                or not location_ids
                or any(
                    not isinstance(location_id, int)
                    or isinstance(location_id, bool)
                    or location_id <= 0
                    for location_id in location_ids
                )
                or len(set(location_ids)) != len(location_ids)
                or not all_location_ids.isdisjoint(location_ids)
            ):
                raise ArchipelagoProtocolError(
                    f'Slot data location IDs for {code}/{check_id} are invalid.'
                )
            normalized_checks[check_id] = list(location_ids)
            all_location_ids.update(location_ids)
        normalized_locations[code] = normalized_checks
    if not all_location_ids:
        raise ArchipelagoProtocolError('Slot data has no active locations.')
    items = slot_data.get('items')
    if not isinstance(items, Mapping) or not items:
        raise ArchipelagoProtocolError('Slot data has no item mapping.')
    normalized_items = {}
    try:
        for item_id, reward_name in items.items():
            numeric_id = int(item_id)
            if numeric_id <= 0 or not isinstance(reward_name, str):
                raise ValueError
            reward_name = reward_name.strip()
            if not reward_name or numeric_id in normalized_items:
                raise ValueError
            normalized_items[numeric_id] = reward_name
    except (TypeError, ValueError) as exc:
        raise ArchipelagoProtocolError(
            'Slot data item mapping is invalid.'
        ) from exc
    slot_data['items'] = normalized_items
    slot_data['locations'] = normalized_locations
    raw_local_victories = slot_data.get('local_victories', {})
    if slot_data_version >= 5:
        if (
            not isinstance(raw_local_victories, Mapping)
            or set(raw_local_victories) != set(mission_order)
        ):
            raise ArchipelagoProtocolError(
                'Slot data local victories do not match mission order.'
            )
    elif raw_local_victories:
        raise ArchipelagoProtocolError(
            'Legacy slot data cannot contain local-victory mappings.'
        )
    normalized_local_victories = {}
    logic_item_ids = set()
    logic_location_ids = set()
    for code, raw_entry in raw_local_victories.items():
        if not isinstance(raw_entry, Mapping):
            raise ArchipelagoProtocolError(
                f'Slot data local victory for {code} is invalid.'
            )
        item_id = raw_entry.get('item')
        location_id = raw_entry.get('location')
        if (
            not isinstance(item_id, int)
            or isinstance(item_id, bool)
            or item_id <= 0
            or not isinstance(location_id, int)
            or isinstance(location_id, bool)
            or location_id <= 0
            or item_id in logic_item_ids
            or location_id in logic_location_ids
            or location_id in all_location_ids
            or normalized_items.get(item_id)
            != f'Mental Omega Local Victory: {code}'
        ):
            raise ArchipelagoProtocolError(
                f'Slot data local victory for {code} is invalid.'
            )
        logic_item_ids.add(item_id)
        logic_location_ids.add(location_id)
        normalized_local_victories[code] = {
            'item': item_id,
            'location': location_id,
        }
    slot_data['local_victories'] = normalized_local_victories
    for key in (
        'randomizer_version',
        'randomizer_seed',
        'campaign_filter',
        'progression_mode',
        'mission_goal',
        'mission_order',
        'goal',
    ):
        if run_manifest.get(key) != slot_data.get(key):
            raise ArchipelagoProtocolError(
                f'Slot data {key} disagrees with run manifest.'
            )
    state_snapshot = run_manifest.get('state_snapshot')
    if not isinstance(state_snapshot, Mapping):
        raise ArchipelagoProtocolError(
            'Slot data run manifest has no server state snapshot.'
        )
    if (
        state_snapshot.get('seed') != slot_data.get('randomizer_seed')
        or state_snapshot.get('mission_order') != mission_order
        or state_snapshot.get('progression_mode')
        != slot_data.get('progression_mode')
        or state_snapshot.get('campaign_filter')
        != slot_data.get('campaign_filter')
    ):
        raise ArchipelagoProtocolError(
            'Slot data server state identity is inconsistent.'
        )
    state_checks = state_snapshot.get('mission_checks')
    if not isinstance(state_checks, Mapping):
        raise ArchipelagoProtocolError(
            'Slot data server state has no mission checks.'
        )
    for code, checks in normalized_locations.items():
        snapshot_checks = state_checks.get(code)
        if not isinstance(snapshot_checks, list):
            raise ArchipelagoProtocolError(
                f'Slot data server state checks for {code} are invalid.'
            )
        snapshot_ids = {
            str(check.get('id'))
            for check in snapshot_checks
            if isinstance(check, Mapping) and check.get('id')
        }
        if not set(checks).issubset(snapshot_ids):
            raise ArchipelagoProtocolError(
                f'Slot data server state misses active checks for {code}.'
            )
    slot_data['run_manifest'] = dict(run_manifest)
    return slot_data


def _location_ids(command, key):
    values = command.get(key, [])
    if not isinstance(values, list) or not all(isinstance(value, int) for value in values):
        raise ArchipelagoProtocolError(f'Connected {key} list is invalid.')
    return tuple(values)


def _slot_info(value):
    if not isinstance(value, Mapping):
        return {}
    result = {}
    for raw_slot, raw_info in value.items():
        if not isinstance(raw_info, Mapping):
            continue
        try:
            slot = int(raw_slot)
        except (TypeError, ValueError):
            continue
        name = str(raw_info.get('name') or '').strip()
        game = str(raw_info.get('game') or '').strip()
        if slot < 0 or not name:
            continue
        result[slot] = {
            'name': name,
            'game': game,
            'type': int(raw_info.get('type') or 0),
        }
    return result


def connect_slot(server, slot_name, password='', client_uuid='mental-omega', timeout=10.0):
    """Connect, authenticate, validate slot data, then close and return identity."""
    try:
        from websockets.sync.client import connect
    except ImportError as exc:
        raise ArchipelagoHandshakeError(
            'The websockets runtime dependency is not installed.'
        ) from exc

    endpoint = normalize_server_uri(server)
    deadline = time.monotonic() + max(0.1, float(timeout))
    connect_command = _connect_command(slot_name, password, client_uuid)
    seed_name = ''
    connect_sent = False

    try:
        with _connect_websocket(
            connect,
            endpoint,
            compression='deflate',
            open_timeout=max(0.1, float(timeout)),
            close_timeout=2,
            max_size=16 * 1024 * 1024,
        ) as socket:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Timed out waiting for Archipelago handshake.')
                for command in _decode_commands(socket.recv(timeout=remaining)):
                    command_name = command['cmd']
                    if command_name == 'RoomInfo':
                        seed_name = str(command.get('seed_name', ''))
                        games = command.get('games', [])
                        if not isinstance(games, list) or GAME_NAME not in games:
                            raise ArchipelagoProtocolError(
                                'Server room does not contain a Mental Omega slot.'
                            )
                        if not connect_sent:
                            _send_commands(socket, connect_command)
                            connect_sent = True
                    elif command_name == 'ConnectionRefused':
                        raise ArchipelagoConnectionRefused(command.get('errors'))
                    elif command_name == 'Connected':
                        if not connect_sent:
                            raise ArchipelagoProtocolError(
                                'Server sent Connected before RoomInfo.'
                            )
                        return HandshakeResult(
                            endpoint=endpoint,
                            seed_name=seed_name,
                            team=int(command['team']),
                            slot=int(command['slot']),
                            checked_locations=_location_ids(
                                command, 'checked_locations'
                            ),
                            missing_locations=_location_ids(
                                command, 'missing_locations'
                            ),
                            slot_data=validate_slot_data(
                                command.get('slot_data')
                            ),
                            slot_info=_slot_info(command.get('slot_info')),
                        )
    except ArchipelagoHandshakeError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ArchipelagoProtocolError(
            'Archipelago handshake packet is missing required data.'
        ) from exc
