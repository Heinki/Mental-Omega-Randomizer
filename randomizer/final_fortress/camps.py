"""Deterministic faction camps, bounded difficulty scaling and safe positions."""

from collections import Counter
from copy import deepcopy
import random

from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES

from .config import DIFFICULTY_IDS, stage_compositions, wave_rosters
from .pressure import size_composition


def _camp_countries(plan, count):
    """Deal every faction before repeating, independently of base AI rolls."""
    rng = random.Random(f'{plan["seed"]}:final_fortress:camp_countries')
    families = list(dict.fromkeys(SIDE_FAMILIES))
    countries = []
    while len(countries) < count:
        rng.shuffle(families)
        for family in families:
            countries.append(rng.choice([country for country, side in zip(SIDE_COUNTRIES, SIDE_FAMILIES)
                                         if side == family]))
    return countries[:count]


def resolve_camps(plan, config):
    balance = config.get('camp_balance')
    if not balance:
        raise ValueError('Configure mixed camp balance before starting a new Fortress run.')
    plan['camp_balance'] = deepcopy(balance)
    camps = plan['map']['camps']
    if not camps:
        return
    ceiling = min(balance['max_guards_per_camp'], balance['max_total_guards'] // len(camps))
    if ceiling < 1:
        raise ValueError('Camp population budget must allow at least one guard per camp.')
    regular_requested = balance['guards_by_difficulty'][plan['difficulty']] * plan['wave_multiplier']
    starter_rules = balance.get('starter_camps') if plan.get('plan_version', 1) >= 21 else None
    countries = (_camp_countries(plan, len(camps)) if plan.get('plan_version', 1) >= 19 else
                 [plan['enemy_countries'][camp['enemy_index']] for camp in camps])
    previous = {}
    for camp, country in zip(camps, countries):
        starter = starter_rules if starter_rules and camp['id'] in starter_rules['camp_ids'] else None
        requested = (starter['guards_by_difficulty'][plan['difficulty']] * plan['wave_multiplier']
                     if starter else regular_requested)
        count = min(requested, ceiling,
                    starter['max_guards_by_difficulty'][plan['difficulty']] if starter else ceiling)
        if len(camp.get('guard_positions', [])) < count:
            raise ValueError('Camp needs more reviewed guard positions: ' + camp['id'])
        rng = random.Random(f'{plan["seed"]}:final_fortress:camp:{camp["id"]}')
        if starter:
            variant = {'id': 'starter_infantry', 'units': starter['units_by_country'][country]}
            special = None
        else:
            stages = wave_rosters(config, plan['difficulty'])[country]
            choices = [(i, variant) for i, stage in enumerate(stages) for variant in stage_compositions(stage)]
            available = [(i, v) for i, v in choices if v.get('id') != previous.get(country)] or choices
            difficulty = DIFFICULTY_IDS.index(plan['difficulty'])
            weights = [(len(stages)-i if difficulty == 0 else 1+i if difficulty == 2 else 2) for i, _ in available]
            _, variant = rng.choices(available, weights=weights, k=1)[0]
            previous[country] = variant.get('id')
            special = (rng.choice(balance['special_units_by_country'][country])
                       if count > 1 and rng.randrange(100) < balance['special_chance_percent'] else None)
        units = size_composition(variant['units'][:5 if special else 6], base_units=count - bool(special),
                                 seed=plan['seed'] + ':' + camp['id'], house=camp['enemy_index']+2, seconds=0)
        counts = Counter({u['type']: u['count'] for u in units})
        if special:
            counts[special] += 1
        camp.update(guards=[{'type': kind, 'count': amount} for kind, amount in counts.items()],
                    guard_country=country, composition_id=variant.get('id'), special_unit=special,
                    requested_guards=requested)
        if plan.get('plan_version', 1) >= 21:
            camp['starter_camp'] = bool(starter)


def guard_positions(camp):
    count = sum(unit['count'] for unit in camp['guards'])
    if 'guard_positions' in camp:
        return deepcopy(camp['guard_positions'][:count])
    p = camp['position']
    return [{'x': p['x']-2+i%5, 'y': p['y']-2-i//5} for i in range(count)]
