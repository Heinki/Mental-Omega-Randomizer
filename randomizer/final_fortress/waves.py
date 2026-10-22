"""Time-based faction compositions and exact scripted-wave count scaling."""

import random
from copy import deepcopy

from .config import stage_compositions, validate_wave_multiplier, wave_rosters
from .pressure import size_composition, spawn_side_count, wave_size


def add_air_support(plan, config):
    """Replace part of each later wave with native airborne attack vehicles.

    Preserve the total population and at least one of every selected ground
    identity, including infantry and Challenge Powerhouses. Air is delivered
    separately so flight and ground movement cannot hold each other's teams.
    """
    stages = config.get('wave_air_support', [])
    if not stages:
        return
    plan['wave_air_support'] = deepcopy(stages)
    previous = {}
    for wave in plan['wave_schedule']:
        stage = next((entry for entry in reversed(stages) if entry['from_seconds'] <= wave['seconds']), None)
        if stage is None:
            continue
        for group in wave['groups']:
            units = group['units']
            total = sum(unit['count'] for unit in units)
            amount = min(max(1, total * stage['percent'] // 100), total - len(units))
            if amount <= 0:
                continue
            choices = stage['units_by_country'][group['country']]
            choices = [unit for unit in choices if unit['type'] != previous.get(group['house'])] or choices
            rng = random.Random(f'{plan["seed"]}:final_fortress:wave_air:{group["house"]}:{wave["seconds"]}')
            kind = rng.choices(choices, weights=[unit['count'] for unit in choices], k=1)[0]['type']
            previous[group['house']] = kind
            remainder = total - amount - len(units)
            extra = size_composition(units, base_units=remainder, seed=plan['seed'],
                                     house=plan['map']['enemy_waypoints'].index(group['waypoint']) + 2,
                                     seconds=wave['seconds']) if remainder else []
            counts = {unit['type']: unit['count'] for unit in extra}
            group['units'] = [{'type': unit['type'], 'count': 1 + counts.get(unit['type'], 0)} for unit in units]
            group['units'].append({'type': kind, 'count': amount})
            group['air_types'] = [kind]


def build_wave_schedule(config, *, difficulty, seed, enemies, wave_multiplier=1,
                        legacy=False, sized_waves=False):
    """Select compositions in isolated streams, then multiply every unit count.

    With multiple alternatives, successive waves for a house do not repeat the
    same named composition. Different time stages can introduce any configured
    infantry, ground, artillery, or other engine types; no Tier 1 filter applies.
    The legacy branch preserves already-persisted fixed wave plans exactly.
    """
    validate_wave_multiplier(wave_multiplier)
    if legacy and (wave_multiplier != 1 or 'wave_rosters' in config):
        raise ValueError('Legacy Final Fortress plans require their original wave configuration.')
    settings = config['settings']
    rosters = wave_rosters(config, difficulty)
    previous = {}
    side_order = list(range(len(enemies)))
    staged_sides = sized_waves and 'spawn_sides' in config['wave_pressure']
    if staged_sides:
        random.Random(f'{seed}:final_fortress:wave_spawn_order').shuffle(side_order)
    schedule = []
    for wave_index, seconds in enumerate(range(
        settings['wave_interval_seconds'], settings['survival_seconds'],
        settings['wave_interval_seconds'],
    )):
        size = wave_size(config, difficulty=difficulty, wave_index=wave_index,
                         wave_multiplier=wave_multiplier) if sized_waves else None
        groups = []
        active_sides = side_order[:spawn_side_count(config, seconds)] if staged_sides else side_order
        for index in active_sides:
            country = enemies[index]
            stage = next(stage for stage in reversed(rosters[country])
                         if stage['from_seconds'] <= seconds)
            if legacy and 'variants' in stage:
                raise ValueError('Legacy Final Fortress plans cannot use composition variants.')
            choices = stage_compositions(stage)
            if len(choices) > 1:
                choices = [entry for entry in choices if entry['id'] != previous.get(index)]
            rng = random.Random(f'{seed}:final_fortress:wave_composition:{index + 2}:{seconds}')
            composition = rng.choice(choices)
            previous[index] = composition['id']
            base = composition['units']
            if size is not None:
                base = size_composition(base, base_units=size['base_units'], seed=seed,
                                        house=index + 2, seconds=seconds)
            units = [{'type': unit['type'], 'count': unit['count'] * wave_multiplier}
                     for unit in base]
            group = {
                'house': f'Multi{index + 2}', 'country': country,
                'waypoint': config['map']['enemy_waypoints'][index], 'units': units,
            }
            if not legacy:
                group['composition_id'] = composition['id']
            groups.append(group)
        total = sum(unit['count'] for group in groups for unit in group['units'])
        if total > settings['max_wave_units']:
            raise ValueError(f'Wave at {seconds} seconds exceeds the configured unit budget.')
        wave = {'seconds': seconds, 'groups': groups}
        if size is not None:
            wave['size'] = size
        schedule.append(wave)
    return schedule
