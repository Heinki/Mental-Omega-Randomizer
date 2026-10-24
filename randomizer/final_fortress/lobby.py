"""Accept Fortress guests in arrival order on one shared lobby port."""

import socket
import threading

from randomizer.coop.lobby import LOBBY_PORT, Lobby


class FortressLobby(Lobby):
    # Every guest must advertise its personal Fundraising rank before launch.
    protocol = 'fortress-auto-2'


class FortressHost:
    """Assign accepted sockets to fixed player slots without changing pairing."""

    def __init__(self, sessions):
        self.sessions = sessions
        self._closed = threading.Event()
        self._listener = None

    def start(self):
        threading.Thread(target=self._run, name='FortressHost', daemon=True).start()

    def close(self):
        self._closed.set()
        if self._listener is not None:
            self._listener.close()
        for lobby in self.sessions.values():
            lobby.close()

    def _run(self):
        events = next(iter(self.sessions.values())).events
        try:
            if self._closed.is_set():
                return
            self._listener = socket.create_server(('0.0.0.0', LOBBY_PORT), backlog=2)
            self._listener.settimeout(0.5)
            events.put(('listening', LOBBY_PORT))
            for slot in sorted(self.sessions):
                while not self._closed.is_set():
                    try:
                        connection, _ = self._listener.accept()
                    except socket.timeout:
                        continue
                    self.sessions[slot].start(connection=connection)
                    break
                if self._closed.is_set():
                    break
        except OSError as exc:
            if not self._closed.is_set():
                events.put(('error', f'Opening the Fortress lobby: {exc}'))
        finally:
            if self._listener is not None:
                self._listener.close()
