"""Strict persisted state; damaged progression is never silently reset."""

from copy import deepcopy
import re

from randomizer.challenges.catalogue import SIDE_COUNTRIES

from . import MODE_ID
from .config import DIFFICULTY_IDS, identifier, integer, text, validate_wave_multiplier
from .perks import rank_limit


SCHEMA_VERSION = 11


def new_state():
    return {
        'schema_version': SCHEMA_VERSION, 'mode_id': MODE_ID,
        'gems': 0, 'owned_perks': [], 'selected_perks': [], 'perk_ranks': {},
        'preferences': {'difficulty': 'normal', 'player_country': None, 'wave_multiplier': 1,
                        'workspace_selected': False, 'selected_challenges': [], 'challenge_stacks': {},
                        'mental_ai_boost': False, 'map_id': None},
        'run': None, 'coop_run_ids': [],
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
            or document['schema_version'] not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, SCHEMA_VERSION)
            or document.get('mode_id') != MODE_ID):
        raise ValueError('Unsupported Final Fortress state schema or mode ID.')
    document = deepcopy(document)
    migrate_special_access = document['schema_version'] < 11
    if document['schema_version'] < 9:
        if 'coop_run_ids' in document:
            raise ValueError('Legacy state contains unsupported co-op receipts.')
        document['coop_run_ids'] = []
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
    if document['schema_version'] < 10:
        if 'map_id' in document['preferences']:
            raise ValueError('Legacy preferences contain an unsupported map selection.')
        document['preferences']['map_id'] = None
    document['schema_version'] = SCHEMA_VERSION
    integer(document['gems'], 'Final Fortress Defensive Points')
    receipts = document['coop_run_ids']
    if (not isinstance(receipts, list)
            or any(not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key) for key in receipts)
            or len(receipts) != len(set(receipts))):
        raise ValueError('Invalid Fortress co-op run receipts.')
    _ids(document['owned_perks'], 'Owned perks')
    _ids(document['selected_perks'], 'Selected perks')
    if not set(document['selected_perks']).issubset(document['owned_perks']):
        raise ValueError('Selected perks must be purchased first.')
    rank_table = document['perk_ranks']
    if not isinstance(rank_table, dict) or set(rank_table) != set(document['owned_perks']):
        raise ValueError('Purchased ranks must match owned perks.')
    for key, rank in rank_table.items():
        integer(rank, 'Purchased perk rank', 1)
        if rank > rank_limit(key):
            raise ValueError('Invalid purchased perk rank.')
    if migrate_primary_weapon and rank_table.get('faction_superweapon') == 1:
        # The former single rank bought the offensive weapon. Keep that
        # purchase when a secondary weapon becomes the new first rank.
        rank_table['faction_superweapon'] = 2
    if migrate_special_access and 'special_unit_access' in rank_table:
        # The former mixed perk included stolen-tech unlocks. Preserve them
        # across faction switches when splitting production into two perks.
        rank_table['stolen_tech_access'] = max(rank_table.get('stolen_tech_access', 0),
                                              min(3, rank_table['special_unit_access']))
        if 'stolen_tech_access' not in document['owned_perks']:
            document['owned_perks'].append('stolen_tech_access')
        if ('special_unit_access' in document['selected_perks']
                and 'stolen_tech_access' not in document['selected_perks']):
            document['selected_perks'].append('stolen_tech_access')
    preferences = document['preferences']
    if (not isinstance(preferences, dict)
            or set(preferences) != {'difficulty', 'player_country', 'wave_multiplier',
                                    'workspace_selected', 'selected_challenges', 'challenge_stacks',
                                    'mental_ai_boost', 'map_id'}
            or preferences['difficulty'] not in DIFFICULTY_IDS
            or preferences['player_country'] not in (None, *SIDE_COUNTRIES)):
        raise ValueError('Invalid Final Fortress preferences.')
    if type(preferences['workspace_selected']) is not bool:
        raise ValueError('Final Fortress workspace selection must be boolean.')
    if type(preferences['mental_ai_boost']) is not bool:
        raise ValueError('Mental AI Boost must be boolean.')
    if preferences['map_id'] is not None:
        identifier(preferences['map_id'], 'Selected map ID')
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
        fields = {
            'id', 'status', 'config', 'plan', 'claimed_events',
        }
        if isinstance(run, dict) and 'coop_player' in run:
            fields.add('coop_player')
        if isinstance(run, dict) and 'kill_counts' in run:
            fields.add('kill_counts')
        if not isinstance(run, dict) or set(run) != fields:
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
            coop_players=plan.get('coop_players', ()),
            fundraising_ranks=plan.get('fundraising_ranks'),
        )
        if version == 5 and 'initial_transfer_kills' not in plan:
            # Early v5 runs predate the native transfer-score correction.
            # Upgrade only that known missing field, after every other frozen
            # input and reward matches. Never recalculate existing Defensive Points receipts.
            without_correction = {key: value for key, value in rebuilt.items()
                                  if key != 'initial_transfer_kills'}
            if without_correction == plan:
                plan['initial_transfer_kills'] = rebuilt['initial_transfer_kills']
        if rebuilt != plan:
            raise ValueError('Final Fortress run plan does not match its configuration.')
        guest = False
        if plan.get('coop_players'):
            slot = run.get('coop_player')
            if (type(slot) is not int or not 0 <= slot < len(plan['coop_players'])
                    or run['id'] not in document['coop_run_ids']):
                raise ValueError('Invalid Fortress co-op player or run receipt.')
            guest = slot > 0
        elif 'coop_player' in run:
            raise ValueError('Solo runs cannot contain a co-op player.')
        if 'kill_counts' in run:
            from .results import FRIENDLY_ACTORS
            counts = run['kill_counts']
            if (not isinstance(counts, dict) or set(counts) != set(FRIENDLY_ACTORS)
                    or run['status'] not in {'victory', 'defeat'}
                    or any(value is not None and (type(value) is not int or value < 0)
                           for value in counts.values())):
                raise ValueError('Invalid Final Fortress kill counters.')
        if not guest and not set(plan['selected_perks']).issubset(document['owned_perks']):
            raise ValueError('Run plan contains unowned perks.')
        if not guest and any(rank > document['perk_ranks'].get(key, 0)
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
