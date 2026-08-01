"""Reward canonicalization, stacking, and human-readable display."""

from math import ceil

from .definitions import (
    BUFF_EFFECTS,
    BUFF_TARGETS,
    NONTRAINABLE_UNIT_IDS,
    RETIRED_REWARD_BY_NAME,
    REWARD_ALIASES,
    REWARD_BY_BUFF_KEY,
    REWARD_BY_NAME,
    _UNIT_POLICY_CONFIG,
    capped_movement_speed,
    movement_speed_ceiling,
    unit_display_label,
)
from randomizer.config.tuning import (
    stacking_amount,
    stacking_multiplier,
    stacking_stack_limit,
)
from randomizer.rewards.power_buff_definitions import (
    power_buff_effect_text,
    power_buff_stack_limit,
)

def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}
    if reward.get('_runtime_canonical'):
        return reward

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

HOUSE_SCOPED_BUFF_TYPES = {'production', 'cost', 'armor', 'veteran'}
HOUSE_WIDE_BUFF_TYPES = {'production', 'cost', 'armor'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload'}
UNIT_STAT_BUFF_TYPES = {
    'health', 'sight', 'ammo', 'passenger_capacity', 'open_topped',
    'self_healing', 'cloak', 'sensors',
}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = (
    MAP_GUARDED_BUFF_TYPES
    | {'speed', 'build_limit', 'building_limit'}
)
def reward_display_name(reward):
    reward = canonical_reward(reward)
    name = reward.get('name', 'Unknown reward')
    if reward.get('kind') == 'buff' and (
        reward.get('buff_type') or reward.get('power_buff_type')
    ):
        effect_lines = buff_effect_lines(reward, include_stack=False)
        if effect_lines:
            return effect_lines[0]
    if reward.get('kind') == 'buff' and name.endswith(' I'):
        return name[:-2]
    return name


def house_category_suffix(target):
    return HOUSE_CATEGORY_SUFFIXES.get(target.get('category', 'units'), 'Units')


def house_wide_buff_scope(reward, unit_specific_mode=False):
    """Return actual CountryType category effect, excluding exact-unit lists."""
    reward = canonical_reward(reward)
    if (
        reward.get('kind') != 'buff'
        or reward.get('power_buff_type')
    ):
        return None
    buff_type = str(reward.get('buff_type') or '')
    target = BUFF_TARGETS.get(str(reward.get('unit') or '').upper(), {})
    if not target or buff_type not in HOUSE_WIDE_BUFF_TYPES:
        return None
    if buff_type == 'production' and target.get('global_production'):
        return ('All', buff_type)
    if unit_specific_mode:
        return None
    return (house_category_suffix(target), buff_type)


def house_wide_buff_label(scope):
    suffix, buff_type = scope
    subjects = {
        'All': 'All Production',
        'Infantry': 'Infantry',
        'Units': 'Vehicles / Naval',
        'Aircraft': 'Aircraft',
        'Buildings': 'Buildings',
        'Defenses': 'Defenses',
    }
    effects = {
        'production': 'Production',
        'cost': 'Cost',
        'armor': 'Armor',
    }
    subject = subjects.get(suffix, suffix)
    effect = effects.get(buff_type, buff_type.title())
    if suffix == 'All' and buff_type == 'production':
        return subject
    return f'{subject} {effect}'


def house_wide_buff_effect_lines(
    scope,
    count=1,
    include_stack=True,
    stack_limit=None,
):
    suffix, buff_type = scope
    label = house_wide_buff_label(scope)
    count = max(1, int(count))
    if buff_type == 'production':
        multiplier = stacking_multiplier('production', count)
        text = f'{label} time {int(round((1.0 - multiplier) * 100))}% shorter'
    elif buff_type == 'cost':
        multiplier = stacking_multiplier('cost', count)
        text = f'{label} {int(round((1.0 - multiplier) * 100))}% cheaper'
    elif buff_type == 'armor':
        multiplier = stacking_multiplier('armor', count)
        text = f'{label} {int(round(((1.0 / multiplier) - 1.0) * 100))}% stronger'
    else:
        return []
    if include_stack:
        text = f'{text} ({stack_label(count, stack_limit)})'
    return [text]


def buff_stack_limit(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return None
    if reward.get('power_buff_type'):
        return power_buff_stack_limit(reward)
    buff_type = reward.get('buff_type')
    if buff_type in {
        'production', 'cost', 'armor', 'health', 'damage', 'range', 'sight',
    }:
        return stacking_stack_limit(buff_type)
    if buff_type == 'self_healing':
        fraction_per_stack = float(
            BUFF_EFFECTS['defense_self_heal_fraction']
        )
        maximum_fraction = float(
            BUFF_EFFECTS['maximum_self_heal_fraction']
        )
        return max(1, int(ceil(maximum_fraction / fraction_per_stack)))
    if buff_type == 'building_limit':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        return max(1, int(target.get('capacity_stack_limit', 4)))
    if buff_type == 'speed':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        safe_ceiling = movement_speed_ceiling(target)
        if safe_ceiling is not None:
            base_speed = max(1, int(round(float(target.get('speed', 1)))))
            if base_speed >= safe_ceiling:
                return 1
            for stacks in range(1, 257):
                if capped_movement_speed(target, stacks) >= safe_ceiling:
                    return stacks
    if buff_type in {'open_topped', 'cloak', 'sensors', 'veteran'}:
        return 1
    return None


def effective_buff_count(reward, count):
    limit = buff_stack_limit(reward)
    if limit is None:
        return count
    return min(count, limit)


def stack_label(count, limit=None):
    text = f'Stacked {count} time' + ('s' if count != 1 else '')
    if limit is not None:
        text += f'; maximum {limit}'
    return text


def buff_effect_lines(reward, count=1, include_label=True, include_stack=True):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    limit = buff_stack_limit(reward)
    if reward.get('power_buff_type'):
        count = effective_buff_count(reward, count)
        prefix = (
            f'{reward.get("power_name", reward.get("superweapon", "Power"))}: '
            if include_label else ''
        )
        text = f'{prefix}{power_buff_effect_text(reward, count)}'
        if include_stack:
            text = f'{text} ({stack_label(count, limit)})'
        return [text]

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)

    def stacked(text):
        if not include_stack:
            return text
        return f'{text} ({stack_label(count, limit)})'

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
        safe_ceiling = movement_speed_ceiling(target)
        if safe_ceiling is not None:
            base_speed = int(round(float(target.get('speed', 1))))
            speed = capped_movement_speed(target, count)
            return [stacked(
                f'{prefix}Speed {base_speed} -> {speed} '
                f'(safe ceiling {safe_ceiling})'
            )]
        multiplier = stacking_multiplier('speed', count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        multiplier = stacking_multiplier('armor', count)
        # Armor is a received-damage multiplier. Express its inverse as
        # effective durability so values can truthfully grow beyond 100%.
        tougher = int(round(((1.0 / multiplier) - 1.0) * 100))
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
    if buff_type in {'build_limit', 'building_limit'}:
        base_limit = int(target.get('build_limit', 1))
        subject = (
            'Simultaneous structure limit'
            if target.get('category') == 'special_buildings'
            else 'Simultaneous unit limit'
        )
        return [stacked(f'{prefix}{subject} {base_limit} -> {base_limit + count}')]
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
    if buff_type == 'passenger_capacity':
        base_passengers = int(target.get('passengers', 0))
        return [stacked(
            f'{prefix}Passenger capacity '
            f'{base_passengers} -> {base_passengers + count}'
        )]
    if buff_type == 'open_topped':
        return [stacked(f'{prefix}Passengers can fire from transport')]
    if buff_type == 'self_healing':
        fraction = min(
            float(BUFF_EFFECTS['maximum_self_heal_fraction']),
            float(BUFF_EFFECTS['defense_self_heal_fraction'])
            * count
        )
        return [stacked(
            f'{prefix}Self-healing {fraction * 100:g}% maximum health per tick'
        )]
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
                f'{stack_label(count, limit)})'
            )
        return [sensor_text]
    return []


def reward_rule_summary(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff' and (
        reward.get('buff_type') or reward.get('power_buff_type')
    ):
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
                    changes.append(f'production time {delta}% shorter')
                elif delta < 0:
                    changes.append(f'production time {abs(delta)}% longer')
                else:
                    changes.append(f'BuildTimeMultiplier={value}')
            elif key_lower in {'owner', 'requiredhouses', 'forbiddenhouses', 'prerequisiteoverride'}:
                continue
            else:
                changes.append(f'{key}={value}')

        if changes:
            summaries.append(f'{unit_display_label(section)}: {", ".join(changes)}')

    return summaries
