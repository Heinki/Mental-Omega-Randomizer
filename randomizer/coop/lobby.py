"""One host, one guest: persistent private control channel for a co-op run."""

from __future__ import annotations

import base64
import json
import queue
import socket
import threading
import time
import zlib

from randomizer.coop.direct import _check_separate_install, _installation, _name, _port


LOBBY_PORT = 19420
PROTOCOL = 1
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
    def __init__(self, game_root, role: str, name: str, *, address='', port=LOBBY_PORT):
        if role not in ('host', 'guest'):
            raise ValueError('Invalid co-op role.')
        self.game_root = game_root
        self.role = role
        self.name = _name(name)
        self.address = address
        self.port = _port(port)
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

    def _run(self):
        try:
            if self.role == 'host':
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
                deadline = time.monotonic() + 30
                while not self._closed.is_set():
                    try:
                        self._socket = socket.create_connection(
                            (self.address, self.port), timeout=5
                        )
                        break
                    except ConnectionRefusedError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.25)
                if self._closed.is_set():
                    return
            self._socket.settimeout(30)
            stream = self._socket.makefile('rb')
            self._send_raw({'type': 'hello', 'protocol': PROTOCOL,
                            'name': self.name, 'installation': _installation(self.game_root)})
            hello = self._receive(stream)
            if hello.get('type') != 'hello' or hello.get('protocol') != PROTOCOL:
                raise ValueError('Incompatible co-op lobby peer.')
            self.peer = _name(hello.get('name', ''))
            if self.peer == self.name:
                raise ValueError('Both players need distinct names.')
            _check_separate_install(_installation(self.game_root), hello.get('installation'))
            self.connected = True
            self.events.put(('connected', self.peer))
            self._socket.settimeout(None)
            while not self._closed.is_set():
                message = self._receive(stream)
                if message.get('type') not in {'state', 'select', 'suggest', 'launch'}:
                    raise ValueError('Invalid co-op lobby message.')
                self.events.put(('message', message))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            if not self._closed.is_set():
                self.events.put(('error', str(exc)))
        finally:
            self.connected = False
            if not self._closed.is_set():
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
