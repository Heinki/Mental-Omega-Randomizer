"""Versioned Conquest economy and faction-native battle grants."""

from collections import Counter
from math import ceil
from .profile import NATIVE_COUNTRIES, ROSTERS, FACTORIES, AIRCRAFT_BUILDINGS, ESCORT_ROSTERS

AIRCRAFT_BUILDING_LABELS = {country: ("War Factory (aircraft production)" if kind in FACTORIES.values() else "aircraft building") for country, kind in AIRCRAFT_BUILDINGS.items()}

FACTORY_TRAINING_PERCENT = (0, 25, 50, 100)

FACTIONS = tuple(NATIVE_COUNTRIES)
DIFFICULTIES = {'Easy': 2, 'Normal': 1, 'Hard': 0, 'Impossible': 0}

SIZES = {'Short — 9 territories': 9, 'Standard — 25 territories': 25,
         'Long — 64 territories': 64, 'Epic — 100 territories': 100}
STATS = {'health': 'Health', 'armor': 'Armor', 'speed': 'Movement speed',
         'reload': 'Attack speed', 'damage': 'Damage'}
MAX_STRENGTH = 40
MAX_ARMIES_PER_NODE = 4
MAX_RESEARCH_RANK = 5
BALANCE_VERSION = 4
RECRUIT_COST = 1000
RESEARCH_COST = 1000
SUPPLY_COST = 500
REPAIR_KIT_COST = 750
INCOME_PER_RANK = 100
MAX_REPAIR_KITS = 3
BATTLE_CREDITS_PER_RANK = 2500
RULES_VERSION = 1
HQ_INFANTRY = 8
HQ_DEFENSES = 2



def _perk(name, cost, maximum, power, description, *, local=False):
    return dict(name=name, cost=cost, maximum=maximum, power=power,
                description=description, local=local)


PERKS = {
    'allies': _perk('Coalition allies', 2500, 3, 0, 'Add one AI ally per rank when the map has room.'),
    'infantry': _perk('Infantry escort', 1000, 6, 3, 'Bring more and stronger infantry as you upgrade.'),
    'vehicles': _perk('Armored escort', 1500, 6, 5, 'Bring more and stronger vehicles as you upgrade.'),
    'veterans': _perk('Starting army training', 700, 2, 0, 'Rank 1: troops start Veteran. Rank 2: troops start Elite.'),
    'veteran_defenses': _perk('Veteran defenses', 1400, 1, 0, 'Starting and newly built defenses begin Veteran. Native technology and ownership requirements remain.'),
    'unique_unit_capacity': _perk('Unique-unit capacity', 1800, 3, 0, 'Add one to supported positive live-unit limits per rank, up to +3. Does not unlock units or add starting troops.'),
    'special_building_limit': _perk('Special Building Limit', 1600, 3, 0, 'Add one to supported positive special-building and capped-defense limits per rank, up to +3. Normal technology requirements remain.'),
    'factory_training': _perk('Factory Training', 1400, 3, 0, 'Barracks and land vehicle factories train eligible troops with 25%, 50%, then 100% progress toward Veteran. Rank 3 produces Veteran units. Excludes naval, airfield aircraft and nontrainable units.'),
    'fortified_emplacements': _perk('Fortified Emplacements', 1200, 3, 0, 'Starting and newly built defenses gain 15% health per rank, up to 45%. Stacks with Veteran defenses; native access requirements remain.'),
    'generator_efficiency': _perk('Generator Efficiency', 900, 3, 0, 'Starting and future generators produce 25% more power per rank, up to 75%. Power consumption is unchanged.'),
    'transport_capacity': _perk('Transport Capacity', 1000, 3, 0, 'Add one passenger slot per rank to reviewed transports, up to +3. Excludes gunner vehicles and sealed payloads. Does not add passengers or unlock units.'),
    'open_topped_transports': _perk('Open-topped Transports', 1800, 1, 0, 'Passengers can fire from reviewed transports. Gunner vehicles, Stallion and Chrono Prison are excluded. Does not unlock units.'),
    'power': _perk('Field power plant', 800, 1, 1, 'Start with a power plant.'),
    'barracks': _perk('Forward Barracks', 1000, 1, 2, 'Start with a barracks. With Node barracks, you get two when defending.'),
    'refinery': _perk('Field refinery', 1600, 1, 4, 'Start with a refinery and one harvester.'),
    'garrison': _perk('Territory garrison', 750, 3, 4, 'Add one defense per rank to this territory.', local=True),
    'node_power': _perk('Node power plant', 500, 2, 1, 'Add one extra power plant per rank when defending here.', local=True),
    'node_barracks': _perk('Node barracks', 1000, 1, 2, 'Add a barracks when defending here. Stacks with Forward Barracks.', local=True),
    'node_refinery': _perk('Node refinery', 1600, 1, 4, 'Add a refinery and harvester when defending here.', local=True),
    'node_factory': _perk('Node vehicle factory', 2000, 1, 5, 'Add a vehicle factory when defending here.', local=True),
    'production': _perk('Production logistics', 1000, 5, 2, 'Build 10% faster per rank, up to 50%.'),
    'discount': _perk('Efficient procurement', 1000, 5, 2, 'Units and buildings cost 10% less per rank, up to 50%.'),
    'recruitment': _perk('Improved recruitment', 1000, 3, 0, 'Recruit one extra strength per rank.'),
    'income': _perk('War treasury', 800, 5, 0, 'Earn 100 more campaign credits per turn per rank.'),
    'battle_treasury': _perk('Battle Treasury', 1500, 3, 3, 'Start battles with 2,500 more credits per rank.'),
    'extended_arsenal': _perk('Extended Arsenal', 1800, 2, 3, 'Combat weapons gain one cell of range per rank.'),
    'civil_engineers': _perk('Civil Engineers', 1000, 5, 0, 'Node upgrades cost 10% less per rank, up to 50%.'),
    'hardened_infrastructure': _perk('Hardened Infrastructure', 1200, 5, 2, 'Production and economy buildings gain 10% health per rank, up to 50%.'),
    'elite_deployment': _perk('Elite Deployment', 1600, 1, 0, 'Troops start Elite.'),
    'factory': _perk('Forward Factory', 2000, 1, 5, 'Start with a vehicle factory. With Node vehicle factory, you get two when defending.'),
    'helipad': _perk('Forward aircraft production', 1600, 1, 3, 'Start with your faction aircraft building.'),
}

# Each rank is a complete cumulative escort, following the faction progression
# used by Fortress. The last slot is the faction's hero or special vehicle.
ESCORT_COUNTS = {
    'infantry': ((3, 0, 0, 0), (6, 0, 0, 0), (6, 2, 0, 0),
                 (6, 3, 2, 0), (8, 4, 3, 0), (8, 4, 3, 1)),
    'vehicles': ((1, 0, 0, 0), (2, 0, 0, 0), (2, 1, 0, 0),
                 (2, 2, 1, 0), (3, 3, 2, 0), (3, 3, 2, 1)),
}
ESCORT_WEIGHTS = {'infantry': (1, 3, 4, 12), 'vehicles': (5, 8, 12, 25)}


def escort_units(country, key, rank):
    if not rank:
        return {}
    return {kind: count for kind, count in zip(ESCORT_ROSTERS[country][key], ESCORT_COUNTS[key][rank - 1]) if count}


def escort_power(key, rank):
    return sum(count * weight for count, weight in zip(ESCORT_COUNTS[key][rank - 1], ESCORT_WEIGHTS[key])) if rank else 0


# Retain this identity for existing purchases, capture rewards and frozen battles.
# New purchases expose Veteran and Elite as two ranks of one perk.
PERKS['elite_deployment']['legacy'] = True
LOCAL_PERKS = tuple(key for key, perk in PERKS.items() if perk['local'])


def starting_force(country, strength, perks, *, headquarters=False, legacy_aircraft=False,
                   balance_version=BALANCE_VERSION, army_count=1, defense_multiplier=1):
    """Freeze the units and buildings used by native and strategic battles."""
    infantry, scout, tank, power, barracks, refinery, collector, defense = ROSTERS[country]
    scouts = strength // 5
    units = Counter({infantry: strength - scouts * 3, scout: scouts})
    modern = balance_version >= BALANCE_VERSION
    if modern:
        for key in ('infantry', 'vehicles'):
            units.update({kind: count * army_count for kind, count in escort_units(country, key, perks.get(key, 0)).items()})
    else:
        units[infantry] += 3 * perks.get('infantry', 0)
        units[tank] += perks.get('vehicles', 0)
    local = defense_multiplier if modern else 1
    # Armies share the commander's production base. Only military defenses
    # multiply with the stack; refinery grants still supply one collector each.
    refineries = perks.get('refinery', 0) + perks.get('node_refinery', 0)
    structures = Counter({power: perks.get('power', 0) + perks.get('node_power', 0),
                          barracks: perks.get('barracks', 0) + perks.get('node_barracks', 0),
                          refinery: refineries, defense: perks.get('garrison', 0) * local})
    structures[FACTORIES[country]] += perks.get('factory', 0) + perks.get('node_factory', 0)
    structures[AIRCRAFT_BUILDINGS[country]] += perks.get('helipad', 0)
    if headquarters:
        units[infantry] += HQ_INFANTRY
        structures[defense] += HQ_DEFENSES * local
    if refineries:
        units[collector] += refineries
    return {'units': dict(+units), 'structures': dict(+structures),
            'veterancy': deployment_rank(perks), 'collector': collector, 'power_type': power}


def starting_structures(force, perks, power=None):
    """Count granted buildings plus the native generators needed to power them."""
    structures = Counter(force['structures'])
    if power is not None:
        balance = sum(float(power.get(kind, 0)) * count for kind, count in structures.items())
        # Purchased generators are extra capacity, beyond the base's needs.
        output = float(power.get(force['power_type'], 0))
        balance -= output * perks.get('node_power', 0)
        if balance < 0:
            if output <= 0:
                raise ValueError('The selected faction has no valid starting generator.')
            structures[force['power_type']] += ceil(-balance / output)
    return dict(+structures)


def deployment_rank(perks):
    return 2 if perks.get('elite_deployment') else perks.get('veterans', 0)


def perk_rank(perks, key):
    return deployment_rank(perks) if key == 'veterans' else perks.get(key, 0)


def combat_power(strength, stats, perks, *, headquarters=False, field_repairs=False,
                 balance_version=BALANCE_VERSION, army_count=1, defense_multiplier=1):
    modern = balance_version >= BALANCE_VERSION
    personal = army_count if modern else 1
    local = defense_multiplier if modern else 1
    mobile = strength + (sum(escort_power(key, perks.get(key, 0)) for key in ('infantry', 'vehicles')) * personal
                         if modern else 3 * perks.get('infantry', 0) + 5 * perks.get('vehicles', 0))
    if headquarters:
        mobile += HQ_INFANTRY
    value = mobile * (1 + .15 * deployment_rank(perks))
    value += sum(p['power'] * perks.get(key, 0) * (local if key == 'garrison' else 1)
                 for key, p in PERKS.items() if key not in ('infantry', 'vehicles'))
    if headquarters:
        value += HQ_DEFENSES * PERKS['garrison']['power'] * local
    if perks.get('veteran_defenses') or perks.get('fortified_emplacements'):
        defenses = perks.get('garrison', 0) + (HQ_DEFENSES if headquarters else 0)
        base_defense = defenses * PERKS['garrison']['power'] * local
        trained = 1.15 if perks.get('veteran_defenses') else 1
        durability = (1 + .15 * perks.get('fortified_emplacements', 0)) ** .5
        value += base_defense * (trained * durability - 1)
    for stat in STATS:
        value *= (1 + stats.get(stat, 0) / 100) ** (.25 if stat == 'speed' else .5)
    if field_repairs:
        value *= 1.1
    return max(1, round(value, 3))
