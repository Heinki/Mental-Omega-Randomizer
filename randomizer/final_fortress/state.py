"""Strict persisted state; damaged progression is never silently reset."""

from copy import deepcopy

from randomizer.challenges.catalogue import SIDE_COUNTRIES

from . import MODE_ID
from .config import DIFFICULTY_IDS, identifier, integer, text, validate_wave_multiplier


SCHEMA_VERSION = 8


def new_state():
    return {
        'schema_version': SCHEMA_VERSION, 'mode_id': MODE_ID,
        'gems': 0, 'owned_perks': [], 'selected_perks': [], 'perk_ranks': {},
        'preferences': {'difficulty': 'normal', 'player_country': None, 'wave_multiplier': 1,
                        'workspace_selected': False, 'selected_challenges': [], 'challenge_stacks': {},
                        'mental_ai_boost': False},
        'run': None,
    }


def _ids(value, name):
    if not isinstance(value, list):
        raise ValueError(f'{name} must be a list.')
    for key in value:
        identifier(key, name)
    if len(value) != len(set(value)):
        raise ValueError(f'{name} contains duplicate IDs.')


def normalize_state(document):
    """Keep removed perk IDs owned; never discard a player's purchase receipt."""
    if not isinstance(document, dict):
        raise ValueError('Final Fortress state must be an object.')
    if (type(document.get('schema_version')) is not int
            or document['schema_version'] not in (1, 2, 3, 4, 5, 6, 7, SCHEMA_VERSION)
            or document.get('mode_id') != MODE_ID):
        raise ValueError('Unsupported Final Fortress state schema or mode ID.')
    document = deepcopy(document)
    if document['schema_version'] < 6:
        if 'perk_ranks' in document:
            raise ValueError('Legacy Final Fortress state contains unsupported rank fields.')
        document['perk_ranks'] = {key: 1 for key in document.get('owned_perks', [])}
        if 'reinforcements' in document['perk_ranks']:
            # The old one-time purchase supplied six units. Preserve its unit
            # count when converting to the new three-units-per-rank army.
            document['perk_ranks']['reinforcements'] = 2
    expected = set(new_state())
    if set(document) != expected:
        raise ValueError('Final Fortress state has missing or unsupported fields.')
    document = deepcopy(document)
    if document['schema_version'] == 1:
        old_preferences = document['preferences']
        if (not isinstance(old_preferences, dict)
                or set(old_preferences) != {'difficulty', 'player_country'}):
            raise ValueError('Invalid legacy Final Fortress preferences.')
        old_preferences['wave_multiplier'] = 1
        document['schema_version'] = 2
    if document['schema_version'] == 2:
        preferences = document['preferences']
        if (not isinstance(preferences, dict)
                or set(preferences) != {'difficulty', 'player_country', 'wave_multiplier'}):
            raise ValueError('Invalid legacy Final Fortress preferences.')
        preferences['workspace_selected'] = False
        document['schema_version'] = 3
    if document['schema_version'] == 3:
        if not isinstance(document['preferences'], dict) or set(document['preferences']) != {
                'difficulty', 'player_country', 'wave_multiplier', 'workspace_selected'}:
            raise ValueError('Invalid legacy Final Fortress preferences.')
        document['preferences']['selected_challenges'] = []
        document['schema_version'] = 4
    if document['schema_version'] == 4:
        preferences = document['preferences']
        if not isinstance(preferences, dict) or set(preferences) != {
                'difficulty', 'player_country', 'wave_multiplier', 'workspace_selected', 'selected_challenges'}:
            raise ValueError('Invalid legacy Final Fortress preferences.')
        preferences['challenge_stacks'] = {key: 1 for key in preferences['selected_challenges']}
        document['schema_version'] = 5
    if document['schema_version'] == 5:
        document['schema_version'] = 6
    migrate_primary_weapon = document['schema_version'] == 6
    if document['schema_version'] < 8:
        if 'mental_ai_boost' in document['preferences']:
            raise ValueError('Legacy preferences contain an unsupported Mental AI Boost field.')
        document['preferences']['mental_ai_boost'] = False
    document['schema_version'] = SCHEMA_VERSION
    integer(document['gems'], 'Final Fortress gems')
    _ids(document['owned_perks'], 'Owned perks')
    _ids(document['selected_perks'], 'Selected perks')
    if not set(document['selected_perks']).issubset(document['owned_perks']):
        raise ValueError('Selected perks must be purchased first.')
    rank_table = document['perk_ranks']
    if not isinstance(rank_table, dict) or set(rank_table) != set(document['owned_perks']):
        raise ValueError('Purchased ranks must match owned perks.')
    for key, rank in rank_table.items():
        integer(rank, 'Purchased perk rank', 1)
        if rank > (8 if key == 'periodic_reinforcements' else 6):
            raise ValueError('Invalid purchased perk rank.')
    if migrate_primary_weapon and rank_table.get('faction_superweapon') == 1:
        # The former single rank bought the offensive weapon. Keep that
        # purchase when a secondary weapon becomes the new first rank.
        rank_table['faction_superweapon'] = 2
    preferences = document['preferences']
    if (not isinstance(preferences, dict)
            or set(preferences) != {'difficulty', 'player_country', 'wave_multiplier',
                                    'workspace_selected', 'selected_challenges', 'challenge_stacks',
                                    'mental_ai_boost'}
            or preferences['difficulty'] not in DIFFICULTY_IDS
            or preferences['player_country'] not in (None, *SIDE_COUNTRIES)):
        raise ValueError('Invalid Final Fortress preferences.')
    if type(preferences['workspace_selected']) is not bool:
        raise ValueError('Final Fortress workspace selection must be boolean.')
    if type(preferences['mental_ai_boost']) is not bool:
        raise ValueError('Mental AI Boost must be boolean.')
    validate_wave_multiplier(preferences['wave_multiplier'])
    _ids(preferences['selected_challenges'], 'Selected challenges')
    if not isinstance(preferences['challenge_stacks'], dict):
        raise ValueError('Challenge stacks must be an object.')
    for key, value in preferences['challenge_stacks'].items():
        identifier(key, 'Challenge ID')
        integer(value, 'Challenge stacks', 1)
        if value > 100:
            raise ValueError('Invalid saved challenge stack count.')
    run = document['run']
    if run is not None:
        if not isinstance(run, dict) or set(run) != {
            'id', 'status', 'config', 'plan', 'claimed_events',
        }:
            raise ValueError('Invalid Final Fortress run fields.')
        text(run['id'], 'Run ID')
        if run['status'] not in {'active', 'defeat', 'victory', 'abandoned'}:
            raise ValueError('Invalid Final Fortress run status.')
        plan = run['plan']
        if not isinstance(plan, dict):
            raise ValueError('Invalid Final Fortress run plan.')
        version = plan.get('plan_version', 1)
        if type(version) is int and version >= 2 and 'wave_multiplier' not in plan:
            raise ValueError('Final Fortress run plan has no wave multiplier.')
        # Rebuild the stored plan using the original balance snapshot. Current
        # configuration edits cannot reprice rewards during an active run.
        from .planning import build_run_plan
        rebuilt = build_run_plan(
            run['config'], difficulty=plan.get('difficulty'),
            seed=plan.get('seed'), player_country=plan.get('player_country'),
            selected_perks=plan.get('selected_perks', ()), perk_ranks=plan.get('perk_ranks'),
            wave_multiplier=plan.get('wave_multiplier', 1), plan_version=version,
            selected_challenges=[entry['id'] for entry in plan.get('challenges', [])],
            challenge_stacks={entry['id']: entry.get('stacks', 1) for entry in plan.get('challenges', [])},
            mental_ai_boost=plan.get('mental_ai_boost', False),
        )
        if version == 5 and 'initial_transfer_kills' not in plan:
            # Early v5 runs predate the native transfer-score correction.
            # Upgrade only that known missing field, after every other frozen
            # input and reward matches. Never recalculate existing Gem receipts.
            without_correction = {key: value for key, value in rebuilt.items()
                                  if key != 'initial_transfer_kills'}
            if without_correction == plan:
                plan['initial_transfer_kills'] = rebuilt['initial_transfer_kills']
        if rebuilt != plan:
            raise ValueError('Final Fortress run plan does not match its configuration.')
        if not set(plan['selected_perks']).issubset(document['owned_perks']):
            raise ValueError('Run plan contains unowned perks.')
        if any(rank > document['perk_ranks'].get(key, 0)
               for key, rank in plan.get('perk_ranks', {}).items()):
            raise ValueError('Run plan contains unpurchased perk ranks.')
        claimed = run['claimed_events']
        allowed = set(plan['gem_rewards']) | {'defeat', 'abandoned'}
        if (not isinstance(claimed, list)
                or any(not isinstance(event, str) or event not in allowed for event in claimed)
                or len(claimed) != len(set(claimed))):
            raise ValueError('Invalid Final Fortress reward receipts.')
        terminal = [event for event in claimed if event in {'victory', 'defeat', 'abandoned'}]
        if (run['status'] == 'active' and terminal) or (
            run['status'] != 'active' and terminal != [run['status']]
        ):
            raise ValueError('Final Fortress terminal status disagrees with receipts.')
        if terminal:
            after = claimed[claimed.index(terminal[0]) + 1:]
            if any(not event.startswith('kills:') for event in after) or (
                    after and run['status'] not in {'victory', 'defeat'}):
                raise ValueError('Only verified kill statistics may follow a completed run.')
    return deepcopy(document)
