"""Check bounded lobby connection retries without a network or real delays."""

from pathlib import Path
import sys
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.coop.lobby import Lobby


def guest():
    return Lobby(ROOT, 'guest', 'Guest', address='127.0.0.1',
                 pairing_code='test-private-pairing-code')


def main():
    lobby = guest()
    connection = Mock()
    with patch('randomizer.coop.lobby.socket.create_connection', side_effect=[
        ConnectionRefusedError(), TimeoutError(), connection,
    ]) as connect, patch.object(lobby._closed, 'wait'):
        lobby._connect_to_host()
    assert connect.call_count == 3
    assert lobby._socket is connection

    lobby = guest()
    elapsed = [0.0]

    def timeout(_address, *, timeout):
        elapsed[0] += timeout
        raise TimeoutError()

    def wait(delay):
        elapsed[0] += delay

    with patch('randomizer.coop.lobby.time.monotonic', side_effect=lambda: elapsed[0]), \
            patch('randomizer.coop.lobby.socket.create_connection', side_effect=timeout) as connect, \
            patch.object(lobby._closed, 'wait', side_effect=wait):
        try:
            lobby._connect_to_host()
        except TimeoutError:
            pass
        else:
            raise AssertionError('Unreachable host must time out.')
    assert elapsed[0] == 30
    assert connect.call_count > 1
    assert lobby._socket is None

    lobby = guest()
    with patch('randomizer.coop.lobby.socket.create_connection', side_effect=TimeoutError()) as connect, \
            patch.object(lobby._closed, 'wait', side_effect=lambda _delay: lobby.close()):
        lobby._connect_to_host()
    assert connect.call_count == 1
    assert lobby._socket is None
    assert lobby._closed.is_set()

    lobby = guest()
    with patch('randomizer.coop.lobby.socket.create_connection', side_effect=OSError('bad route')) as connect:
        try:
            lobby._connect_to_host()
        except OSError as exc:
            assert str(exc) == 'bad route'
        else:
            raise AssertionError('Non-transient connection errors must remain visible.')
    assert connect.call_count == 1
    print('Transient refusal/timeout recovery, 30-second deadline, cancellation, error propagation: passed')


if __name__ == '__main__':
    main()
