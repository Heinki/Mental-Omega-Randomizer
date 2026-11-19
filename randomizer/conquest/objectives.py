"""Selectable campaign victory rules shared by solo and cooperative play."""

import random

from .players import actor_ids, allied, coalition


MODES = {
    'territories': 'Capture all enemy nodes',
    'headquarters': 'Capture HQ',
    'turn_limit': 'Most nodes at turn limit',
    'objectives': 'Capture and hold highlighted nodes',
}
DEFAULT_MODE = 'territories'
DEFAULT_TURN_LIMIT = 20
DEFAULT_OBJECTIVE_COUNT = 3
DEFAULT_HOLD_TURNS = 3


def validate_settings(settings):
    mode = settings.get('victory_mode')
    if mode not in MODES:
        raise ValueError('Choose a valid Conquest game mode.')
    if mode == 'turn_limit' and (type(settings.get('turn_limit')) is not int or
                                 not 1 <= settings['turn_limit'] <= 10000):
        raise ValueError('Turn limit must be a whole number from 1 to 10,000.')
    if mode == 'objectives' and (
        type(settings.get('objective_count')) is not int or settings['objective_count'] not in (3, 4, 5) or
        type(settings.get('hold_turns')) is not int or settings['hold_turns'] not in (3, 4, 5)):
        raise ValueError('Choose 3–5 highlighted nodes and 3–5 turns to hold them.')


def team_label(state, side):
    if side is None:
        return 'Nobody'
    teams = state['settings'].get('teams')
    return f'Team {teams[side]}' if teams else {'player': 'Your team', 'ai': 'The enemy'}[side]


def node_counts(state):
    counts = dict.fromkeys((coalition(state, actor) for actor in actor_ids(state)), 0)
    for node in state['nodes']:
        if node['owner'] != 'neutral':
            counts[coalition(state, node['owner'])] += 1
    return counts


def ai_targets(state, actor):
    """Use the active AI's alliances when selecting its strategic objectives."""
    mode = state['settings'].get('victory_mode')
    if mode == 'headquarters':
        return {node['id'] for node in state['nodes'] if node.get('hq')
                and not allied(state, actor, node['hq']) and not allied(state, actor, node['owner'])}
    if mode == 'objectives':
        return {index for index in state['objectives']['nodes']
                if not allied(state, actor, state['nodes'][index]['owner'])}
    return set()


def objective_holder(state):
    owners = {coalition(state, state['nodes'][index]['owner'])
              for index in state['objectives']['nodes']}
    return next(iter(owners)) if len(owners) == 1 and 'neutral' not in owners else None


def initialize(state):
    state['completed_round'] = 0
    if state['settings']['victory_mode'] == 'objectives':
        # Use a separate deterministic stream, preserving map and battle seeds.
        candidates = [node['id'] for node in state['nodes'] if not node.get('hq')]
        if len(candidates) < state['settings']['objective_count']:
            # A nine-node board with four humans can have only four neutral nodes.
            candidates = [node['id'] for node in state['nodes']]
        nodes = sorted(random.Random(state['settings']['seed'] + ':objectives').sample(
            candidates, state['settings']['objective_count']))
        state['objectives'] = dict(nodes=nodes, holder=None, since=None)
        update_control(state)


def update_control(state):
    """Reset the continuous hold immediately when any objective changes sides."""
    if state['settings'].get('victory_mode') != 'objectives':
        return
    progress = state['objectives']
    holder = objective_holder(state)
    if progress['holder'] != holder:
        progress.update(holder=holder, since=state['turn'] if holder else None)


def held_turns(state):
    progress = state['objectives']
    return max(0, state['completed_round'] - progress['since']) if progress['holder'] else 0


def winner(state):
    """Evaluate explicit modes; callers retain the legacy rule for old saves."""
    mode = state['settings']['victory_mode']
    counts = node_counts(state)
    # A side without territory cannot move or recruit, in any game mode.
    active = [side for side, count in counts.items() if count]
    if len(active) == 1:
        return active[0]
    if mode == 'headquarters':
        headquarters = {node['hq']: coalition(state, node['owner'])
                        for node in state['nodes'] if node.get('hq')}
        return next((side for side in active if all(owner == side
            for actor, owner in headquarters.items() if coalition(state, actor) != side)), None)
    if (mode == 'turn_limit' and state['completed_round'] == state['turn'] and
            state['completed_round'] >= state['settings']['turn_limit']):
        leaders = [side for side in active if counts[side] == max(counts.values())]
        if len(leaders) == 1:
            return leaders[0]
    elif mode == 'objectives' and held_turns(state) >= state['settings']['hold_turns']:
        return state['objectives']['holder']
    return None


def validate_progress(state):
    """Reject missing or inconsistent objective progress on disk and the wire."""
    settings = state['settings']
    if 'victory_mode' not in settings:
        if 'objectives' in state or 'completed_round' in state:
            raise ValueError('Conquest objective progress requires a saved game mode.')
        return
    validate_settings(settings)
    completed = state.get('completed_round')
    if (type(completed) is not int or completed not in (state['turn'] - 1, state['turn']) or
        completed == state['turn'] and not state['winner']):
        raise ValueError('Invalid completed Conquest round.')
    if {node.get('hq') for node in state['nodes'] if node.get('hq')} != set(actor_ids(state)):
        raise ValueError('Conquest game modes require every original headquarters.')
    if settings['victory_mode'] != 'objectives':
        if 'objectives' in state:
            raise ValueError('Unexpected Conquest objective progress.')
        return
    progress = state.get('objectives')
    if not isinstance(progress, dict) or set(progress) != {'nodes', 'holder', 'since'}:
        raise ValueError('Invalid Conquest objective progress.')
    nodes = progress['nodes']
    if (not isinstance(nodes, list) or len(nodes) != settings['objective_count'] or
        any(type(index) is not int or not 0 <= index < len(state['nodes']) for index in nodes) or
        len(set(nodes)) != len(nodes)):
        raise ValueError('Invalid highlighted Conquest nodes.')
    holder, since = progress['holder'], progress['since']
    valid_since = since is None if holder is None else type(since) is int and 1 <= since <= state['turn']
    if holder not in (None, *node_counts(state)) or holder != objective_holder(state) or not valid_since:
        raise ValueError('Invalid continuous Conquest hold.')


def description(settings):
    mode = settings.get('victory_mode')
    if mode == 'territories':
        return 'Capture every enemy-owned node. Neutral nodes are optional.'
    if mode == 'headquarters':
        return 'Capture all headquarters belonging to opposing teams.'
    if mode == 'turn_limit':
        return (f'Own the most nodes after round {settings["turn_limit"]}. '
                'Ties continue one full round at a time until broken.')
    if mode == 'objectives':
        return (f'Capture all {settings["objective_count"]} highlighted nodes and hold them for '
                f'{settings["hold_turns"]} full rounds. Losing one resets the hold.')
    return 'Capture opposing HQs and destroy all opposing armies.'


def summary(state):
    mode = state['settings'].get('victory_mode')
    counts = node_counts(state)
    score = 'Nodes: ' + ' / '.join(f'{team_label(state, side)} {count}' for side, count in counts.items())
    if mode is None:
        return 'Legacy HQ and army elimination'
    if mode == 'turn_limit':
        completed, limit = state['completed_round'], state['settings']['turn_limit']
        clock = f'Rounds completed: {completed}/{limit}' if completed < limit else f'Round limit reached ({limit})'
        if completed >= limit and not state['winner']:
            clock = 'Overtime · next complete round decides'
        return f'{MODES[mode]} · {clock} · {score}'
    if mode == 'objectives':
        progress = state['objectives']
        control = dict.fromkeys(counts, 0)
        for index in progress['nodes']:
            side = coalition(state, state['nodes'][index]['owner'])
            if side != 'neutral':
                control[side] += 1
        breakdown = ' / '.join(f'{team_label(state, side)} {count}' for side, count in control.items())
        return (f'Objectives: {breakdown} · {team_label(state, progress["holder"])} hold: '
                f'{held_turns(state)}/{state["settings"]["hold_turns"]} full rounds')
    return f'{MODES[mode]} · {score}'


def result_text(state):
    counts = node_counts(state)
    side = state['winner']
    team = team_label(state, side)
    mode = state['settings'].get('victory_mode')
    if mode is None:
        return ('Enemy HQ captured; no enemy armies remain.' if side == 'player' else
                'All friendly HQs captured; no friendly armies remain.')
    rivals = [count for rival, count in counts.items() if rival != side]
    if not any(rivals):
        return f'{team} captured every opposing node.'
    if mode == 'headquarters':
        return f'{team} captured all opposing headquarters.'
    if mode == 'turn_limit':
        return f'{team} won on territory: {counts[side]} nodes to {max(rivals)}.'
    if mode == 'objectives':
        return (f'{team} held all {len(state["objectives"]["nodes"])} highlighted nodes '
                f'for {state["settings"]["hold_turns"]} full rounds.')
    return f'{team} captured every opposing node.'
