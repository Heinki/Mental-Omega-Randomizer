"""Persistent reconnecting Archipelago session worker."""

from dataclasses import dataclass
import queue
import threading
from typing import Any, Mapping

from .handshake import (
    ArchipelagoConnectionRefused,
    ArchipelagoHandshakeError,
    ArchipelagoProtocolError,
    HandshakeResult,
    _connect_command,
    _decode_commands,
    _location_ids,
    _send_commands,
    normalize_server_uri,
    validate_slot_data,
)
from .ledger import ReceivedItemLedger


CLIENT_GOAL = 30


class ArchipelagoIdentityMismatch(ArchipelagoProtocolError):
    """A persisted client checkpoint belongs to another generated session."""


@dataclass(frozen=True)
class SessionConfig:
    server: str
    slot_name: str
    password: str = ''
    client_uuid: str = 'mental-omega'
    connect_timeout: float = 10.0
    reconnect_delay: float = 1.0
    reconnect_delay_max: float = 30.0

    def normalized(self):
        if not str(self.slot_name or '').strip():
            raise ValueError('Archipelago slot name is required.')
        if not str(self.client_uuid or '').strip():
            raise ValueError('Archipelago client UUID is required.')
        return SessionConfig(
            server=normalize_server_uri(self.server),
            slot_name=str(self.slot_name).strip(),
            password=str(self.password or ''),
            client_uuid=str(self.client_uuid).strip(),
            connect_timeout=max(0.1, float(self.connect_timeout)),
            reconnect_delay=max(0.05, float(self.reconnect_delay)),
            reconnect_delay_max=max(
                max(0.05, float(self.reconnect_delay)),
                float(self.reconnect_delay_max),
            ),
        )


@dataclass(frozen=True)
class SessionEvent:
    kind: str
    payload: Any = None


class ArchipelagoSession:
    """Own one worker thread and expose thread-safe synchronization commands."""

    def __init__(self, config, event_callback=None, checkpoint=None):
        self.config = config.normalized()
        self._event_callback = event_callback or (lambda _event: None)
        self._lock = threading.RLock()
        self._socket_lock = threading.Lock()
        self._socket = None
        self._thread = None
        self._stop_event = threading.Event()
        self._outbound = queue.Queue()
        self._status = 'disconnected'

        checkpoint = checkpoint or {}
        if not isinstance(checkpoint, Mapping):
            raise ValueError('Archipelago checkpoint must be an object.')
        if checkpoint.get('format', 1) != 1:
            raise ValueError('Unsupported Archipelago checkpoint format.')
        self._seed_name = str(checkpoint.get('seed_name', ''))
        self._team = self._optional_int(checkpoint.get('team'))
        self._slot = self._optional_int(checkpoint.get('slot'))
        self._completed_locations = {
            int(location)
            for location in checkpoint.get('completed_locations', [])
        }
        self._missing_locations = set()
        self._goal_complete = bool(checkpoint.get('goal_complete', False))
        self._ledger = ReceivedItemLedger.from_checkpoint(checkpoint)

    @staticmethod
    def _optional_int(value):
        return None if value is None else int(value)

    @property
    def status(self):
        with self._lock:
            return self._status

    @property
    def running(self):
        thread = self._thread
        return bool(thread and thread.is_alive())

    def checkpoint(self):
        with self._lock:
            value = {
                'format': 1,
                'seed_name': self._seed_name,
                'team': self._team,
                'slot': self._slot,
                'completed_locations': sorted(self._completed_locations),
                'goal_complete': self._goal_complete,
            }
            value.update(self._ledger.to_checkpoint())
            return value

    def start(self):
        with self._lock:
            if self.running:
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name='MentalOmegaArchipelagoClient',
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout=5.0):
        self._stop_event.set()
        with self._socket_lock:
            socket = self._socket
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(max(0.0, float(timeout)))
        return not self.running

    def report_locations(self, locations):
        added = []
        with self._lock:
            for location in locations:
                location = int(location)
                if location <= 0:
                    raise ValueError('Archipelago location IDs must be positive.')
                if location not in self._completed_locations:
                    self._completed_locations.add(location)
                    added.append(location)
        if added:
            self._emit_checkpoint()
            self._outbound.put({
                'cmd': 'LocationChecks',
                'locations': sorted(added),
            })
        return tuple(sorted(added))

    def acknowledge_received(self, indexes):
        with self._lock:
            changed = self._ledger.acknowledge(indexes)
        if changed:
            self._emit_checkpoint()
        return changed

    def mark_goal_complete(self):
        with self._lock:
            changed = not self._goal_complete
            self._goal_complete = True
        if changed:
            self._emit_checkpoint()
            self._outbound.put({'cmd': 'StatusUpdate', 'status': CLIENT_GOAL})
        return changed

    def send_chat(self, text):
        text = str(text or '').strip()
        if not text:
            return False
        with self._lock:
            if self._status != 'connected':
                return False
        self._outbound.put({'cmd': 'Say', 'text': text})
        return True

    def request_sync(self):
        self._outbound.put({'cmd': 'Sync'})

    def _emit(self, kind, payload=None):
        try:
            self._event_callback(SessionEvent(kind, payload))
        except Exception:
            pass

    def _emit_checkpoint(self):
        self._emit('checkpoint', self.checkpoint())

    def _set_status(self, status, **details):
        with self._lock:
            self._status = status
        payload = {'state': status}
        payload.update(details)
        self._emit('status', payload)

    def _run(self):
        attempt = 0
        try:
            while not self._stop_event.is_set():
                state = 'connecting' if attempt == 0 else 'reconnecting'
                self._set_status(state, attempt=attempt + 1)
                try:
                    self._connection_cycle()
                except (
                    ArchipelagoConnectionRefused,
                    ArchipelagoIdentityMismatch,
                    ArchipelagoProtocolError,
                ) as exc:
                    self._emit('error', {'message': str(exc), 'fatal': True})
                    break
                except ArchipelagoHandshakeError as exc:
                    self._emit('error', {'message': str(exc), 'fatal': True})
                    break
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    self._emit('error', {
                        'message': str(exc) or exc.__class__.__name__,
                        'fatal': False,
                    })
                finally:
                    with self._socket_lock:
                        self._socket = None

                if self._stop_event.is_set():
                    break
                attempt += 1
                delay = min(
                    self.config.reconnect_delay * (2 ** min(attempt - 1, 8)),
                    self.config.reconnect_delay_max,
                )
                self._set_status('reconnecting', attempt=attempt + 1, delay=delay)
                if self._stop_event.wait(delay):
                    break
        finally:
            self._set_status('disconnected')

    def _connection_cycle(self):
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise ArchipelagoHandshakeError(
                'The websockets runtime dependency is not installed.'
            ) from exc

        command = _connect_command(
            self.config.slot_name,
            self.config.password,
            self.config.client_uuid,
        )
        with connect(
            self.config.server,
            compression='deflate',
            open_timeout=self.config.connect_timeout,
            close_timeout=2,
            max_size=16 * 1024 * 1024,
        ) as socket:
            with self._socket_lock:
                self._socket = socket
            connect_sent = False
            authenticated = False
            room_seed_name = ''

            while not self._stop_event.is_set():
                if authenticated:
                    self._flush_outbound(socket)
                try:
                    message = socket.recv(timeout=0.25)
                except TimeoutError:
                    continue
                for packet in _decode_commands(message):
                    packet_name = packet['cmd']
                    if packet_name == 'RoomInfo':
                        room_seed_name = str(packet.get('seed_name', ''))
                        games = packet.get('games', [])
                        if not isinstance(games, list) or 'Mental Omega' not in games:
                            raise ArchipelagoProtocolError(
                                'Server room does not contain a Mental Omega slot.'
                            )
                        if not connect_sent:
                            _send_commands(socket, command)
                            connect_sent = True
                    elif packet_name == 'ConnectionRefused':
                        raise ArchipelagoConnectionRefused(packet.get('errors'))
                    elif packet_name == 'Connected':
                        if not connect_sent:
                            raise ArchipelagoProtocolError(
                                'Server sent Connected before RoomInfo.'
                            )
                        result = HandshakeResult(
                            endpoint=self.config.server,
                            seed_name=room_seed_name,
                            team=int(packet['team']),
                            slot=int(packet['slot']),
                            checked_locations=_location_ids(
                                packet, 'checked_locations'
                            ),
                            missing_locations=_location_ids(
                                packet, 'missing_locations'
                            ),
                            slot_data=validate_slot_data(packet.get('slot_data')),
                        )
                        self._accept_connected(result)
                        authenticated = True
                        self._resynchronize(socket)
                    elif packet_name == 'ReceivedItems':
                        if authenticated:
                            self._accept_received_items(socket, packet)
                    elif packet_name == 'RoomUpdate':
                        if authenticated:
                            self._accept_room_update(packet)
                    elif packet_name == 'PrintJSON':
                        self._emit('message', self._message_text(packet))
                    elif packet_name == 'InvalidPacket':
                        self._emit('error', {
                            'message': str(packet.get('text', 'Invalid packet.')),
                            'fatal': False,
                        })

    def _accept_connected(self, result):
        with self._lock:
            expected = (self._seed_name, self._team, self._slot)
            actual = (result.seed_name, result.team, result.slot)
            if self._seed_name and expected != actual:
                raise ArchipelagoIdentityMismatch(
                    'Saved Archipelago progress belongs to another '
                    f'session/slot: expected {expected!r}, got {actual!r}.'
                )
            self._seed_name, self._team, self._slot = actual
            self._completed_locations.update(result.checked_locations)
            self._missing_locations = set(result.missing_locations)
        self._emit_checkpoint()
        self._set_status(
            'connected',
            seed_name=result.seed_name,
            team=result.team,
            slot=result.slot,
        )
        self._emit('connected', result)

    def _resynchronize(self, socket):
        with self._lock:
            completed = sorted(self._completed_locations)
            goal_complete = self._goal_complete
        commands = []
        if completed:
            commands.append({'cmd': 'LocationChecks', 'locations': completed})
        if goal_complete:
            commands.append({'cmd': 'StatusUpdate', 'status': CLIENT_GOAL})
        if commands:
            _send_commands(socket, *commands)

    def _flush_outbound(self, socket):
        commands = []
        while True:
            try:
                commands.append(self._outbound.get_nowait())
            except queue.Empty:
                break
        if commands:
            _send_commands(socket, *commands)

    def _accept_received_items(self, socket, packet):
        items = packet.get('items')
        if not isinstance(items, list):
            raise ArchipelagoProtocolError('ReceivedItems items must be a list.')
        with self._lock:
            pending, desynchronized = self._ledger.ingest(
                packet.get('index'), items
            )
            completed = sorted(self._completed_locations)
        self._emit_checkpoint()
        if pending:
            self._emit('received_items', pending)
        if desynchronized:
            commands = [{'cmd': 'Sync'}]
            if completed:
                commands.append({
                    'cmd': 'LocationChecks',
                    'locations': completed,
                })
            _send_commands(socket, *commands)
            self._emit('desynchronized', {
                'received_index': int(packet.get('index')),
                'expected_index': self._ledger.next_index,
            })

    def _accept_room_update(self, packet):
        if 'checked_locations' not in packet:
            return
        checked = _location_ids(packet, 'checked_locations')
        changed = False
        with self._lock:
            for location in checked:
                if location not in self._completed_locations:
                    self._completed_locations.add(location)
                    changed = True
                self._missing_locations.discard(location)
        if changed:
            self._emit_checkpoint()
            self._emit('locations_checked', checked)

    @staticmethod
    def _message_text(packet):
        data = packet.get('data', [])
        if not isinstance(data, list):
            return ''
        return ''.join(
            str(part.get('text', ''))
            for part in data
            if isinstance(part, Mapping)
        )
