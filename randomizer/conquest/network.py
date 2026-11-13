"""Conquest protocol identities and host-authorized campaign commands."""

from randomizer.conquest.transport_lobby import Lobby
from randomizer.conquest.transport_interfaces import unicast_ipv4
from .players import roster, human_ids, gift
from . import campaign


class ConquestLobby(Lobby):
    mode = 'mo-conquest-1'


def validate_endpoints(state, endpoints):
    players = roster(state)
    if not state.get('coop') or not isinstance(endpoints, list) or len(endpoints) != len(players):
        raise ValueError('Network roster differs from the committed campaign.')
    seen = set()
    for player, endpoint in zip(players, endpoints):
        if not isinstance(endpoint, dict) or set(endpoint) != {'name', 'address', 'port'} or endpoint['name'] != player['name']:
            raise ValueError('Invalid Conquest endpoint identity.')
        address, port = unicast_ipv4(endpoint['address']), endpoint['port']
        if type(port) is not int or not 1 <= port <= 65535 or (address, port) in seen:
            raise ValueError('Invalid or repeated Conquest endpoint.')
        seen.add((address, port))


def decision_actor(state):
    battle = state.get('pending')
    if battle:
        return battle.get('decision_actor', 'player')
    return state['phase']


def authorize_action(state, actor, action, values):
    """Never accept a client-supplied faction, wallet, outcome or snapshot."""
    keys = {'recruit': {'node', 'army_id', 'new_army'}, 'move': {'source', 'target', 'army_id'},
            'purchase': {'kind', 'key', 'node'}, 'end': set(), 'auto': set(),
            'launch': set(), 'gift': {'node', 'recipient'}, 'use_item': {'key'}}
    if actor not in human_ids(state) or decision_actor(state) != actor:
        raise ValueError('It is another player’s turn.')
    if action not in keys or not isinstance(values, dict) or not set(values) <= keys[action]:
        raise ValueError('Invalid cooperative campaign command.')
    if action in ('launch', 'auto') and (not state['pending'] or state['pending']['attempt']):
        raise ValueError('This encounter is not available for a battle decision.')
    if action not in ('launch', 'auto'):
        campaign._turn(state, actor)
    if action == 'launch':
        return
    operations = {
        'recruit': lambda: campaign.recruit(state, values['node'], actor,
            army_id=values.get('army_id'), new_army=values.get('new_army', False)),
        'move': lambda: campaign.move(state, values['source'], values['target'], actor, army_id=values.get('army_id')),
        'purchase': lambda: campaign.purchase(state, values['kind'], values.get('key', ''), values.get('node'), actor),
        'use_item': lambda: campaign.use_item(state, values['key'], actor),
        'end': lambda: campaign.end_turn(state, actor),
        'auto': lambda: campaign.autobattle(state),
        'gift': lambda: gift(state, values['node'], values['recipient'], actor),
    }
    try:
        return operations[action]()
    except (KeyError, TypeError) as exc:
        raise ValueError('Incomplete cooperative campaign command.') from exc
