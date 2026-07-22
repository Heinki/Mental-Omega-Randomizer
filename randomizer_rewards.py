"""Reward catalogue and display helpers for the Mental Omega randomizer."""

from randomizer_weapon_stats import (
    ROSTER_DAMAGE_WEAPON_REFS,
    ROSTER_WEAPON_REFS,
    WEAPON_BASE_STATS,
)
from randomizer_static_config import load_static_config


_UNIT_DATA_CONFIG = load_static_config('rewards/unit_data.json')
_REWARD_CATALOGUE_CONFIG = load_static_config('rewards/catalogue.json')

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
MAX_REWARDS_PER_CHECK = 30

# Complete playable 3.3.6 faction rosters.  These use the real rulesmo.ini
# section IDs, which frequently differ from the public-facing unit names.
# Keep economy, construction, support and hero units here too: a buffs-only
# seed must be able to improve every player-owned faction unit, not merely the
# small subset that also has an access reward.
FACTION_UNIT_ROSTERS = dict(_UNIT_DATA_CONFIG['faction_unit_rosters'])

# Snapshot of the installed 3.3.6 rules values used by map-local stat buffs.
# Tuple order: Cost, Speed, Strength, Sight, GuardRange, Ammo.  GuardRange
# falls back to Sight when the base rules inherit/omit it.
UNIT_BASE_STATS = {
    unit_id: tuple(values)
    for unit_id, values in _UNIT_DATA_CONFIG['unit_base_stats'].items()
}

def build_roster_weapon_stats():
    """Expand the generated rules registry into the normal reward format."""
    roster = {}
    field_names = ('damage', 'rof', 'range')
    for unit_id, weapon_ids in ROSTER_WEAPON_REFS.items():
        weapons = {}
        for weapon_id in weapon_ids:
            values = WEAPON_BASE_STATS.get(weapon_id)
            if not values:
                continue
            stats = {}
            for field, value in zip(field_names, values):
                if value is None or value <= 0:
                    continue
                # Damage=1 is commonly a launcher/scanner control value. The
                # real damaging payload is registered separately below.
                if field == 'damage' and value <= 1:
                    continue
                # ROF=1 is already the engine minimum and cannot be reduced
                # to make the weapon fire faster.
                if field == 'rof' and value <= 1:
                    continue
                stats[field] = value
            if stats:
                weapons[weapon_id] = stats
        for weapon_id in ROSTER_DAMAGE_WEAPON_REFS.get(unit_id, ()):
            values = WEAPON_BASE_STATS.get(weapon_id)
            damage = values[0] if values else None
            if damage is not None and damage > 1:
                weapons.setdefault(weapon_id, {})['damage'] = damage
        if weapons:
            roster[unit_id] = weapons
    return roster


# Complete playable 3.3.6 weapon baselines extracted from RULESMO.INI.
ROSTER_WEAPON_STATS = build_roster_weapon_stats()

# Installed 3.3.6 capability snapshot. Do not offer a one-time enable reward
# when the TechnoType already has that capability. Explicit ``no`` values are
# intentionally absent because those units can still gain the capability.
EXISTING_SELF_HEALING_IDS = frozenset('''
AMEDIC TTNK AKULA DRED SQD MIND QUETZ RIOT SUPR TANY SIEG ARMR CMIN AMCV COMA
ABRM CHRTNK THOR VCARR BFRT CRYO DLPH HCRUIS CARRIER STORM ORCA BEAG FORTRESS
HBIRD DESO DESOR CHITZ VOLKOV MORALES YUNRU HARV SMCV RAVA WOLF MWF APOC SCHP
EMPR EDRN CNTR ZEP FOX DUST BRUTE YURI YURIPR SCRG STALKER LIBRA UNDER ASSN
YMIN PCV DISK SCAV DEVO RUINER BASIL GOTTER NAUT BSUB BLIGHT VENOM WASP BANE
SIBFIN SICALI EUREKA URAGAN NMIN FMCV BUZZ COND MEGA MAD VIPER HURR PROME
GHTNK BOID LEVI FAFILD FACONF
'''.split())
EXISTING_CLOAK_IDS = frozenset('''
AKULA SUB SQD DLPH STORM ORCA BEAG FORTRESS HBIRD FOX DUST UNDER YMIN SHADOW
QUAD SLED NAUT BSUB BLIGHT VENOM SHARK GACPIL GACRYO NATRAP YAVNMM FAFILD
FACONF FAMMIN
'''.split())
EXISTING_SENSOR_IDS = frozenset('''
SHK AKULA DRED SUB SQD GHOST TANY SIEG ROBO DEST DLPH SHOCK VOLKOV MORALES
YUNRU BOREK ARMA LIBRA UNDER ASSN STING SHADOW SLED NAUT BSUB HUNTR SIBFIN
SICALI EUREKA MSA SWORD SHARK NASCOM FAFILD FACONF
'''.split())
EXISTING_CAPABILITY_IDS = {
    'self_healing': EXISTING_SELF_HEALING_IDS,
    'cloak': EXISTING_CLOAK_IDS,
    'sensors': EXISTING_SENSOR_IDS,
}

# These types mount disguise, capture/defuse, scanner, or explicit
# ``NotAWeapon`` helpers. Their WeaponType fields are engine controls rather
# than attacks, so weapon-stat rewards are misleading or ineffective.
NONCOMBAT_WEAPON_TARGET_IDS = frozenset({
    'ENGINEER', 'SENGINEER', 'YENGINEER', 'FENGINEER',
    'SPY', 'SBTR', 'INTRUDER', 'HIJACKER',
    'MWF', 'MSA', 'SWPR', 'ORCIN',
})

# Installed 3.3.6 TechnoTypes with ``Trainable=no`` cannot use veterancy.
# Keep this separate from NONCOMBAT_WEAPON_TARGET_IDS: some support units have
# meaningful veteran behavior despite lacking an ordinary damaging weapon,
# while many combat/support types below are simply unable to train.
NONTRAINABLE_UNIT_IDS = frozenset('''
AMEDIC ENGINEER SPY SUPR CMIN AMCV SHAD CRYO HBIRD
SENGINEER SBTR ARSO DRON SMCV RAVA MWF FDRON EDRN DUST
YENGINEER KAOS INTRUDER HIJACKER REPU YMIN PCV DRIL COYO QUAD RUINER YHVR
FENGINEER SYNC CLAIR NMIN FMCV MSA RACC COON CONF DIVER MAD ORCIN BOID SEAT HARB
'''.split())

# Economy, base-operation, and mission-transport essentials are deliberately
# never access items. They remain available regardless of randomizer progress.
AMPHIBIOUS_TRANSPORT_UNIT_IDS = frozenset({'LCRF', 'SAPC', 'YHVR', 'SEAT'})
ENGINEER_UNIT_IDS = frozenset({
    'ENGINEER', 'SENGINEER', 'YENGINEER', 'FENGINEER',
})
ALWAYS_AVAILABLE_UNIT_IDS = {
    'AMCV', 'SMCV', 'PCV', 'FMCV',
    'CMIN', 'HARV', 'YMIN', 'NMIN',
    *ENGINEER_UNIT_IDS,
    *AMPHIBIOUS_TRANSPORT_UNIT_IDS,
}
ALWAYS_AVAILABLE_BUILDING_IDS = {
    'GACNST', 'NACNST', 'YACNST', 'FACNST',
    'GAPOWR', 'NAPOWR', 'YAPOWR', 'FATRAP',
    'GAREFN', 'NAREFN', 'YAREFN', 'FAREFN',
}
ALWAYS_AVAILABLE_TECH_IDS = ALWAYS_AVAILABLE_UNIT_IDS | ALWAYS_AVAILABLE_BUILDING_IDS

# Explicit cross-faction gameplay roles used only for single-campaign buff
# sharing. Unique units remain independent; they are never forced into a weak
# equivalence merely because their broad sidebar category matches.
UNIT_ROLE_EQUIVALENCE_GROUPS = tuple(
    frozenset(group)
    for group in _UNIT_DATA_CONFIG['unit_role_equivalence_groups']
)


def unit_role_equivalents(unit_id):
    unit_id = str(unit_id or '').upper()
    equivalents = {unit_id} if unit_id else set()
    for group in UNIT_ROLE_EQUIVALENCE_GROUPS:
        if unit_id in group:
            equivalents.update(group)
    return frozenset(equivalents)

FACTION_DEFENSE_ROSTERS = dict(_UNIT_DATA_CONFIG['faction_defense_rosters'])

# Tuple order: Cost, Strength, Sight, GuardRange.
DEFENSE_BASE_STATS = {
    unit_id: tuple(values)
    for unit_id, values in _UNIT_DATA_CONFIG['defense_base_stats'].items()
}

DEFENSE_WEAPON_STATS = dict(_UNIT_DATA_CONFIG['defense_weapon_stats'])

# RULESMO.INI explicitly marks these defenses Trainable=yes and gives them
# veteran/elite behavior.  Support structures and mine-style defenses without
# that flag must not receive a dead "Veteran start" reward.
TRAINABLE_DEFENSE_IDS = {
    'GAPILL', 'NASAM', 'GAGUN', 'GACPIL', 'ATESLA', 'GTGCAN', 'GAHYPE',
    'NALASR', 'NAFLAK', 'TESLA', 'NAHAMM',
    'YAGGUN', 'YARAIL', 'YAHADE', 'YAPSYT',
    'FASONI', 'FAGUAR', 'FARAIL', 'FACOMP', 'FAAVAL',
}


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

UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['unit_unlock_rewards']

EXTRA_UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['extra_unit_unlock_rewards']

FACTION_ACCESS_RULES = _REWARD_CATALOGUE_CONFIG['faction_access_rules']

NAVAL_UNIT_IDS = {
    'LCRF', 'DEST', 'AEGIS', 'DLPH', 'HCRUIS', 'CARRIER', 'SIREN',
    'SAPC', 'SUB', 'SWLF', 'REAP', 'DBOAT', 'DRED', 'AKULA',
    'YHVR', 'SLED', 'SQD', 'NAUT', 'BSUB',
    'SEAT', 'SWORD', 'SHARK', 'MANTA', 'LEVI',
}


def access_target_lookup():
    lookup = {}
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        for category, units in categories.items():
            for unit_id, label in units.items():
                lookup[unit_id] = (faction, category, label)
    return lookup


def reward_tech_ids(rewards):
    return {
        section.upper()
        for reward in rewards
        for section, values in reward.get('rules', {}).items()
        if any(key.lower() == 'techlevel' for key in values)
    }


def build_missing_roster_unlock_rewards(existing_rewards):
    existing_ids = reward_tech_ids(existing_rewards)
    rewards = []
    for unit_id, (faction, category, label) in access_target_lookup().items():
        if unit_id in ALWAYS_AVAILABLE_UNIT_IDS or unit_id in existing_ids:
            continue
        access = FACTION_ACCESS_RULES[faction]
        prerequisite = access['naval'] if unit_id in NAVAL_UNIT_IDS else access[category]
        rewards.append({
            'name': f'{label} Access',
            'description': f'Allows {label} production from the earliest matching faction facility.',
            'rules': build_unlock(unit_id, 1, prerequisite, access['houses']),
            'factions': [faction],
        })
    return rewards


def build_defense_unlock_rewards():
    rewards = []
    for faction, defenses in FACTION_DEFENSE_ROSTERS.items():
        access = FACTION_ACCESS_RULES[faction]
        for defense_id, label in defenses.items():
            rewards.append({
                'name': f'{label} Access',
                'description': f'Allows {label} construction from the faction Construction Yard.',
                'access_category': 'defense',
                'rules': build_unlock(defense_id, 1, access['defenses'], access['houses']),
                'factions': [faction],
            })
    return rewards


def normalize_roster_unlock_rules(rewards):
    lookup = access_target_lookup()
    for reward in rewards:
        for section, values in reward.get('rules', {}).items():
            unit_id = section.upper()
            target = lookup.get(unit_id)
            if not target or unit_id in ALWAYS_AVAILABLE_UNIT_IDS:
                continue
            faction, category, _ = target
            access = FACTION_ACCESS_RULES[faction]
            prerequisite = access['naval'] if unit_id in NAVAL_UNIT_IDS else access[category]
            values.update({
                'Owner': access['houses'],
                'RequiredHouses': access['houses'],
                'ForbiddenHouses': 'none',
                'PrerequisiteOverride': prerequisite,
            })


ROSTER_UNIT_UNLOCK_REWARDS = build_missing_roster_unlock_rewards(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS
)
DEFENSE_UNLOCK_REWARDS = build_defense_unlock_rewards()
normalize_roster_unlock_rules(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS + ROSTER_UNIT_UNLOCK_REWARDS
)

BUFF_TARGETS = dict(_UNIT_DATA_CONFIG['buff_targets'])


def default_plural(label):
    special = {
        'Infantry': 'Infantry',
        'Navy SEAL': 'Navy SEALs',
        'Stryker IFV': 'Stryker IFVs',
        'Archon AMC': 'Archon AMCs',
        'Allied MCV': 'Allied MCVs',
        'Soviet MCV': 'Soviet MCVs',
        'Epsilon MCV': 'Epsilon MCVs',
        'Foehn MCV': 'Foehn MCVs',
        'Stalin\'s Fist': 'Stalin\'s Fists',
    }
    return special.get(label, f'{label}s')


def add_complete_faction_buff_targets():
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        for category, units in categories.items():
            for unit_id, label in units.items():
                cost, speed, strength, sight, guard_range, ammo = UNIT_BASE_STATS[unit_id]
                target = BUFF_TARGETS.setdefault(unit_id, {})
                # Preserve any hand-authored weapon tables while replacing the
                # old placeholder labels/stats with the installed 3.3.6 data.
                target.update({
                    'label': label,
                    'plural': default_plural(label),
                    'category': category,
                    'factions': [faction],
                    'cost': cost,
                    'speed': speed,
                    'strength': strength,
                    'sight': sight,
                    'guard_range': guard_range,
                    'trainable': unit_id not in NONTRAINABLE_UNIT_IDS,
                })
                if ammo is not None:
                    target['ammo'] = ammo
                else:
                    target.pop('ammo', None)
                if unit_id in ROSTER_WEAPON_STATS:
                    target['weapons'] = ROSTER_WEAPON_STATS[unit_id]

    defense_buff_types = [
        'production', 'cost', 'armor', 'health', 'sight',
        'damage', 'reload', 'range',
        'self_healing', 'cloak', 'sensors', 'veteran',
    ]
    for faction, defenses in FACTION_DEFENSE_ROSTERS.items():
        for defense_id, label in defenses.items():
            cost, strength, sight, guard_range = DEFENSE_BASE_STATS[defense_id]
            target = {
                'label': label,
                'plural': default_plural(label),
                'category': 'defenses',
                'factions': [faction],
                'cost': cost,
                'strength': strength,
                'sight': sight,
                'guard_range': guard_range,
                'allowed_buff_types': defense_buff_types,
                'trainable': defense_id in TRAINABLE_DEFENSE_IDS,
            }
            if not target['trainable']:
                target['allowed_buff_types'] = [
                    buff_type for buff_type in defense_buff_types if buff_type != 'veteran'
                ]
            if defense_id in DEFENSE_WEAPON_STATS:
                target['weapons'] = DEFENSE_WEAPON_STATS[defense_id]
            BUFF_TARGETS[defense_id] = target


add_complete_faction_buff_targets()

# Installed Mental Omega 3.3.6 trainable hero/unique units whose positive
# BuildLimit is a live simultaneous-unit cap. Script-only mobile types and
# capped defenses are deliberately absent: changing those limits can break
# campaign teams, loss conditions, or base plans.
LIMITED_HERO_BUILD_LIMITS = dict(_UNIT_DATA_CONFIG['limited_hero_build_limits'])
LIMITED_HERO_UNIT_IDS = frozenset(LIMITED_HERO_BUILD_LIMITS)
for limited_unit_id, build_limit in LIMITED_HERO_BUILD_LIMITS.items():
    BUFF_TARGETS[limited_unit_id]['build_limit'] = build_limit

# Speed 10 proved unsafe for infantry pathfinding on campaign slopes, notably
# Malver in Singularity. Earned infantry movement buffs use direct TechnoType
# values capped at this conservative limit. Faster native infantry retain
# their authored speed but cannot be accelerated.
MAX_BUFFED_INFANTRY_SPEED = 8


def capped_infantry_speed(base_speed, count):
    """Return safe earned infantry speed without lowering faster native types."""
    base_speed = max(1, int(base_speed))
    ceiling = max(base_speed, MAX_BUFFED_INFANTRY_SPEED)
    return min(ceiling, max(1, int(round(base_speed * (1.10 ** count)))))

# Westwood-spawn missiles do not expose their real impact damage as a normal
# WeaponType. These General-section fields are the actual payload damage for
# the corresponding playable launchers.
SPECIAL_DAMAGE_FIELDS = dict(_UNIT_DATA_CONFIG['special_damage_fields'])
for special_unit_id, damage_fields in SPECIAL_DAMAGE_FIELDS.items():
    BUFF_TARGETS[special_unit_id]['special_damage_fields'] = damage_fields

UNIT_LABELS = dict(_UNIT_DATA_CONFIG['unit_labels'])

for faction_categories in FACTION_UNIT_ROSTERS.values():
    for roster_units in faction_categories.values():
        UNIT_LABELS.update(roster_units)
for faction_defenses in FACTION_DEFENSE_ROSTERS.values():
    UNIT_LABELS.update(faction_defenses)


def unit_display_label(unit_id):
    target = BUFF_TARGETS.get(unit_id)
    if target:
        return target.get('label', unit_id)
    return UNIT_LABELS.get((unit_id or '').upper(), unit_id)


ACCESS_REWARD_ALIASES = dict(_REWARD_CATALOGUE_CONFIG['access_reward_aliases'])


def normalize_access_reward_display_names():
    """Use the installed playable name for every single-unit access item."""
    access_rewards = (
        UNIT_UNLOCK_REWARDS
        + EXTRA_UNIT_UNLOCK_REWARDS
        + ROSTER_UNIT_UNLOCK_REWARDS
        + DEFENSE_UNLOCK_REWARDS
    )
    for reward in access_rewards:
        unlocked_ids = [
            section
            for section, values in reward.get('rules', {}).items()
            if any(key.lower() == 'techlevel' for key in values)
        ]
        if len(unlocked_ids) != 1:
            continue
        unit_id = unlocked_ids[0].upper()
        target = BUFF_TARGETS.get(unit_id)
        if not target:
            continue
        old_name = reward.get('name', '')
        new_name = f'{target["label"]} Access'
        if old_name and old_name != new_name:
            ACCESS_REWARD_ALIASES[old_name] = new_name
        reward['name'] = new_name
        reward['description'] = (
            f'Allows {target["plural"]} where the map tech tree permits them.'
        )


normalize_access_reward_display_names()


BUFF_TYPES = _REWARD_CATALOGUE_CONFIG['buff_types']


def build_buff_rewards():
    rewards = []
    for unit_id, target in BUFF_TARGETS.items():
        for buff_type in BUFF_TYPES:
            buff_type_id = buff_type['id']
            allowed_types = target.get('allowed_buff_types')
            if allowed_types and buff_type_id not in allowed_types:
                continue
            if unit_id in EXISTING_CAPABILITY_IDS.get(buff_type_id, ()):
                continue
            if buff_type_id == 'veteran' and not target.get('trainable', True):
                continue
            if (
                buff_type_id == 'speed'
                and target.get('category') == 'infantry'
                and int(target.get('speed', 0)) >= MAX_BUFFED_INFANTRY_SPEED
            ):
                # Already at the safe ceiling or authored faster. No no-op.
                continue
            if (
                unit_id in NONCOMBAT_WEAPON_TARGET_IDS
                and buff_type_id in {'damage', 'reload', 'range'}
            ):
                continue
            if buff_type.get('requires_stat') and buff_type.get('requires_stat') not in target:
                continue
            if buff_type.get('requires_weapons') and not target.get('weapons'):
                continue
            required_weapon_stat = buff_type.get('requires_weapon_stat')
            if required_weapon_stat:
                required_weapon_min = buff_type.get('requires_weapon_min', 0)
                has_weapon_stat = any(
                    stats.get(required_weapon_stat, 0) > required_weapon_min
                    for stats in target.get('weapons', {}).values()
                )
                has_special_damage = (
                    required_weapon_stat == 'damage'
                    and bool(target.get('special_damage_fields'))
                )
                if not has_weapon_stat and not has_special_damage:
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


# Keep the normal Allied storm independent from mission-local [General]
# settings. SFIRE reduces shared lightning values for its scripted Ion Storm.
LIGHTNING_STORM_MAP_RULES = _REWARD_CATALOGUE_CONFIG['lightning_storm_map_rules']

CHRONOSHIFT_MAP_RULES = _REWARD_CATALOGUE_CONFIG['chronoshift_map_rules']

CHRONOWARP_MAP_RULES = _REWARD_CATALOGUE_CONFIG['chronowarp_map_rules']


SUPERWEAPON_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['superweapon_unlock_rewards']

SECONDARY_SUPERWEAPON_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['secondary_superweapon_unlock_rewards']


BUILDING_FREE_SUPPORT_POWER_VALUES = _REWARD_CATALOGUE_CONFIG['building_free_support_power_values']


def building_free_support_values(**overrides):
    values = dict(BUILDING_FREE_SUPPORT_POWER_VALUES)
    values.update(overrides)
    return values


AID_POWER_MAP_CONFIGS = _REWARD_CATALOGUE_CONFIG['aid_power_map_configs']
for aid_config in AID_POWER_MAP_CONFIGS:
    for clone_group in ('techno_clones', 'auxiliary_clones'):
        for clone in aid_config.get(clone_group, {}).values():
            if 'reference_keys' in clone:
                clone['reference_keys'] = tuple(clone['reference_keys'])
AID_POWER_MAP_CONFIG_BY_SUPERWEAPON = {
    config['superweapon']: config
    for config in AID_POWER_MAP_CONFIGS
}


def build_aid_power_rewards():
    # Installed player-facing support powers plus useful mine/grid spawners.
    # Neutral tech powers, internal handlers, and powers whose effect requires
    # a separately owned source object remain excluded.
    definitions = [
        # Allies
        ('Airborne Power', 'Drops 6 G.I.s and 4 Guardian G.I.s at the selected area.', 'Allies', 'AmericanParaDropSpecial', 6),
        ('Bloodhounds Power', 'Drops 3 Airborne Humvees and 2 Stryker I.F.V.s at the selected area.', 'Allies', 'BloodhoundsSpecial', 26),
        ('Zephyrobot Power', 'Deploys a targeting beacon for Zephyr Artillery units you already own.', 'Allies', 'ZephyrBeaconSpecial', 34),
        ('Lightning Rod Power', 'Deploys a temporary Lightning Rod at the selected area.', 'Allies', 'LightningRodSpecial', 51),
        ('Ultra Miner Power', 'Deploys an Ultra Miner at the selected area.', 'Allies', 'WarpMinersSpecial', 61),
        ('Kingsnakes Power', 'Deploys a temporary Kingsnake defense portal at the selected area.', 'Allies', 'KingsnakesSpecial', 126),
        ('Paladin Aid Power', 'Deploys 2 Paladin Tank Hunters for the player.', 'Allies', 'PaladinAidSpecial', 128),
        ('Force Shield Power', 'Protects friendly units and structures in the selected area.', 'Allies', 'ForceShieldSpecial', 10),
        ('Target Painter Power', 'Marks enemies in the selected area for increased damage.', 'Allies', 'TargetPainterSpecial', 11),
        ('Sonar Pulse Power', 'Reveals submerged units in the selected water area.', 'Allies', 'SonarPulseSpecial', 12),
        ('Mercury Strike Power', 'Calls a Mercury orbital strike on the selected area.', 'Allies', 'MercurySpecial', 22),
        ('Satellite Scan Power', 'Reveals the selected map area.', 'Allies', 'SpySatSpecial', 24),
        ('Black Widow Alpha Power', 'Calls a Black Widow Alpha airstrike.', 'Allies', 'BlackWidowAlphaSpecial', 41),
        ('Black Widow Power', 'Calls a Black Widow airstrike.', 'Allies', 'BlackWidowSpecial', 50),
        ('Chronoboost Power', 'Boosts friendly units in the selected area.', 'Allies', 'ChronoboostSpecial', 78),
        ('Cryoshot Power', 'Freezes targets in the selected area.', 'Allies', 'CryoshotSpecial', 103),
        ('Cryospear Power', 'Calls an upgraded freezing strike on the selected area.', 'Allies', 'CryospearSpecial', 104),
        ('Glacial Screen Power', 'Protects friendly targets in the selected area with a glacial screen.', 'Allies', 'GlacialScreenSpecial', 127),
        ('Cryomine Field Power', 'Deploys 4 Cryomines at the selected area.', 'Allies', 'CryomineSpawn', 92),
        ('Chronolift Power', 'Relocates a friendly structure between selected locations.', 'Allies', 'ChronoliftSpecial', 64),
        # Soviets
        ('Repair Drone Power', 'Drops 1 Repair Drone at the selected area.', 'Soviets', 'RepairDroneSpecial', 13),
        ('Tank Drop Power', 'Drops the Russian Hydra Cannon and Tank Killer contingent at the selected area.', 'Soviets', 'TankDropSpecial', 16),
        ('Instant Shelter Power', 'Deploys a Battle Bunker with 2 Conscripts at the selected area.', 'Soviets', 'InstantShelterSpecial', 29),
        ('Motor Ambush Power', 'Deploys 3 Mortar Quads at the selected area.', 'Soviets', 'MotorAmbushSpecial', 32),
        ('Naval Mine Power', 'Deploys a Naval Mine at the selected water area.', 'Soviets', 'NavalMineSpecial', 60),
        ('V3 Test Drop Power', 'Drops 20 V3 Launchers using an isolated test power.', 'Soviets', 'MORV3TestSpecial', -1),
        ('Terror Drop Power', 'Drops 2 Terror Drones at the selected area.', 'Soviets', 'TerrorDropSpecial', 62),
        ('Flame Tower Power', 'Deploys a temporary Flame Tower at the selected area.', 'Soviets', 'FlameTowerSpecial', 68),
        ('Drakuv Prison Vehicle Power', 'Deploys a Drakuv Prison Vehicle for the player.', 'Soviets', 'DrakuvSpecial', 70),
        ('Repair Drones Power', 'Drops the upgraded Repair Drone contingent at the selected area.', 'Soviets', 'RepairDronesSpecial', 124),
        ('Disruptor Power', 'Deploys a Disruptor support unit for the player.', 'Soviets', 'DisruptorSpecial', 125),
        ('Spy Plane Power', 'Sends a reconnaissance aircraft over the selected area.', 'Soviets', 'SpyPlaneSpecial', 8),
        ('Smoke Bombs Power', 'Calls a smoke-bomb airstrike on the selected area.', 'Soviets', 'SmokebombsSpecial', 14),
        ('EM Pulse Power', 'Launches an electromagnetic pulse at the selected area.', 'Soviets', 'EMPulsSpecial', 19),
        ('Irradiation Gamma Power', 'Irradiates friendly targets in the selected area.', 'Soviets', 'IrradiateSpecial', 25),
        ('Overcharge Power', 'Overcharges friendly targets in the selected area.', 'Soviets', 'OverchargeSpecial', 42),
        ('Wallbuster Power', 'Calls a wall-busting strike on the selected area.', 'Soviets', 'WallbusterSpecial', 69),
        ('Irradiation Beta Power', 'Irradiates friendly targets in the selected area.', 'Soviets', 'IrradiateBetaSpecial', 120),
        ('Rad Attack Power', 'Calls a radiation airstrike on the selected area.', 'Soviets', 'RadAttackSpecial', 121),
        ('Pack Attack Power', 'Calls a larger radiation airstrike on the selected area.', 'Soviets', 'PackAttackSpecial', 122),
        ('EMP Minefield Power', 'Deploys 4 EMP Mines at the selected area.', 'Soviets', 'EMPMineSpawn', 59),
        # Epsilon
        ('Risen Monolith Power', 'Deploys a temporary Risen Monolith at the selected area.', 'Epsilon', 'RisenMonolithSpecial', 15),
        ('Scout Raven Power', 'Deploys a Scout Raven at the selected area.', 'Epsilon', 'RavenSpecial', 18),
        ('Vision Power', 'Deploys an Epsilon Vision scout at the selected area.', 'Epsilon', 'VisionSpecial', 21),
        ('Magnetic Beam Power', 'Deploys the Magnetic Beam support object at the selected area.', 'Epsilon', 'MagnetShiftSpecial', 30),
        ('Libra Clones Power', 'Drops 3 Libra Clones at the selected area.', 'Epsilon', 'LibraCloneSpecial', 33),
        ('Bloatick Trap Power', 'Deploys a Bloatick Trap at the selected area.', 'Epsilon', 'TickTrapSpecial', 36),
        ('Quick Fort Power', 'Deploys a temporarily strengthened Tank Bunker at the selected area.', 'Epsilon', 'QuickFortSpecial', 86),
        ('Ruiner Power', 'Deploys a Ruiner support unit for the player.', 'Epsilon', 'RuinerSpecial', 93),
        ('Hijackers Power', 'Drops 3 Hijackers at the selected area.', 'Epsilon', 'HijackersSpecial', 108),
        ('Shadow Ring Power', 'Cloaks friendly targets in the selected area.', 'Epsilon', 'IllusionSpecial', 31),
        ('Kinetic Barrier Power', 'Protects friendly targets in the selected area.', 'Epsilon', 'KineticBarrierSpecial', 37),
        ('Geneburst Power', 'Mutates targets in the selected area.', 'Epsilon', 'MutationSpecial', 38),
        ('Toxic Strike Power', 'Calls a toxic airstrike on the selected area.', 'Epsilon', 'ToxicStrikeSpecial', 44),
        ('Regen Drugs Power', 'Regenerates friendly infantry in the selected area.', 'Epsilon', 'RegenDrugsSpecial', 105),
        ('Wonder Drugs Power', 'Applies enhanced regeneration in the selected area.', 'Epsilon', 'WonderDrugsSpecial', 109),
        ('Genomine Field Power', 'Deploys 4 Genomines at the selected area.', 'Epsilon', 'GenomineSpawn', 84),
        # Foehn
        ('Spinblade Power', 'Deploys a Spinblade support structure at the selected area.', 'Foehn', 'SpinbladeSpecial', 39),
        ('Megaarena Power', 'Deploys a temporary Megaarena Projector at the selected area.', 'Foehn', 'MegaarenaSpecial', 52),
        ('Knightfall Power', 'Deploys a Knightfall reinforcement beacon at the selected area.', 'Foehn', 'KnightfallSpecial', 72),
        ('Harbinger Power', 'Calls a Harbinger strike aircraft over the selected area.', 'Foehn', 'HarbingerSpecial', 75),
        ('Sweeper Drop Power', 'Drops 2 Sweepers at the selected area.', 'Foehn', 'SweeperDropSpecial', 76),
        ('Signal Jammer Power', 'Deploys a temporary Signal Jammer at the selected area.', 'Foehn', 'SignalJammerSpecial', 77),
        ('Decoy Team Power', 'Deploys a holographic infantry decoy team at the selected area.', 'Foehn', 'DecoyTeamSpecial', 118),
        ('Decoy Squadron Power', 'Deploys a holographic aircraft decoy squadron at the selected area.', 'Foehn', 'DecoySquadronSpecial', 119),
        ('M.A.D. Mine Power', 'Deploys exactly 1 M.A.D. Mine at the selected area.', 'Foehn', 'MADMineSpecial', 133),
        ('Nanofiber Sync Power', 'Strengthens friendly targets in the selected area.', 'Foehn', 'NanofiberSyncSpecial', 40),
        ('Boid Blitz Power', 'Launches a Boid Blitz at the selected area.', 'Foehn', 'BoidBlitzSpecial', 46),
        ('Recon Sortie Power', 'Sends reconnaissance aircraft over the selected area.', 'Foehn', 'ReconSortieSpecial', 49),
        ('Devourer Power', 'Calls a Devourer strike on the selected area.', 'Foehn', 'DevourerSpecial', 74),
        ('Chaos Touch Power', 'Disorients enemies in the selected area.', 'Foehn', 'ChaosTouchSpecial', 106),
        ('Confusion Grid Power', 'Deploys a 3 by 3 Confusion Grid at the selected area.', 'Foehn', 'ConfusionGridSpawn', 57),
        ('Stasis Grid Power', 'Deploys a 3 by 3 Stasis Grid at the selected area.', 'Foehn', 'StasisGridSpawn', 63),
    ]
    rewards = []
    for name, description, faction, superweapon, index in definitions:
        modified_config = AID_POWER_MAP_CONFIG_BY_SUPERWEAPON.get(superweapon)
        if modified_config and modified_config.get('disabled'):
            continue
        reward = {
            'name': name,
            'description': description + ' Restored at the start of future missions without its normal source building.',
            'rules': {},
            'factions': [faction],
            'kind': 'superweapon',
            'power_category': 'aid',
            'superweapon': superweapon,
            'superweapon_index': index,
        }
        if modified_config and modified_config['values']:
            reward['superweapon_rules'] = dict(modified_config['values'])
        if modified_config and modified_config.get('sections'):
            reward['superweapon_rule_sections'] = {
                section: dict(values)
                for section, values in modified_config['sections'].items()
            }
        if modified_config and modified_config.get('techno_clones'):
            reward['superweapon_techno_clones'] = {
                section: {
                    key: dict(value) if key == 'values' else value
                    for key, value in clone.items()
                }
                for section, clone in modified_config['techno_clones'].items()
            }
        if modified_config and modified_config.get('auxiliary_clones'):
            reward['superweapon_auxiliary_clones'] = {
                section: {
                    key: dict(value) if key == 'values' else value
                    for key, value in clone.items()
                }
                for section, clone in modified_config['auxiliary_clones'].items()
            }
        if modified_config and modified_config.get('custom'):
            reward['superweapon_custom'] = True
        if modified_config and modified_config.get('clone'):
            reward['superweapon_clone'] = modified_config['clone']
        if modified_config and modified_config.get('cameo_superweapon'):
            reward['cameo_superweapon'] = modified_config['cameo_superweapon']
        rewards.append(reward)
    return rewards


AID_POWER_UNLOCK_REWARDS = build_aid_power_rewards()

REWARD_POOL = (
    UNIT_UNLOCK_REWARDS
    + EXTRA_UNIT_UNLOCK_REWARDS
    + ROSTER_UNIT_UNLOCK_REWARDS
    + DEFENSE_UNLOCK_REWARDS
    + SUPERWEAPON_UNLOCK_REWARDS
    + SECONDARY_SUPERWEAPON_UNLOCK_REWARDS
    + AID_POWER_UNLOCK_REWARDS
    + UNIT_BUFF_REWARDS
)
REWARD_BY_NAME = {reward.get('name'): reward for reward in REWARD_POOL if reward.get('name')}
REWARD_BY_BUFF_KEY = {
    (reward.get('unit'), reward.get('buff_type')): reward
    for reward in UNIT_BUFF_REWARDS
}
RETIRED_REWARD_BY_NAME = _REWARD_CATALOGUE_CONFIG['retired_reward_by_name']
REWARD_ALIASES = {
    **ACCESS_REWARD_ALIASES,
    'Medic Drill I': 'Field Medic Drill I',
    'Humvee Assembly I': 'Humvee Drill I',
    'IFV Assembly I': 'IFV Drill I',
    'Cryo Legionnaires': 'Chrono Legionnaire Access',
    'Chrono Legionnaires': 'Chrono Legionnaire Access',
    'Battle Fortress Access': 'Barracuda Access',
    'Mind Control Access': 'Mastermind Access',
    'Base Construction Drill I': 'Faction Production Drill I',
    'Mind Control Unit Targeting Package I': 'Mastermind Recon Package I',
}
for target in BUFF_TARGETS.values():
    # Existing seeds may contain the removed GuardRange reward. Convert it to
    # the same unit's useful vision reward instead of applying behavior that
    # can pull units out of position or leaving the old location reward empty.
    old_name = f'{target["label"]} Targeting Package I'
    replacement_name = f'{target["label"]} Recon Package I'
    if replacement_name in REWARD_BY_NAME:
        REWARD_ALIASES[old_name] = replacement_name
    # CountryType has no functional army-wide ROF multiplier in this engine.
    # Preserve old seeds by converting each former Rapid Fire item into the
    # same target's working cloned-weapon fire-rate reward.
    old_rof_name = f'{target["label"]} Rapid Fire I'
    replacement_rof_name = f'{target["label"]} Weapon Tuning I'
    if replacement_rof_name in REWARD_BY_NAME:
        REWARD_ALIASES[old_rof_name] = replacement_rof_name
for defense_id, target in BUFF_TARGETS.items():
    if target.get('category') == 'defenses' and not target.get('trainable'):
        REWARD_ALIASES[
            f'{target["label"]} Veteran Training I'
        ] = f'{target["label"]} Armor Plating I'
for unit_id in NONTRAINABLE_UNIT_IDS:
    target = BUFF_TARGETS.get(unit_id)
    if target:
        REWARD_ALIASES[
            f'{target["label"]} Veteran Training I'
        ] = f'{target["label"]} Armor Plating I'

for buff_type in BUFF_TYPES:
    REWARD_ALIASES[f'Mind Control Unit {buff_type["name"]} I'] = f'Mastermind {buff_type["name"]} I'


def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}

    reward_name = reward.get('name')
    if not reward_name:
        return reward
    reward_name = REWARD_ALIASES.get(reward_name, reward_name)

    if reward_name in RETIRED_REWARD_BY_NAME:
        return RETIRED_REWARD_BY_NAME[reward_name]
    current_reward = REWARD_BY_NAME.get(reward_name)
    if current_reward:
        return current_reward
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        if (
            reward.get('buff_type') == 'veteran'
            and str(reward.get('unit') or '').upper() in NONTRAINABLE_UNIT_IDS
        ):
            replacement = REWARD_BY_BUFF_KEY.get(
                (str(reward.get('unit') or '').upper(), 'armor')
            )
            if replacement:
                return replacement
        active_reward = REWARD_BY_BUFF_KEY.get(
            (reward.get('unit'), reward.get('buff_type'))
        )
        if active_reward:
            return active_reward
        return {
            'name': f'{reward_name} (retired: redundant or inapplicable)',
            'description': (
                'Disabled because the installed unit already has this capability '
                'or has no compatible combat weapon.'
            ),
            'rules': {},
            'factions': list(reward.get('factions') or []),
            'kind': 'retired',
            'retired_reward': True,
        }
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

HOUSE_SCOPED_BUFF_TYPES = {'production', 'cost', 'speed', 'armor', 'veteran'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload'}
UNIT_STAT_BUFF_TYPES = {'health', 'sight', 'ammo', 'self_healing', 'cloak', 'sensors'}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = MAP_GUARDED_BUFF_TYPES | {'build_limit'}
MAX_VETERANCY_STACKS = 1


def reward_display_name(reward):
    reward = canonical_reward(reward)
    name = reward.get('name', 'Unknown reward')
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        effect_lines = buff_effect_lines(reward, include_stack=False)
        if effect_lines:
            return effect_lines[0]
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
    if reward.get('buff_type') == 'speed':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        if target.get('category') == 'infantry':
            base_speed = max(1, int(target.get('speed', 1)))
            if base_speed >= MAX_BUFFED_INFANTRY_SPEED:
                return 1
            for stacks in range(1, 33):
                if capped_infantry_speed(base_speed, stacks) >= MAX_BUFFED_INFANTRY_SPEED:
                    return stacks
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


def buff_effect_lines(reward, count=1, include_label=True, include_stack=True):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)

    def stacked(text):
        if not include_stack:
            return text
        return f'{text} ({stack_label(count)})'

    if buff_type == 'production':
        multiplier = max(0.35, 0.85 ** count)
        shorter = int(round((1.0 - multiplier) * 100))
        effect = (
            'Construction time'
            if target.get('category') in {'buildings', 'defenses'}
            else 'Production time'
        )
        return [stacked(f'{prefix}{effect} {shorter}% shorter')]
    if buff_type == 'cost':
        multiplier = max(0.30, 0.80 ** count)
        cheaper = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Cost {cheaper}% cheaper')]
    if buff_type == 'speed':
        if target.get('category') == 'infantry':
            base_speed = int(target.get('speed', 1))
            speed = capped_infantry_speed(base_speed, count)
            return [stacked(
                f'{prefix}Speed {base_speed} -> {speed} '
                f'(safe infantry ceiling {MAX_BUFFED_INFANTRY_SPEED})'
            )]
        multiplier = min(1.75, 1.10 ** count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        multiplier = max(0.50, 0.90 ** count)
        tougher = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Armor {tougher}% stronger')]
    if buff_type == 'health':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Health {stronger}% higher')]
    if buff_type == 'sight':
        increase = min(4, count)
        return [stacked(f'{prefix}Vision +{increase}')]
    if buff_type == 'veteran':
        return [stacked(f'{prefix}Veteran start')]
    if buff_type == 'build_limit':
        base_limit = int(target.get('build_limit', 1))
        return [stacked(f'{prefix}Simultaneous unit limit {base_limit} -> {base_limit + count}')]
    if buff_type == 'damage':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Damage {stronger}% higher')]
    if buff_type == 'reload':
        multiplier = max(0.45, 0.90 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Fire rate {faster}% faster')]
    if buff_type == 'range':
        increase = min(3.0, 0.5 * count)
        if increase.is_integer():
            increase_text = str(int(increase))
        else:
            increase_text = f'{increase:.1f}'
        return [stacked(f'{prefix}Range +{increase_text}')]
    if buff_type == 'ammo':
        increase = min(5, count)
        base_ammo = int(target.get('ammo', 0))
        total_ammo = base_ammo + increase
        if reward.get('unit') == 'ABRM':
            return [stacked(f'{prefix}Main-cannon ammo {base_ammo} -> {total_ammo}')]
        return [stacked(f'{prefix}Ammo {base_ammo} -> {total_ammo}')]
    if buff_type == 'self_healing':
        return [stacked(f'{prefix}Self-healing enabled')]
    if buff_type == 'cloak':
        return [stacked(f'{prefix}Cloaking enabled')]
    if buff_type == 'sensors':
        sensor_range = int(round(target.get('sight', 5) + 2))
        sensor_text = f'{prefix}Sensors enabled ({sensor_range}-cell range)'
        if include_stack:
            sensor_text = (
                f'{prefix}Sensors enabled ({sensor_range}-cell range; '
                f'{stack_label(count)})'
            )
        return [sensor_text]
    return []


def reward_rule_summary(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        return buff_effect_lines(reward)
    if reward.get('kind') == 'superweapon':
        return ['Building-free repeating power; restored at the start of future missions.']

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
