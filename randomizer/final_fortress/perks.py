"""Ranked, opt-in survival perks; no campaign reward or purchase state."""

from copy import deepcopy
from collections import Counter

from randomizer.challenges.catalogue import SIDE_COUNTRIES


def ranks(perk):
    return perk.get('ranks', [{'gem_cost': perk['gem_cost'], 'effects': perk['effects']}])


def rank_limit(perk_id):
    return {'reinforcements': 8, 'periodic_reinforcements': 12, 'lab_reserve_squad': 10,
            'cheaper_construction': 5, 'cheaper_production': 5,
            'special_building_limit': 3, 'fundraising': 4, 'stolen_tech_access': 4,
            'transport_capacity': 3, 'fortified_infrastructure': 3,
            'open_topped_transports': 1}.get(perk_id, 6)


def owned_rank(state, key):
    return state.get('perk_ranks', {}).get(key, int(key in state['owned_perks']))


def next_price(perk, rank):
    entries = ranks(perk)
    return entries[rank]['gem_cost'] if rank < len(entries) else None


def validate_perk(perk):
    from .config import _object, _units, _position, _techno, integer, text
    fields = ['id', 'display_name', 'description', 'gem_cost', 'effects']
    if 'ranks' in perk:
        fields.append('ranks')
    _object(perk, fields, 'Perk')
    text(perk['display_name'], 'Perk display name')
    text(perk['description'], 'Perk description')
    integer(perk['gem_cost'], 'Perk Defensive Points cost', 1)
    entries = ranks(perk)
    maximum = rank_limit(perk['id'])
    if not isinstance(entries, list) or not 1 <= len(entries) <= maximum:
        raise ValueError(f'This perk requires one to {maximum} ranks.')
    if entries[0] != {'gem_cost': perk['gem_cost'], 'effects': perk['effects']}:
        raise ValueError('The first perk rank must match its displayed base price and effects.')
    previous = 0
    for index, entry in enumerate(entries):
        _object(entry, ('gem_cost', 'effects'), 'Perk rank')
        integer(entry['gem_cost'], 'Perk rank price', 1)
        if entry['gem_cost'] < previous:
            raise ValueError('Perk upgrade prices must not decrease.')
        previous = entry['gem_cost']
        effects = entry['effects']
        if not isinstance(effects, dict):
            raise ValueError('Perk effects must be an object.')
        supported = {'starting_credits', 'starting_units', 'starting_defenses', 'veterancy',
                     'production_percent', 'starting_units_by_country', 'buildings_by_country',
                     'defenses_by_country', 'defense_veterancy', 'defense_percent',
                     'tier_buffs', 'support_powers_by_country', 'reveal_map', 'allied_helpers',
                     'harvesters_by_country', 'fallback_units_by_country', 'power_buildings_by_country',
                     'superweapons_by_country', 'power_upgrade_stacks',
                     'special_units_by_country', 'reinforcements', 'healing_stacks',
                     'recon_stacks', 'unique_limit_stacks', 'income_stacks',
                     'lab_emergency_repair', 'lab_reserve_units_by_country', 'lab_reserve_shield_seconds',
                     'lab_health_percent', 'lab_reserve_veterancy', 'generator_power_percent',
                     'construction_discount_percent', 'unit_discount_percent',
                     'special_building_limit_stacks', 'fundraising_stacks',
                     'transport_capacity_stacks', 'infrastructure_health_percent', 'open_topped'}
        if not effects or set(effects) - supported:
            raise ValueError('Unsupported or empty perk effects.')
        if 'lab_emergency_repair' in effects and type(effects['lab_emergency_repair']) is not bool:
            raise ValueError('Lab emergency repair must be boolean.')
        if 'open_topped' in effects and type(effects['open_topped']) is not bool:
            raise ValueError('Open-topped transport access must be boolean.')
        if 'lab_reserve_shield_seconds' in effects:
            integer(effects['lab_reserve_shield_seconds'], 'Lab reserve shield seconds', 1)
            if effects['lab_reserve_shield_seconds'] > 30 or 'lab_reserve_units_by_country' not in effects:
                raise ValueError('Lab reserve shields require a reserve squad and last at most 30 seconds.')
        for key, limit in (('starting_credits', 100000), ('veterancy', 2),
                           ('production_percent', 50), ('defense_veterancy', 1),
                           ('defense_percent', 60), ('allied_helpers', 2), ('power_upgrade_stacks', 6),
                           ('healing_stacks', 6), ('recon_stacks', 6),
                           ('unique_limit_stacks', 6), ('income_stacks', 4), ('lab_health_percent', 100),
                           ('lab_reserve_veterancy', 2), ('generator_power_percent', 150),
                           ('construction_discount_percent', 25), ('unit_discount_percent', 25),
                           ('special_building_limit_stacks', 3), ('fundraising_stacks', 4),
                           ('transport_capacity_stacks', 3), ('infrastructure_health_percent', 45)):
            if key in effects:
                integer(effects[key], key)
                if effects[key] > limit:
                    raise ValueError(f'{key} exceeds its survival perk limit.')
        if 'starting_units' in effects:
            _units(effects['starting_units'])
        for defense in effects.get('starting_defenses', []):
            _object(defense, ('type', 'position'), 'Starting defense')
            _techno(defense['type'])
            _position(defense['position'])
        for key in ('starting_units_by_country', 'buildings_by_country',
                    'defenses_by_country', 'support_powers_by_country', 'harvesters_by_country',
                    'fallback_units_by_country', 'power_buildings_by_country', 'superweapons_by_country',
                    'special_units_by_country', 'lab_reserve_units_by_country'):
            if key not in effects:
                continue
            table = effects[key]
            if not isinstance(table, dict) or set(table) != set(SIDE_COUNTRIES):
                raise ValueError(f'{key} must cover all playable countries.')
            for country, values in table.items():
                if key in ('starting_units_by_country', 'harvesters_by_country', 'fallback_units_by_country',
                           'lab_reserve_units_by_country'):
                    _units(values)
                    if key == 'lab_reserve_units_by_country':
                        if (not values or len(values) > 6 or sum(unit['count'] for unit in values) > 30
                                or len({unit['type'] for unit in values}) != len(values)):
                            raise ValueError('Lab reserves require 1–30 units in at most six unique types per house.')
                    elif sum(unit['count'] for unit in values) > 15:
                        raise ValueError('Starting armies are limited to 15 units.')
                else:
                    maximum = {'defenses_by_country': 32, 'support_powers_by_country': 5,
                               'power_buildings_by_country': 24, 'special_units_by_country': 32}.get(key, 5)
                    minimum = 0 if key == 'power_buildings_by_country' else 1
                    if not isinstance(values, list) or not minimum <= len(values) <= maximum:
                        raise ValueError(f'{key} requires {minimum} to {maximum} native types.')
                    for value in values:
                        _techno(value)
                    if key == 'special_units_by_country':
                        if perk['id'] == 'stolen_tech_access' and len(values) != index + 1:
                            raise ValueError('Each stolen-tech rank must unlock exactly one additional type.')
                        if len(set(values)) != len(values):
                            raise ValueError('Special-unit unlocks must be unique.')
                        if index:
                            previous_units = entries[index - 1]['effects'].get(key, {}).get(country, [])
                            if len(values) <= len(previous_units) or values[:len(previous_units)] != previous_units:
                                raise ValueError('Special-unit ranks must retain previous unlocks and add new types.')
        if 'reinforcements' in effects:
            reinforcement = effects['reinforcements']
            fields = ['first_seconds', 'interval_seconds', 'max_active_units', 'units_by_country']
            if 'veterancy' in reinforcement:
                fields.append('veterancy')
                integer(reinforcement['veterancy'], 'Reinforcement veterancy')
                if reinforcement['veterancy'] > 2:
                    raise ValueError('Reinforcement veterancy must be Rookie, Veteran or Elite.')
            _object(reinforcement, fields, 'Reinforcements')
            for field in ('first_seconds', 'interval_seconds', 'max_active_units'):
                integer(reinforcement[field], 'Reinforcement ' + field, 1)
            table = reinforcement['units_by_country']
            if not isinstance(table, dict) or set(table) != set(SIDE_COUNTRIES):
                raise ValueError('Reinforcements must cover all playable countries.')
            for units in table.values():
                _units(units)
                if not 1 <= len(units) <= 10 or sum(unit['count'] for unit in units) > 30:
                    raise ValueError('Reinforcements require 1–10 types and at most 30 units per house.')
                if len({unit['type'] for unit in units}) != len(units):
                    raise ValueError('Reinforcement types must be unique within each arrival.')
        if 'tier_buffs' in effects:
            table = effects['tier_buffs']
            if not isinstance(table, dict) or set(table) - {'1', '2', '3'}:
                raise ValueError('Unit perks must name tiers 1, 2, or 3.')
            for value in table.values():
                integer(value, 'Tier buff percent', 1)
                if value > 30:
                    raise ValueError('Player unit tier buffs cannot exceed 30%.')
        if 'reveal_map' in effects and type(effects['reveal_map']) is not bool:
            raise ValueError('Reveal map must be boolean.')


def resolve_effects(config, selected, purchased, country, *, include_power=False,
                    include_power_upgrades=False, include_arsenal=False, include_utilities=False,
                    include_lab_support=False, include_lab_shield=False, include_lab_health=False,
                    include_lab_veterancy=False, include_generator_power=False,
                    include_economy=False, share_starting_power=False, include_logistics=False):
    effects = {'starting_credits': 0, 'starting_units': [], 'starting_defenses': [],
               'veterancy': 0, 'production_percent': 0, 'starting_buildings': [],
               'defense_types': [], 'defense_veterancy': 0, 'defense_percent': 0,
               'tier_buffs': {}, 'support_powers': [], 'reveal_map': False, 'allied_helpers': 0,
               'starting_harvesters': []}
    if include_power:
        effects['starting_power_buildings'] = []
    if include_power_upgrades:
        effects['power_upgrade_stacks'] = 0
    if include_arsenal:
        effects.update(special_access=[], reinforcements=None)
    utility_fields = ('healing_stacks', 'recon_stacks', 'unique_limit_stacks', 'income_stacks')
    if include_utilities:
        effects.update({field: 0 for field in utility_fields})
    if include_logistics:
        effects.update(transport_capacity_stacks=0, infrastructure_health_percent=0, open_topped=False)
    if include_lab_support:
        effects.update(lab_emergency_repair=False, lab_reserve_units=[])
    if include_lab_shield:
        effects['lab_reserve_shield_seconds'] = 0
    if include_lab_health:
        effects['lab_health_percent'] = 0
    if include_lab_veterancy:
        effects['lab_reserve_veterancy'] = 0
    if include_generator_power:
        effects['generator_power_percent'] = 0
    economy_fields = ('construction_discount_percent', 'unit_discount_percent',
                      'special_building_limit_stacks', 'fundraising_stacks')
    if include_economy:
        effects.update({field: 0 for field in economy_fields})
    catalogue = {entry['id']: entry for entry in config['perks']}
    fallback = []
    shared_power = Counter()
    for key in selected:
        rank = purchased.get(key, 1)
        entries = ranks(catalogue[key])
        if type(rank) is not int or not 1 <= rank <= len(entries):
            raise ValueError(f'Invalid purchased perk rank: {key}.')
        current = entries[rank - 1]['effects']
        if include_logistics:
            for field in ('transport_capacity_stacks', 'infrastructure_health_percent'):
                effects[field] = max(effects[field], current.get(field, 0))
            effects['open_topped'] |= current.get('open_topped', False)
        if include_economy:
            for field in economy_fields:
                effects[field] = max(effects[field], current.get(field, 0))
        if include_generator_power:
            effects['generator_power_percent'] = max(
                effects['generator_power_percent'], current.get('generator_power_percent', 0))
        if include_lab_veterancy:
            effects['lab_reserve_veterancy'] = max(
                effects['lab_reserve_veterancy'], current.get('lab_reserve_veterancy', 0))
        if include_lab_health:
            effects['lab_health_percent'] = max(effects['lab_health_percent'], current.get('lab_health_percent', 0))
        if include_lab_shield:
            effects['lab_reserve_shield_seconds'] = max(
                effects['lab_reserve_shield_seconds'], current.get('lab_reserve_shield_seconds', 0))
        if include_lab_support:
            effects['lab_emergency_repair'] |= current.get('lab_emergency_repair', False)
            if 'lab_reserve_units_by_country' in current:
                if effects['lab_reserve_units']:
                    raise ValueError('Choose only one Lab reserve squad perk.')
                effects['lab_reserve_units'] = deepcopy(current['lab_reserve_units_by_country'][country])
        if include_utilities:
            for field in utility_fields:
                effects[field] = max(effects[field], current.get(field, 0))
        if include_arsenal:
            effects['special_access'].extend(current.get('special_units_by_country', {}).get(country, []))
            if 'reinforcements' in current:
                if effects['reinforcements'] is not None:
                    raise ValueError('Choose only one recurring reinforcement perk.')
                reinforcement = deepcopy(current['reinforcements'])
                reinforcement['units'] = reinforcement.pop('units_by_country')[country]
                effects['reinforcements'] = reinforcement
        effects['starting_credits'] += current.get('starting_credits', 0)
        effects['starting_units'].extend(deepcopy(current.get('starting_units', [])))
        effects['starting_units'].extend(deepcopy(current.get('starting_units_by_country', {}).get(country, [])))
        effects['starting_defenses'].extend(deepcopy(current.get('starting_defenses', [])))
        effects['starting_harvesters'].extend(deepcopy(current.get('harvesters_by_country', {}).get(country, [])))
        fallback.extend(deepcopy(current.get('fallback_units_by_country', {}).get(country, [])))
        for source, target in (('buildings_by_country', 'starting_buildings'),
                               ('defenses_by_country', 'defense_types'),
                               ('support_powers_by_country', 'support_powers')):
            effects[target].extend(current.get(source, {}).get(country, []))
        if include_power:
            power = current.get('power_buildings_by_country', {}).get(country, [])
            if share_starting_power and key in ('starting_buildings', 'starting_defenses'):
                # Defense grants already budget for the complete optional
                # production base. Reuse that allowance when both are selected;
                # building-only loadouts retain their own native power top-up.
                shared_power |= Counter(power)
            else:
                effects['starting_power_buildings'].extend(power)
        if include_power_upgrades:
            effects['support_powers'].extend(current.get('superweapons_by_country', {}).get(country, []))
            effects['power_upgrade_stacks'] = max(effects['power_upgrade_stacks'], current.get('power_upgrade_stacks', 0))
        for field in ('veterancy', 'production_percent', 'defense_veterancy', 'defense_percent', 'allied_helpers'):
            effects[field] = max(effects[field], current.get(field, 0))
        effects['reveal_map'] |= current.get('reveal_map', False)
        for tier, value in current.get('tier_buffs', {}).items():
            effects['tier_buffs'][tier] = max(effects['tier_buffs'].get(tier, 0), value)
    if not effects['starting_units']:
        effects['starting_units'] = fallback
    if include_power:
        effects['starting_power_buildings'].extend(shared_power.elements())
    if include_power_upgrades:
        effects['support_powers'] = list(dict.fromkeys(effects['support_powers']))
    if sum(unit['count'] for unit in effects['starting_units']) > 15:
        raise ValueError('Combined starting-army perks exceed the 15-unit limit.')
    return effects
