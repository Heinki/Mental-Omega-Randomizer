import hashlib
import hmac
import json
import socket
import time

from .transport_interfaces import unicast_ipv4


def probe_network(players, slot, token, closed, release, ready, *, bind_address='', timeout=20):
    local_address = unicast_ipv4(bind_address if bind_address else players[slot]['ip'])
    peers = {index: (player['ip'], int(player['port']))
             for index, player in enumerate(players) if index != slot}
    received = set()
    acknowledged = set()
    reported = False
    deadline = time.monotonic() + timeout
    next_send = 0

    def packet(kind, target):
        payload = f'conquest-udp-v1:{kind}:{slot}:{target}'
        proof = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return json.dumps({'kind': kind, 'slot': slot, 'target': target, 'proof': proof}).encode()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        def send(kind, target, endpoint):
            try:
                connection.sendto(packet(kind, target), endpoint)
            except (ConnectionResetError, ConnectionRefusedError):
                # A peer may not have opened its UDP listener yet. Winsock
                # reports its ICMP Port Unreachable on a later send/receive.
                # Retry until the normal all-player check deadline instead
                # of dropping the healthy TCP lobby during startup.
                pass

        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            connection.bind((local_address, int(players[slot]['port'])))
        except OSError as exc:
            raise OSError(f"Cannot open local game UDP {players[slot]['port']}; check the ZeroTier connection and close other game/launcher instances.") from exc
        connection.settimeout(0.1)
        while not closed.is_set() and not release.is_set():
            now = time.monotonic()
            if now >= deadline:
                missing = set(peers) - (received & acknowledged)
                names = ', '.join(players[index]['name'] for index in sorted(missing))
                raise TimeoutError(
                    f'Game UDP check failed for {names or "another player"}. '
                    'Allow game UDP through every PC firewall and ZeroTier flow rules; '
                    'all players must reach every other player, including guests.'
                )
            if now >= next_send:
                for index, endpoint in peers.items():
                    send('ping', index, endpoint)
                next_send = now + 0.25
            try:
                data, endpoint = connection.recvfrom(1024)
            except (socket.timeout, ConnectionResetError, ConnectionRefusedError):
                continue
            try:
                message = json.loads(data)
                sender = message['slot']
                kind = message['kind']
                if (type(sender) is not int or sender not in peers
                        or endpoint != peers[sender] or message['target'] != slot
                        or kind not in ('ping', 'ack')):
                    continue
                payload = f'conquest-udp-v1:{kind}:{sender}:{slot}'
                expected = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(str(message['proof']), expected):
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            if kind == 'ping':
                received.add(sender)
                send('ack', sender, endpoint)
            else:
                acknowledged.add(sender)
            if not reported and received & acknowledged == set(peers):
                reported = True
                ready()
