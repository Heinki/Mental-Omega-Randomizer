"""Reward-weight defaults, validation, and reward classification."""

from math import isfinite


DEFAULT_REWARD_WEIGHT = 100
MAX_REWARD_WEIGHT = 100

MAIN_REWARD_WEIGHT_TYPES = (
    {
        'id': 'unit_unlocks',
        'label': 'Unit unlocks',
        'description': 'Normal unit and building access rewards.',
    },
    {
        'id': 'power_unlocks',
        'label': 'Superweapon / aid unlocks',
        'description': 'Offensive, secondary, aid, and Special power unlocks.',
    },
    {
        'id': 'special_unlocks',
        'label': 'Special unit unlocks',
        'description': 'Campaign/map-only Special unit and building access rewards.',
    },
    {
        'id': 'production',
        'label': 'Production increase',
        'description': 'Faction-wide production and construction speed rewards.',
    },
    {
        'id': 'unit_buffs',
        'label': 'Unit buffs',
        'description': 'Unit and building stat upgrades.',
    },
    {
        'id': 'power_buffs',
        'label': 'Superweapon buffs',
        'description': 'Upgrades for already-unlocked superweapons and aid powers.',
    },
)

UNIT_BUFF_WEIGHT_TYPES = (
    ('speed', 'Movement'),
    ('health', 'Health'),
    ('damage', 'Damage'),
    ('range', 'Range'),
    ('reload', 'Fire rate'),
    ('armor', 'Armor'),
    ('cost', 'Cost'),
    ('production', 'Production time'),
    ('self_healing', 'Healing'),
    ('sight', 'Vision'),
    ('ammo', 'Ammo'),
    ('passenger_capacity', 'Passenger capacity'),
    ('open_topped', 'Passenger firing'),
    ('cloak', 'Cloaking'),
    ('sensors', 'Sensors'),
    ('veteran', 'Veterancy'),
    ('build_limit', 'Unique / hero unit limit'),
    ('building_limit', 'Special building limit'),
    ('other', 'Other existing buffs'),
)

POWER_BUFF_WEIGHT_TYPES = (
    ('recharge', 'Recharge'),
    ('cost', 'Cost'),
    ('area', 'Area'),
    ('damage', 'Damage'),
    ('duration', 'Duration'),
    ('payload', 'Extra unit'),
    ('other', 'Other existing buffs'),
)

_MAIN_IDS = tuple(item['id'] for item in MAIN_REWARD_WEIGHT_TYPES)
_UNIT_BUFF_IDS = tuple(item[0] for item in UNIT_BUFF_WEIGHT_TYPES)
_POWER_BUFF_IDS = tuple(item[0] for item in POWER_BUFF_WEIGHT_TYPES)

DEFAULT_REWARD_WEIGHTS = {
    'main': {item_id: DEFAULT_REWARD_WEIGHT for item_id in _MAIN_IDS},
    'unit_buffs': {
        item_id: DEFAULT_REWARD_WEIGHT for item_id in _UNIT_BUFF_IDS
    },
    'power_buffs': {
        item_id: DEFAULT_REWARD_WEIGHT for item_id in _POWER_BUFF_IDS
    },
}


def clamp_reward_weight(value, default=DEFAULT_REWARD_WEIGHT):
    """Return one safe integer weight."""
    try:
        numeric = float(value)
        number = int(round(numeric)) if isfinite(numeric) else int(default)
    except (TypeError, ValueError):
        number = int(default)
    return max(0, min(MAX_REWARD_WEIGHT, number))


def normalize_reward_weights(value):
    """Return complete safe weights; absent legacy settings use defaults."""
    source = value if isinstance(value, dict) else {}
    normalized = {}
    for section, item_ids in (
        ('main', _MAIN_IDS),
        ('unit_buffs', _UNIT_BUFF_IDS),
        ('power_buffs', _POWER_BUFF_IDS),
    ):
        section_source = source.get(section)
        if not isinstance(section_source, dict):
            section_source = {}
        normalized[section] = {
            item_id: clamp_reward_weight(
                section_source.get(item_id, DEFAULT_REWARD_WEIGHT)
            )
            for item_id in item_ids
        }
    return normalized


def reward_weights_are_default(value):
    return normalize_reward_weights(value) == DEFAULT_REWARD_WEIGHTS


def unit_buff_weight_type(buff_type):
    buff_type = str(buff_type or '')
    return buff_type if buff_type in _UNIT_BUFF_IDS else 'other'


def power_buff_weight_type(buff_type):
    buff_type = str(buff_type or '')
    return buff_type if buff_type in _POWER_BUFF_IDS else 'other'


def main_reward_weight_type(reward):
    """Classify one canonical reward into a user-facing main weight."""
    if reward.get('kind') == 'buff':
        if reward.get('power_buff_type'):
            return 'power_buffs'
        if reward.get('global_buff') and reward.get('buff_type') == 'production':
            return 'production'
        return 'unit_buffs'
    if reward.get('kind') == 'superweapon':
        return 'power_unlocks'
    if reward.get('special_reward') or reward.get('access_category') == 'special':
        return 'special_unlocks'
    return 'unit_unlocks'


def reward_selection_weight(reward, weights):
    """Return combined main/sub-weight; zero means never selectable."""
    main_type = main_reward_weight_type(reward)
    try:
        weight = weights['main'][main_type]
        unit_weights = weights['unit_buffs']
        power_weights = weights['power_buffs']
    except (KeyError, TypeError):
        weights = normalize_reward_weights(weights)
        weight = weights['main'][main_type]
        unit_weights = weights['unit_buffs']
        power_weights = weights['power_buffs']
    if main_type == 'unit_buffs':
        sub_type = unit_buff_weight_type(reward.get('buff_type'))
        weight *= unit_weights[sub_type]
    elif main_type == 'power_buffs':
        sub_type = power_buff_weight_type(reward.get('power_buff_type'))
        weight *= power_weights[sub_type]
    return weight
