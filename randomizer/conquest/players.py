"""Personal campaign identities and cooperative ownership policies."""

import re


def roster(state):
    return state.get('coop', {}).get('players', [
        dict(id='player', name='Commander', country=state['settings']['player_country'])])


def human_ids(state):
    return tuple(p['id'] for p in roster(state))


def human(state, actor):
    return actor in human_ids(state)


def country(state, actor):
    return next((p['country'] for p in roster(state) if p['id'] == actor), state['settings']['ai_country'])


def label(state, actor):
    return next((p['name'] for p in roster(state) if p['id'] == actor), 'Enemy' if actor == 'ai' else 'Neutral')


def bonus_owners(state, actor):
    return human_ids(state) if human(state, actor) and state.get('coop', {}).get('shared_nodes', False) else (actor,)


def validate_roster(players):
    from .catalogue import FACTIONS
    if not isinstance(players, list) or not 2 <= len(players) <= 4:
        raise ValueError('Conquest co-op needs two to four players.')
    names = set()
    for i, p in enumerate(players):
        if (not isinstance(p, dict) or set(p) != {'id', 'name', 'country'} or
            p['id'] != ('player' if i == 0 else f'player{i+1}') or
            not isinstance(p['name'], str) or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', p['name']) or
            p['name'] != p['name'].strip() or not p['name'] or p['country'] not in FACTIONS or
            p['name'].casefold() in names):
            raise ValueError('Invalid or duplicate Conquest player identity.')
        names.add(p['name'].casefold())


def gift(state, node, recipient, faction):
    from .campaign import _turn, _node, army_at, record
    _turn(state, faction)
    target = _node(state, node)
    if not state.get('coop') or not human(state, faction) or recipient not in human_ids(state) or recipient == faction:
        raise ValueError('Choose another human teammate.')
    if target['owner'] != faction or army_at(state, node):
        raise ValueError('You can give only your own empty territory. Move its army first.')
    if sum(n['owner'] == faction for n in state['nodes']) <= 1:
        raise ValueError('Keep at least one territory of your own.')
    if state['coop']['gifts'][faction] == state['turn']:
        raise ValueError('You already gave a territory this turn.')
    if target.get('gifted_round') == state['turn']:
        raise ValueError('A territory cannot be given again in the same round.')
    target.update(owner=recipient, gifted_round=state['turn'], income_after=state['turn'] + 1)
    state['coop']['gifts'][faction] = state['turn']
    record(state, f'{label(state, faction)} gave this territory to {label(state, recipient)}. Income starts next round; capture rewards do not transfer.', faction, node)
