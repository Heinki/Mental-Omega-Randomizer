"""Starting-reward setting normalization and pool classification."""


DEFAULT_STARTING_REWARD_COUNT = 0
MAX_STARTING_REWARD_COUNT = 9999
STARTING_REWARD_TYPE_DEFINITIONS = (
    {
        'id': 'access',
        'label': 'Units / buildings',
        'description': 'Normal and Special unit, defense, and building unlocks.',
    },
    {
        'id': 'superweapon',
        'label': 'Offensive superweapons',
        'description': 'Offensive superweapon unlocks.',
    },
    {
        'id': 'secondary_superweapon',
        'label': 'Secondary powers',
        'description': 'Secondary superweapon unlocks.',
    },
    {
        'id': 'aid_power',
        'label': 'Support / aid powers',
        'description': 'Support, aid, drop, mine, and grid power unlocks.',
    },
)
DEFAULT_STARTING_REWARD_TYPES = tuple(
    definition['id'] for definition in STARTING_REWARD_TYPE_DEFINITIONS
)
STARTING_UNLOCK_CATEGORY_LABELS = (
    'Units',
    'Buildings',
    'Superweapons',
    'Support powers',
    'Other unlocks',
)


def normalize_starting_reward_count(value):
    """Return one bounded nonnegative starting-reward amount."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_STARTING_REWARD_COUNT
    return max(0, min(MAX_STARTING_REWARD_COUNT, count))


def normalize_starting_reward_types(value):
    """Return known starting-reward categories in stable display order."""
    selected = (
        {str(item) for item in value}
        if isinstance(value, (list, tuple, set))
        else set(DEFAULT_STARTING_REWARD_TYPES)
    )
    return [
        reward_type
        for reward_type in DEFAULT_STARTING_REWARD_TYPES
        if reward_type in selected
    ]


def normalize_starting_unlock_reward_names(value):
    """Return unique portable reward names in saved order."""
    names = value if isinstance(value, (list, tuple, set)) else ()
    return list(dict.fromkeys(
        str(name).strip() for name in names if str(name).strip()
    ))


def starting_reward_type(reward):
    """Classify one canonical reward for starting-pool filtering."""
    if reward.get('kind') == 'buff':
        # Buffs remain normal progression rewards.  Returning no family also
        # blocks stale portable settings which still name removed buff types.
        return None
    if reward.get('kind') == 'superweapon':
        return {
            'secondary': 'secondary_superweapon',
            'aid': 'aid_power',
        }.get(reward.get('power_category'), 'superweapon')
    return 'access'


def filter_starting_reward_pool(pool, allowed_types):
    """Keep only user-selected starting-reward categories."""
    allowed = set(normalize_starting_reward_types(allowed_types))
    return [reward for reward in pool if starting_reward_type(reward) in allowed]
