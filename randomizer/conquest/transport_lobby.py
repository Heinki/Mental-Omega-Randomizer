"""Bounded, paired TCP control channel for one host and up to three guests."""

import base64
import binascii
import copy
import hashlib
import hmac
import json
import queue
import re
import secrets
import select
import socket
import threading
import time
import zlib

from .transport_feature import player_count, require_enabled
from .transport_network import probe_network
from .transport_interfaces import unicast_ipv4, zerotier_ipv4_addresses
from .transport_compatibility import FINGERPRINT_POLICY, normalize_text


PROTOCOL = 7
LOBBY_PORT = 19420
MAX_WIRE = 16 * 1024 * 1024
MAX_DATA = 32 * 1024 * 1024
from .profile import INSTALLATION_FILES



def pack(data):
    if len(data) > MAX_DATA:
        raise ValueError('Co-op data exceeds size limit.')
    return base64.b64encode(zlib.compress(data)).decode('ascii')


def unpack(value):
    try:
        decoder = zlib.decompressobj()
        data = decoder.decompress(base64.b64decode(value, validate=True), MAX_DATA + 1)
    except (binascii.Error, zlib.error, TypeError) as exc:
        raise ValueError('Invalid co-op data.') from exc
    if len(data) > MAX_DATA or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('Invalid or excessive co-op data.')
    return data


def installation(root):
    return installation_manifest(root)[0]


def installation_manifest(root):
    fingerprint, files, _raw_files = installation_details(root)
    return fingerprint, files


from functools import lru_cache
from pathlib import Path
from randomizer.core.paths import SOURCE_DIR, FROZEN


def installation_details(root):
    """Compare real native assets, launchers and balance data without loose preloads."""
    paths = [Path(root) / name for name in INSTALLATION_FILES]
    paths.extend(sorted(Path(root).glob('*.mix')))
    if FROZEN:
        import sys
        paths.append(Path(sys.executable))
    else:
        paths.extend(sorted((SOURCE_DIR / 'randomizer').rglob('*.py')))
    paths.extend(sorted(p for p in (SOURCE_DIR / 'configs').rglob('*.json')
                        if 'player' not in p.relative_to(SOURCE_DIR / 'configs').parts))
    signature = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in paths)
    fingerprint, files, raw_files = _installation_details(signature)
    return fingerprint, dict(files), dict(raw_files)


@lru_cache(maxsize=2)
def _installation_details(signature):
    digest = hashlib.sha256()
    files, raw_files = {}, {}
    for name, size, modified in signature:
        path = Path(name)
        key = '__launcher__/' + path.relative_to(SOURCE_DIR).as_posix() if path.is_relative_to(SOURCE_DIR) else path.name
        raw = hashlib.sha256()
        if path.suffix.lower() in ('.ini', '.py', '.json'):
            data = path.read_bytes()
            raw.update(data)
            value = hashlib.sha256(normalize_text(data)).hexdigest()
        else:
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    raw.update(chunk)
            value = raw.hexdigest()
        raw_files[key] = raw.hexdigest()
        files[key] = value
        digest.update(key.encode())
        digest.update(value.encode())
    return digest.hexdigest(), files, raw_files


class _Snapshot:
    """Encode one detached snapshot once, on a sender rather than the UI."""
    def __init__(self, snapshot):
        self.snapshot = copy.deepcopy(snapshot)
        self.data = None
        self.lock = threading.Lock()

    def encode(self):
        with self.lock:
            if self.data is None:
                message = {'type': 'state', 'snapshot': pack(json.dumps(self.snapshot).encode())}
                data = json.dumps(message, separators=(',', ':')).encode() + b'\n'
                if len(data) > MAX_WIRE:
                    raise ValueError('Co-op message exceeds size limit.')
                self.data = data
                self.snapshot = None
            return self.data


class Lobby:
    mode = 'campaign'
    allow_auto_count = False
    def __init__(self, root, role, name, count, *, address='', port=LOBBY_PORT,
                 game_port=1234, pairing_code='', bind_address=''):
        require_enabled()
        if role not in ('host', 'guest'):
            raise ValueError('Select Host or Join.')
        if role == 'guest':
            try:
                address = unicast_ipv4(address)
            except ValueError:
                raise ValueError(
                    'Enter only the host\'s ZeroTier Managed IPv4: four numbers separated by dots. '
                    'Do not include /24, a port, a network ID, or the pairing code.'
                ) from None
        if bind_address:
            bind_address = unicast_ipv4(bind_address)
        if isinstance(name, str):
            name = name.strip()
        if not isinstance(name, str) or not name.strip() or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name):
            raise ValueError('Player name must contain 1–15 letters, digits, spaces, underscores or hyphens.')
        if not 1 <= int(port) <= 65535 or not 1 <= int(game_port) <= 65535:
            raise ValueError('Ports must be between 1 and 65535.')
        if not isinstance(pairing_code, str) or not pairing_code.strip() or len(pairing_code) > 128:
            raise ValueError('Enter the host pairing code.')
        self.root, self.role, self.name = root, role, name
        self.count = player_count(count)
        self.address, self.port, self.game_port = address, int(port), int(game_port)
        self.pairing_code = pairing_code.strip()
        self.bind_address = bind_address
        self.events = queue.Queue()
        self.players = [{'name': name, 'ip': '127.0.0.1', 'port': self.game_port}]
        self.slot = 0
        self.peers = {}
        self.outbound = {}
        self.closed = threading.Event()
        self.lock = threading.RLock()
        self.listeners = []
        self.connected = False
        self.network_release = threading.Event()
        self.network_ready = set()
        self.network_token = ''
        self.pairing = None
        self.last_received = {}

    def start(self):
        threading.Thread(target=self._run, daemon=True, name='ConquestLobby').start()

    def close(self):
        with self.lock:
            if self.closed.is_set():
                return
            self.closed.set()
            self.connected = False
            self.network_release.set()
            connections = [*self.listeners, self.pairing, *self.peers.values()]
            for outgoing in self.outbound.values():
                try:
                    outgoing.put_nowait(None)
                except queue.Full:
                    pass  # The active writer will notice closed after shutdown.
        threading.Thread(target=self._close_sockets, args=(connections,),
                         daemon=True, name='ConquestClose').start()

    @staticmethod
    def _close_sockets(connections):
        for connection in connections:
            if connection:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()

    def _register_peer(self, slot, connection):
        with self.lock:
            if self.closed.is_set():
                connection.close()
                raise ConnectionAbortedError('Co-op connection cancelled.')
            outgoing = queue.Queue(maxsize=32)
            self.peers[slot] = connection
            self.outbound[slot] = outgoing
        threading.Thread(target=self._writer, args=(slot, connection, outgoing),
                         daemon=True, name=f'ConquestSend-{slot}').start()

    def _writer(self, slot, connection, outgoing):
        try:
            while not self.closed.is_set():
                data = outgoing.get()
                if data is None or self.closed.is_set():
                    return
                if isinstance(data, _Snapshot):
                    data = data.encode()
                started = time.monotonic()
                connection.sendall(data)
                elapsed = time.monotonic() - started
                if elapsed >= 0.25:
                    self.events.put(('diagnostic', ('coop_slow_send', {
                        'slot': slot, 'bytes': len(data), 'seconds': round(elapsed, 3),
                        'queued': outgoing.qsize(),
                    })))
        except (OSError, ValueError, TypeError) as exc:
            if not self.closed.is_set():
                self.events.put(('error', f'Co-op send to player {slot + 1} failed: {exc}'))
                self.close()

    @staticmethod
    def receive(stream):
        data = stream.readline(MAX_WIRE + 1)
        if not data:
            raise ConnectionError('Co-op peer disconnected before sending a message.')
        if len(data) > MAX_WIRE:
            raise ValueError('Co-op message exceeds size limit.')
        if not data.endswith(b'\n'):
            raise ConnectionError('Co-op peer disconnected before completing a message.')
        message = json.loads(data)
        if not isinstance(message, dict):
            raise ValueError('Invalid co-op message.')
        return message

    def send(self, message, slot=None):
        data = json.dumps(message, separators=(',', ':')).encode() + b'\n'
        if len(data) > MAX_WIRE:
            raise ValueError('Co-op message exceeds size limit.')
        self._enqueue(data, slot)

    def send_snapshot(self, snapshot):
        """Keep state ahead of later prepare/go messages in each peer's FIFO."""
        self._enqueue(_Snapshot(snapshot))

    def _enqueue(self, data, slot=None):
        with self.lock:
            if self.closed.is_set():
                raise ConnectionError('Co-op lobby is disconnected.')
            targets = [self.outbound[slot]] if slot is not None else list(self.outbound.values())
            for outgoing in targets:
                try:
                    outgoing.put_nowait(data)
                except queue.Full:
                    reason = 'Co-op peer cannot keep up with queued messages. Reconnect the lobby.'
                    self.events.put(('error', reason))
                    self.close()
                    raise ConnectionError(reason) from None

    def _connect_to_host(self):
        deadline = time.monotonic() + 30
        while not self.closed.is_set():
            try:
                return socket.create_connection(
                    (self.address, self.port), timeout=min(5, max(0.001, deadline - time.monotonic())),
                    source_address=(self.bind_address, 0) if self.bind_address else None,
                )
            except (ConnectionRefusedError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise
                self.closed.wait(min(0.25, max(0, deadline - time.monotonic())))
        raise ConnectionAbortedError('Co-op connection cancelled.')

    def _open_host_listeners(self):
        addresses = (self.bind_address,) if self.bind_address else zerotier_ipv4_addresses()
        for address in addresses:
            listener = socket.create_server((unicast_ipv4(address), self.port), backlog=3)
            with self.lock:
                if self.closed.is_set():
                    listener.close()
                    raise ConnectionAbortedError('Co-op connection cancelled.')
                self.listeners.append(listener)

    def _start_network_check(self):
        threading.Thread(target=self._check_network, daemon=True, name='ConquestUDP').start()

    def _check_network(self):
        try:
            self.events.put(('status', f'Checking game UDP {self.game_port} between all players...'))
            probe_network(self.players, self.slot, self.network_token, self.closed,
                          self.network_release, self._network_checked, bind_address=self.bind_address)
            if not self.closed.is_set() and self.network_release.is_set():
                self.connected = True
                now = time.monotonic()
                self.last_received = {slot: now for slot in self.peers}
                for connection in list(self.peers.values()):
                    connection.settimeout(30)
                threading.Thread(target=self._heartbeat, daemon=True, name='ConquestHeartbeat').start()
                self.events.put(('connected', self.players))
        except (OSError, ValueError) as exc:
            if not self.closed.is_set():
                self.events.put(('error', str(exc)))
                self.close()

    def _heartbeat(self):
        while not self.closed.wait(3):
            try:
                if any(time.monotonic() - received > 25 for received in list(self.last_received.values())):
                    raise TimeoutError('Co-op control connection lost. Reconnect the lobby before launching another mission.')
                self.send({'type': 'ping'})
            except OSError as exc:
                if not self.closed.is_set():
                    self.events.put(('error', str(exc)))
                    self.close()
                return

    def _network_checked(self):
        if self.role == 'guest':
            self.send({'type': 'network_ready'})
        else:
            self._mark_network_ready(0)

    def _mark_network_ready(self, slot):
        with self.lock:
            self.network_ready.add(slot)
            if self.network_ready == set(range(self.count)) and not self.network_release.is_set():
                self.send({'type': 'network_ok'})
                self.network_release.set()

    def _run(self):
        phase = 'reading the local native game runtime'
        stream = None
        try:
            fingerprint, self.runtime_files, raw_files = installation_details(self.root)
            self.events.put(('diagnostic', ('coop_runtime_manifest', {
                'role': self.role, 'fingerprint': fingerprint, 'files': self.runtime_files,
                'fingerprint_policy': FINGERPRINT_POLICY, 'raw_files': raw_files,
            })))
            if self.role == 'host':
                phase = f'opening the host lobby (TCP {self.port})'
                self._open_host_listeners()
                self.events.put(('status', f'Waiting for {self.count - 1} guests'))
                while len(self.players) < self.count and not self.closed.is_set():
                    available, _write, _error = select.select(self.listeners, [], [], 0.5)
                    if not available:
                        continue
                    connection, remote = available[0].accept()
                    try:
                        self.pairing = connection
                        self._pair(connection, fingerprint, remote[0])
                        self.pairing = None
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        connection.close()
                        self.pairing = None
                        self.events.put(('status', f'Guest rejected: {exc}'))
                if self.closed.is_set():
                    return
                with self.lock:
                    listeners, self.listeners = self.listeners, []
                for listener in listeners:
                    listener.close()
                self.network_token = secrets.token_hex(32)
                for slot in list(self.peers):
                    self.send({'type': 'roster', 'players': self.players, 'slot': slot,
                               'network_token': self.network_token}, slot)
                self._start_network_check()
            else:
                phase = f'connecting to the host over ZeroTier (TCP {self.port})'
                self.events.put(('status', f'Connecting to host (TCP {self.port})...'))
                connection = self._connect_to_host()
                self._register_peer(0, connection)
                connection.settimeout(15)
                stream = connection.makefile('rb')
                phase = 'waiting for the host greeting'
                self.events.put(('status', 'Host reached; checking native game runtime...'))
                hello = self.receive(stream)
                if hello.get('protocol') != PROTOCOL:
                    raise ValueError('Co-op protocol differs. Update every launcher to the same build.')
                if hello.get('mode', 'campaign') != self.mode:
                    raise ValueError('Host and guest must select the same game mode.')
                if self.allow_auto_count:
                    count = hello.get('count')
                    if type(count) is not int or count not in (2, 3):
                        raise ValueError('Host supplied an invalid Fortress player count.')
                    self.count = count
                if hello.get('fingerprint_policy') != FINGERPRINT_POLICY:
                    raise ValueError('native game compatibility check differs. Update both launchers to the same build.')
                nonce = hello['nonce']
                proof = hmac.new(self.pairing_code.encode(), nonce.encode(), hashlib.sha256).hexdigest()
                phase = 'checking native game runtime and pairing code with the host'
                self.send({'type': 'hello', 'protocol': PROTOCOL, 'name': self.name,
                           'mode': self.mode,
                           'count': self.count, 'port': self.game_port,
                           'fingerprint': fingerprint, 'files': self.runtime_files, 'proof': proof,
                           'fingerprint_policy': FINGERPRINT_POLICY,
                           'folder': str(self.root.resolve()), 'node': socket.gethostname()})
                paired = self.receive(stream)
                expected = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
                if (paired.get('type') == 'rejected'
                        and hmac.compare_digest(str(paired.get('proof', '')), expected)):
                    if paired.get('reason') == 'runtime':
                        raise ValueError(self._runtime_mismatch(hello, 'Host'))
                    reasons = {'protocol': 'Co-op protocol differs. Update both launchers.',
                               'count': 'Player count differs. Choose the same count on both PCs.'}
                    detail = paired.get('detail')
                    raise ValueError(reasons.get(paired.get('reason'), detail if isinstance(detail, str) else 'Host rejected the connection.'))
                if paired.get('type') != 'paired' or not hmac.compare_digest(str(paired.get('proof', '')), expected):
                    raise ValueError('Host did not authenticate with the pairing code. Check that both codes match.')
                if hello.get('fingerprint') != fingerprint:
                    raise ValueError(self._runtime_mismatch(hello, 'Host'))
                connection.settimeout(None)
                self.events.put(('status', f'Paired; waiting for all {self.count} players...'))
                threading.Thread(target=self._reader, args=(0, stream), daemon=True).start()
                stream = None  # The reader owns the stream after pairing.
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if not self.closed.is_set():
                if isinstance(exc, TimeoutError):
                    detail = f'Timed out while {phase}.'
                    if phase.startswith('connecting to the host'):
                        detail += f' Confirm Host is waiting and its firewall allows TCP {self.port} on ZeroTier.'
                else:
                    detail = f'Failed while {phase}: {exc}'
                self.events.put(('error', detail))
                self.close()
        finally:
            if stream is not None:
                stream.close()

    def _runtime_mismatch(self, remote, peer):
        files = remote.get('files')
        differences = {}
        if isinstance(files, dict):
            for name, local_hash in self.runtime_files.items():
                remote_hash = files.get(name)
                if remote_hash != local_hash:
                    # Only fixed relative paths and hashes enter diagnostic output.
                    valid = isinstance(remote_hash, str) and re.fullmatch(r'[0-9a-f]{64}', remote_hash)
                    differences[name] = {'local': local_hash, 'remote': remote_hash if valid else 'unavailable'}
        self.events.put(('diagnostic', ('coop_runtime_mismatch', {
            'role': self.role, 'files': differences,
        })))
        if differences:
            return (f'{peer} native game runtime differs: ' + ', '.join(differences)
                    + '. Use matching native game game files on both PCs; see connection log for hashes.')
        return (f'{peer} native game runtime differs. Use matching native game game files on both PCs. '
                'Update both launchers for per-file diagnostics.')

    def _pair(self, connection, fingerprint, ip):
        connection.settimeout(15)
        nonce = secrets.token_hex(24)
        connection.sendall((json.dumps({'nonce': nonce, 'protocol': PROTOCOL, 'fingerprint': fingerprint,
                                       'mode': self.mode,
                                       'count': self.count,
                                       'files': self.runtime_files,
                                       'fingerprint_policy': FINGERPRINT_POLICY}) + '\n').encode())
        stream = connection.makefile('rb')
        try:
            self._authenticate_guest(connection, stream, fingerprint, nonce, ip)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            try:
                proof = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
                connection.sendall((json.dumps({'type': 'rejected', 'reason': 'setup',
                                               'detail': str(exc), 'proof': proof}) + '\n').encode())
            except OSError:
                pass
            stream.close()
            raise

    def _authenticate_guest(self, connection, stream, fingerprint, nonce, ip):
        hello = self.receive(stream)
        expected = hmac.new(self.pairing_code.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(hello.get('proof', '')), expected):
            raise ValueError('Pairing code differs. Guest must paste the host pairing code.')
        reason = None
        detail = ''
        if hello.get('mode', 'campaign') != self.mode:
            reason, detail = 'mode', 'Host and guest must select the same game mode.'
        elif hello.get('protocol') != PROTOCOL or hello.get('fingerprint_policy') != FINGERPRINT_POLICY:
            reason, detail = 'protocol', 'Co-op protocol differs. Update both launchers.'
        elif hello.get('count') != self.count:
            reason, detail = 'count', 'Player count differs. Choose the same count on both PCs.'
        elif hello.get('fingerprint') != fingerprint:
            reason, detail = 'runtime', self._runtime_mismatch(hello, 'Guest')
        if reason:
            proof = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
            connection.sendall((json.dumps({'type': 'rejected', 'reason': reason, 'proof': proof}) + '\n').encode())
            raise ValueError(detail)
        name = str(hello.get('name', '')).strip()
        if not name.strip() or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name):
            raise ValueError('Invalid guest name.')
        if name.casefold() in {player['name'].casefold() for player in self.players}:
            raise ValueError('Players need distinct names.')
        if hello.get('node') == socket.gethostname() and hello.get('folder') == str(self.root.resolve()):
            raise ValueError('Each player needs a separate native game game folder.')
        port = int(hello['port'])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid game UDP port.')
        if hello.get('node') == socket.gethostname() and port == self.game_port:
            raise ValueError('Players on one computer need distinct game UDP ports.')
        if any(player['ip'] == ip and player['port'] == port for player in self.players):
            raise ValueError('Players on one computer need distinct game UDP ports.')
        local_ip = connection.getsockname()[0]
        if len(self.players) > 1 and self.players[0]['ip'] != local_ip:
            raise ValueError('All guests must join the same host interface IPv4.')
        self.players[0]['ip'] = local_ip
        slot = len(self.players)
        proof = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
        connection.sendall((json.dumps({'type': 'paired', 'proof': proof}) + '\n').encode())
        self.players.append({'name': name, 'ip': ip, 'port': port})
        self._register_peer(slot, connection)
        self.events.put(('status', f'{len(self.players)}/{self.count} players ready'))
        connection.settimeout(None)
        threading.Thread(target=self._reader, args=(slot, stream), daemon=True).start()

    def _reader(self, slot, stream):
        try:
            while not self.closed.is_set():
                message = self.receive(stream)
                self.last_received[slot] = time.monotonic()
                if message.get('type') == 'ping':
                    self.send({'type': 'pong'}, slot)
                elif message.get('type') == 'pong':
                    continue
                elif message.get('type') == 'roster' and self.role == 'guest':
                    players = message['players']
                    local_slot = message['slot']
                    if (not isinstance(players, list) or len(players) != self.count
                            or type(local_slot) is not int or not 0 < local_slot < self.count
                            or players[local_slot]['name'] != self.name):
                        raise ValueError('Invalid cooperative player roster.')
                    names, endpoints = set(), set()
                    for player in players:
                        name = player['name']
                        ip = unicast_ipv4(player['ip'])
                        port = int(player['port'])
                        if (not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name)
                                or name.casefold() in names or not 1 <= port <= 65535
                                or (ip, port) in endpoints):
                            raise ValueError('Invalid cooperative player roster.')
                        names.add(name.casefold())
                        endpoints.add((ip, port))
                    token = message['network_token']
                    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{64}', token):
                        raise ValueError('Invalid game network check.')
                    self.players, self.slot, self.network_token = players, local_slot, token
                    self.players[0]['ip'] = self.address
                    self._start_network_check()
                elif message.get('type') == 'network_ready' and self.role == 'host':
                    self._mark_network_ready(slot)
                elif message.get('type') == 'network_ok' and self.role == 'guest':
                    self.network_release.set()
                else:
                    self.events.put(('message', (slot, message)))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if not self.closed.is_set():
                self.events.put(('error', str(exc)))
                self.close()
        finally:
            stream.close()
