"""One host, one guest: persistent private control channel for a co-op run."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import queue
import re
import secrets
import socket
import threading
import time
import zlib

from randomizer.coop.direct import _check_separate_install, _installation, _name, _port
from randomizer.coop.runtime import installation_details, validate_runtime


LOBBY_PORT = 19420
PROTOCOL = 3
MAX_WIRE = 8 * 1024 * 1024
MAX_STATE = 32 * 1024 * 1024


def encode_state(state: dict) -> str:
    raw = json.dumps(state, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_STATE:
        raise ValueError('Shared run state is too large.')
    return base64.b64encode(zlib.compress(raw, 6)).decode('ascii')


def decode_state(encoded: str) -> dict:
    compressed = base64.b64decode(encoded, validate=True)
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(compressed, MAX_STATE + 1)
    if len(raw) > MAX_STATE or decompressor.unconsumed_tail or not decompressor.eof:
        raise ValueError('Shared run state is invalid or too large.')
    state = json.loads(raw)
    if not isinstance(state, dict) or not state.get('coop_mode'):
        raise ValueError('Host did not send a co-op run.')
    return state


class Lobby:
    def __init__(self, game_root, role: str, name: str, *, address='', port=LOBBY_PORT,
                 pairing_code=''):
        if role not in ('host', 'guest'):
            raise ValueError('Invalid co-op role.')
        if role == 'guest':
            try:
                address = str(ipaddress.IPv4Address(str(address).strip()))
            except ipaddress.AddressValueError:
                raise ValueError(
                    "Enter only the host's ZeroTier Managed IPv4: four numbers separated by dots. "
                    'Do not include /24, a port, a network ID, or the pairing code.'
                ) from None
        if not isinstance(pairing_code, str) or not 16 <= len(pairing_code.strip()) <= 128:
            raise ValueError('Enter the host pairing code (16–128 characters).')
        self.game_root = game_root
        self.role = role
        self.name = _name(name)
        self.address = address
        self.port = _port(port)
        self.pairing_code = pairing_code.strip()
        self.events = queue.Queue()
        self._socket = None
        self._listener = None
        self._send_lock = threading.Lock()
        self._closed = threading.Event()
        self.connected = False
        self.peer = ''

    def start(self):
        threading.Thread(target=self._run, name='CoopLobby', daemon=True).start()

    def close(self):
        self._closed.set()
        for connection in (self._socket, self._listener):
            if connection is not None:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
        self.connected = False

    def send(self, message: dict):
        if not self.connected or self._socket is None:
            raise ConnectionError('Co-op peer is not connected.')
        data = json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\n'
        if len(data) > MAX_WIRE:
            raise ValueError('Co-op lobby message is too large.')
        with self._send_lock:
            self._socket.sendall(data)

    def _connect_to_host(self):
        """Retry transient refusal or timeout within one cancellable 30-second window."""
        deadline = time.monotonic() + 30
        while not self._closed.is_set():
            try:
                self._socket = socket.create_connection(
                    (self.address, self.port),
                    timeout=min(5, max(0.001, deadline - time.monotonic())),
                )
                break
            except (ConnectionRefusedError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise
                self._closed.wait(min(0.25, deadline - time.monotonic()))

    def _run(self):
        phase = 'reading the local Mental Omega runtime'
        stream = None
        try:
            runtime = installation_details(self.game_root)
            self.events.put(('diagnostic', ('coop_local_runtime', runtime)))
            if self.role == 'host':
                phase = f'opening the host lobby (TCP {self.port})'
                self._listener = socket.create_server(('0.0.0.0', self.port), backlog=1)
                self.events.put(('listening', self.port))
                self._listener.settimeout(0.5)
                while not self._closed.is_set():
                    try:
                        self._socket, _ = self._listener.accept()
                        break
                    except socket.timeout:
                        continue
                if self._closed.is_set():
                    return
                self._listener.close()
                self._listener = None
            else:
                phase = f'connecting to the host over ZeroTier (TCP {self.port})'
                self.events.put(('status', f'Connecting to host (TCP {self.port})…'))
                self._connect_to_host()
                if self._closed.is_set():
                    return
            self._socket.settimeout(30)
            stream = self._socket.makefile('rb')
            local_nonce = secrets.token_hex(16)
            phase = 'waiting for the peer greeting'
            self.events.put(('status', 'Peer reached; checking runtime and pairing code…'))
            self._send_raw({'type': 'hello', 'protocol': PROTOCOL,
                            'name': self.name, 'installation': _installation(self.game_root),
                            'runtime': runtime,
                            'nonce': local_nonce, 'paired': bool(self.pairing_code)})
            hello = self._receive(stream)
            if hello.get('type') != 'hello' or hello.get('protocol') != PROTOCOL:
                raise ValueError('Co-op protocol differs. Update both launchers to the same build.')
            self.peer = _name(hello.get('name', ''))
            if self.peer == self.name:
                raise ValueError('Both players need distinct names.')
            _check_separate_install(_installation(self.game_root), hello.get('installation'))
            peer_nonce = hello.get('nonce')
            if (not isinstance(peer_nonce, str) or not re.fullmatch(r'[0-9a-f]{32}', peer_nonce)
                    or bool(self.pairing_code) != bool(hello.get('paired'))):
                raise ValueError('Co-op pairing settings differ.')
            host_nonce, guest_nonce = (
                (local_nonce, peer_nonce) if self.role == 'host'
                else (peer_nonce, local_nonce)
            )
            def proof(role):
                payload = f'coop-lobby-v3:{role}:{host_nonce}:{guest_nonce}'.encode('ascii')
                return hmac.new(self.pairing_code.encode('utf-8'), payload,
                                hashlib.sha256).hexdigest()
            self._send_raw({'type': 'proof', 'value': proof(self.role)})
            phase = 'authenticating the pairing code'
            peer_proof = self._receive(stream)
            opposite = 'guest' if self.role == 'host' else 'host'
            if (peer_proof.get('type') != 'proof'
                    or not hmac.compare_digest(str(peer_proof.get('value', '')),
                                               proof(opposite))):
                raise ValueError('Co-op pairing code differs.')
            phase = 'comparing Mental Omega runtime files'
            if isinstance(hello.get('runtime'), dict):
                self.events.put(('diagnostic', ('coop_peer_runtime', hello['runtime'])))
            validate_runtime(runtime, hello.get('runtime'))
            self.connected = True
            self.events.put(('connected', self.peer))
            self._socket.settimeout(None)
            phase = 'receiving lobby messages'
            while not self._closed.is_set():
                message = self._receive(stream)
                if message.get('type') not in {
                    'state', 'select', 'suggest', 'launch',
                    'shop_stage', 'shop_ready', 'shop_victory', 'shop_failure',
                }:
                    raise ValueError('Invalid co-op lobby message.')
                self.events.put(('message', message))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            if not self._closed.is_set():
                detail = f'Timed out while {phase}.' if isinstance(exc, TimeoutError) else f'{phase}: {exc}'
                if isinstance(exc, TimeoutError) and phase.startswith('connecting'):
                    detail += ' Check the host listener, ZeroTier authorization/route and host firewall.'
                self.events.put(('error', detail))
        finally:
            if stream is not None:
                stream.close()
            self.close()
            self.connected = False
            self.events.put(('disconnected', self.peer))

    def _send_raw(self, message):
        data = json.dumps(message, separators=(',', ':')).encode('utf-8') + b'\n'
        self._socket.sendall(data)

    @staticmethod
    def _receive(stream):
        data = stream.readline(MAX_WIRE + 1)
        if not data or len(data) > MAX_WIRE or not data.endswith(b'\n'):
            raise ConnectionError('Co-op peer disconnected or sent invalid data.')
        message = json.loads(data)
        if not isinstance(message, dict):
            raise ValueError('Invalid co-op lobby message.')
        return message
