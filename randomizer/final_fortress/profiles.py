"""Normal progression and an opt-in, source-only local testing profile."""

import os

from randomizer.core.paths import APP_DIR, FROZEN

from .config import validate_config
from .perks import ranks
from .state import new_state, normalize_state


STANDARD_PROFILE = 'Standard'
ALL_UNLOCKS_PROFILE = 'Testing (all unlocks)'
LOCAL_TESTING_ENABLED = (
    not FROZEN
    and os.environ.get('RANDOMIZER_FINAL_FORTRESS_DEBUG') == '1'
    and (APP_DIR / 'final_fortress_testing_state.json').is_file()
)
PROFILE_PATHS = {
    STANDARD_PROFILE: APP_DIR / 'final_fortress_state.json',
}
if LOCAL_TESTING_ENABLED:
    PROFILE_PATHS[ALL_UNLOCKS_PROFILE] = APP_DIR / 'final_fortress_testing_state.json'


def require_local_testing():
    """Compiled builds cannot create or upgrade all-unlocks profiles."""
    if not LOCAL_TESTING_ENABLED:
        raise ValueError(
            'Testing profiles require a source checkout, RANDOMIZER_FINAL_FORTRESS_DEBUG=1, '
            'and an existing local testing save.'
        )


def all_unlocks_state(config):
    """Create purchased maximum ranks without inventing gameplay receipts."""
    require_local_testing()
    validate_config(config)
    state = new_state()
    state['owned_perks'] = [perk['id'] for perk in config['perks']]
    state['selected_perks'] = list(state['owned_perks'])
    state['perk_ranks'] = {perk['id']: len(ranks(perk)) for perk in config['perks']}
    state['preferences'].update(player_country='USSR', workspace_selected=True)
    return normalize_state(state)
