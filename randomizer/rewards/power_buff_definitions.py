"""Reviewed reward definitions for isolated superweapon and aid-power buffs."""

from randomizer.config.static import load_static_config


POWER_BUFF_CONFIG = load_static_config('rewards/power_buffs.json')
POWER_BUFF_TYPES = tuple(
    dict(definition) for definition in POWER_BUFF_CONFIG['buff_types']
)
POWER_BUFF_TYPE_BY_ID = {
    definition['id']: definition for definition in POWER_BUFF_TYPES
}


def _normalized_ids(values):
    return frozenset(str(value).upper() for value in values)


def power_payload_buff_unit_ids(power_id):
    """Return payload TechnoTypes whose own buffs unlock with one power."""
    power_id = str(power_id or '').upper()
    for configured_id, unit_ids in POWER_BUFF_CONFIG['payload'].get(
        'buff_unit_ids_by_power', {}
    ).items():
        if str(configured_id).upper() == power_id:
            return frozenset(str(unit_id).upper() for unit_id in unit_ids)
    return frozenset()


def payload_buff_unit_ids_for_powers(power_ids):
    """Return all TechnoTypes made buff-eligible by unlocked powers."""
    return frozenset(
        unit_id
        for power_id in power_ids
        for unit_id in power_payload_buff_unit_ids(power_id)
    )


POWER_BUFF_POWER_IDS = {
    'cost': _normalized_ids(POWER_BUFF_CONFIG['cost']['power_ids']),
    'area': _normalized_ids(
        set(POWER_BUFF_CONFIG['area']['direct_fields'])
        | set(POWER_BUFF_CONFIG['area']['warhead_fields'])
    ),
    'damage': _normalized_ids(
        set(POWER_BUFF_CONFIG['damage']['direct_fields'])
        | set(POWER_BUFF_CONFIG['damage'].get('techno_fields', {}))
    ),
    'duration': _normalized_ids(
        set(POWER_BUFF_CONFIG['duration']['direct_fields'])
        | set(POWER_BUFF_CONFIG['duration']['warhead_fields'])
    ),
    'vision': _normalized_ids(
        POWER_BUFF_CONFIG['vision']['power_fields']
    ),
    'payload': _normalized_ids(
        set(POWER_BUFF_CONFIG['payload']['unit_delivery_power_ids'])
        | set(POWER_BUFF_CONFIG['payload']['paradrop_power_ids'])
        | set(POWER_BUFF_CONFIG['payload']['spy_plane_power_ids'])
        | set(POWER_BUFF_CONFIG['payload'].get('drop_pod_power_ids', ()))
    ),
}


def power_buff_type_ids(power_id):
    """Return reviewed buffs for one unlockable power, in UI order."""
    power_id = str(power_id or '').upper()
    if not power_id:
        return ()
    allowed = {
        buff_id
        for buff_id, power_ids in POWER_BUFF_POWER_IDS.items()
        if power_id in power_ids
    }
    if POWER_BUFF_CONFIG['recharge'].get('applies_to_all_powers'):
        allowed.add('recharge')
    return tuple(
        definition['id']
        for definition in POWER_BUFF_TYPES
        if definition['id'] in allowed
    )


def build_power_buff_rewards(power_rewards):
    """Create one repeatable reward per reviewed power capability."""
    rewards = []
    for power_reward in power_rewards:
        power_id = str(power_reward.get('superweapon') or '').strip()
        if not power_id:
            continue
        for buff_id in power_buff_type_ids(power_id):
            definition = POWER_BUFF_TYPE_BY_ID[buff_id]
            rewards.append({
                'name': (
                    f'{power_reward["name"]} {definition["name"]} I'
                ),
                'description': (
                    f'{power_reward["name"]}: {definition["description"]}'
                ),
                'rules': {},
                'factions': list(power_reward.get('factions') or ()),
                'kind': 'buff',
                'power_buff_type': buff_id,
                'power_name': power_reward['name'],
                'power_category': power_reward.get(
                    'power_category', 'offensive'
                ),
                'superweapon': power_id,
                'special_reward': bool(power_reward.get('special_reward')),
            })
    return rewards


def power_buff_stack_limit(reward):
    """Return the required configured cap for one power buff."""
    definition = POWER_BUFF_TYPE_BY_ID.get(reward.get('power_buff_type'))
    if not definition:
        return None
    return max(1, int(definition['maximum_stacks']))


def power_buff_effect_text(reward, count=1):
    """Return concise effect text for reward lists and Unlocks."""
    definition = POWER_BUFF_TYPE_BY_ID.get(reward.get('power_buff_type'))
    if not definition:
        return ''
    count = max(1, int(count))
    limit = power_buff_stack_limit(reward)
    if limit is not None:
        count = min(count, limit)
    buff_id = definition['id']
    if buff_id == 'recharge':
        factor = float(POWER_BUFF_CONFIG['recharge']['factor_per_stack'])
        return f'Recharge {round((1.0 - factor ** count) * 100)}% faster'
    if buff_id == 'cost':
        factor = float(POWER_BUFF_CONFIG['cost']['factor_per_stack'])
        return f'Activation cost {round((1.0 - factor ** count) * 100)}% cheaper'
    if buff_id == 'area':
        amount = float(POWER_BUFF_CONFIG['area']['amount_per_stack']) * count
        return f'Effect radius +{amount:g} cells'
    if buff_id == 'damage':
        factor = float(POWER_BUFF_CONFIG['damage']['factor_per_stack'])
        return f'Damage {round((factor ** count - 1.0) * 100)}% higher'
    if buff_id == 'duration':
        factor = float(POWER_BUFF_CONFIG['duration']['factor_per_stack'])
        return f'Effect duration {round((factor ** count - 1.0) * 100)}% longer'
    if buff_id == 'vision':
        amount = int(POWER_BUFF_CONFIG['vision']['amount_per_stack']) * count
        return f'Plane vision +{amount}'
    if buff_id == 'payload':
        return f'Delivered payload +{count}'
    return definition['name']
