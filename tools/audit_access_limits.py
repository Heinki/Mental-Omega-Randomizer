"""Regression checks for optional unit/power access limits."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.rewards.access_limits import normalize_access_limits
from randomizer.rewards.definitions import REWARD_POOL
from randomizer.rewards.planning import plan_seed_rewards
from randomizer.rewards.rules import tech_ids_for_rewards


MISSION_CODES = ('A', 'B', 'C')
SLOTS_BY_CODE = {'A': 24, 'B': 16, 'C': 20}
LEGACY_PLAN_SHA256 = (
    '228f2ca516c7ec5369bb721bf0f1c6b9334e6e436c662d54e156114b6c18c9ef'
)


def make_plan(
    *, seed='ACCESS-LIMIT-PARITY', limits=None, initial=(), weights=None
):
    return plan_seed_rewards(
        MISSION_CODES,
        seed,
        SLOTS_BY_CODE,
        progression_mode='Linear',
        grid=None,
        reward_factions_for_code=lambda _code: (),
        reward_pool_for_code=lambda _code: REWARD_POOL,
        configured_reward_pool=lambda: REWARD_POOL,
        initial_rewards=initial,
        reward_weights=weights,
        access_limits=limits,
    )


def all_rewards(plan):
    return [reward for code in MISSION_CODES for reward in plan[code]]


def access_identities(rewards):
    unit_ids = set()
    power_ids = set()
    for reward in rewards:
        if reward.get('kind') == 'buff':
            continue
        if reward.get('kind') == 'superweapon':
            power_id = str(reward.get('superweapon') or '').upper()
            if power_id:
                power_ids.add(power_id)
            continue
        unit_ids.update(tech_ids_for_rewards([reward]))
    return unit_ids, power_ids


def main():
    assert normalize_access_limits(None) == {
        'enabled': False,
        'units': 1,
        'powers': 1,
    }
    assert normalize_access_limits({
        'enabled': True,
        'units': 0,
        'powers': 'invalid',
    }) == {
        'enabled': True,
        'units': 1,
        'powers': 1,
    }

    legacy_plan = make_plan()
    serialized = json.dumps(
        legacy_plan,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    assert hashlib.sha256(serialized).hexdigest() == LEGACY_PLAN_SHA256

    limited_plan = make_plan(
        seed='ACCESS-LIMIT-ON',
        limits={'enabled': True, 'units': 3, 'powers': 2},
    )
    limited_rewards = all_rewards(limited_plan)
    unit_ids, power_ids = access_identities(limited_rewards)
    assert len(unit_ids) == 3
    assert len(power_ids) == 2
    assert sum(reward.get('kind') == 'buff' for reward in limited_rewards) > 0

    weighted_plan = make_plan(
        seed='ACCESS-LIMIT-WEIGHTED',
        limits={'enabled': True, 'units': 4, 'powers': 3},
        weights={'main': {'unit_unlocks': 99}},
    )
    weighted_ids = access_identities(all_rewards(weighted_plan))
    assert len(weighted_ids[0]) <= 4
    assert len(weighted_ids[1]) <= 3

    initial_unit = next(
        reward for reward in REWARD_POOL
        if reward.get('kind') not in {'buff', 'superweapon'}
        and len(tech_ids_for_rewards([reward])) == 1
    )
    initial_power = next(
        reward for reward in REWARD_POOL
        if reward.get('kind') == 'superweapon'
    )
    initial = (initial_unit, initial_power)
    continued_plan = make_plan(
        seed='ACCESS-LIMIT-INITIAL',
        limits={'enabled': True, 'units': 1, 'powers': 1},
        initial=initial,
    )
    continued_ids = access_identities(initial + tuple(all_rewards(continued_plan)))
    assert len(continued_ids[0]) == 1
    assert len(continued_ids[1]) == 1

    print(
        'Access-limit audit passed: disabled planning unchanged; '
        'unit/power caps and initial-reward accounting verified.'
    )


if __name__ == '__main__':
    main()
