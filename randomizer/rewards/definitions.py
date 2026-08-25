"""Reward catalogue and display helpers for the Mental Omega randomizer."""

from randomizer.rewards.weapon_stats import (
    ROSTER_DAMAGE_WEAPON_REFS,
    ROSTER_WEAPON_REFS,
    WEAPON_BASE_STATS,
)
from randomizer.config.static import load_static_config
from randomizer.config.tuning import (
    BUFF_EFFECTS,
    REWARD_PLANNING,
)
from randomizer.rewards.power_buff_definitions import (
    build_power_buff_rewards,
)
from randomizer.rewards.enemy_scaling import build_enemy_reward_pool
from randomizer.rewards.roster import (
    randomizer_unit_ids_with_behavior,
    randomizer_unit_template_values,
)


_UNIT_DATA_CONFIG = load_static_config('rewards/unit_data.json')
_REWARD_CATALOGUE_CONFIG = load_static_config('rewards/catalogue.json')
_FACTION_CONFIG = load_static_config('factions.json')
_UNIT_POLICY_CONFIG = load_static_config('rewards/unit_policy.json')
_BUFF_EXCEPTION_CONFIG = load_static_config('rewards/buff_exceptions.json')
_SPECIAL_BUILDING_CONFIG = load_static_config('rewards/special_buildings.json')
SPECIAL_BUILDING_DEFINITIONS = tuple(
    dict(definition) for definition in _SPECIAL_BUILDING_CONFIG['buildings']
)

# This module is intentionally data-heavy. Keeping it separate from the Tk
# launcher makes future Archipelago item/location work much easier.

DEFAULT_UNLOCK_BUILD_HOUSES = _FACTION_CONFIG['default_unlock_build_houses']
DEFAULT_REWARDS_PER_CHECK = int(REWARD_PLANNING['default_rewards_per_check'])
MAX_REWARDS_PER_CHECK = int(REWARD_PLANNING['maximum_rewards_per_check'])

# Delivery payloads owned exclusively through aid powers. Keep this mandatory
# in code so preserved editable packaged rosters cannot restore production
# access, unit buffs, Advanced options, or Unlocks cards. Drakuv/RAVA is also a
# normal Soviet production reward; its aid power resolves to that same clone.
AID_ONLY_UNIT_IDS = frozenset({'RUINER', 'HARB'})

# Complete playable 3.3.6 faction rosters.  These use the real rulesmo.ini
# section IDs, which frequently differ from the public-facing unit names.
# Keep economy, construction, support and hero units here too: a buffs-only
# seed must be able to improve every player-owned faction unit, not merely the
# small subset that also has an access reward.
FACTION_UNIT_ROSTERS = {
    faction: {
        category: {
            str(unit_id).upper(): label
            for unit_id, label in units.items()
            if str(unit_id).upper() not in AID_ONLY_UNIT_IDS
        }
        for category, units in categories.items()
    }
    for faction, categories in _UNIT_DATA_CONFIG['faction_unit_rosters'].items()
}
# Mandatory 3.3.6 ownership correction. Preserve it even when an older
# portable/external roster catalogue still classifies SHINBOT as Epsilon.
for faction_categories in FACTION_UNIT_ROSTERS.values():
    for roster_units in faction_categories.values():
        roster_units.pop('SHINBOT', None)
FACTION_UNIT_ROSTERS['Allies']['units']['SHINBOT'] = 'Shin Tsurugi Decimator'
SPECIAL_REWARD_UNIT_IDS = frozenset(
    str(unit_id).upper()
    for unit_id in _UNIT_DATA_CONFIG.get('special_reward_unit_ids', ())
)
UNIT_SIDEBAR_IMAGES = {
    str(unit_id).upper(): dict(config)
    for unit_id, config in _UNIT_DATA_CONFIG['unit_sidebar_images'].items()
}
STANDALONE_WEAPON_TEMPLATES = {
    str(weapon_id).upper(): dict(values)
    for weapon_id, values in _UNIT_DATA_CONFIG.get(
        'standalone_weapon_templates', {}
    ).items()
}
STANDALONE_UNIT_RULE_TEMPLATES = {
    str(unit_id).upper(): {
        str(list_name): {
            str(section_id): dict(values)
            for section_id, values in templates.items()
        }
        for list_name, templates in lists.items()
    }
    for unit_id, lists in _UNIT_DATA_CONFIG.get(
        'standalone_unit_rule_templates', {}
    ).items()
}
for unit_rules in STANDALONE_UNIT_RULE_TEMPLATES.values():
    for weapon_id, values in unit_rules.get('WeaponTypes', {}).items():
        STANDALONE_WEAPON_TEMPLATES.setdefault(
            weapon_id.upper(), dict(values)
        )

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
EXISTING_SELF_HEALING_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['self_healing']
)
EXISTING_CLOAK_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['cloak']
)
EXISTING_SENSOR_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['sensors']
)
TRANSPORT_BASE_STATS = {
    str(unit_id).upper(): dict(stats)
    for unit_id, stats in _UNIT_DATA_CONFIG.get(
        'transport_base_stats', {}
    ).items()
}
EXISTING_OPEN_TOPPED_IDS = frozenset(
    unit_id
    for unit_id, stats in TRANSPORT_BASE_STATS.items()
    if stats['open_topped']
)
TRANSPORT_GUNNER_IDS = frozenset(
    TRANSPORT_BASE_STATS
).intersection(
    randomizer_unit_ids_with_behavior('Gunner', 'yes')
)
TRANSPORT_OPEN_TOPPED_BLOCKED_IDS = frozenset(
    unit_id
    for unit_id, stats in TRANSPORT_BASE_STATS.items()
    if stats.get('open_topped_blocked', False)
) | frozenset({'SHAD'})
EXISTING_CAPABILITY_IDS = {
    'self_healing': EXISTING_SELF_HEALING_IDS,
    'cloak': EXISTING_CLOAK_IDS,
    'sensors': EXISTING_SENSOR_IDS,
    'open_topped': EXISTING_OPEN_TOPPED_IDS,
}

# Reviewed gameplay exclusions for buffs that are technically constructible
# but redundant, misleading, or ineffective for a specific TechnoType. Keep
# this policy editable beside the installed capability snapshot.
EXCLUDED_BUFF_TYPE_IDS = {
    buff_type: frozenset(str(unit_id).upper() for unit_id in unit_ids)
    for buff_type, unit_ids in _BUFF_EXCEPTION_CONFIG['excluded_buff_type_ids'].items()
}
SUICIDE_RANGE_EXCLUDED_UNIT_IDS = frozenset({
    'BGGY', 'BIKE', 'DBOAT', 'DTRUCK', 'OTRK', 'TERROR',
})
# Engine-safety exclusions cannot depend on replacing editable packaged config
# during an upgrade. Old RandomizerLauncherData copies remain user-owned.
MANDATORY_EXCLUDED_BUFF_TYPE_IDS = {
    'cloak': frozenset({'NAIRDM'}),
    # Suicide weapons detonate at their firing point. Extra range makes these
    # units self-destruct before reaching the target, wasting the attack.
    # Keep this mandatory so retry assistance and externally supplied legacy
    # rewards cannot bypass the editable catalogue exclusion.
    'range': SUICIDE_RANGE_EXCLUDED_UNIT_IDS,
    # Gunner=yes transports use their sole passenger as an IFV weapon/driver,
    # not as ordinary cargo. More seats or OpenTopped mixes incompatible
    # passenger logics, so both rewards are absent from every selection path.
    # Salamander and Super Thor fill every authored seat with invisible
    # passengers that are weapon systems. Capacity stacks would expose empty
    # cargo slots and alter their fixed weapon payload contract.
    'passenger_capacity': (
        TRANSPORT_GUNNER_IDS | frozenset({'CHRP', 'SALA', 'STHOR'})
    ),
    # Stallion is weaponless and explicitly cannot passively acquire targets;
    # live verification found that its passengers therefore never fire.
    'open_topped': (
        TRANSPORT_GUNNER_IDS
        | TRANSPORT_OPEN_TOPPED_BLOCKED_IDS
        | frozenset({'CHRP'})
    ),
}

# These types mount disguise, capture/defuse, scanner, or explicit
# ``NotAWeapon`` helpers. Their WeaponType fields are engine controls rather
# than attacks, so weapon-stat rewards are misleading or ineffective.
NONCOMBAT_WEAPON_TARGET_IDS = frozenset(
    _UNIT_POLICY_CONFIG['noncombat_weapon_target_ids']
)

# Installed 3.3.6 TechnoTypes with ``Trainable=no`` cannot use veterancy.
# Keep this separate from NONCOMBAT_WEAPON_TARGET_IDS: some support units have
# meaningful veteran behavior despite lacking an ordinary damaging weapon,
# while many combat/support types below are simply unable to train.
NONTRAINABLE_UNIT_IDS = frozenset(_UNIT_POLICY_CONFIG['nontrainable_unit_ids'])

# Engineers and amphibious transports are base-operation/mission essentials.
# They never become progression access rewards and remain available regardless
# of randomizer progress.
AMPHIBIOUS_TRANSPORT_UNIT_IDS = frozenset(
    values[0] for values in _FACTION_CONFIG['amphibious_transports'].values()
)
ENGINEER_UNIT_IDS = frozenset(_FACTION_CONFIG['engineer_by_family'].values())
# Engineer "weapons" are engine controls for repair/capture/vehicle entry.
# Old saves and externally supplied stacks must never clone or tune them.
for _buff_type in ('damage', 'reload', 'range'):
    MANDATORY_EXCLUDED_BUFF_TYPE_IDS[_buff_type] = (
        MANDATORY_EXCLUDED_BUFF_TYPE_IDS.get(_buff_type, frozenset())
        | ENGINEER_UNIT_IDS
    )
ALWAYS_AVAILABLE_UNIT_IDS = set(
    _UNIT_POLICY_CONFIG['always_available_core_unit_ids']
) | set(ENGINEER_UNIT_IDS) | set(AMPHIBIOUS_TRANSPORT_UNIT_IDS)
ALWAYS_AVAILABLE_BUILDING_IDS = set(
    _UNIT_POLICY_CONFIG['always_available_building_ids']
)
ALWAYS_AVAILABLE_TECH_IDS = ALWAYS_AVAILABLE_UNIT_IDS | ALWAYS_AVAILABLE_BUILDING_IDS

# Explicit cross-faction gameplay roles used for compatible single-campaign
# translation and optional Chaos / All Campaigns buff sharing. Unique units
# remain independent; they are never forced into a weak equivalence merely
# because their broad sidebar category matches.
UNIT_ROLE_EQUIVALENCE_GROUPS = tuple(
    frozenset(group)
    for group in _UNIT_DATA_CONFIG['unit_role_equivalence_groups']
)
_UNIT_ROLE_EQUIVALENTS_BY_ID = {}
for _equivalence_group in UNIT_ROLE_EQUIVALENCE_GROUPS:
    for _equivalent_unit_id in _equivalence_group:
        _UNIT_ROLE_EQUIVALENTS_BY_ID.setdefault(
            _equivalent_unit_id, set()
        ).update(_equivalence_group)
_UNIT_ROLE_EQUIVALENTS_BY_ID = {
    unit_id: frozenset(equivalents)
    for unit_id, equivalents in _UNIT_ROLE_EQUIVALENTS_BY_ID.items()
}


def unit_role_equivalents(unit_id):
    unit_id = str(unit_id or '').upper()
    if not unit_id:
        return frozenset()
    return _UNIT_ROLE_EQUIVALENTS_BY_ID.get(
        unit_id, frozenset((unit_id,))
    )

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
TRAINABLE_DEFENSE_IDS = set(_UNIT_POLICY_CONFIG['trainable_defense_ids'])


def build_unlock(
    section,
    tech_level,
    prerequisite=None,
    houses=DEFAULT_UNLOCK_BUILD_HOUSES,
):
    values = {
        'TechLevel': str(tech_level),
        'Owner': houses,
        'RequiredHouses': houses,
        'ForbiddenHouses': 'none',
    }
    prerequisites = (
        [prerequisite]
        if isinstance(prerequisite, str)
        else list(prerequisite or ())
    )
    prerequisites = list(dict.fromkeys(
        str(item).upper() for item in prerequisites if str(item).strip()
    ))
    if len(prerequisites) == 1:
        values.update({
            'Prerequisite': prerequisites[0],
            'PrerequisiteOverride': None,
            'Prerequisite.List0': None,
            'Prerequisite.Lists': None,
        })
    elif prerequisites:
        values['Prerequisite'] = prerequisites[0]
        values['PrerequisiteOverride'] = None
        values['Prerequisite.List0'] = None
        values['Prerequisite.Lists'] = str(len(prerequisites) - 1)
        for index, building_id in enumerate(prerequisites[1:], start=1):
            values[f'Prerequisite.List{index}'] = building_id
    return {section: values}

UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['unit_unlock_rewards']

EXTRA_UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['extra_unit_unlock_rewards']

FACTION_ACCESS_RULES = _REWARD_CATALOGUE_CONFIG['faction_access_rules']

NAVAL_UNIT_IDS = set(_UNIT_POLICY_CONFIG['naval_unit_ids'])
ADDITIONAL_PRODUCTION_PREREQUISITES = {
    str(unit_id).upper(): tuple(str(value).upper() for value in values)
    for unit_id, values in _UNIT_POLICY_CONFIG[
        'additional_production_prerequisites'
    ].items()
}
LINKED_ACCESS_VARIANTS = {
    str(unit_id).upper(): {
        str(variant_id).upper(): str(prerequisite).upper()
        for variant_id, prerequisite in variants.items()
    }
    for unit_id, variants in _UNIT_POLICY_CONFIG['linked_access_variants'].items()
}
LINKED_BUFF_VARIANTS = {
    str(unit_id).upper(): {
        str(variant_id).upper(): dict(definition)
        for variant_id, definition in variants.items()
    }
    for unit_id, variants in _UNIT_DATA_CONFIG['linked_buff_variants'].items()
}


def linked_buff_variant_ids(unit_id):
    """Return one gameplay identity and its land/water presentation variants."""
    unit_id = str(unit_id or '').upper()
    if not unit_id:
        return frozenset()
    identities = {unit_id}
    identities.update(LINKED_BUFF_VARIANTS.get(unit_id, {}))
    for source_id, variants in LINKED_BUFF_VARIANTS.items():
        if unit_id in variants:
            identities.add(source_id)
            identities.update(variants)
    return frozenset(identities)


def unit_production_prerequisites(unit_id, primary):
    return tuple(dict.fromkeys((
        str(primary).upper(),
        *ADDITIONAL_PRODUCTION_PREREQUISITES.get(str(unit_id).upper(), ()),
    )))


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
        rules = build_unlock(
            unit_id,
            1,
            unit_production_prerequisites(unit_id, prerequisite),
            access['houses'],
        )
        for variant_id, variant_prerequisite in LINKED_ACCESS_VARIANTS.get(
            unit_id, {}
        ).items():
            rules.update(build_unlock(
                variant_id,
                1,
                variant_prerequisite,
                access['houses'],
            ))
        rewards.append({
            'name': f'{label} Access',
            'description': f'Allows {label} production from the earliest matching faction facility.',
            'access_category': (
                'special' if unit_id in SPECIAL_REWARD_UNIT_IDS else category
            ),
            'special_reward': unit_id in SPECIAL_REWARD_UNIT_IDS,
            'rules': rules,
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
                'access_category': (
                    'special' if defense_id in SPECIAL_REWARD_UNIT_IDS else 'defense'
                ),
                'special_reward': defense_id in SPECIAL_REWARD_UNIT_IDS,
                'rules': build_unlock(defense_id, 1, access['defenses'], access['houses']),
                'factions': [faction],
            })
    return rewards


def build_special_building_unlock_rewards():
    rewards = []
    for definition in SPECIAL_BUILDING_DEFINITIONS:
        building_id = str(definition['id']).upper()
        faction = str(definition['faction'])
        label = str(definition['name'])
        access = FACTION_ACCESS_RULES[faction]
        rules = build_unlock(
            building_id,
            definition.get('tech_level', 1),
            str(definition['prerequisite']).upper(),
            access['houses'],
        )
        build_limit = definition.get('build_limit')
        if build_limit is not None:
            rules[building_id]['BuildLimit'] = str(build_limit)
        if definition.get('build_category'):
            rules[building_id]['BuildCat'] = str(definition['build_category'])
        if definition.get('cameo_priority') is not None:
            rules[building_id]['CameoPriority'] = str(definition['cameo_priority'])
        rewards.append({
            'name': f'{label} Access',
            'description': (
                f'Allows construction of the {label} directly from the '
                'faction Construction Yard, without its normal tech structure.'
            ),
            'access_category': 'special_building',
            'special_reward': bool(definition.get('special_reward')),
            'rules': rules,
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
            normalized = build_unlock(
                unit_id,
                values.get('TechLevel', values.get('techlevel', 1)),
                unit_production_prerequisites(unit_id, prerequisite),
                access['houses'],
            )[unit_id]
            for key in list(values):
                if key.lower().startswith('prerequisite'):
                    values.pop(key)
            values.update({
                'Owner': access['houses'],
                'RequiredHouses': access['houses'],
                'ForbiddenHouses': 'none',
            })
            values.update({
                key: value
                for key, value in normalized.items()
                if key.lower().startswith('prerequisite')
            })


ROSTER_UNIT_UNLOCK_REWARDS = build_missing_roster_unlock_rewards(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS
)
DEFENSE_UNLOCK_REWARDS = build_defense_unlock_rewards()
SPECIAL_BUILDING_UNLOCK_REWARDS = build_special_building_unlock_rewards()
normalize_roster_unlock_rules(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS + ROSTER_UNIT_UNLOCK_REWARDS
)

BUFF_TARGETS = {
    str(unit_id).upper(): dict(target)
    for unit_id, target in _UNIT_DATA_CONFIG['buff_targets'].items()
    if str(unit_id).upper() not in AID_ONLY_UNIT_IDS
}


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
        'Cloning Vats': 'Cloning Vats',
        'Soviet Cloning Vats': 'Soviet Cloning Vats',
        'Hands of Ereshkigal': 'Hands of Ereshkigal',
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
                    'special_reward': unit_id in SPECIAL_REWARD_UNIT_IDS,
                })
                if ammo is not None:
                    target['ammo'] = ammo
                else:
                    target.pop('ammo', None)
                if unit_id in ROSTER_WEAPON_STATS:
                    target['weapons'] = ROSTER_WEAPON_STATS[unit_id]
                transport_stats = TRANSPORT_BASE_STATS.get(unit_id)
                if transport_stats:
                    target['passengers'] = int(transport_stats['passengers'])

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
                'special_reward': defense_id in SPECIAL_REWARD_UNIT_IDS,
            }
            if not target['trainable']:
                target['allowed_buff_types'] = [
                    buff_type for buff_type in defense_buff_types if buff_type != 'veteran'
                ]
            if defense_id in DEFENSE_WEAPON_STATS:
                target['weapons'] = DEFENSE_WEAPON_STATS[defense_id]
            BUFF_TARGETS[defense_id] = target


add_complete_faction_buff_targets()

# Spawned missile AircraftTypes can have a shorter pursuit envelope than an
# upgraded launcher. Keep this optional for compatibility with older editable
# unit-data overrides; configured entries extend only the reviewed launchers.
for unit_id, support in _UNIT_DATA_CONFIG.get(
    'spawned_missile_range_support', {}
).items():
    BUFF_TARGETS[str(unit_id).upper()][
        'spawned_missile_range_support'
    ] = dict(support)

# Normal miners expose clone-local vanilla Storage. Harvest speed remains a
# global rules setting in the installed engine, so only capacity is eligible.
_RANDOMIZER_TEMPLATE_VALUES = randomizer_unit_template_values()
for harvester_id in randomizer_unit_ids_with_behavior('Harvester', 'yes'):
    target = BUFF_TARGETS.get(harvester_id)
    template = _RANDOMIZER_TEMPLATE_VALUES.get(harvester_id, {})
    storage = next((
        value for key, value in template.items()
        if str(key).lower() == 'storage'
    ), None)
    try:
        storage = int(float(str(storage).strip()))
    except (TypeError, ValueError):
        continue
    if target is not None and storage > 0:
        target['storage'] = storage
        target['allowed_buff_types'] = ['storage']

# Engineers are always-accessible base essentials. Cloaking is their only
# reward-pool buff for now; direct player clones keep it off enemy Engineers.
for engineer_id in ENGINEER_UNIT_IDS:
    BUFF_TARGETS[engineer_id]['allowed_buff_types'] = ['cloak']

# Installed Mental Omega 3.3.6 trainable hero/unique units whose positive
# BuildLimit is a live simultaneous-unit cap. Script-only mobile types and
# capped defenses are deliberately absent: changing those limits can break
# campaign teams, loss conditions, or base plans.
LIMITED_HERO_BUILD_LIMITS = dict(_UNIT_DATA_CONFIG['limited_hero_build_limits'])
LIMITED_HERO_UNIT_IDS = frozenset(LIMITED_HERO_BUILD_LIMITS)
for limited_unit_id, build_limit in LIMITED_HERO_BUILD_LIMITS.items():
    BUFF_TARGETS[limited_unit_id]['build_limit'] = build_limit

for definition in SPECIAL_BUILDING_DEFINITIONS:
    if not definition.get('capacity_rewards'):
        continue
    building_id = str(definition['id']).upper()
    label = str(definition['name'])
    target = {
        'label': label,
        'plural': default_plural(label),
        'category': 'special_buildings',
        'factions': [str(definition['faction'])],
        'build_limit': int(definition.get('build_limit', 1)),
        'building_limit': int(definition.get('build_limit', 1)),
        'capacity_stack_limit': int(definition.get('capacity_stack_limit', 4)),
        'build_category': str(definition.get('build_category', 'Tech')),
        'cameo_priority': int(definition.get('cameo_priority', -1000)),
        'allowed_buff_types': ['building_limit'],
        'trainable': False,
        'special_reward': bool(definition.get('special_reward')),
    }
    template = _RANDOMIZER_TEMPLATE_VALUES.get(building_id, {})
    cash_amount = next((
        value for key, value in template.items()
        if str(key).lower() == 'producecashamount'
    ), None)
    cash_delay = next((
        value for key, value in template.items()
        if str(key).lower() == 'producecashdelay'
    ), None)
    try:
        cash_amount = int(float(str(cash_amount).strip()))
        cash_delay = int(float(str(cash_delay).strip()))
    except (TypeError, ValueError):
        cash_amount = cash_delay = 0
    if cash_amount > 0 and cash_delay > 0:
        target['produce_cash_amount'] = cash_amount
        target['produce_cash_delay'] = cash_delay
        target['allowed_buff_types'].append('income')
    BUFF_TARGETS[building_id] = target

# High movement values break campaign pathfinding, formation spacing, landing,
# and MCV deployment. Every mobile category therefore uses a direct
# TechnoType Speed value with a reviewed ceiling. Faster authored identities
# retain their original speed but cannot be accelerated.
MOVEMENT_SPEED_SAFE_CEILINGS = {
    str(category): int(value)
    for category, value in BUFF_EFFECTS[
        'movement_speed'
    ]['safe_ceilings'].items()
}
MAX_BUFFED_INFANTRY_SPEED = MOVEMENT_SPEED_SAFE_CEILINGS['infantry']


def movement_speed_ceiling(target):
    """Return reviewed earned-speed ceiling for one mobile reward target."""
    if isinstance(target, dict):
        category = target.get('category')
    else:
        category = target
    return MOVEMENT_SPEED_SAFE_CEILINGS.get(str(category or ''))


def capped_movement_speed(target, count):
    """Return safe earned movement speed without lowering authored speed."""
    base_speed = max(1, int(round(float(target.get('speed', 1)))))
    safe_ceiling = movement_speed_ceiling(target)
    if safe_ceiling is None:
        return base_speed
    ceiling = max(base_speed, safe_ceiling)
    factor = float(BUFF_EFFECTS['speed']['factor_per_stack'])
    return min(
        ceiling,
        max(
            base_speed,
            base_speed + max(0, int(count)),
            int(round(base_speed * (factor ** max(0, int(count))))),
        ),
    )


def capped_infantry_speed(base_speed, count):
    """Backward-compatible infantry-only wrapper."""
    return capped_movement_speed(
        {'category': 'infantry', 'speed': base_speed},
        count,
    )

# Westwood-spawn missiles do not expose their real impact damage as a normal
# WeaponType. These General-section fields are the actual payload damage for
# the corresponding playable launchers.
SPECIAL_DAMAGE_FIELDS = dict(_UNIT_DATA_CONFIG['special_damage_fields'])
for special_unit_id, damage_fields in SPECIAL_DAMAGE_FIELDS.items():
    BUFF_TARGETS[special_unit_id]['special_damage_fields'] = damage_fields

UNIT_LABELS = dict(_UNIT_DATA_CONFIG['unit_labels'])
UNIT_LABELS.update({
    str(definition['id']).upper(): str(definition['name'])
    for definition in SPECIAL_BUILDING_DEFINITIONS
})

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
        + SPECIAL_BUILDING_UNLOCK_REWARDS
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
GLOBAL_BUFF_REWARDS = _REWARD_CATALOGUE_CONFIG['global_buff_rewards']


def build_buff_rewards():
    rewards = []
    for unit_id, target in BUFF_TARGETS.items():
        # Runtime-only payload targets consume another unit's earned buffs.
        # They need clone metadata, not separately rollable reward cards.
        if target.get('inherits_equivalent_payload_buffs'):
            continue
        for buff_type in BUFF_TYPES:
            buff_type_id = buff_type['id']
            broad_exclusions = (
                frozenset()
                if buff_type_id == 'storage' and target.get('storage')
                else EXCLUDED_BUFF_TYPE_IDS.get('all', frozenset())
            )
            if unit_id in (
                broad_exclusions
                | EXCLUDED_BUFF_TYPE_IDS.get(buff_type_id, frozenset())
                | MANDATORY_EXCLUDED_BUFF_TYPE_IDS.get(
                    buff_type_id, frozenset()
                )
            ):
                continue
            allowed_types = target.get('allowed_buff_types')
            if allowed_types and buff_type_id not in allowed_types:
                continue
            if unit_id in EXISTING_CAPABILITY_IDS.get(buff_type_id, ()):
                continue
            if buff_type_id == 'veteran' and not target.get('trainable', True):
                continue
            if (
                buff_type_id == 'speed'
                and movement_speed_ceiling(target) is not None
                and int(target.get('speed', 0))
                >= movement_speed_ceiling(target)
            ):
                # Already at safe ceiling or authored faster. No no-op reward.
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
                'special_reward': bool(target.get('special_reward')),
            })
    return rewards


UNIT_BUFF_REWARDS = build_buff_rewards()

# Linked land/water identities share one visible access item and one set of
# rewards. Their separate map clones still need variant-specific weapons so a
# Robot Tank buff affects both the War Factory and Naval Yard forms safely.
for source_id, variants in LINKED_BUFF_VARIANTS.items():
    source_target = BUFF_TARGETS[source_id]
    for variant_id, definition in variants.items():
        # Linked identities share earned stacks, not authored base values.
        # Campaign prototypes can differ from their normal Foehn counterpart
        # in cost, speed, strength, art, and faction while using related
        # weapons. Preserve the variant's own target metadata.
        variant_target = dict(source_target)
        variant_target.update(BUFF_TARGETS.get(variant_id, {}))
        if definition.get('category'):
            variant_target['category'] = str(definition['category'])
            variant_target['runtime_transform'] = True
        variant_target['weapons'] = {
            str(weapon_id).upper(): dict(stats)
            for weapon_id, stats in definition.get('weapons', {}).items()
        }
        variant_target['linked_buff_source'] = source_id
        variant_target['linked_buff_weapon_only'] = bool(
            definition.get('weapon_buffs_only', False)
        )
        BUFF_TARGETS[variant_id] = variant_target
        UNIT_LABELS.setdefault(variant_id, variant_target['label'])

SUPERWEAPON_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['superweapon_unlock_rewards']

SECONDARY_SUPERWEAPON_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['secondary_superweapon_unlock_rewards']


AID_POWER_MAP_CONFIGS = _REWARD_CATALOGUE_CONFIG['aid_power_map_configs']

# Moon Reinforcements is granted at map start like other portable powers, but
# its charge must still begin empty. Preserve that normal initial cooldown for
# packaged installs whose editable catalogue predates the corrected value.
for aid_config in AID_POWER_MAP_CONFIGS:
    if aid_config.get('superweapon') == 'KnightfallSpawn':
        aid_config.setdefault('values', {})['SW.InitialReady'] = 'no'

# GenericWarhead detonates the private warhead directly. Keep both filtering
# layers explicit. GenericWarhead does not apply SW.AffectsHouse to the direct
# EMP/AttachEffect loop; Ares uses the warhead's AffectsAllies for both the
# owner and allied houses, and AffectsEnemies for non-allied houses. Retain
# AffectsOwner as a harmless explicit compatibility value for engine variants.
# Zero verses for misc armor also preserve neutral scenery independent of
# diplomacy. ASOMNIA's additional Libra immunity is mission-specific and must
# not make enemy Libra immune to the portable power globally. Older editable
# packaged catalogues may omit these corrected values.
for aid_config in AID_POWER_MAP_CONFIGS:
    if aid_config.get('superweapon') != 'TimeFreezeSpecial':
        continue
    aid_config.setdefault('values', {}).update({
        'IsPowered': 'false',
        'Type': 'GenericWarhead',
        'Action': 'Custom',
        'Range': '1.4',
        'Cursor': 'Glacial',
        'NoCursor': 'NoCanDo',
        'SW.AutoFire': 'no',
        'SW.ManualFire': 'yes',
        'SW.ShowCameo': 'yes',
        'SW.UseAITargeting': 'no',
        'SW.AITargeting': 'Offensive',
        'SW.Warhead': 'MORTimeFreezeWH',
        'SW.Damage': '0',
        'SW.AffectsHouse': 'enemies',
        'SW.AffectsTarget': 'infantry,units,buildings',
        'SW.RequiresTarget': 'land',
        'SW.RequiredHouses': '',
        'SW.ForbiddenHouses': '',
        'SW.AuxBuildings': '',
        'SW.NegBuildings': '',
        'SW.Designators': '',
        'SW.Inhibitors': '',
        'SW.AnyInhibitor': 'no',
        'SW.FireIntoShroud': 'yes',
        'SW.RangeMaximum': '384',
        'SW.RangeMinimum': '-1',
        'EMPulse.TargetSelf': None,
        'EMPulse.Cannons': None,
    })
    time_freeze_clones = aid_config.setdefault('techno_clones', {})
    time_freeze_clone = time_freeze_clones.setdefault('TimeFreezeWH', {})
    time_freeze_clone.update({
        'clone': 'MORTimeFreezeWH',
        'list': 'Warheads',
        'reference_keys': ['SW.Warhead'],
    })
    time_freeze_clone.setdefault('values', {}).update({
        'AllowZeroDamage': 'yes',
        'DamageAirThreshold': '-1',
        'Verses': '3%,3%,3%,3%,3%,3%,3%,3%,3%,3%,3%',
        'CellSpread': '225',
        'EMP.Duration': '0',
        'EMP.Cap': '0',
        'PercentAtMax': '1',
        'Versus.misc': '0%',
        'AffectsOwner': 'no',
        'AffectsAllies': 'no',
        'AffectsEnemies': 'yes',
        'Conventional': 'no',
        'PreventScatter': 'yes',
        'Sonar.Duration': '615',
        'DisableWeapons.Duration': '615',
        'EffectsRequireVerses': 'yes',
        'EffectsRequireDamage': 'no',
        'Nonprovocative': 'yes',
        'AttachEffect.Duration': '615',
        'AttachEffect.Animation': 'SPHERE',
        'AttachEffect.ForceDecloak': 'yes',
        'AttachEffect.SpeedMultiplier': '0',
        'AttachEffect.FirepowerMultiplier': '0',
    })
    time_freeze_provider = time_freeze_clones.setdefault(
        'TimeFreezeProvider', {}
    )
    time_freeze_provider.update({
        'source': 'DUMMYDUMMY',
        'clone': 'MORTimeFreezeProvider',
        'list': 'BuildingTypes',
        'startup_count': 1,
        'static_startup': True,
        'provides_superweapon': True,
    })
    time_freeze_provider.setdefault('values', {}).update({
        'Name': 'Randomizer Time Freeze Provider',
        'UIName': 'NAME:DUMMYDUMMY',
        'Image': 'DUMMYDUMMY',
        'SuperWeapon': None,
        'SuperWeapon2': None,
        'TechLevel': '-1',
        'BuildLimit': '0',
        'AIBuildThis': 'no',
        'Power': '0',
        'Powered': 'false',
        'Capturable': 'false',
        'Selectable': 'no',
        'Unsellable': 'yes',
        'LegalTarget': 'no',
        'Insignificant': 'yes',
        'ImmuneToEMP': 'yes',
        'DontScore': 'yes',
        'KeepAlive': 'no',
        'BaseNormal': 'no',
        'AIBaseNormal': 'no',
        'IsBaseDefense': 'no',
        'RadarInvisible': 'yes',
        'IsPassable': 'yes',
        'Firestorm.Wall': 'no',
        'Sight': '0',
    })

# Maintenance uses the same GenericWarhead source lookup as Time Freeze.
# Its native Tech Maintenance Facility is the firer; an action-34-only copy
# has no BuildingClass. Preserve a hidden CASTRF-derived exact-House provider
# plus explicit zero-damage/house filters even when packaged editable configs
# predate them. The private warhead also has to be registered in [Warheads];
# emitting only [MORMaintenanceWH] makes Ares parse SW.Warhead as null.
for aid_config in AID_POWER_MAP_CONFIGS:
    if aid_config.get('superweapon') != 'MaintenanceSpecial':
        continue
    aid_config.setdefault('values', {}).update({
        'SW.AffectsHouse': 'team',
        'SW.AffectsTarget': 'buildings',
    })
    maintenance_clone = aid_config.setdefault(
        'auxiliary_clones', {}
    ).setdefault('MaintenanceWH', {})
    maintenance_clone.setdefault('values', {}).update({
        'AllowZeroDamage': 'yes',
        'EffectsRequireDamage': 'no',
        'AffectsOwner': 'yes',
        'AffectsAllies': 'yes',
        'AffectsEnemies': 'no',
    })
    maintenance_provider = aid_config.setdefault(
        'techno_clones', {}
    ).setdefault('MaintenanceProvider', {})
    maintenance_provider.update({
        'source': 'CASTRF',
        'clone': 'MORMaintenanceProvider',
        'list': 'BuildingTypes',
        'startup_count': 1,
        'static_startup': True,
        'provides_superweapon': True,
    })
    maintenance_provider.setdefault('values', {}).update({
        'Name': 'Randomizer Maintenance Provider',
        'UIName': 'NAME:DUMMYDUMMY',
        'Image': 'DUMMYDUMMY',
        'InvisibleInGame': 'yes',
        'SuperWeapon': None,
        'SuperWeapon2': None,
        'TechLevel': '-1',
        'BuildLimit': '0',
        'AIBuildThis': 'no',
        'Power': '0',
        'Powered': 'false',
        'Immune': 'yes',
        'Capturable': 'false',
        'NeedsEngineer': 'no',
        'Selectable': 'no',
        'Unsellable': 'yes',
        'LegalTarget': 'no',
        'Insignificant': 'yes',
        'ImmuneToEMP': 'yes',
        'DontScore': 'yes',
        'KeepAlive': 'no',
        'BaseNormal': 'no',
        'AIBaseNormal': 'no',
        'IsBaseDefense': 'no',
        'RadarInvisible': 'yes',
        'IsPassable': 'yes',
        'Firestorm.Wall': 'no',
        'Sight': '0',
    })

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
    # Internal handlers and unconfigured powers whose effect requires a
    # separately owned source object remain excluded.
    definitions = _REWARD_CATALOGUE_CONFIG['aid_power_rewards']
    rewards = []
    for definition in definitions:
        name = definition['name']
        description = definition['description']
        faction = definition['faction']
        superweapon = definition['superweapon']
        index = definition['index']
        modified_config = AID_POWER_MAP_CONFIG_BY_SUPERWEAPON.get(superweapon)
        if modified_config and modified_config.get('disabled'):
            continue
        building_bound = bool(
            modified_config and modified_config.get('grant_buildings')
        )
        preserves_prerequisites = bool(
            modified_config and modified_config.get('preserve_prerequisites')
        )
        reward = {
            'name': name,
            'description': (
                description
                if building_bound or preserves_prerequisites
                else description + ' Restored at the start of future missions without its normal source building.'
            ),
            'rules': {},
            'factions': [faction],
            'kind': 'superweapon',
            'power_category': 'aid',
            'superweapon': superweapon,
            'superweapon_index': index,
            'special_reward': bool(definition.get('special_reward')),
        }
        if definition.get('requires_any_tech_ids'):
            reward['requires_any_tech_ids'] = [
                str(unit_id).upper()
                for unit_id in definition['requires_any_tech_ids']
            ]
        if building_bound:
            reward['superweapon_grant_buildings'] = list(
                modified_config['grant_buildings']
            )
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
        if modified_config and modified_config.get('provider_only'):
            reward['superweapon_provider_only'] = True
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
        if modified_config and modified_config.get('source_superweapon'):
            reward['superweapon_source'] = (
                modified_config['source_superweapon']
            )
        if modified_config and modified_config.get(
            'ignore_foreign_tech_gate'
        ):
            reward['superweapon_ignore_foreign_tech_gate'] = True
        if modified_config and modified_config.get('cameo_superweapon'):
            reward['cameo_superweapon'] = modified_config['cameo_superweapon']
        if modified_config and modified_config.get('sidebar_image'):
            reward['superweapon_sidebar_image'] = modified_config['sidebar_image']
        if modified_config and modified_config.get('delivery_player_clone_ids'):
            reward['superweapon_delivery_player_clone_ids'] = [
                str(unit_id).upper()
                for unit_id in modified_config['delivery_player_clone_ids']
            ]
        if modified_config and modified_config.get('player_clone_reference_fields'):
            reward['superweapon_player_clone_reference_fields'] = {
                str(field): [str(unit_id).upper() for unit_id in unit_ids]
                for field, unit_ids in modified_config[
                    'player_clone_reference_fields'
                ].items()
            }
        if modified_config and modified_config.get('player_clone_value_overrides'):
            reward['superweapon_player_clone_value_overrides'] = {
                str(unit_id).upper(): dict(values)
                for unit_id, values in modified_config[
                    'player_clone_value_overrides'
                ].items()
            }
        rewards.append(reward)
    return rewards


AID_POWER_UNLOCK_REWARDS = build_aid_power_rewards()
POWER_BUFF_REWARDS = build_power_buff_rewards(
    SUPERWEAPON_UNLOCK_REWARDS
    + SECONDARY_SUPERWEAPON_UNLOCK_REWARDS
    + AID_POWER_UNLOCK_REWARDS
)
ENEMY_REWARD_POOL = build_enemy_reward_pool(
    SUPERWEAPON_UNLOCK_REWARDS
    + SECONDARY_SUPERWEAPON_UNLOCK_REWARDS
    + AID_POWER_UNLOCK_REWARDS
)

REWARD_POOL = (
    UNIT_UNLOCK_REWARDS
    + EXTRA_UNIT_UNLOCK_REWARDS
    + ROSTER_UNIT_UNLOCK_REWARDS
    + DEFENSE_UNLOCK_REWARDS
    + SPECIAL_BUILDING_UNLOCK_REWARDS
    + SUPERWEAPON_UNLOCK_REWARDS
    + SECONDARY_SUPERWEAPON_UNLOCK_REWARDS
    + AID_POWER_UNLOCK_REWARDS
    + GLOBAL_BUFF_REWARDS
    + UNIT_BUFF_REWARDS
    + POWER_BUFF_REWARDS
    + ENEMY_REWARD_POOL
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
    # Rhino's normal shell consumes ammunition, while its empty-magazine
    # Tesla shell consumes none and is deliberately stronger. Increasing the
    # magazine therefore delays the stronger weapon instead of providing a
    # positive reserve benefit. Preserve old earned stacks as real ROF buffs.
    'Rhino Heavy Tank Ammo Reserves I': 'Rhino Heavy Tank Weapon Tuning I',
    # Old M.A.D. Tank deploy-fire cadence is not a useful adjustable stat.
    # Keep serialized stacks useful without retaining any fire-rate UI/effect.
    'Old M.A.D. Tank Weapon Tuning I': 'Old M.A.D. Tank Reinforced Frames I',
    # Extra Demobomb range makes the truck detonate before reaching its target.
    # Preserve published save/AP item identity as a safe same-unit health stack.
    'Old Demo Truck Optics I': 'Old Demo Truck Reinforced Frames I',
    # These former Firepower rewards described indirect spawned
    # missile/aircraft payload damage. The player clone only owns its direct
    # launcher weapons, so changing the shared payload would either do nothing
    # or buff enemy copies. Preserve old stacks as a real same-unit effect.
    'Akula Missile Sub Firepower I': 'Akula Missile Sub Weapon Tuning I',
    'Kuznetsov Dreadnought Firepower I': 'Kuznetsov Dreadnought Weapon Tuning I',
    'Mosquito Demoboat Firepower I': 'Mosquito Demoboat Reinforced Frames I',
    'Quetzal Firepower I': 'Quetzal Weapon Tuning I',
    'Hailstorm Firepower I': 'Hailstorm Weapon Tuning I',
    'Enterprise Aircraft Carrier Firepower I': 'Enterprise Aircraft Carrier Weapon Tuning I',
    'Scud Launcher Firepower I': 'Scud Launcher Weapon Tuning I',
    'Foxtrot Firepower I': 'Foxtrot Optics I',
    'Gehenna Platform Firepower I': 'Gehenna Platform Weapon Tuning I',
    'M.A.D.M.A.N. Firepower I': 'M.A.D.M.A.N. Reinforced Frames I',
    'Leviathan Helicarrier Firepower I': 'Leviathan Helicarrier Weapon Tuning I',
    'Seitaad Ballista Firepower I': 'Seitaad Ballista Weapon Tuning I',
    'Space Commando Repair Systems I': 'Space Commando Reinforced Frames I',
    'Robo Tengu Sensor Suite I': 'Robo Tengu Reinforced Frames I',
    'Paradox Engine Repair Systems I': 'Paradox Engine Reinforced Frames I',
    'Spy Plane Power Reinforced Payload I': 'Spy Plane Power Expanded Recon I',
}
for unit_id, legacy_labels in {
    'TRACTOR': ('Tyrant',),
}.items():
    current_label = BUFF_TARGETS[unit_id]['label']
    for reward in UNIT_BUFF_REWARDS:
        if reward.get('unit') != unit_id:
            continue
        current_name = str(reward.get('name') or '')
        if not current_name.startswith(current_label):
            continue
        suffix = current_name[len(current_label):]
        for legacy_label in legacy_labels:
            legacy_name = f'{legacy_label}{suffix}'
            # A newly added unit may legitimately reuse an old display label.
            # Current catalogue identities must win over ambiguous save aliases.
            if legacy_name not in REWARD_BY_NAME:
                REWARD_ALIASES[legacy_name] = current_name
for definition in SPECIAL_BUILDING_DEFINITIONS:
    building_name = str(definition['name'])
    REWARD_ALIASES[
        f'{building_name} Command Capacity I'
    ] = f'{building_name} Structure Capacity I'
for limited_unit_id in LIMITED_HERO_UNIT_IDS:
    target = BUFF_TARGETS[limited_unit_id]
    # Seeds made before the structure/unit capacity split could assign the
    # structure-only reward to a hero. Preserve the earned stack by migrating
    # it to that hero's valid unit-capacity reward at load/launch time.
    REWARD_ALIASES[
        f'{target["label"]} Structure Capacity I'
    ] = f'{target["label"]} Command Capacity I'
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
