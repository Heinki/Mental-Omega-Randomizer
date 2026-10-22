"""Strict independent survival, wave, camp, challenge and economy contracts."""

from pathlib import PurePosixPath
import re

from randomizer.challenges.catalogue import SIDE_COUNTRIES

DIFFICULTY_IDS = ('easy', 'normal', 'hard')
WAVE_MULTIPLIERS = tuple(range(1, 11))
_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_TECHNO = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,23}\Z')


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}.')
    return value


def validate_wave_multiplier(value):
    integer(value, 'Wave multiplier', 1)
    if value not in WAVE_MULTIPLIERS:
        raise ValueError('Wave multiplier must be between x1 and x10.')
    return value


def identifier(value, name):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f'{name} must be a stable lowercase identifier.')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or any(
        char in value for char in '\r\n\x00'
    ):
        raise ValueError(f'{name} must be non-empty single-line text.')
    return value


def _object(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f'{name} requires exactly: {", ".join(fields)}.')


def _techno(value):
    if not isinstance(value, str) or not _TECHNO.fullmatch(value):
        raise ValueError(f'Invalid engine type ID: {value!r}.')


def _list(value, name):
    if not isinstance(value, list):
        raise ValueError(f'{name} must be a list.')


def _position(value):
    _object(value, ('x', 'y'), 'Position')
    integer(value['x'], 'Position x')
    integer(value['y'], 'Position y')


def _unique(entries, name):
    _list(entries, name)
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f'{name} entries must be objects.')
        key = identifier(entry.get('id'), name)
        if key in seen:
            raise ValueError(f'Duplicate {name} ID: {key}.')
        seen.add(key)


def _units(entries):
    _list(entries, 'Units')
    for unit in entries:
        _object(unit, ('type', 'count'), 'Unit')
        _techno(unit['type'])
        integer(unit['count'], 'Unit count', 1)


def _map(value):
    if value is None:
        return
    fields = ['id', 'display_name', 'source', 'player_waypoint', 'enemy_waypoints',
              'protected_building', 'camps']
    fields.extend(key for key in ('allied_waypoints', 'perk_layouts', 'enemy_defenses',
                                 'enemy_wave_positions') if key in value)
    _object(value, fields, 'Map')
    identifier(value['id'], 'Map ID')
    text(value['display_name'], 'Map display name')
    source = text(value['source'], 'Map source')
    path = PurePosixPath(source)
    if (path.is_absolute() or '..' in path.parts or '\\' in source
            or ':' in source or path.suffix.lower() not in {'.map', '.mpr', '.yrm'}):
        raise ValueError('Map source must be a relative game-root map path.')
    integer(value['player_waypoint'], 'Player waypoint')
    _list(value['enemy_waypoints'], 'Enemy waypoints')
    if len(value['enemy_waypoints']) != 3:
        raise ValueError('Final Fortress requires exactly three enemy AIs.')
    points = [value['player_waypoint'], *value['enemy_waypoints']]
    for waypoint in points:
        integer(waypoint, 'Spawn waypoint')
    if len(set(points)) != 4:
        raise ValueError('Each actor requires a distinct waypoint.')
    allies = value.get('allied_waypoints', [])
    if not isinstance(allies, list) or len(allies) > 2:
        raise ValueError('Final Fortress supports at most two allied start positions.')
    if len(set(points + allies)) != len(points + allies):
        raise ValueError('Allied helpers require distinct unused start positions.')
    for waypoint in points + allies:
        integer(waypoint, 'Spawn waypoint')
        if waypoint > 7:
            raise ValueError('Native skirmish start positions range from 0 to 7.')
    if 'perk_layouts' in value:
        layouts = value['perk_layouts']
        if not isinstance(layouts, dict) or set(layouts) != {str(point) for point in [value['player_waypoint'], *allies]}:
            raise ValueError('Perk layouts must cover the player and allied start positions.')
        for layout in layouts.values():
            fields = ['buildings', 'defenses', 'units']
            if 'power' in layout:
                fields.append('power')
            _object(layout, fields, 'Perk layout')
            for field, counts in (('buildings', (5,)), ('defenses', (4, 16))):
                if not isinstance(layout[field], list) or len(layout[field]) not in counts:
                    raise ValueError(f'Perk layout requires {counts} {field} positions.')
                for position in layout[field]:
                    _position(position)
            if 'power' in layout:
                if not isinstance(layout['power'], list) or not 1 <= len(layout['power']) <= 12:
                    raise ValueError('Perk layout requires 1–12 power plant positions.')
                for position in layout['power']:
                    _position(position)
            _position(layout['units'])
    if 'enemy_defenses' in value:
        defense = value['enemy_defenses']
        _object(defense, ('layouts', 'types_by_country'), 'Enemy base defenses')
        if not isinstance(defense['layouts'], dict) or set(defense['layouts']) != {
                str(point) for point in value['enemy_waypoints']}:
            raise ValueError('Enemy fortification layouts must cover all three enemy starts.')
        for positions in defense['layouts'].values():
            if not isinstance(positions, list) or not 12 <= len(positions) <= 32:
                raise ValueError('Enemy bases require 12–32 fortification positions.')
            for position in positions:
                _position(position)
        table = defense['types_by_country']
        if not isinstance(table, dict) or set(table) != set(SIDE_COUNTRIES):
            raise ValueError('Enemy fortification types must cover all playable countries.')
        for types in table.values():
            if not isinstance(types, list) or len(types) != 3 or len(set(types)) != 3:
                raise ValueError('Enemy fortifications require three distinct faction defense types.')
            for kind in types:
                _techno(kind)
    if 'enemy_wave_positions' in value:
        positions = value['enemy_wave_positions']
        if not isinstance(positions, dict) or set(positions) != {str(p) for p in value['enemy_waypoints']}:
            raise ValueError('Enemy arrival positions must cover all three enemy starts.')
        for position in positions.values():
            _position(position)
    building = value['protected_building']
    if building is not None:
        _object(building, ('type', 'position'), 'Protected building')
        _techno(building['type'])
        if building['position'] is not None:
            _position(building['position'])
    _unique(value['camps'], 'Camp')
    if len(value['camps']) > 6:
        raise ValueError('Final Fortress supports at most six camps.')
    for camp in value['camps']:
        fields = ['id', 'display_name', 'gems']
        if 'position' in camp:
            fields += ['position', 'guards', 'enemy_index']
        if 'guard_positions' in camp:
            fields.append('guard_positions')
        _object(camp, fields, 'Camp')
        text(camp['display_name'], 'Camp display name')
        integer(camp['gems'], 'Camp gems')
        if 'position' in camp:
            _position(camp['position'])
            integer(camp['enemy_index'], 'Camp enemy index')
            if camp['enemy_index'] > 2:
                raise ValueError('Camp enemy index must be 0–2.')
            _units(camp['guards'])
            if not camp['guards'] or sum(u['count'] for u in camp['guards']) > 12:
                raise ValueError('Camps require 1–12 guards.')
        if 'guard_positions' in camp:
            positions = camp['guard_positions']
            if not isinstance(positions, list) or not 1 <= len(positions) <= 40:
                raise ValueError('Camps require 1–40 reviewed guard positions.')
            for position in positions:
                _position(position)
            cells = [(p['x'], p['y']) for p in positions]
            if len(set(cells)) != len(cells) or camp.get('position') in positions:
                raise ValueError('Camp guard positions must be distinct and leave the crate cell free.')


def stage_compositions(stage):
    """Read both fixed legacy stages and configurable mixed compositions."""
    if 'variants' in stage:
        return stage['variants']
    return ({'id': None, 'units': stage['units']},)


def wave_rosters(config, difficulty):
    """New configurations decouple wave composition from native AI difficulty."""
    if 'wave_rosters' in config:
        return config['wave_rosters']
    return config['difficulties'][difficulty]['waves']


def _validate_rosters(rosters, settings, *, sized_waves=False):
    if not isinstance(rosters, dict) or set(rosters) - set(SIDE_COUNTRIES):
        raise ValueError('Wave rosters must use native playable country IDs.')
    largest = 0
    for country, stages in rosters.items():
        _list(stages, f'{country} wave stages')
        times = []
        for stage in stages:
            if not isinstance(stage, dict):
                raise ValueError('Wave stages must be objects.')
            variant_stage = 'variants' in stage
            _object(stage, ('from_seconds', 'variants' if variant_stage else 'units'),
                    'Wave stage')
            time = integer(stage['from_seconds'], 'Wave stage start', 1)
            if time >= settings['survival_seconds']:
                raise ValueError('Wave stages must start before victory.')
            times.append(time)
            if variant_stage:
                _unique(stage['variants'], 'Wave composition')
                if not stage['variants']:
                    raise ValueError('Wave stages require at least one composition.')
            for composition in stage_compositions(stage):
                if variant_stage:
                    _object(composition, ('id', 'units'), 'Wave composition')
                _units(composition['units'])
                if not composition['units']:
                    raise ValueError('Wave compositions require unit entries.')
                largest = max(largest, sum(unit['count'] for unit in composition['units']))
        if times and (times != sorted(set(times)) or times[0] > settings['wave_interval_seconds']):
            raise ValueError('Wave stages must be ordered and cover the first wave.')
    if not sized_waves and largest and (
        settings['max_wave_units'] is None or largest * 3 > settings['max_wave_units']
    ):
        raise ValueError('Maximum wave units must cover three faction groups at x1.')


def validate_config(sections, path=None):
    """Validate pending defaults and populated definitions without guessing data."""
    try:
        shared_waves = isinstance(sections, dict) and 'wave_rosters' in sections
        sized_waves = isinstance(sections, dict) and 'wave_pressure' in sections
        fields = ['settings', 'map', 'difficulties', 'milestones', 'perks']
        if isinstance(sections, dict) and 'challenges' in sections:
            fields.append('challenges')
        if isinstance(sections, dict) and 'performance' in sections:
            fields.append('performance')
        if isinstance(sections, dict) and 'crate_rewards' in sections:
            fields.append('crate_rewards')
        if isinstance(sections, dict) and 'camp_balance' in sections:
            fields.append('camp_balance')
        if isinstance(sections, dict) and 'wave_air_support' in sections:
            fields.append('wave_air_support')
        if shared_waves:
            fields.append('wave_rosters')
        if sized_waves:
            fields.append('wave_pressure')
            if not shared_waves:
                raise ValueError('Wave growth requires shared faction wave rosters.')
        _object(sections, fields, 'Final Fortress sections')
        if 'camp_balance' in sections:
            balance = sections['camp_balance']
            fields = ['guards_by_difficulty', 'max_guards_per_camp', 'max_total_guards',
                      'special_chance_percent', 'special_units_by_country']
            if 'starter_camps' in balance:
                fields.append('starter_camps')
            _object(balance, fields, 'Camp balance')
            if not isinstance(balance['guards_by_difficulty'], dict) or set(balance['guards_by_difficulty']) != set(DIFFICULTY_IDS):
                raise ValueError('Camp guard counts must cover all difficulties.')
            for count in balance['guards_by_difficulty'].values():
                integer(count, 'Base camp guards', 1)
            integer(balance['max_guards_per_camp'], 'Camp guard ceiling', 1)
            integer(balance['max_total_guards'], 'Total camp guard ceiling', 1)
            integer(balance['special_chance_percent'], 'Special camp unit chance')
            if (balance['max_guards_per_camp'] > 40 or balance['max_total_guards'] > 240
                    or balance['special_chance_percent'] > 100):
                raise ValueError('Camp balance exceeds the guard/chance limits.')
            table = balance['special_units_by_country']
            if not isinstance(table, dict) or set(table) != set(SIDE_COUNTRIES):
                raise ValueError('Camp special pools must cover all playable countries.')
            for units in table.values():
                if not isinstance(units, list) or not units or len(set(units)) != len(units):
                    raise ValueError('Camp special pools require distinct installed unit IDs.')
                for kind in units:
                    _techno(kind)
            if 'starter_camps' in balance:
                starter = balance['starter_camps']
                _object(starter, ('camp_ids', 'guards_by_difficulty', 'max_guards_by_difficulty',
                                  'units_by_country'), 'Starter camp balance')
                _list(starter['camp_ids'], 'Starter camp IDs')
                for key in starter['camp_ids']:
                    identifier(key, 'Starter camp ID')
                if not starter['camp_ids'] or len(set(starter['camp_ids'])) != len(starter['camp_ids']):
                    raise ValueError('Starter camp IDs must be nonempty and distinct.')
                for field in ('guards_by_difficulty', 'max_guards_by_difficulty'):
                    _object(starter[field], DIFFICULTY_IDS, 'Starter camp ' + field)
                    for count in starter[field].values():
                        integer(count, 'Starter camp guard count', 1)
                for difficulty in DIFFICULTY_IDS:
                    if not (starter['guards_by_difficulty'][difficulty]
                            <= starter['max_guards_by_difficulty'][difficulty] <= balance['max_guards_per_camp']
                            and starter['guards_by_difficulty'][difficulty] < balance['guards_by_difficulty'][difficulty]):
                        raise ValueError('Starter camps need lower base populations and valid separate ceilings.')
                _object(starter['units_by_country'], SIDE_COUNTRIES, 'Starter camp faction pools')
                for units in starter['units_by_country'].values():
                    _units(units)
                    if not units or len(units) > 6 or len({unit['type'] for unit in units}) != len(units):
                        raise ValueError('Starter camps need one to six distinct basic unit types.')
        if 'crate_rewards' in sections:
            _unique(sections['crate_rewards'], 'Crate reward')
            if not sections['crate_rewards']:
                raise ValueError('Crates require at least one reward option.')
            for reward in sections['crate_rewards']:
                _object(reward, ('id', 'display_name', 'weight', 'credits', 'units_by_country'), 'Crate reward')
                text(reward['display_name'], 'Crate reward name')
                integer(reward['weight'], 'Crate reward weight', 1)
                integer(reward['credits'], 'Crate credits')
                rosters = reward['units_by_country']
                if not isinstance(rosters, dict) or (rosters and set(rosters) != set(SIDE_COUNTRIES)):
                    raise ValueError('Unit crate rewards must cover every playable country.')
                for units in rosters.values():
                    _units(units)
                    if not units or len(units) > 6 or sum(unit['count'] for unit in units) > 15:
                        raise ValueError('Unit crates require 1–15 units and at most six types.')
                if not reward['credits'] and not rosters:
                    raise ValueError('Crates must grant credits or units.')
        if 'performance' in sections:
            performance = sections['performance']
            _object(performance, ('units_per_tier', 'gems_per_tier', 'max_tiers'), 'Performance')
            for key, value in performance.items():
                integer(value, 'Performance ' + key, 1)
            if performance['max_tiers'] > 20:
                raise ValueError('Performance rewards support at most 20 tiers.')
        settings = sections['settings']
        _object(settings, ('survival_seconds', 'wave_interval_seconds',
                           'completion_gems', 'max_wave_units'), 'Settings')
        duration = integer(settings['survival_seconds'], 'Survival seconds', 1)
        interval = integer(settings['wave_interval_seconds'], 'Wave interval', 1)
        if interval >= duration:
            raise ValueError('Wave interval must be shorter than survival time.')
        if settings['completion_gems'] is not None:
            integer(settings['completion_gems'], 'Completion gems')
        if settings['max_wave_units'] is not None:
            integer(settings['max_wave_units'], 'Maximum units per wave', 1)
        if sized_waves:
            pressure = sections['wave_pressure']
            pressure_fields = ['growth_per_wave', 'max_active_units', 'overflow']
            if isinstance(pressure, dict) and 'spawn_sides' in pressure:
                pressure_fields.append('spawn_sides')
            _object(pressure, pressure_fields, 'Wave pressure')
            if pressure['growth_per_wave'] not in (None, 'starting_amount'):
                integer(pressure['growth_per_wave'], 'Base unit growth per wave', 1)
            if pressure['max_active_units'] is not None:
                integer(pressure['max_active_units'], 'Maximum living wave units', 1)
            if pressure['overflow'] not in (None, 'delay'):
                raise ValueError('Wave overflow must be delay or unset.')
            if 'spawn_sides' in pressure:
                stages = pressure['spawn_sides']
                _list(stages, 'Wave spawn-side stages')
                if not stages:
                    raise ValueError('Wave spawn-side stages cannot be empty.')
                times, counts = [], []
                for stage in stages:
                    _object(stage, ('from_seconds', 'count'), 'Wave spawn-side stage')
                    time = integer(stage['from_seconds'], 'Spawn-side stage time', 1)
                    count = integer(stage['count'], 'Wave spawn-side count', 1)
                    if time >= duration or count > 3:
                        raise ValueError('Spawn-side stages require one through three sides before victory.')
                    times.append(time)
                    counts.append(count)
                if (times != sorted(set(times)) or times[0] > interval
                        or counts != sorted(set(counts)) or counts[0] != 1 or counts[-1] != 3):
                    raise ValueError('Spawn-side stages must cover the first wave and increase from one to three.')
        _map(sections['map'])
        starter = sections.get('camp_balance', {}).get('starter_camps')
        if starter and not set(starter['camp_ids']) <= {camp['id'] for camp in (sections['map'] or {}).get('camps', [])}:
            raise ValueError('Starter camp IDs must refer to configured camps.')
        _object(sections['difficulties'], DIFFICULTY_IDS, 'Difficulties')
        for index, difficulty in enumerate(DIFFICULTY_IDS):
            profile = sections['difficulties'][difficulty]
            profile_fields = ['engine_difficulty']
            if not shared_waves:
                profile_fields.append('waves')
            if sized_waves:
                profile_fields.append('starting_wave_units')
            _object(profile, profile_fields, 'Difficulty')
            if type(profile['engine_difficulty']) is not int or profile['engine_difficulty'] != index:
                raise ValueError(f'{difficulty} must use engine difficulty {index}.')
            if sized_waves:
                integer(profile['starting_wave_units'], 'First-wave units per enemy', 1)
            if not shared_waves:
                _validate_rosters(profile['waves'], settings)
        if shared_waves:
            _validate_rosters(sections['wave_rosters'], settings, sized_waves=sized_waves)
        if 'wave_air_support' in sections:
            stages = sections['wave_air_support']
            _list(stages, 'Air support stages')
            times = []
            for stage in stages:
                _object(stage, ('from_seconds', 'percent', 'units_by_country'), 'Air support stage')
                time = integer(stage['from_seconds'], 'Air support stage start', 1)
                if time >= settings['survival_seconds'] or time % settings['wave_interval_seconds']:
                    raise ValueError('Air support must start on a wave before victory.')
                times.append(time)
                if not 1 <= integer(stage['percent'], 'Air support percent', 1) <= 50:
                    raise ValueError('Air support may replace at most half a wave.')
                if not isinstance(stage['units_by_country'], dict) or set(stage['units_by_country']) != set(SIDE_COUNTRIES):
                    raise ValueError('Air support must cover every playable country.')
                for units in stage['units_by_country'].values():
                    _units(units)
                    if not units or len(units) > 4 or len({unit['type'] for unit in units}) != len(units):
                        raise ValueError('Air support needs one to four distinct weighted unit choices.')
            if times != sorted(set(times)):
                raise ValueError('Air support stages must be ordered and unique.')
        _unique(sections['milestones'], 'Milestone')
        seconds = set()
        for milestone in sections['milestones']:
            _object(milestone, ('id', 'seconds', 'gems'), 'Milestone')
            time = integer(milestone['seconds'], 'Milestone seconds', 1)
            if time >= duration or time in seconds:
                raise ValueError('Milestone times must be unique and precede victory.')
            seconds.add(time)
            integer(milestone['gems'], 'Milestone gems')
        _unique(sections.get('challenges', []), 'Challenge')
        effect_ids = set()
        for challenge in sections.get('challenges', []):
            if 'enemy_effect_id' in challenge:
                from .challenges import definitions, definition
                fields = ['id', 'enemy_effect_id', 'victory_gems_per_stack']
                fields.extend(key for key in ('shots', 'recharge_multiplier') if key in challenge)
                _object(challenge, fields, 'Challenge')
                if challenge['enemy_effect_id'] not in {entry['id'] for entry in definitions()}:
                    raise ValueError('Challenge must reference a supported Fortress enemy effect.')
                for field, maximum in (('shots', 12), ('recharge_multiplier', 10)):
                    if field in challenge:
                        if definition(challenge)['effect'] != 'power':
                            raise ValueError('Launch count and recharge settings apply only to reinforcement powers.')
                        integer(challenge[field], 'Challenge ' + field, 1)
                        if challenge[field] > maximum:
                            raise ValueError('Challenge power setting exceeds its bounded limit.')
                if challenge['enemy_effect_id'] in effect_ids:
                    raise ValueError('Each Grid enemy effect may appear only once in Challenge.')
                effect_ids.add(challenge['enemy_effect_id'])
                integer(challenge['victory_gems_per_stack'], 'Challenge Gems per stack', 1)
                continue
            _object(challenge, ('id', 'display_name', 'description', 'effect',
                                'percent', 'victory_gems'), 'Challenge')
            text(challenge['display_name'], 'Challenge name')
            text(challenge['description'], 'Challenge description')
            if challenge['effect'] not in ('armor', 'production', 'speed'):
                raise ValueError('Challenges may only strengthen enemy armor, production or speed.')
            integer(challenge['percent'], 'Challenge percent', 1)
            if challenge['percent'] > 100:
                raise ValueError('Challenge percent must not exceed 100.')
            if challenge['effect'] == 'production' and challenge['percent'] == 100:
                raise ValueError('Enemy production time must remain positive.')
            integer(challenge['victory_gems'], 'Challenge completion gems', 1)
        _unique(sections['perks'], 'Perk')
        for perk in sections['perks']:
            from .perks import validate_perk
            validate_perk(perk)
    except ValueError as exc:
        raise ValueError(f'Final Fortress config ({path or "document"}): {exc}') from exc


def load_config():
    from randomizer.config.static import load_static_config
    return load_static_config('final_fortress.json')


def configuration_gaps(config, difficulty, wave_multiplier=1):
    """Explain pending choices without turning them into implicit defaults."""
    if difficulty not in DIFFICULTY_IDS:
        raise ValueError('Unknown Final Fortress difficulty.')
    validate_wave_multiplier(wave_multiplier)
    gaps = []
    if config['map'] is None:
        gaps.append('Choose the map and starting positions.')
    elif config['map']['protected_building'] is None:
        gaps.append('Choose the protected building and its position.')
    elif config['map']['protected_building']['position'] is None:
        gaps.append('Validate the protected building position beside the starting MCV.')
    rosters = wave_rosters(config, difficulty)
    if any(not rosters.get(country) for country in SIDE_COUNTRIES):
        gaps.append('Define faction wave rosters and time-based mixed compositions.')
    if config['settings']['completion_gems'] is None:
        gaps.append('Choose the completion Gem reward (zero is allowed).')
    if config['settings']['max_wave_units'] is None:
        gaps.append('Choose the maximum additional units per wave.')
    elif 'wave_pressure' not in config:
        largest = max((sum(unit['count'] for unit in composition['units'])
                       for stages in rosters.values() for stage in stages
                       for composition in stage_compositions(stage)), default=0)
        if largest * 3 * wave_multiplier > config['settings']['max_wave_units']:
            gaps.append(f'x{wave_multiplier} can exceed the configured wave unit budget; '
                        'increase the budget or choose a lower multiplier.')
    if 'wave_pressure' in config:
        pressure = config['wave_pressure']
        if pressure['growth_per_wave'] is None:
            gaps.append('Choose how many base units to add per enemy after each wave.')
        if pressure['max_active_units'] is None:
            gaps.append('Choose the maximum living scripted-wave units.')
        if pressure['overflow'] is None:
            gaps.append('Choose how to handle waves delayed by the living-unit limit.')
        side_stages = pressure.get('spawn_sides')
        maximum_sides = max(stage['count'] for stage in side_stages) if side_stages else 3
        initial_total = (config['difficulties'][difficulty]['starting_wave_units']
                         * wave_multiplier * maximum_sides)
        for limit in (config['settings']['max_wave_units'], pressure['max_active_units']):
            if limit is not None and initial_total > limit:
                gaps.append(f'Maintaining the opening base count across {maximum_sides} active sides '
                            f'requires at least {initial_total} units; the configured limit is too low '
                            'for this multiplier.')
                break
    return tuple(gaps)
