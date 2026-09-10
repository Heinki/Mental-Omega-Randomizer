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
    REWARD_PLANNING,
    stacked_cost,
    stacked_self_heal_amount,
    stacked_weapon_damage,
    stacked_weapon_rof,
    stacking_amount,
    stacking_multiplier,
    stacking_stack_limit,
)
from randomizer.rewards.power_buff_definitions import (
    power_buff_effect_text,
    power_buff_stack_limit,
    power_buff_type_ids,
)
from randomizer.rewards.enemy_scaling import (
    enemy_effect_text,
    enemy_reward_display_name,
)

def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}
    if reward.get('_runtime_canonical') and not reward.get('enemy_reward'):
        return reward

    reward_name = reward.get('name')
    if not reward_name:
        return reward
    reward_name = REWARD_ALIASES.get(reward_name, reward_name)

    if reward.get('enemy_reward'):
        current_enemy = REWARD_BY_NAME.get(reward_name)
        if current_enemy and current_enemy.get('enemy_reward'):
            merged = dict(current_enemy)
            for key in (
                'enemy_maximum', 'enemy_source', 'enemy_earned_from',
                'enemy_per_stack_percent',
                'enemy_minimum_engine_multiplier',
            ):
                if key in reward:
                    merged[key] = reward[key]
            merged['_runtime_canonical'] = True
            return merged
        return {
            'name': f'{reward_name} (retired: unverified AI reward)',
            'description': (
                'Disabled because no end-to-end hostile-AI application or '
                'launch is currently verified.'
            ),
            'kind': 'message',
            'retired_reward': True,
        }

    if reward_name in RETIRED_REWARD_BY_NAME:
        return RETIRED_REWARD_BY_NAME[reward_name]
    current_reward = REWARD_BY_NAME.get(reward_name)
    if current_reward:
        return current_reward
    if reward.get('kind') == 'buff' and reward.get('power_buff_type'):
        if reward.get('power_buff_type') not in power_buff_type_ids(
            reward.get('superweapon')
        ):
            return {
                'name': f'{reward_name} (retired: inapplicable)',
                'description': (
                    'Disabled because this power does not support that buff.'
                ),
                'rules': {},
                'factions': list(reward.get('factions') or []),
                'kind': 'retired',
                'retired_reward': True,
            }
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

# Only the dedicated global-production reward is house-wide. Ordinary unit
# rewards stay attached to their exact TechnoType; veterancy still needs the
# CountryType Veteran* lists because the engine exposes no per-type equivalent.
HOUSE_SCOPED_BUFF_TYPES = {'production', 'veteran'}
HOUSE_WIDE_BUFF_TYPES = {'production'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload'}
UNIT_STAT_BUFF_TYPES = {
    'health', 'sight', 'ammo', 'storage', 'income',
    'passenger_capacity', 'open_topped',
    'self_healing', 'cloak', 'sensors',
}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = (
    MAP_GUARDED_BUFF_TYPES
    | {
        'cost', 'armor', 'speed', 'build_limit', 'building_limit',
    }
)
def reward_display_name(reward):
    reward = canonical_reward(reward)
    if reward.get('enemy_reward'):
        return enemy_reward_display_name(reward)
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
    """Return the sole supported global buff scope: all production time."""
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
    if buff_type != 'production' or not target.get('global_production'):
        return None
    return ('All', buff_type)


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


def _uncached_buff_stack_limit(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return None
    if reward.get('enemy_reward'):
        try:
            return max(1, int(reward.get('enemy_maximum', 1)))
        except (TypeError, ValueError):
            return 1
    if reward.get('buff_type') == 'starting_credits':
        try:
            per_stack = max(1, int(reward['credits_per_stack']))
            maximum = max(per_stack, int(reward['maximum_credits']))
        except (KeyError, TypeError, ValueError):
            return 1
        return max(1, maximum // per_stack)
    if reward.get('power_buff_type'):
        return power_buff_stack_limit(reward)
    buff_type = reward.get('buff_type')
    if buff_type in {
        'production', 'armor', 'health', 'range', 'sight', 'ammo',
        'storage', 'income',
    }:
        return stacking_stack_limit(buff_type)
    if buff_type == 'cost':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        configured = stacking_stack_limit('cost')
        base_cost = max(1, int(round(float(target.get('cost', 1)))))
        previous = base_cost
        for count in range(1, configured + 1):
            current = stacked_cost(base_cost, count)
            if current == previous:
                return max(1, count - 1)
            previous = current
        return configured
    if buff_type in {'damage', 'reload'}:
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        field = 'damage' if buff_type == 'damage' else 'rof'
        minimum = 0 if buff_type == 'damage' else 1
        values = [
            int(round(float(stats[field])))
            for stats in target.get('weapons', {}).values()
            if float(stats.get(field, 0)) > minimum
        ]
        configured = stacking_stack_limit(buff_type)
        if not values:
            return configured
        previous = tuple(values)
        calculator = (
            stacked_weapon_damage
            if buff_type == 'damage'
            else stacked_weapon_rof
        )
        for count in range(1, configured + 1):
            current = tuple(calculator(value, count) for value in values)
            if current == previous:
                return max(1, count - 1)
            previous = current
        return configured
    if buff_type == 'self_healing':
        fraction_per_stack = float(
            BUFF_EFFECTS['defense_self_heal_fraction']
        )
        maximum_fraction = float(
            BUFF_EFFECTS['maximum_self_heal_fraction']
        )
        configured = max(1, int(ceil(
            maximum_fraction / fraction_per_stack
        )))
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        base_strength = float(target.get('strength', 1))
        previous = stacked_self_heal_amount(base_strength, 1)
        for count in range(2, configured + 1):
            current = stacked_self_heal_amount(base_strength, count)
            if current == previous:
                return count - 1
            previous = current
        return configured
    if buff_type == 'building_limit':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        return max(1, int(target.get('capacity_stack_limit', 4)))
    if buff_type in {'passenger_capacity', 'build_limit'}:
        return max(1, int(
            REWARD_PLANNING['buff_stack_limits'][buff_type]
        ))
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


_BUFF_STACK_LIMIT_BY_NAME = {}


def buff_stack_limit(reward):
    """Return immutable catalogue limits without recalculating stat curves."""
    reward = canonical_reward(reward)
    reward_name = reward.get('name')
    if reward_name and REWARD_BY_NAME.get(reward_name) is reward:
        if reward_name not in _BUFF_STACK_LIMIT_BY_NAME:
            _BUFF_STACK_LIMIT_BY_NAME[reward_name] = (
                _uncached_buff_stack_limit(reward)
            )
        return _BUFF_STACK_LIMIT_BY_NAME[reward_name]
    return _uncached_buff_stack_limit(reward)


def effective_buff_count(reward, count):
    limit = buff_stack_limit(reward)
    if limit is None:
        return count
    return min(count, limit)


def starting_credit_bonus(rewards):
    """Return the capped real-credit bonus earned for every mission start."""
    total = 0
    maximum = 0
    for reward in canonical_rewards(rewards):
        if reward.get('buff_type') != 'starting_credits':
            continue
        try:
            total += max(0, int(reward['credits_per_stack']))
            maximum = max(maximum, int(reward['maximum_credits']))
        except (KeyError, TypeError, ValueError):
            continue
    return min(total, max(0, maximum))


def stack_label(count, limit=None):
    return f'{count}/{limit} stacks' if limit is not None else f'{count} stacks'


def inherited_unit_buff_rewards(rewards, unit_id):
    """Project earned army-wide effects onto a unit for display only.

    Use that unit's canonical buff definition so base stats and stack caps
    match its own clone. Never change the saved reward or grant unit access.
    """
    target = BUFF_TARGETS.get(unit_id, {})
    if not target or target.get('global_buff'):
        return []
    inherited = []
    for reward in canonical_rewards(list(rewards)):
        if reward.get('kind') != 'buff' or not reward.get('global_buff'):
            continue
        kind = reward.get('buff_type')
        source = BUFF_TARGETS.get(reward.get('unit'), {})
        applies = bool(
            kind == 'production' and source.get('global_production')
            and target.get('category') in {
                'infantry', 'units', 'aircraft', 'defenses', 'special_buildings',
            }
        )
        if not applies:
            continue
        unit_reward = REWARD_BY_BUFF_KEY.get((unit_id, kind))
        if unit_reward is not None:
            inherited.append(unit_reward)
    return inherited


def unit_buff_counts(rewards, unit_id):
    """Combine earned copies from every source for one displayed unit."""
    rewards = canonical_rewards(list(rewards))
    inherited = inherited_unit_buff_rewards(rewards, unit_id)
    counts = {}
    for reward in [*rewards, *inherited]:
        if reward.get('kind') != 'buff' or reward.get('unit') != unit_id:
            continue
        kind = reward.get('buff_type')
        counts[kind] = effective_buff_count(reward, counts.get(kind, 0) + 1)
    return counts


def buff_effect_lines(
    reward, count=1, include_label=True, include_stack=True, *, buff_counts=None, multiline=False,
):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    if reward.get('enemy_reward'):
        count = effective_buff_count(reward, count)
        text = enemy_effect_text(reward, count)
        if include_label:
            text = f'AI Reward: {text}'
        if include_stack:
            text = f'{text} ({stack_label(count, buff_stack_limit(reward))})'
        return [text]

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

    if reward.get('buff_type') == 'starting_credits':
        count = effective_buff_count(reward, count)
        amount = count * max(0, int(reward.get('credits_per_stack', 0)))
        text = f'Starting credits +{amount:,} per mission'
        if include_stack:
            text = f'{text} ({stack_label(count, limit)})'
        return [text]

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)

    def stacked(text):
        if not include_stack or limit == 1:
            return text
        return f'{text} · {stack_label(count, limit)}'

    def number(value):
        return f'{value:,.6f}'.rstrip('0').rstrip('.')

    def value_text(label, current, base, unit=''):
        text = f'{prefix}{label} {number(current)}'
        if count:
            text += f' [{number(base)}]'
        return [stacked(text + unit)]

    def weapon_text(label, field, calculator, minimum=0, unit='', show_base=True):
        pairs = {}
        for weapon, stats in target.get('weapons', {}).items():
            base = float(stats.get(field, 0))
            if base <= minimum or not stats.get('buff_safe', True):
                continue
            current = calculator(base)
            pairs.setdefault((current, base if show_base else None), []).append(weapon)
        if not pairs:
            return [stacked(f'{prefix}{label}: no applicable weapon')]
        parts = []
        for (current, base), weapons in pairs.items():
            detail = number(current)
            if count and show_base:
                detail += f' [{number(base)}]'
            detail += unit
            if len(pairs) > 1:
                detail = f'{" / ".join(weapons)}: {detail}'
            parts.append(detail)
        if multiline and len(parts) > 1:
            return [stacked(f'{prefix}{label}') + '\n    ' + '\n    '.join(parts)]
        return [stacked(f'{prefix}{label} ' + '; '.join(parts))]

    def durability():
        counts = dict(buff_counts or {})
        counts[buff_type] = count
        for kind in ('health', 'armor'):
            other = REWARD_BY_BUFF_KEY.get((reward.get('unit'), kind))
            if other:
                counts[kind] = effective_buff_count(other, counts.get(kind, 0))
        base = max(1, int(round(float(target.get('strength', 1)))))
        health = stacking_multiplier('health', counts.get('health', 0))
        armor = stacking_multiplier('armor', counts.get('armor', 0))
        return base, max(1, int(round(int(round(base * health)) / armor)))

    if buff_type == 'production':
        multiplier = stacking_multiplier('production', count)
        effect = (
            'Construction time'
            if target.get('category') in {'buildings', 'defenses'}
            else 'Production time'
        )
        return [stacked(f'{prefix}{effect} {round((1 - multiplier) * 100)}% shorter')]
    if buff_type == 'cost':
        base = int(round(float(target.get('cost', 0))))
        return value_text('Cost', stacked_cost(base, count), base, ' credits')

    if buff_type == 'speed':
        safe_ceiling = movement_speed_ceiling(target)
        if safe_ceiling is not None:
            base_speed = int(round(float(target.get('speed', 1))))
            speed = capped_movement_speed(target, count)
            return [stacked(
                f'{prefix}Speed {speed} [{base_speed}]'
            )]
        multiplier = stacking_multiplier('speed', count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        base, strength = durability()
        return value_text('Armor durability', strength, base, ' HP')

    if buff_type == 'health':
        base, strength = durability()
        return value_text('Health', strength, base, ' HP')

    if buff_type == 'sight':
        base = int(round(float(target.get('sight', 0))))
        return value_text('Vision', int(round(base + stacking_amount('sight', count))), base, ' cells')

    if buff_type == 'veteran':
        return [stacked(f'{prefix}Veteran start')]
    if buff_type in {'build_limit', 'building_limit'}:
        base_limit = int(target.get('build_limit', 1))
        subject = (
            'Simultaneous structure limit'
            if target.get('category') == 'special_buildings'
            else 'Simultaneous unit limit'
        )
        return value_text(subject, base_limit + count, base_limit)
    if buff_type == 'damage':
        return weapon_text('Damage', 'damage', lambda base: stacked_weapon_damage(base, count))

    if buff_type == 'reload':
        return weapon_text(
            'Fire rate', 'rof',
            lambda base: round((base / stacked_weapon_rof(base, count) - 1) * 100),
            minimum=1, unit='% faster', show_base=False,
        )

    if buff_type == 'range':
        return weapon_text(
            'Range', 'range', lambda base: base + stacking_amount('range', count),
            unit=' cells',
        )

    if buff_type == 'ammo':
        increase = int(stacking_amount('ammo', count))
        base_ammo = int(target.get('ammo', 0))
        total_ammo = base_ammo + increase
        ammo_label = _UNIT_POLICY_CONFIG['ammo_display_labels'].get(
            reward.get('unit'), 'Ammo'
        )
        return value_text(ammo_label, total_ammo, base_ammo)
    if buff_type == 'storage':
        increase = int(stacking_amount('storage', count))
        base_storage = int(target.get('storage', 0))
        return [stacked(
            f'{prefix}Ore storage {base_storage + increase:,} [{base_storage:,}]'
        )]
    if buff_type == 'income':
        increase = int(stacking_amount('income', count))
        base_income = int(target.get('produce_cash_amount', 0))
        return [stacked(
            f'{prefix}Income {base_income + increase:,} [{base_income:,}] credits'
        )]
    if buff_type == 'passenger_capacity':
        base_passengers = int(target.get('passengers', 0))
        return [stacked(
            f'{prefix}Passenger capacity {base_passengers + count} '
            f'[{base_passengers}]'
        )]
    if buff_type == 'open_topped':
        return [stacked(f'{prefix}Passengers can fire from transport')]
    if buff_type == 'self_healing':
        _base, base_strength = durability()
        heal_amount = stacked_self_heal_amount(base_strength, count)
        return [stacked(
            f'{prefix}Self-healing {heal_amount} HP per tick'
        )]
    if buff_type == 'cloak':
        return [stacked(f'{prefix}Cloaking enabled')]
    if buff_type == 'sensors':
        sensor_range = int(round(
            target.get('sight', 5) + float(BUFF_EFFECTS['sensor_sight_bonus'])
        ))
        return [stacked(f'{prefix}Sensors {sensor_range} cells')]
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
