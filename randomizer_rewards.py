"""Reward catalogue and display helpers for the Mental Omega randomizer."""

# This module is intentionally data-heavy. Keeping it separate from the Tk
# launcher makes future Archipelago item/location work much easier.

ALLIED_BUILD_HOUSES = 'UnitedStates,Europeans,Pacific,Europeans2,MORPLAYER'
SOVIET_BUILD_HOUSES = 'USSR,Latin,Chinese,MORPLAYER'
EPSILON_BUILD_HOUSES = 'PsiCorps,Headquaters,ScorpionCell,MORPLAYER'
FOEHN_BUILD_HOUSES = 'Guild1,Guild2,Guild3,MORPLAYER'
ALL_BUILD_HOUSES = (
    ALLIED_BUILD_HOUSES + ',' + SOVIET_BUILD_HOUSES + ','
    + EPSILON_BUILD_HOUSES + ',' + FOEHN_BUILD_HOUSES
)
DEFAULT_REWARDS_PER_CHECK = 1
MAX_REWARDS_PER_CHECK = 5


def build_unlock(section, tech_level, prerequisite=None, houses=ALLIED_BUILD_HOUSES):
    values = {
        'TechLevel': str(tech_level),
        'Owner': houses,
        'RequiredHouses': houses,
        'ForbiddenHouses': 'none',
    }
    if prerequisite:
        values['PrerequisiteOverride'] = prerequisite
    return {section: values}

UNIT_UNLOCK_REWARDS = [
    {
        'name': 'GI Access',
        'description': 'Allows basic Allied GIs where the map tech tree permits them.',
        'rules': build_unlock('E1', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Guardian GI Access',
        'description': 'Allows Guardian GIs where the map tech tree permits them.',
        'rules': build_unlock('GGI', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Attack Dog Access',
        'description': 'Allows Allied Attack Dogs where the map tech tree permits them.',
        'rules': build_unlock('ADOG', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Field Medic Access',
        'description': 'Allows Allied Field Medics where the map tech tree permits them.',
        'rules': build_unlock('AMEDIC', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Rocketeer Access',
        'description': 'Allows Rocketeers where the map tech tree permits them.',
        'rules': build_unlock('JUMPJET', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Engineer Corps',
        'description': 'Allows Engineers where the map tech tree permits them.',
        'rules': build_unlock('ENGINEER', 1, 'ALLRAX,SOVRAX,YURRAX,FOERAX', ALL_BUILD_HOUSES),
        'factions': ['Allies', 'Soviets', 'Epsilon', 'Foehn'],
    },
    {
        'name': 'Humvee Access',
        'description': 'Allows Humvees where the map tech tree permits them.',
        'rules': build_unlock('AHMV', 2, 'GAWEAP'),
        'factions': ['Allies'],
    },
    {
        'name': 'IFV Access',
        'description': 'Allows IFVs where the map tech tree permits them.',
        'rules': build_unlock('FV', 2, 'GAWEAP'),
        'factions': ['Allies'],
    },
    {
        'name': 'Cryo Legionnaires',
        'description': 'Allows Cryo Legionnaires where the map tech tree permits them.',
        'rules': build_unlock('CLEG', 3, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Battle Fortress Access',
        'description': 'Allows Battle Fortresses where the map tech tree permits them.',
        'rules': build_unlock('FORTRESS', 4, 'GAWEAP'),
        'factions': ['Allies'],
    },
    {
        'name': 'Conscript Access',
        'description': 'Allows Conscripts where the map tech tree permits them.',
        'rules': build_unlock('E2', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Flak Trooper Access',
        'description': 'Allows Flak Troopers where the map tech tree permits them.',
        'rules': build_unlock('FLAKT', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Soviet Attack Dog Access',
        'description': 'Allows Soviet Attack Dogs where the map tech tree permits them.',
        'rules': build_unlock('DOG', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Tesla Trooper Access',
        'description': 'Allows Tesla Troopers where the map tech tree permits them.',
        'rules': build_unlock('SHK', 2, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Heavy Tank Access',
        'description': 'Allows Soviet Heavy Tanks where the map tech tree permits them.',
        'rules': {'HTNK': {'TechLevel': '2'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Flak Track Access',
        'description': 'Allows Flak Tracks where the map tech tree permits them.',
        'rules': {'HTK': {'TechLevel': '2'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Tesla Tank Access',
        'description': 'Allows Tesla Tanks where the map tech tree permits them.',
        'rules': {'TTNK': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Akula Access',
        'description': 'Allows Akulas where the map tech tree permits them.',
        'rules': {'AKULA': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Dreadnought Access',
        'description': 'Allows Dreadnoughts where the map tech tree permits them.',
        'rules': {'DRED': {'TechLevel': '4'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Initiate Access',
        'description': 'Allows Initiates where the map tech tree permits them.',
        'rules': {'INIT': {'TechLevel': '1'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Lasher Tank Access',
        'description': 'Allows Lasher Tanks where the map tech tree permits them.',
        'rules': {'LTNK': {'TechLevel': '2'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Gatling Tank Access',
        'description': 'Allows Gatling Tanks where the map tech tree permits them.',
        'rules': {'YTNK': {'TechLevel': '2'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Virus Access',
        'description': 'Allows Viruses where the map tech tree permits them.',
        'rules': {'VIRUS': {'TechLevel': '3'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Mastermind Access',
        'description': 'Allows Masterminds where the map tech tree permits them.',
        'rules': {'MIND': {'TechLevel': '4'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Knightframe Access',
        'description': 'Allows Knightframes where the map tech tree permits them.',
        'rules': {'KNIGHT': {'TechLevel': '1'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Jackal Racer Access',
        'description': 'Allows Jackal Racers where the map tech tree permits them.',
        'rules': {'JACKAL': {'TechLevel': '2'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Cyclops Walker Access',
        'description': 'Allows Cyclops Walkers where the map tech tree permits them.',
        'rules': {'CYCL': {'TechLevel': '2'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Draco Tank Access',
        'description': 'Allows Draco Tanks where the map tech tree permits them.',
        'rules': {'DRACO': {'TechLevel': '3'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Quetzal Access',
        'description': 'Allows Quetzals where the map tech tree permits them.',
        'rules': {'QUETZ': {'TechLevel': '4'}},
        'factions': ['Foehn'],
    },
]

EXTRA_UNIT_UNLOCK_REWARDS = [
    {
        'name': 'Destroyer Access',
        'description': 'Allows Allied Destroyers where the map tech tree permits them.',
        'rules': build_unlock('DEST', 3, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Dolphin Access',
        'description': 'Allows Dolphins where the map tech tree permits them.',
        'rules': build_unlock('DLPH', 3, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Aegis Cruiser Access',
        'description': 'Allows Aegis Cruisers where the map tech tree permits them.',
        'rules': build_unlock('AEGIS', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Aircraft Carrier Access',
        'description': 'Allows Aircraft Carriers where the map tech tree permits them.',
        'rules': build_unlock('CARRIER', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Allied Transport Access',
        'description': 'Allows Allied naval transports where the map tech tree permits them.',
        'rules': build_unlock('LCRF', 2, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Battlecruiser Access',
        'description': 'Allows Allied battlecruisers where the map tech tree permits them.',
        'rules': build_unlock('HCRUIS', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Typhoon Sub Access',
        'description': 'Allows Soviet submarines where the map tech tree permits them.',
        'rules': {'SUB': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Squid Access',
        'description': 'Allows Giant Squids where the map tech tree permits them.',
        'rules': {'SQD': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Sea Scorpion Access',
        'description': 'Allows Sea Scorpions where the map tech tree permits them.',
        'rules': {'DBOAT': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Soviet Transport Access',
        'description': 'Allows Soviet naval transports where the map tech tree permits them.',
        'rules': {'SAPC': {'TechLevel': '2'}},
        'factions': ['Soviets'],
    },
]

BUFF_TARGETS = {
    'MOR_BUILDINGS': {
        'label': 'Base Construction',
        'plural': 'Buildings',
        'category': 'buildings',
        'factions': ['Allies', 'Soviets', 'Epsilon', 'Foehn'],
        'allowed_buff_types': ['production'],
        'buff_descriptions': {
            'production': 'Buildings construct 15% faster in future launched missions.',
        },
        'global_buff': True,
    },
    'E1': {
        'label': 'GI',
        'plural': 'GIs',
        'category': 'infantry',
        'factions': ['Allies'],
        'cost': 100,
        'speed': 6,
        'strength': 125,
        'sight': 5,
        'guard_range': 5,
        'weapons': {
            'M60': {'damage': 15, 'rof': 20, 'range': 4},
            'M60E': {'damage': 20, 'rof': 20, 'range': 5},
            'Para': {'damage': 18, 'rof': 20, 'range': 5},
            'ParaE': {'damage': 24, 'rof': 20, 'range': 6},
        },
    },
    'GGI': {'label': 'Guardian GI', 'plural': 'Guardian GIs', 'category': 'infantry', 'factions': ['Allies'], 'cost': 150, 'speed': 6, 'strength': 150, 'sight': 6, 'guard_range': 6},
    'AMEDIC': {'label': 'Field Medic', 'plural': 'Field Medics', 'category': 'infantry', 'factions': ['Allies'], 'cost': 500, 'speed': 6, 'strength': 125, 'sight': 5, 'guard_range': 5},
    'JUMPJET': {'label': 'Rocketeer', 'plural': 'Rocketeers', 'category': 'infantry', 'factions': ['Allies'], 'cost': 650, 'speed': 8, 'strength': 150, 'sight': 7, 'guard_range': 7},
    'E2': {'label': 'Conscript', 'plural': 'Conscripts', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 100, 'speed': 5, 'strength': 125, 'sight': 5, 'guard_range': 5},
    'FLAKT': {'label': 'Flak Trooper', 'plural': 'Flak Troopers', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 300, 'speed': 5, 'strength': 125, 'sight': 6, 'guard_range': 6},
    'DOG': {'label': 'Soviet Attack Dog', 'plural': 'Soviet Attack Dogs', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 200, 'speed': 8, 'strength': 100, 'sight': 5, 'guard_range': 5},
    'SHK': {'label': 'Tesla Trooper', 'plural': 'Tesla Troopers', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 500, 'speed': 4, 'strength': 200, 'sight': 6, 'guard_range': 6},
    'AHMV': {
        'label': 'Humvee',
        'plural': 'Humvees',
        'category': 'units',
        'factions': ['Allies'],
        'cost': 500,
        'speed': 9,
        'strength': 300,
        'sight': 6,
        'guard_range': 6,
        'weapons': {
            'HumveeGun': {'damage': 60, 'rof': 35, 'range': 6},
            'HumveeGunE': {'damage': 75, 'rof': 30, 'range': 7},
        },
    },
    'FV': {'label': 'IFV', 'plural': 'IFVs', 'category': 'units', 'factions': ['Allies'], 'cost': 800, 'speed': 10, 'strength': 300, 'sight': 8, 'guard_range': 8},
    'HTNK': {'label': 'Heavy Tank', 'plural': 'Heavy Tanks', 'category': 'units', 'factions': ['Soviets'], 'cost': 900, 'speed': 7, 'strength': 500, 'sight': 6, 'guard_range': 6},
    'HTK': {'label': 'Flak Track', 'plural': 'Flak Tracks', 'category': 'units', 'factions': ['Soviets'], 'cost': 500, 'speed': 8, 'strength': 250, 'sight': 5, 'guard_range': 5},
    'TTNK': {'label': 'Tesla Tank', 'plural': 'Tesla Tanks', 'category': 'units', 'factions': ['Soviets'], 'cost': 1200, 'speed': 6, 'strength': 400, 'sight': 7, 'guard_range': 7},
    'AKULA': {'label': 'Akula', 'plural': 'Akulas', 'category': 'units', 'factions': ['Soviets'], 'cost': 1200, 'speed': 5, 'strength': 600, 'sight': 8, 'guard_range': 8},
    'DRED': {'label': 'Dreadnought', 'plural': 'Dreadnoughts', 'category': 'units', 'factions': ['Soviets'], 'cost': 2000, 'speed': 4, 'strength': 800, 'sight': 8, 'guard_range': 8},
    'SUB': {'label': 'Typhoon Sub', 'plural': 'Typhoon Subs', 'category': 'units', 'factions': ['Soviets'], 'cost': 1000, 'speed': 4, 'strength': 600, 'sight': 8, 'guard_range': 8},
    'SQD': {'label': 'Giant Squid', 'plural': 'Giant Squids', 'category': 'units', 'factions': ['Soviets'], 'cost': 1000, 'speed': 8, 'strength': 300, 'sight': 5, 'guard_range': 5},
    'DBOAT': {'label': 'Sea Scorpion', 'plural': 'Sea Scorpions', 'category': 'units', 'factions': ['Soviets'], 'cost': 600, 'speed': 8, 'strength': 400, 'sight': 7, 'guard_range': 7},
    'SAPC': {'label': 'Soviet Transport', 'plural': 'Soviet Transports', 'category': 'units', 'factions': ['Soviets'], 'cost': 900, 'speed': 6, 'strength': 300, 'sight': 6, 'guard_range': 6},
    'INIT': {'label': 'Initiate', 'plural': 'Initiates', 'category': 'infantry', 'factions': ['Epsilon'], 'cost': 150, 'speed': 5, 'strength': 100, 'sight': 5, 'guard_range': 5},
    'LTNK': {'label': 'Lasher Tank', 'plural': 'Lasher Tanks', 'category': 'units', 'factions': ['Epsilon'], 'cost': 700, 'speed': 8, 'strength': 350, 'sight': 6, 'guard_range': 6},
    'YTNK': {'label': 'Gatling Tank', 'plural': 'Gatling Tanks', 'category': 'units', 'factions': ['Epsilon'], 'cost': 600, 'speed': 8, 'strength': 300, 'sight': 6, 'guard_range': 6},
    'VIRUS': {'label': 'Virus', 'plural': 'Viruses', 'category': 'infantry', 'factions': ['Epsilon'], 'cost': 700, 'speed': 5, 'strength': 100, 'sight': 8, 'guard_range': 8},
    'MIND': {'label': 'Mastermind', 'plural': 'Masterminds', 'category': 'units', 'factions': ['Epsilon'], 'cost': 1500, 'speed': 5, 'strength': 300, 'sight': 8, 'guard_range': 8},
    'KNIGHT': {'label': 'Knightframe', 'plural': 'Knightframes', 'category': 'units', 'factions': ['Foehn'], 'cost': 500, 'speed': 9, 'strength': 250, 'sight': 6, 'guard_range': 6},
    'JACKAL': {'label': 'Jackal Racer', 'plural': 'Jackal Racers', 'category': 'units', 'factions': ['Foehn'], 'cost': 600, 'speed': 10, 'strength': 250, 'sight': 7, 'guard_range': 7},
    'CYCL': {'label': 'Cyclops Walker', 'plural': 'Cyclops Walkers', 'category': 'units', 'factions': ['Foehn'], 'cost': 900, 'speed': 7, 'strength': 450, 'sight': 7, 'guard_range': 7},
    'DRACO': {'label': 'Draco Tank', 'plural': 'Draco Tanks', 'category': 'units', 'factions': ['Foehn'], 'cost': 1200, 'speed': 7, 'strength': 450, 'sight': 7, 'guard_range': 7},
    'QUETZ': {'label': 'Quetzal', 'plural': 'Quetzals', 'category': 'aircraft', 'factions': ['Foehn'], 'cost': 1400, 'speed': 12, 'strength': 300, 'sight': 8, 'guard_range': 8},
}

UNIT_LABELS = {
    'ADOG': 'Attack Dog',
    'AEGIS': 'Aegis Cruiser',
    'AHMV': 'Humvee',
    'AMEDIC': 'Field Medic',
    'CARRIER': 'Aircraft Carrier',
    'CLEG': 'Cryo Legionnaire',
    'DEST': 'Destroyer',
    'DLPH': 'Dolphin',
    'E1': 'GI',
    'E2': 'Conscript',
    'DOG': 'Soviet Attack Dog',
    'ENGINEER': 'Engineer',
    'FORTRESS': 'Battle Fortress',
    'FV': 'IFV',
    'GGI': 'Guardian GI',
    'HCRUIS': 'Battlecruiser',
    'JUMPJET': 'Rocketeer',
    'LCRF': 'Allied Transport',
    'AKULA': 'Akula',
    'DBOAT': 'Sea Scorpion',
    'DRED': 'Dreadnought',
    'FLAKT': 'Flak Trooper',
    'HTK': 'Flak Track',
    'HTNK': 'Heavy Tank',
    'SAPC': 'Soviet Transport',
    'SHK': 'Tesla Trooper',
    'SQD': 'Giant Squid',
    'SUB': 'Typhoon Sub',
    'TTNK': 'Tesla Tank',
    'INIT': 'Initiate',
    'LTNK': 'Lasher Tank',
    'MIND': 'Mastermind',
    'VIRUS': 'Virus',
    'YTNK': 'Gatling Tank',
    'CYCL': 'Cyclops Walker',
    'DRACO': 'Draco Tank',
    'JACKAL': 'Jackal Racer',
    'KNIGHT': 'Knightframe',
    'QUETZ': 'Quetzal',
}


def unit_display_label(unit_id):
    target = BUFF_TARGETS.get(unit_id)
    if target:
        return target.get('label', unit_id)
    return UNIT_LABELS.get((unit_id or '').upper(), unit_id)


BUFF_TYPES = [
    {
        'id': 'production',
        'name': 'Drill',
        'setting_label': 'Production / construction speed',
        'description': '{plural} build/train 15% faster in future launched missions.',
    },
    {
        'id': 'cost',
        'name': 'Logistics',
        'setting_label': 'Cost reduction',
        'description': '{plural} cost 20% less in future launched missions.',
    },
    {
        'id': 'speed',
        'name': 'Mobility',
        'setting_label': 'Movement speed',
        'description': '{plural} move faster in future launched missions.',
    },
    {
        'id': 'armor',
        'name': 'Armor Plating',
        'setting_label': 'Armor',
        'description': '{plural} take less incoming damage in future launched missions.',
    },
    {
        'id': 'health',
        'name': 'Reinforced Frames',
        'setting_label': 'Health',
        'description': '{plural} gain more health in future launched missions.',
        'requires_stat': 'strength',
    },
    {
        'id': 'sight',
        'name': 'Recon Package',
        'setting_label': 'Vision',
        'description': '{plural} gain more vision in future launched missions.',
        'requires_stat': 'sight',
    },
    {
        'id': 'damage',
        'name': 'Firepower',
        'setting_label': 'Damage',
        'description': '{plural} deal more weapon damage in future launched missions.',
        'requires_weapons': True,
        'requires_clone': True,
    },
    {
        'id': 'reload',
        'name': 'Weapon Tuning',
        'setting_label': 'Weapon reload',
        'description': '{plural} reload their weapons faster in future launched missions.',
        'requires_weapons': True,
        'requires_clone': True,
    },
    {
        'id': 'rof',
        'name': 'Rapid Fire',
        'setting_label': 'Attack speed',
        'description': '{plural} improve the player house attack-speed multiplier in future launched missions.',
        'requires_weapons': True,
    },
    {
        'id': 'range',
        'name': 'Optics',
        'setting_label': 'Attack range',
        'description': '{plural} gain more weapon range in future launched missions.',
        'requires_weapons': True,
        'requires_clone': True,
    },
    {
        'id': 'ammo',
        'name': 'Ammo Reserves',
        'setting_label': 'Ammo',
        'description': '{plural} gain more ammunition before reloading in future launched missions.',
        'requires_stat': 'ammo',
        'requires_clone': True,
    },
    {
        'id': 'self_healing',
        'name': 'Repair Systems',
        'setting_label': 'Self-healing',
        'description': '{plural} gain self-healing in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'cloak',
        'name': 'Stealth Systems',
        'setting_label': 'Cloaking',
        'description': '{plural} gain cloaking in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'sensors',
        'name': 'Sensor Suite',
        'setting_label': 'Sensors',
        'description': '{plural} gain sensors in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'guard_range',
        'name': 'Targeting Package',
        'setting_label': 'Target acquisition range',
        'description': '{plural} acquire targets from farther away in future launched missions.',
        'requires_stat': 'guard_range',
        'requires_clone': True,
    },
    {
        'id': 'veteran',
        'name': 'Veteran Training',
        'setting_label': 'Veteran start',
        'description': '{plural} start as veterans for the player house in future launched missions.',
    },
]


def build_buff_rewards():
    rewards = []
    for unit_id, target in BUFF_TARGETS.items():
        for buff_type in BUFF_TYPES:
            allowed_types = target.get('allowed_buff_types')
            if allowed_types and buff_type.get('id') not in allowed_types:
                continue
            if buff_type.get('requires_stat') and buff_type.get('requires_stat') not in target:
                continue
            if buff_type.get('requires_weapons') and not target.get('weapons'):
                continue
            rewards.append({
                'name': f'{target["label"]} {buff_type["name"]} I',
                'description': target.get('buff_descriptions', {}).get(
                    buff_type['id'],
                    buff_type['description'].format(plural=target['plural']),
                ),
                'rules': {},
                'factions': target['factions'],
                'kind': 'buff',
                'unit': unit_id,
                'buff_type': buff_type['id'],
                'global_buff': bool(target.get('global_buff')),
            })
    return rewards


UNIT_BUFF_REWARDS = build_buff_rewards()

REWARD_POOL = UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS + UNIT_BUFF_REWARDS
REWARD_ALIASES = {
    'Medic Drill I': 'Field Medic Drill I',
    'Humvee Assembly I': 'Humvee Drill I',
    'IFV Assembly I': 'IFV Drill I',
    'Chrono Legionnaires': 'Cryo Legionnaires',
    'Mind Control Access': 'Mastermind Access',
}

for buff_type in BUFF_TYPES:
    REWARD_ALIASES[f'Mind Control Unit {buff_type["name"]} I'] = f'Mastermind {buff_type["name"]} I'


def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}

    reward_name = reward.get('name')
    if not reward_name:
        return reward
    reward_name = REWARD_ALIASES.get(reward_name, reward_name)

    for candidate in REWARD_POOL:
        if candidate.get('name') == reward_name:
            return candidate
    return reward


def canonical_rewards(rewards):
    if isinstance(rewards, list):
        return [canonical_reward(reward) for reward in rewards if isinstance(reward, dict)]
    if isinstance(rewards, dict):
        return [canonical_reward(rewards)]
    return []


def check_rewards(check):
    rewards = canonical_rewards(check.get('rewards'))
    if rewards:
        return rewards
    return canonical_rewards(check.get('reward'))


def reward_names(rewards):
    names = [reward_display_name(reward) for reward in rewards]
    return ', '.join(names) if names else 'No reward'


def clamp_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def valid_choice(value, choices, default):
    return value if value in choices else default


HOUSE_CATEGORY_SUFFIXES = {
    'infantry': 'Infantry',
    'units': 'Units',
    'aircraft': 'Aircraft',
    'buildings': 'Buildings',
    'defenses': 'Defenses',
}

HOUSE_SCOPED_BUFF_TYPES = {'production', 'cost', 'speed', 'armor', 'rof', 'veteran'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload'}
UNIT_STAT_BUFF_TYPES = {'health', 'sight', 'ammo', 'self_healing', 'cloak', 'sensors', 'guard_range'}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = MAP_GUARDED_BUFF_TYPES
MAX_VETERANCY_STACKS = 1


def reward_display_name(reward):
    reward = canonical_reward(reward)
    name = reward.get('name', 'Unknown reward')
    if reward.get('kind') == 'buff' and name.endswith(' I'):
        return name[:-2]
    return name


def house_category_suffix(target):
    return HOUSE_CATEGORY_SUFFIXES.get(target.get('category', 'units'), 'Units')


def buff_stack_limit(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return None
    if reward.get('buff_type') == 'veteran':
        return MAX_VETERANCY_STACKS
    if reward.get('buff_type') in {'self_healing', 'cloak', 'sensors'}:
        return 1
    return None


def effective_buff_count(reward, count):
    limit = buff_stack_limit(reward)
    if limit is None:
        return count
    return min(count, limit)


def stack_label(count):
    return f'Stacked {count} time' + ('s' if count != 1 else '')


def buff_effect_lines(reward, count=1, include_label=True):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)
    if buff_type == 'production':
        multiplier = max(0.35, 0.85 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        effect = 'Construction' if target.get('category') == 'buildings' else 'Production'
        return [f'{prefix}{effect} {faster}% faster ({stack_label(count)})']
    if buff_type == 'cost':
        multiplier = max(0.30, 0.80 ** count)
        cheaper = int(round((1.0 - multiplier) * 100))
        return [f'{prefix}Cost {cheaper}% cheaper ({stack_label(count)})']
    if buff_type == 'speed':
        multiplier = min(1.75, 1.10 ** count)
        faster = int(round((multiplier - 1.0) * 100))
        return [f'{prefix}Speed {faster}% faster ({stack_label(count)})']
    if buff_type == 'armor':
        multiplier = max(0.50, 0.90 ** count)
        tougher = int(round((1.0 - multiplier) * 100))
        return [f'{prefix}Armor {tougher}% stronger ({stack_label(count)})']
    if buff_type == 'health':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [f'{prefix}Health {stronger}% higher ({stack_label(count)})']
    if buff_type == 'sight':
        increase = min(4, count)
        return [f'{prefix}Vision +{increase} ({stack_label(count)})']
    if buff_type == 'rof':
        multiplier = max(0.40, 0.90 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        return [f'{prefix}Attack speed {faster}% faster ({stack_label(count)})']
    if buff_type == 'veteran':
        return [f'{prefix}Veteran start ({stack_label(count)})']
    if buff_type == 'damage':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [f'{prefix}Damage {stronger}% higher ({stack_label(count)})']
    if buff_type == 'reload':
        multiplier = max(0.45, 0.90 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        return [f'{prefix}Weapon reload {faster}% faster ({stack_label(count)})']
    if buff_type == 'range':
        increase = min(3.0, 0.5 * count)
        if increase.is_integer():
            increase_text = str(int(increase))
        else:
            increase_text = f'{increase:.1f}'
        return [f'{prefix}Range +{increase_text} ({stack_label(count)})']
    if buff_type == 'ammo':
        increase = min(5, count)
        return [f'{prefix}Ammo +{increase} ({stack_label(count)})']
    if buff_type == 'self_healing':
        return [f'{prefix}Self-healing enabled ({stack_label(count)})']
    if buff_type == 'cloak':
        return [f'{prefix}Cloaking enabled ({stack_label(count)})']
    if buff_type == 'sensors':
        return [f'{prefix}Sensors enabled ({stack_label(count)})']
    if buff_type == 'guard_range':
        increase = min(5, count)
        return [f'{prefix}Targeting range +{increase} ({stack_label(count)})']
    return []


def reward_rule_summary(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        return buff_effect_lines(reward)

    summaries = []
    rules = reward.get('rules', {})
    for section, values in rules.items():
        changes = []
        for key, value in values.items():
            key_lower = key.lower()
            if key_lower == 'techlevel':
                changes.append('unlocked')
            elif key_lower == 'buildtimemultiplier':
                try:
                    multiplier = float(value)
                    delta = int(round((1.0 - multiplier) * 100))
                except (TypeError, ValueError):
                    delta = 0
                if delta > 0:
                    changes.append(f'builds/trains {delta}% faster')
                elif delta < 0:
                    changes.append(f'builds/trains {abs(delta)}% slower')
                else:
                    changes.append(f'BuildTimeMultiplier={value}')
            elif key_lower in {'owner', 'requiredhouses', 'forbiddenhouses', 'prerequisiteoverride'}:
                continue
            else:
                changes.append(f'{key}={value}')

        if changes:
            summaries.append(f'{unit_display_label(section)}: {", ".join(changes)}')

    return summaries


def reward_display_lines(reward, indent='  '):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    lines = []
    for summary in reward_rule_summary(reward):
        lines.append(f'{indent}{summary}')
    return lines


