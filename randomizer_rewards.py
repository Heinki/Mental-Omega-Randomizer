"""Reward catalogue and display helpers for the Mental Omega randomizer."""

from randomizer_weapon_stats import (
    ROSTER_DAMAGE_WEAPON_REFS,
    ROSTER_WEAPON_REFS,
    WEAPON_BASE_STATS,
)
from randomizer_static_config import load_static_config
from randomizer_tuning import (
    BUFF_EFFECTS,
    REWARD_PLANNING,
    stacking_amount,
    stacking_multiplier,
)


_UNIT_DATA_CONFIG = load_static_config('rewards/unit_data.json')
_REWARD_CATALOGUE_CONFIG = load_static_config('rewards/catalogue.json')
_FACTION_CONFIG = load_static_config('factions.json')
_UNIT_POLICY_CONFIG = load_static_config('rewards/unit_policy.json')
_BUFF_EXCEPTION_CONFIG = load_static_config('rewards/buff_exceptions.json')

# This module is intentionally data-heavy. Keeping it separate from the Tk
# launcher makes future Archipelago item/location work much easier.

DEFAULT_UNLOCK_BUILD_HOUSES = _FACTION_CONFIG['default_unlock_build_houses']
DEFAULT_REWARDS_PER_CHECK = int(REWARD_PLANNING['default_rewards_per_check'])
MAX_REWARDS_PER_CHECK = int(REWARD_PLANNING['maximum_rewards_per_check'])

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
EXISTING_SELF_HEALING_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['self_healing']
)
EXISTING_CLOAK_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['cloak']
)
EXISTING_SENSOR_IDS = frozenset(
    _UNIT_POLICY_CONFIG['existing_capability_ids']['sensors']
)
EXISTING_CAPABILITY_IDS = {
    'self_healing': EXISTING_SELF_HEALING_IDS,
    'cloak': EXISTING_CLOAK_IDS,
    'sensors': EXISTING_SENSOR_IDS,
}

# Reviewed gameplay exclusions for buffs that are technically constructible
# but redundant, misleading, or ineffective for a specific TechnoType. Keep
# this policy editable beside the installed capability snapshot.
EXCLUDED_BUFF_TYPE_IDS = {
    buff_type: frozenset(str(unit_id).upper() for unit_id in unit_ids)
    for buff_type, unit_ids in _BUFF_EXCEPTION_CONFIG['excluded_buff_type_ids'].items()
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

# Economy, base-operation, and mission-transport essentials are deliberately
# never access items. They remain available regardless of randomizer progress.
AMPHIBIOUS_TRANSPORT_UNIT_IDS = frozenset(
    values[0] for values in _FACTION_CONFIG['amphibious_transports'].values()
)
ENGINEER_UNIT_IDS = frozenset(_FACTION_CONFIG['engineer_by_family'].values())
ALWAYS_AVAILABLE_UNIT_IDS = set(
    _UNIT_POLICY_CONFIG['always_available_core_unit_ids']
) | set(ENGINEER_UNIT_IDS) | set(AMPHIBIOUS_TRANSPORT_UNIT_IDS)
ALWAYS_AVAILABLE_BUILDING_IDS = set(
    _UNIT_POLICY_CONFIG['always_available_building_ids']
)
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
    if prerequisite:
        values['PrerequisiteOverride'] = prerequisite
    return {section: values}

UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['unit_unlock_rewards']

EXTRA_UNIT_UNLOCK_REWARDS = _REWARD_CATALOGUE_CONFIG['extra_unit_unlock_rewards']

FACTION_ACCESS_RULES = _REWARD_CATALOGUE_CONFIG['faction_access_rules']

NAVAL_UNIT_IDS = set(_UNIT_POLICY_CONFIG['naval_unit_ids'])


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
MAX_BUFFED_INFANTRY_SPEED = int(BUFF_EFFECTS['infantry_speed']['safe_ceiling'])


def capped_infantry_speed(base_speed, count):
    """Return safe earned infantry speed without lowering faster native types."""
    base_speed = max(1, int(base_speed))
    ceiling = max(base_speed, MAX_BUFFED_INFANTRY_SPEED)
    factor = float(BUFF_EFFECTS['infantry_speed']['factor_per_stack'])
    return min(ceiling, max(1, int(round(base_speed * (factor ** count)))))

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
            if unit_id in (
                EXCLUDED_BUFF_TYPE_IDS.get('all', frozenset())
                | EXCLUDED_BUFF_TYPE_IDS.get(buff_type_id, frozenset())
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
        reward = {
            'name': name,
            'description': (
                description
                if building_bound
                else description + ' Restored at the start of future missions without its normal source building.'
            ),
            'rules': {},
            'factions': [faction],
            'kind': 'superweapon',
            'power_category': 'aid',
            'superweapon': superweapon,
            'superweapon_index': index,
        }
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
        if modified_config and modified_config.get('sidebar_image'):
            reward['superweapon_sidebar_image'] = modified_config['sidebar_image']
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
MAX_VETERANCY_STACKS = int(BUFF_EFFECTS['maximum_veterancy_stacks'])


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
        multiplier = stacking_multiplier('production', count)
        shorter = int(round((1.0 - multiplier) * 100))
        effect = (
            'Construction time'
            if target.get('category') in {'buildings', 'defenses'}
            else 'Production time'
        )
        return [stacked(f'{prefix}{effect} {shorter}% shorter')]
    if buff_type == 'cost':
        multiplier = stacking_multiplier('cost', count)
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
        multiplier = stacking_multiplier('speed', count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        multiplier = stacking_multiplier('armor', count)
        tougher = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Armor {tougher}% stronger')]
    if buff_type == 'health':
        multiplier = stacking_multiplier('health', count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Health {stronger}% higher')]
    if buff_type == 'sight':
        increase = int(stacking_amount('sight', count))
        return [stacked(f'{prefix}Vision +{increase}')]
    if buff_type == 'veteran':
        return [stacked(f'{prefix}Veteran start')]
    if buff_type == 'build_limit':
        base_limit = int(target.get('build_limit', 1))
        return [stacked(f'{prefix}Simultaneous unit limit {base_limit} -> {base_limit + count}')]
    if buff_type == 'damage':
        multiplier = stacking_multiplier('damage', count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Damage {stronger}% higher')]
    if buff_type == 'reload':
        multiplier = stacking_multiplier('reload', count)
        faster = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Fire rate {faster}% faster')]
    if buff_type == 'range':
        increase = stacking_amount('range', count)
        if increase.is_integer():
            increase_text = str(int(increase))
        else:
            increase_text = f'{increase:.1f}'
        return [stacked(f'{prefix}Range +{increase_text}')]
    if buff_type == 'ammo':
        increase = int(stacking_amount('ammo', count))
        base_ammo = int(target.get('ammo', 0))
        total_ammo = base_ammo + increase
        ammo_label = _UNIT_POLICY_CONFIG['ammo_display_labels'].get(
            reward.get('unit'), 'Ammo'
        )
        return [stacked(f'{prefix}{ammo_label} {base_ammo} -> {total_ammo}')]
    if buff_type == 'self_healing':
        return [stacked(f'{prefix}Self-healing enabled')]
    if buff_type == 'cloak':
        return [stacked(f'{prefix}Cloaking enabled')]
    if buff_type == 'sensors':
        sensor_range = int(round(
            target.get('sight', 5) + float(BUFF_EFFECTS['sensor_sight_bonus'])
        ))
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
