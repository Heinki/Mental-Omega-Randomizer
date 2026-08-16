"""Reviewed AI-only rewards and deterministic standalone/AP planning."""

import random
import re

from randomizer.config.static import load_static_config
from randomizer.config.tuning import stacking_amount, stacking_multiplier


_CONFIG = load_static_config('rewards/enemy_scaling.json')
ENEMY_SCALING_DEFAULTS = dict(_CONFIG['defaults'])


def _tier_unit_buff_definitions():
    definitions = []
    for tier in (1, 2, 3):
        for template in _CONFIG.get('tier_unit_buff_templates', ()):
            definition = dict(template)
            definition.update({
                'id': f'tier{tier}_{template["id"]}',
                'name': f'AI T{tier} Unit {template["name"]}',
                'type': template['name'],
                'category': f'T{tier} Units',
                'effect': 'unit',
                'tier': tier,
            })
            definitions.append(definition)
    return definitions


ENEMY_BUFF_DEFINITIONS = tuple(
    [dict(item) for item in _CONFIG['buffs']]
    + _tier_unit_buff_definitions()
)
ENEMY_BUFF_BY_ID = {
    str(item['id']): item for item in ENEMY_BUFF_DEFINITIONS
}
SUPPORTED_AI_REWARD_IDS = frozenset(
    definition['id']
    for definition in ENEMY_BUFF_DEFINITIONS
    if definition.get('effect') in {'armor', 'production', 'unit', 'power'}
)


def _enemy_group_ids(*, effects=(), types=()):
    return tuple(
        definition['id']
        for definition in ENEMY_BUFF_DEFINITIONS
        if (
            definition.get('effect') in effects
            or definition.get('type') in types
        )
    )


ENEMY_BUFF_GROUP_DEFINITIONS = (
    {
        'id': 'stat_bonuses',
        'label': 'AI unit stat bonuses',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') == 'armor'
            or (
                definition.get('effect') == 'unit'
                and definition.get('unit_buff_type') not in {
                    'damage', 'range', 'reload',
                }
            )
        ),
    },
    {
        'id': 'weapon_bonuses',
        'label': 'AI weapon bonuses',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') == 'unit'
            and definition.get('unit_buff_type') in {
                'damage', 'range', 'reload',
            }
        ),
    },
    {
        'id': 'production',
        'label': 'AI production-speed bonuses',
        'effect_ids': _enemy_group_ids(effects={'production'}),
    },
    {
        'id': 'support_powers',
        'label': 'AI support powers',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') == 'power'
            and definition.get('category') != 'Superweapons'
        ),
    },
    {
        'id': 'superweapons',
        'label': 'AI superweapons',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') == 'power'
            and definition.get('category') == 'Superweapons'
        ),
    },
)
UNSUPPORTED_AI_REWARD_REASONS = (
    'AI unit unlocks skipped: generic production changes can replace '
    'story-critical unit identities or alter mission scripts.',
)
MAX_ENEMY_BUFF_CAP = 100
MAX_ENEMY_TOTAL_BUFFS = 999
ENEMY_STACK_MODEL_VERSION = 6
ENEMY_REWARD_PLAN_VERSION = 1
NEW_ENEMY_POWER_IDS = (
    'ai_lightning_storm',
    'ai_nuclear_missile',
    'ai_psychic_dominator',
    'ai_great_tempest',
    'ai_bloodhounds',
    'ai_moon_reinforcements',
)
MAX_GENERATED_POWER_ID_LENGTH = 21


def _bounded_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(minimum, min(maximum, number))


def normalize_enemy_scaling_settings(value):
    """Normalize seed-frozen AI reward settings."""
    source = value if isinstance(value, dict) else {}
    try:
        stack_model_version = max(
            0, int(source.get('stack_model_version', 1))
        )
    except (TypeError, ValueError):
        stack_model_version = 1
    allowed_source = source.get(
        'allowed_buff_ids', ENEMY_SCALING_DEFAULTS['allowed_buff_ids']
    )
    if not isinstance(allowed_source, (list, tuple, set)):
        allowed_source = ENEMY_SCALING_DEFAULTS['allowed_buff_ids']
    allowed_values = {str(item) for item in allowed_source}
    allowed = [
        buff_id for buff_id in ENEMY_BUFF_BY_ID
        if buff_id in SUPPORTED_AI_REWARD_IDS
        and ('*' in allowed_values or buff_id in allowed_values)
    ]
    caps_source = source.get('caps')
    if not isinstance(caps_source, dict):
        caps_source = ENEMY_SCALING_DEFAULTS['caps']
    caps = {}
    for buff_id, definition in ENEMY_BUFF_BY_ID.items():
        hard_maximum = int(definition['maximum_stacks'])
        raw_cap = caps_source.get(
            buff_id,
            ENEMY_SCALING_DEFAULTS['caps'].get(buff_id, hard_maximum),
        )
        # Version 1 exposed no cap controls and shipped a fixed value of 3.
        # Upgrade that legacy default to the corrected five-stack model while
        # preserving explicit lower values such as 0, 1, or 2.
        if stack_model_version < 2 and raw_cap == 3:
            raw_cap = hard_maximum
        configured = _bounded_int(
            raw_cap,
            0,
            min(MAX_ENEMY_BUFF_CAP, hard_maximum),
            hard_maximum,
        )
        caps[buff_id] = configured
    capacity = sum(caps[buff_id] for buff_id in allowed)
    return {
        'stack_model_version': ENEMY_STACK_MODEL_VERSION,
        'maximum_total_buffs': _bounded_int(
            source.get(
                'maximum_total_buffs',
                ENEMY_SCALING_DEFAULTS['maximum_total_buffs'],
            ),
            0,
            min(MAX_ENEMY_TOTAL_BUFFS, capacity),
            ENEMY_SCALING_DEFAULTS['maximum_total_buffs'],
        ),
        'allowed_buff_ids': allowed,
        'caps': caps,
    }


def enemy_buff_capacity(settings):
    """Return enabled per-effect capacity after normalization."""
    normalized = normalize_enemy_scaling_settings(settings)
    allowed = set(normalized['allowed_buff_ids'])
    return sum(
        cap for effect_id, cap in normalized['caps'].items()
        if effect_id in allowed
    )


def _enemy_power_clone_id(superweapon):
    short = re.sub(r'Special$', '', str(superweapon), flags=re.IGNORECASE)
    return (
        'MORE' + re.sub(r'[^A-Za-z0-9_]', '', short)
    )[:MAX_GENERATED_POWER_ID_LENGTH]


def build_enemy_reward_pool(power_rewards):
    """Build canonical enemy rewards, reusing reviewed portable power plans."""
    powers = {
        str(reward.get('superweapon') or '').upper(): reward
        for reward in power_rewards
        if reward.get('kind') == 'superweapon'
    }
    rewards = []
    for definition in ENEMY_BUFF_DEFINITIONS:
        power_id = str(definition.get('superweapon') or '').upper()
        reward = dict(powers.get(power_id, {})) if power_id else {}
        reward.update({
            'name': definition['name'],
            'description': enemy_effect_text(definition, 1),
            'rules': {},
            'factions': ['Neutral'],
            'kind': 'buff',
            'buff_type': 'enemy',
            'enemy_reward': True,
            'enemy_effect_id': definition['id'],
            'enemy_type': definition['type'],
            'enemy_category': definition['category'],
            'enemy_effect': definition['effect'],
            'enemy_maximum': int(definition['maximum_stacks']),
            'tier': int(definition.get('tier', 0)),
            'unit_buff_type': definition.get('unit_buff_type'),
            'enemy_country_suffix': definition.get('country_suffix', ''),
            'enemy_per_stack_percent': float(
                definition.get('per_stack_percent', 0)
            ),
            'enemy_per_stack_value': float(definition.get(
                'per_stack_value', definition.get('per_stack_percent', 0)
            )),
            'enemy_value_unit': str(definition.get('value_unit', '%')),
            'enemy_minimum_engine_multiplier': float(
                definition.get('minimum_engine_multiplier', 0.001)
            ),
            'enemy_maximum': int(definition['maximum_stacks']),
        })
        if power_id:
            reward['superweapon'] = definition['superweapon']
            reward['enemy_ai_targeting'] = definition['ai_targeting']
            reward['enemy_ai_targeting_constraints'] = str(
                definition.get('ai_targeting_constraints', 'enemy')
            )
            reward['enemy_faction_families'] = tuple(
                str(family).strip().lower()
                for family in definition.get('faction_families', ())
                if str(family).strip()
            )
            reward['enemy_use_existing_power'] = bool(
                definition.get('use_existing_power', False)
            )
            reward['enemy_superweapon_clone'] = _enemy_power_clone_id(
                definition['superweapon']
            )
        rewards.append(reward)
    return rewards


def configured_enemy_reward(reward, settings):
    """Return one seed-settings copy, or None when disabled/invalid."""
    if not reward.get('enemy_reward'):
        return reward
    settings = normalize_enemy_scaling_settings(settings)
    effect_id = str(reward.get('enemy_effect_id') or '')
    cap = settings['caps'].get(effect_id, 0)
    if effect_id not in settings['allowed_buff_ids'] or cap <= 0:
        return None
    configured = dict(reward)
    configured['enemy_maximum'] = cap
    configured['_runtime_canonical'] = True
    return configured


def enemy_effect_values(reward, count=1, base_engine_value=1.0):
    """Return exact cumulative engine and human-facing AI bonus values."""
    effect_id = str(reward.get('enemy_effect_id') or reward.get('id') or '')
    definition = ENEMY_BUFF_BY_ID.get(effect_id, reward)
    maximum = max(1, int(
        reward.get('enemy_maximum', definition.get('maximum_stacks', 1))
    ))
    count = min(maximum, max(1, int(count)))
    per_stack_percent = max(0.0, float(
        reward.get(
            'enemy_per_stack_percent',
            definition.get('per_stack_percent', 0),
        )
    ))
    per_stack_value = max(0.0, float(
        reward.get(
            'enemy_per_stack_value',
            definition.get('per_stack_value', per_stack_percent),
        )
    ))
    try:
        base_engine_value = float(base_engine_value)
    except (TypeError, ValueError):
        base_engine_value = 1.0
    base_engine_value = max(0.001, base_engine_value)
    effect = definition.get('effect')
    fraction = per_stack_percent / 100.0
    if effect == 'armor':
        # Country Armor*Mult is armor strength. Convert the configured human
        # bonus to its reciprocal received-damage multiplier, then back to the
        # engine value explicitly so UI and INI use the same calculation.
        armor_strength = 1.0 + (fraction * count)
        received_damage = 1.0 / max(0.001, armor_strength)
        relative_engine = 1.0 / received_damage
    elif effect == 'production':
        minimum = max(0.001, float(reward.get(
            'enemy_minimum_engine_multiplier',
            definition.get('minimum_engine_multiplier', 0.001),
        )))
        relative_engine = max(minimum, 1.0 - (fraction * count))
        received_damage = None
    elif effect == 'unit':
        buff_type = definition.get('unit_buff_type')
        if buff_type in {'health', 'damage', 'speed'}:
            relative_engine = stacking_multiplier(buff_type, count)
        elif buff_type == 'armor':
            relative_engine = 1.0 / max(
                0.001, stacking_multiplier('armor', count)
            )
        elif buff_type == 'reload':
            relative_engine = stacking_multiplier('reload', count)
        else:
            relative_engine = 1.0
        received_damage = None
    elif effect == 'power':
        relative_engine = 1.0
        received_damage = None
    else:
        relative_engine = 1.0
        received_damage = None
    final_engine = max(0.001, base_engine_value * relative_engine)
    # Map multipliers are serialized to three decimals. Make the receipt and
    # UI report the exact value the engine receives, not an unrounded ideal.
    final_engine = float(f'{final_engine:.3f}')
    relative_applied = final_engine / base_engine_value
    displayed = (
        (relative_applied - 1.0) * 100.0
        if effect == 'armor'
        or (
            effect == 'unit'
            and definition.get('unit_buff_type') in {
                'health', 'damage', 'speed', 'armor',
            }
        )
        else (1.0 - relative_applied) * 100.0
        if effect == 'production'
        or (
            effect == 'unit'
            and definition.get('unit_buff_type') == 'reload'
        )
        else 0.0
    )
    return {
        'per_stack_value': per_stack_value,
        'current_stacks': count,
        'maximum_stacks': maximum,
        'base_engine_value': base_engine_value,
        'relative_engine_value': relative_applied,
        'final_engine_value': final_engine,
        'damage_received_multiplier': received_damage,
        'displayed_percentage': max(0, int(round(displayed))),
    }


def enemy_effect_text(reward, count=1, base_engine_value=1.0):
    """Describe the exact cumulative effect applied to the generated map."""
    effect_id = str(reward.get('enemy_effect_id') or reward.get('id') or '')
    definition = ENEMY_BUFF_BY_ID.get(effect_id, reward)
    values = enemy_effect_values(reward, count, base_engine_value)
    category = definition.get('category', 'forces')
    effect = definition.get('effect')
    if effect == 'armor':
        return f'{category} Armor {values["displayed_percentage"]}% stronger'
    if effect == 'production':
        return (
            f'{category} Production '
            f'{values["displayed_percentage"]}% faster'
        )
    if effect == 'unit':
        buff_type = definition.get('unit_buff_type')
        if buff_type == 'health':
            detail = f'Health +{values["displayed_percentage"]}%'
        elif buff_type == 'armor':
            detail = f'Armor {values["displayed_percentage"]}% stronger'
        elif buff_type == 'speed':
            detail = f'Speed +{values["displayed_percentage"]}%'
        elif buff_type == 'damage':
            detail = f'Weapon damage +{values["displayed_percentage"]}%'
        elif buff_type == 'reload':
            detail = (
                f'Fire delay {values["displayed_percentage"]}% shorter'
            )
        elif buff_type in {'sight', 'range', 'ammo'}:
            amount = stacking_amount(buff_type, count)
            label = {
                'sight': 'Vision', 'range': 'Weapon range', 'ammo': 'Ammo',
            }[buff_type]
            detail = f'{label} +{amount:g}'
        elif buff_type == 'self_healing':
            detail = f'Self-healing {count}% max health per tick'
        elif buff_type == 'cloak':
            detail = 'Cloaking enabled'
        elif buff_type == 'sensors':
            detail = 'Sensors enabled'
        else:
            detail = definition.get('name', 'Unit bonus')
        return f'{category} {detail}'
    if effect == 'power':
        return f'{definition.get("name", "AI power")} unlocked for hostile AI'
    return definition.get('name', 'Hostile AI strengthened')


def enemy_reward_display_name(reward, count=1):
    values = enemy_effect_values(reward, count)
    return (
        f'AI Reward: Enemy {enemy_effect_text(reward, count)} '
        f'(Stack {values["current_stacks"]}/{values["maximum_stacks"]})'
    )


def plan_enemy_trap_rewards(seed, settings, reward_pool):
    """Roll the shared deterministic standalone/AP enemy inventory."""
    settings = normalize_enemy_scaling_settings(settings)
    maximum_total = settings['maximum_total_buffs']
    if maximum_total <= 0:
        return []
    configured = [
        candidate
        for reward in reward_pool
        if reward.get('enemy_reward')
        if (candidate := configured_enemy_reward(reward, settings)) is not None
    ]
    rng = random.Random(f'{seed}:ai-trap-rewards')
    counts = {}
    traps = []
    while len(traps) < maximum_total:
        candidates = [
            reward for reward in configured
            if counts.get(reward['enemy_effect_id'], 0)
            < int(reward['enemy_maximum'])
        ]
        if not candidates:
            break
        reward = dict(rng.choice(candidates))
        effect_id = reward['enemy_effect_id']
        counts[effect_id] = counts.get(effect_id, 0) + 1
        traps.append(reward)
    return traps


def plan_enemy_check_rewards(
    seed,
    settings,
    reward_pool,
    mission_order,
    mission_checks,
):
    """Attach standalone AI bonuses to normal reward slots without replacing them."""
    inventory = plan_enemy_trap_rewards(seed, settings, reward_pool)
    if not inventory:
        return []
    slots = []
    for code in mission_order:
        for check in mission_checks.get(code, ()):
            if not isinstance(check, dict) or not check.get('id'):
                continue
            try:
                slot_count = max(
                    0,
                    int(check.get('base_reward_count', 0))
                    + int(check.get('multiplier_bonus_count', 0)),
                )
            except (TypeError, ValueError):
                slot_count = 0
            if slot_count <= 0:
                rewards = check.get('rewards')
                if isinstance(rewards, list):
                    slot_count = len(rewards)
                elif isinstance(check.get('reward'), dict):
                    slot_count = 1
            slots.extend(
                (str(code), str(check['id']))
                for _index in range(slot_count)
            )
    assignment_count = min(len(inventory), len(slots))
    if assignment_count <= 0:
        return []
    plan = []
    for index, reward in enumerate(inventory[:assignment_count]):
        # Spread a capped inventory across the full run instead of loading all
        # consequences into the first missions.
        slot_index = (
            ((2 * index + 1) * len(slots))
            // (2 * assignment_count)
        )
        code, check_id = slots[min(slot_index, len(slots) - 1)]
        plan.append({
            'mission': code,
            'check_id': check_id,
            'reward': dict(reward),
        })
    return plan
