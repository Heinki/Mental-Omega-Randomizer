"""Persistent reconnecting Archipelago session worker."""

from dataclasses import dataclass
import queue
import threading
from typing import Any, Mapping

from .handshake import (
    ArchipelagoConnectionRefused,
    ArchipelagoHandshakeError,
    ArchipelagoProtocolError,
    ArchipelagoTlsError,
    HandshakeResult,
    _connect_command,
    _decode_commands,
    _location_ids,
    _send_commands,
    _slot_info,
    _connect_websocket,
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

    def __init__(
        self,
        config,
        event_callback=None,
        checkpoint=None,
        diagnostic_callback=None,
    ):
        self.config = config.normalized()
        self._event_callback = event_callback or (lambda _event: None)
        self._diagnostic_callback = diagnostic_callback or (
            lambda _name, _details: None
        )
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
        checkpoint_format = int(checkpoint.get('format', 1))
        if checkpoint_format not in {1, 2}:
            raise ValueError('Unsupported Archipelago checkpoint format.')
        self._seed_name = str(checkpoint.get('seed_name', ''))
        self._team = self._optional_int(checkpoint.get('team'))
        self._slot = self._optional_int(checkpoint.get('slot'))
        self._completed_locations = {
            int(location)
            for location in checkpoint.get('completed_locations', [])
        }
        # Format 1 mixed server-confirmed locations with every RoomUpdate
        # broadcast seen in a multiworld. Never resend that ambiguous legacy
        # set. Controller reconciliation reconstructs real local MO checks.
        self._pending_locations = (
            {
                int(location)
                for location in checkpoint.get('pending_locations', [])
            }
            if checkpoint_format >= 2
            else set()
        )
        self._server_locations = set()
        self._missing_locations = set()
        self._goal_complete = bool(checkpoint.get('goal_complete', False))
        self._ledger = ReceivedItemLedger.from_checkpoint(checkpoint)
        self._slot_info = {}
        self._game_data = {}
        self._requested_games = set()
        self._metadata_ready = False
        self._deferred_received_items = {}
        self._deferred_location_info = {}
        self._deferred_messages = []

    def _diagnose(self, name, **details):
        try:
            self._diagnostic_callback(str(name), details)
        except Exception:
            pass

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
                'format': 2,
                'seed_name': self._seed_name,
                'team': self._team,
                'slot': self._slot,
                'completed_locations': sorted(self._completed_locations),
                'pending_locations': sorted(self._pending_locations),
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
            self._diagnose(
                'archipelago_session_started',
                endpoint=self.config.server,
                slot_name=self.config.slot_name,
                checkpoint_seed=self._seed_name,
                pending_locations=len(self._pending_locations),
                received_items=len(self._ledger.records),
                acknowledged_items=len(self._ledger.acknowledged_indexes),
            )
            return True

    def stop(self, timeout=5.0):
        self._diagnose(
            'archipelago_session_stop_requested',
            status=self.status,
            endpoint=self.config.server,
            slot_name=self.config.slot_name,
        )
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
                if (
                    location in self._server_locations
                    or location in self._pending_locations
                ):
                    continue
                self._completed_locations.add(location)
                self._pending_locations.add(location)
                added.append(location)
        if added:
            self._diagnose(
                'archipelago_locations_queued',
                count=len(added),
                first_location=min(added),
                last_location=max(added),
                pending_locations=len(self._pending_locations),
                room_seed=self._seed_name,
            )
            self._emit_checkpoint()
            self._outbound.put({
                'cmd': 'LocationChecks',
                'locations': sorted(added),
            })
            self._outbound.put({
                'cmd': 'LocationScouts',
                'locations': sorted(added),
                'create_as_hint': 0,
            })
        return tuple(sorted(added))

    def acknowledge_received(self, indexes):
        indexes = tuple(indexes)
        with self._lock:
            changed = self._ledger.acknowledge(indexes)
        if changed:
            self._diagnose(
                'archipelago_items_acknowledged',
                count=len(indexes),
                acknowledged_items=len(self._ledger.acknowledged_indexes),
                received_items=len(self._ledger.records),
            )
            self._emit_checkpoint()
        return changed

    def mark_goal_complete(self):
        with self._lock:
            changed = not self._goal_complete
            self._goal_complete = True
        if changed:
            self._diagnose(
                'archipelago_goal_queued',
                room_seed=self._seed_name,
                team=self._team,
                slot=self._slot,
            )
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
        self._diagnose(
            'archipelago_connection_status',
            endpoint=self.config.server,
            slot_name=self.config.slot_name,
            **payload,
        )
        self._emit('status', payload)

    def _run(self):
        attempt = 0
        try:
            while not self._stop_event.is_set():
                state = 'connecting' if attempt == 0 else 'reconnecting'
                self._set_status(state, attempt=attempt + 1)
                try:
                    self._connection_cycle()
                except ArchipelagoTlsError as exc:
                    self._diagnose(
                        'archipelago_tls_verification_failed',
                        **exc.diagnostics,
                    )
                    self._emit('error', {
                        'message': str(exc),
                        'fatal': True,
                        'diagnostics': exc.diagnostics,
                    })
                    break
                except (
                    ArchipelagoConnectionRefused,
                    ArchipelagoIdentityMismatch,
                    ArchipelagoProtocolError,
                ) as exc:
                    self._diagnose(
                        'archipelago_connection_fatal_error',
                        error_type=exc.__class__.__name__,
                        error=str(exc),
                    )
                    self._emit('error', {'message': str(exc), 'fatal': True})
                    break
                except ArchipelagoHandshakeError as exc:
                    self._diagnose(
                        'archipelago_handshake_failed',
                        error_type=exc.__class__.__name__,
                        error=str(exc),
                    )
                    self._emit('error', {'message': str(exc), 'fatal': True})
                    break
                except Exception as exc:
                    if self._stop_event.is_set():
                        break
                    self._diagnose(
                        'archipelago_connection_error',
                        error_type=exc.__class__.__name__,
                        error=str(exc) or exc.__class__.__name__,
                    )
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
        with _connect_websocket(
            connect,
            self.config.server,
            compression='deflate',
            open_timeout=self.config.connect_timeout,
            close_timeout=2,
            # Multiworld game metadata can exceed normal packet sizes. Names
            # are required to render WHO/WHAT/WHERE without numeric IDs.
            max_size=64 * 1024 * 1024,
        ) as socket:
            self._diagnose(
                'archipelago_socket_opened',
                endpoint=self.config.server,
                slot_name=self.config.slot_name,
            )
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
                        self._diagnose(
                            'archipelago_room_info_received',
                            room_seed=room_seed_name,
                            games=sorted(str(game) for game in games)
                            if isinstance(games, list) else [],
                            endpoint=self.config.server,
                        )
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
                            slot_info=_slot_info(packet.get('slot_info')),
                        )
                        location_count = sum(
                            len(values)
                            for mission in result.slot_data.get(
                                'locations', {}
                            ).values()
                            for values in mission.values()
                        )
                        self._diagnose(
                            'archipelago_slot_authenticated',
                            room_seed=result.seed_name,
                            randomizer_seed=result.slot_data.get(
                                'randomizer_seed', ''
                            ),
                            manifest_checksum=result.slot_data.get(
                                'manifest_checksum', ''
                            ),
                            progression_mode=result.slot_data.get(
                                'progression_mode', ''
                            ),
                            team=result.team,
                            slot=result.slot,
                            missions=len(result.slot_data.get(
                                'mission_order', ()
                            )),
                            locations=location_count,
                            checked_locations=len(result.checked_locations),
                            missing_locations=len(result.missing_locations),
                        )
                        self._accept_connected(result)
                        authenticated = True
                        self._request_server_metadata(socket, result)
                        self._resynchronize(socket)
                    elif packet_name == 'ReceivedItems':
                        if authenticated:
                            self._accept_received_items(socket, packet)
                    elif packet_name == 'RoomUpdate':
                        if authenticated:
                            self._accept_room_update(packet)
                    elif packet_name == 'DataPackage':
                        if authenticated:
                            self._accept_data_package(packet)
                    elif packet_name == 'LocationInfo':
                        if authenticated:
                            self._accept_location_info(packet)
                    elif packet_name == 'PrintJSON':
                        if self._metadata_ready:
                            self._emit('message', self._message_segments(packet))
                        else:
                            self._deferred_messages.append(dict(packet))
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
            server_checked = set(result.checked_locations)
            self._server_locations = server_checked
            self._pending_locations.difference_update(server_checked)
            self._completed_locations = (
                server_checked | self._pending_locations
            )
            self._missing_locations = set(result.missing_locations)
            self._slot_info = dict(result.slot_info)
        self._emit_checkpoint()
        self._set_status(
            'connected',
            seed_name=result.seed_name,
            team=result.team,
            slot=result.slot,
        )
        self._emit('connected', result)

    def _request_server_metadata(self, socket, result):
        games = {
            str(info.get('game') or '').strip()
            for info in result.slot_info.values()
            if str(info.get('game') or '').strip()
            and str(info.get('game') or '').strip() != 'Archipelago'
        }
        self._requested_games = games
        self._metadata_ready = not games
        commands = []
        if games:
            commands.append({
                'cmd': 'GetDataPackage',
                'games': sorted(games),
            })
        scout_locations = sorted({
            int(location)
            for mission in result.slot_data.get('locations', {}).values()
            if isinstance(mission, Mapping)
            for values in mission.values()
            if isinstance(values, list)
            for location in values
            if int(location) > 0
        })
        if scout_locations:
            commands.append({
                'cmd': 'LocationScouts',
                'locations': scout_locations,
                'create_as_hint': 0,
            })
        if commands:
            _send_commands(socket, *commands)
        self._diagnose(
            'archipelago_metadata_requested',
            games=len(games),
            scouted_locations=len(scout_locations),
            command_count=len(commands),
        )
        if self._metadata_ready:
            self._flush_metadata_events()

    def _resynchronize(self, socket):
        with self._lock:
            pending = sorted(self._pending_locations)
            goal_complete = self._goal_complete
        commands = []
        if pending:
            commands.append({'cmd': 'LocationChecks', 'locations': pending})
        if goal_complete:
            commands.append({'cmd': 'StatusUpdate', 'status': CLIENT_GOAL})
        if commands:
            _send_commands(socket, *commands)
        self._diagnose(
            'archipelago_resynchronization_sent',
            pending_locations=len(pending),
            goal_complete=goal_complete,
            command_count=len(commands),
        )

    def _flush_outbound(self, socket):
        commands = []
        while True:
            try:
                commands.append(self._outbound.get_nowait())
            except queue.Empty:
                break
        if commands:
            _send_commands(socket, *commands)
            self._diagnose(
                'archipelago_outbound_batch_sent',
                command_count=len(commands),
                command_names=[command.get('cmd', '') for command in commands],
                location_count=sum(
                    len(command.get('locations', ()))
                    for command in commands
                    if isinstance(command.get('locations'), list)
                ),
            )

    def _accept_received_items(self, socket, packet):
        items = packet.get('items')
        if not isinstance(items, list):
            raise ArchipelagoProtocolError('ReceivedItems items must be a list.')
        with self._lock:
            pending, desynchronized = self._ledger.ingest(
                packet.get('index'), items
            )
            completed = sorted(self._completed_locations)
        self._diagnose(
            'archipelago_received_items_packet',
            start_index=packet.get('index'),
            received_count=len(items),
            pending_count=len(pending),
            ledger_count=len(self._ledger.records),
            desynchronized=desynchronized,
        )
        # Do not serialize an unacknowledged network inventory on Tk before
        # reward persistence. Archipelago replays it after reconnect; the
        # controller saves rewards first, then acknowledges and checkpoints.
        if pending:
            if self._metadata_ready:
                self._emit(
                    'received_items',
                    tuple(self._resolved_received_item(item) for item in pending),
                )
            else:
                self._deferred_received_items.update({
                    item.index: item for item in pending
                })
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

    @staticmethod
    def _network_name_table(value):
        if not isinstance(value, Mapping):
            return {}
        result = {}
        for name, raw_id in value.items():
            try:
                identifier = int(raw_id)
            except (TypeError, ValueError):
                continue
            if isinstance(raw_id, bool) or not str(name):
                continue
            result[identifier] = str(name)
        return result

    def _accept_data_package(self, packet):
        data = packet.get('data')
        games = data.get('games') if isinstance(data, Mapping) else None
        if not isinstance(games, Mapping):
            raise ArchipelagoProtocolError('DataPackage has no game metadata.')
        for game, raw_data in games.items():
            if not isinstance(raw_data, Mapping):
                continue
            game_name = str(game)
            self._game_data[game_name] = {
                'items': self._network_name_table(
                    raw_data.get('item_name_to_id')
                ),
                'locations': self._network_name_table(
                    raw_data.get('location_name_to_id')
                ),
            }
        self._metadata_ready = self._requested_games.issubset(
            self._game_data
        )
        self._diagnose(
            'archipelago_data_package_received',
            received_games=sorted(str(game) for game in games),
            metadata_ready=self._metadata_ready,
        )
        if self._metadata_ready:
            self._flush_metadata_events()

    @staticmethod
    def _network_item(value):
        if not isinstance(value, Mapping):
            raise ArchipelagoProtocolError('LocationInfo entry is invalid.')
        try:
            return {
                key: int(value[key])
                for key in ('item', 'location', 'player', 'flags')
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ArchipelagoProtocolError(
                'LocationInfo entry is missing numeric fields.'
            ) from exc

    def _accept_location_info(self, packet):
        values = packet.get('locations')
        if not isinstance(values, list):
            raise ArchipelagoProtocolError('LocationInfo locations are invalid.')
        records = [self._network_item(value) for value in values]
        self._diagnose(
            'archipelago_location_info_received',
            count=len(records),
            metadata_ready=self._metadata_ready,
        )
        if self._metadata_ready:
            self._emit(
                'location_info',
                tuple(self._resolved_location_info(value) for value in records),
            )
            return
        self._deferred_location_info.update({
            value['location']: value for value in records
        })

    def _player_metadata(self, slot):
        info = self._slot_info.get(int(slot), {})
        return {
            'slot': int(slot),
            'name': str(info.get('name') or ''),
            'game': str(info.get('game') or ''),
        }

    def _resolved_name(self, game, category, identifier):
        values = self._game_data.get(str(game), {}).get(category, {})
        return str(values.get(int(identifier), ''))

    def _resolved_received_item(self, record):
        source = self._player_metadata(record.player)
        recipient = self._player_metadata(self._slot or 0)
        if int(record.location) == 0:
            source = {
                'slot': int(record.player),
                'name': 'Starting inventory',
                'game': recipient['game'],
            }
        location_name = (
            'Precollected / starting inventory'
            if int(record.location) == 0
            else self._resolved_name(
                source['game'], 'locations', record.location
            )
        )
        return {
            **record.to_dict(),
            'item_name': self._resolved_name(
                recipient['game'], 'items', record.item
            ),
            'from_player': source['name'],
            'from_game': source['game'],
            'recipient_player': recipient['name'],
            'recipient_game': recipient['game'],
            'location_name': location_name,
        }

    def _resolved_location_info(self, record):
        source = self._player_metadata(self._slot or 0)
        recipient = self._player_metadata(record['player'])
        return {
            **record,
            'item_name': self._resolved_name(
                recipient['game'], 'items', record['item']
            ),
            'from_player': source['name'],
            'from_game': source['game'],
            'recipient_player': recipient['name'],
            'recipient_game': recipient['game'],
            'location_name': self._resolved_name(
                source['game'], 'locations', record['location']
            ),
        }

    def _flush_metadata_events(self):
        new_item_count = 0
        location_info_count = 0
        if self._deferred_received_items:
            values = tuple(
                self._resolved_received_item(record)
                for _, record in sorted(self._deferred_received_items.items())
            )
            self._deferred_received_items.clear()
            new_item_count = len(values)
            self._emit('received_items', values)
        pending_indexes = {
            record.index for record in self._ledger.pending
        }
        existing_metadata = tuple(
            self._resolved_received_item(record)
            for record in self._ledger.records
            if record.index not in pending_indexes
        )
        if existing_metadata:
            self._emit('received_metadata', existing_metadata)
        if self._deferred_location_info:
            values = tuple(
                self._resolved_location_info(record)
                for _, record in sorted(self._deferred_location_info.items())
            )
            self._deferred_location_info.clear()
            location_info_count = len(values)
            self._emit('location_info', values)
        self._diagnose(
            'archipelago_metadata_events_flushed',
            new_items=new_item_count,
            existing_item_metadata=len(existing_metadata),
            pending_items=len(pending_indexes),
            location_info=location_info_count,
        )
        if self._deferred_messages:
            values = tuple(self._deferred_messages)
            self._deferred_messages.clear()
            for packet in values:
                self._emit('message', self._message_segments(packet))

    def _accept_room_update(self, packet):
        if 'checked_locations' not in packet:
            return
        checked = _location_ids(packet, 'checked_locations')
        confirmed = []
        with self._lock:
            for location in checked:
                # RoomUpdate is broadcast for checks made by other slots too.
                # It carries no owner. Accept only locations this MO client
                # already reported and is awaiting confirmation for.
                if location not in self._pending_locations:
                    continue
                self._pending_locations.discard(location)
                self._completed_locations.add(location)
                self._server_locations.add(location)
                self._missing_locations.discard(location)
                confirmed.append(location)
        if confirmed:
            self._diagnose(
                'archipelago_locations_confirmed',
                count=len(confirmed),
                first_location=min(confirmed),
                last_location=max(confirmed),
                pending_locations=len(self._pending_locations),
            )
            self._emit_checkpoint()
            self._emit('locations_checked', tuple(confirmed))

    def _item_send_segments(self, packet):
        value = packet.get('item')
        try:
            item = self._network_item(value)
            recipient_slot = int(packet['receiving'])
        except (ArchipelagoProtocolError, KeyError, TypeError, ValueError):
            return None
        source = self._player_metadata(item['player'])
        recipient = self._player_metadata(recipient_slot)
        item_name = self._resolved_name(
            recipient['game'], 'items', item['item']
        )
        location_name = self._resolved_name(
            source['game'], 'locations', item['location']
        )
        if not all((source['name'], recipient['name'], item_name, location_name)):
            return None
        return (
            {'text': source['name'], 'role': 'player', 'slot': source['slot']},
            {'text': f' ({source["game"]})', 'role': 'game'},
            {'text': ' found ', 'role': 'text'},
            {'text': item_name, 'role': 'item', 'flags': item['flags']},
            {'text': ' for ', 'role': 'text'},
            {
                'text': recipient['name'],
                'role': 'player',
                'slot': recipient['slot'],
            },
            {'text': f' ({recipient["game"]})', 'role': 'game'},
            {'text': ' at ', 'role': 'text'},
            {'text': location_name, 'role': 'location'},
        )

    def _message_segments(self, packet):
        if str(packet.get('type') or '') == 'ItemSend':
            item_send = self._item_send_segments(packet)
            if item_send is not None:
                return item_send
        data = packet.get('data', [])
        if not isinstance(data, list):
            return ()
        rendered = []
        for part in data:
            if not isinstance(part, Mapping):
                continue
            text = str(part.get('text', ''))
            part_type = str(part.get('type') or '')
            role = 'text'
            result = {
                'text': text,
                'role': role,
                'color': str(part.get('color') or ''),
            }
            try:
                identifier = int(text)
            except (TypeError, ValueError):
                rendered.append(result)
                continue
            if part_type == 'player_id':
                text = self._player_metadata(identifier)['name'] or text
                result.update({
                    'text': text,
                    'role': 'player',
                    'slot': identifier,
                })
            elif part_type in {'item_id', 'location_id'}:
                try:
                    player = int(part.get('player', self._slot or 0))
                except (TypeError, ValueError):
                    player = self._slot or 0
                game = self._player_metadata(player)['game']
                category = 'items' if part_type == 'item_id' else 'locations'
                text = self._resolved_name(game, category, identifier) or text
                result.update({
                    'text': text,
                    'role': 'item' if part_type == 'item_id' else 'location',
                    'flags': int(part.get('flags') or 0),
                })
            rendered.append(result)
        return tuple(rendered)

    def _message_text(self, packet):
        return ''.join(
            str(part.get('text', ''))
            for part in self._message_segments(packet)
        ).strip()
