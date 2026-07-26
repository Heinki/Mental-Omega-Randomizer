"""Pure deterministic reward planning for a generated seed."""

import random

from randomizer.progression.grid import grid_opening_mission_codes
from randomizer.rewards.rules import tech_ids_for_rewards
from randomizer.rewards.catalogue import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BUFF_TARGETS,
    buff_stack_limit,
    canonical_reward,
    unit_role_equivalents,
)
from randomizer.config.tuning import REWARD_PLANNING


MAX_GLOBAL_BUFF_REPEATS_PER_SEED = int(
    REWARD_PLANNING['maximum_global_buff_repeats_per_seed']
)
GLOBAL_BUFF_REWARD_INTERVAL = int(
    REWARD_PLANNING['global_buff_reward_interval']
)


def plan_seed_rewards(
    mission_codes,
    seed,
    slots_by_code,
    *,
    progression_mode,
    grid,
    reward_factions_for_code,
    reward_pool_for_code,
    configured_reward_pool,
    starting_unlocked_tech_ids=(),
    require_access_for_unit_buffs=True,
    share_role_buffs=False,
):
    """Assign rewards without reading GUI or mutable launcher state.

    Callback inputs expose existing reward-pool policy while keeping RNG order
    and planner state isolated. Callers may therefore test planning without Tk.
    """
    rng = random.Random(f'{seed}:seed-rewards')
    used_access_names = set()
    seed_unlocked_tech_ids = (
        set(starting_unlocked_tech_ids)
        | set(ALWAYS_AVAILABLE_TECH_IDS)
    )
    buff_counts = {}
    unit_buff_counts = {}
    global_buff_counts = {}
    plan = {
        code: [None] * max(0, int(slots_by_code.get(code, 0)))
        for code in mission_codes
    }
    global_index = 0

    def unit_access_earned(unit):
        return (
            unit in seed_unlocked_tech_ids
            or (
                share_role_buffs
                and bool(
                    unit_role_equivalents(unit).intersection(
                        seed_unlocked_tech_ids
                    )
                )
            )
        )

    def buff_count_key(reward):
        unit = reward.get('unit')
        if share_role_buffs and unit and not reward.get('global_buff'):
            return (
                reward.get('buff_type'),
                tuple(sorted(unit_role_equivalents(unit))),
            )
        return reward.get('name')

    def record_unit_buff(unit):
        units = unit_role_equivalents(unit) if share_role_buffs else {unit}
        for affected_unit in units:
            unit_buff_counts[affected_unit] = (
                unit_buff_counts.get(affected_unit, 0) + 1
            )

    # Cache each faction pool once. Canonicalization and metadata are static
    # during one draw.
    pool_cache = {}
    pool_by_code = {}
    access_by_code = {}
    buffs_by_code = {}
    for code in mission_codes:
        pool_key = tuple(sorted(reward_factions_for_code(code)))
        if pool_key not in pool_cache:
            canonical_pool = tuple(
                canonical_reward(reward)
                for reward in reward_pool_for_code(code)
            )
            access_template = tuple(
                reward
                for reward in canonical_pool
                if reward.get('kind') != 'buff'
            )
            buff_metadata = tuple(
                (
                    reward,
                    buff_stack_limit(reward),
                    buff_count_key(reward),
                    reward.get('unit'),
                    bool(reward.get('global_buff') or not reward.get('unit')),
                    reward.get('name'),
                )
                for reward in canonical_pool
                if reward.get('kind') == 'buff'
            )
            pool_cache[pool_key] = (
                canonical_pool,
                access_template,
                buff_metadata,
            )
        canonical_pool, access_template, buff_metadata = pool_cache[pool_key]
        access = list(access_template)
        rng.shuffle(access)
        pool_by_code[code] = canonical_pool
        access_by_code[code] = access
        buffs_by_code[code] = buff_metadata

    def is_unit_access(reward):
        return any(
            BUFF_TARGETS.get(unit_id, {}).get('category')
            in {'infantry', 'units', 'aircraft'}
            for unit_id in tech_ids_for_rewards([reward])
        )

    def draw_access(code, unit_only=False):
        access = access_by_code.get(code, [])
        for index in range(len(access) - 1, -1, -1):
            reward = access[index]
            name = reward.get('name')
            if name in used_access_names:
                access.pop(index)
                continue
            if unit_only and not is_unit_access(reward):
                continue
            access.pop(index)
            used_access_names.add(name)
            return dict(reward)
        return None

    def draw_buff(code, prefer_global=False):
        buffs = buffs_by_code.get(code, [])
        if not buffs:
            return None

        unit_candidates = []
        global_candidates = []
        for reward, limit, count_key, unit, is_global, name in buffs:
            if limit is not None and buff_counts.get(count_key, 0) >= limit:
                continue
            if is_global:
                count = global_buff_counts.get(name, 0)
                if count < MAX_GLOBAL_BUFF_REPEATS_PER_SEED:
                    global_candidates.append(reward)
            elif not require_access_for_unit_buffs or unit_access_earned(unit):
                unit_candidates.append(reward)

        if prefer_global and global_candidates:
            candidates = global_candidates
        elif unit_candidates:
            least_buffs = min(
                unit_buff_counts.get(reward.get('unit'), 0)
                for reward in unit_candidates
            )
            candidates = [
                reward
                for reward in unit_candidates
                if unit_buff_counts.get(reward.get('unit'), 0) == least_buffs
            ]
        else:
            candidates = global_candidates
        if not candidates:
            return None

        reward = dict(rng.choice(candidates))
        if reward.get('global_buff') or not reward.get('unit'):
            name = reward.get('name')
            global_buff_counts[name] = global_buff_counts.get(name, 0) + 1
        count_key = buff_count_key(reward)
        buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
        unit = reward.get('unit')
        if unit:
            record_unit_buff(unit)
        return reward

    def draw_repeatable_fallback(code):
        pool = [dict(reward) for reward in pool_by_code.get(code, ())]
        buffs = [reward for reward in pool if reward.get('kind') == 'buff']
        candidates = []
        for reward in buffs or pool:
            limit = buff_stack_limit(reward)
            name = reward.get('name')
            if reward.get('kind') == 'superweapon' and name in used_access_names:
                continue
            count_key = buff_count_key(reward)
            if limit is not None and buff_counts.get(count_key, 0) >= limit:
                continue
            if reward.get('kind') == 'buff':
                unit = reward.get('unit')
                if (
                    require_access_for_unit_buffs
                    and unit
                    and not reward.get('global_buff')
                    and not unit_access_earned(unit)
                ):
                    continue
            candidates.append(reward)
        if not candidates:
            candidates = [
                dict(reward)
                for reward in configured_reward_pool()
                if reward.get('kind') == 'buff'
                and (
                    not require_access_for_unit_buffs
                    or reward.get('global_buff')
                    or not reward.get('unit')
                    or unit_access_earned(reward.get('unit'))
                )
            ]
        if not candidates:
            return None
        reward = dict(rng.choice(candidates))
        if reward.get('kind') == 'buff':
            count_key = buff_count_key(reward)
            buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
            unit = reward.get('unit')
            if unit:
                record_unit_buff(unit)
        return reward

    slot_order = []
    reserved_opening_slots = set()
    if progression_mode == 'Grid Mode' and isinstance(grid, dict):
        for code in grid_opening_mission_codes(grid):
            if code in plan and plan[code]:
                slot = (code, 0)
                reserved_opening_slots.add(slot)
                slot_order.append((code, 0, True))

        remaining_slots = [
            (code, slot_index, False)
            for code in mission_codes
            for slot_index in range(len(plan[code]))
            if (code, slot_index) not in reserved_opening_slots
        ]
        rng.shuffle(remaining_slots)
        slot_order.extend(remaining_slots)
    else:
        slot_order = [
            (code, slot_index, False)
            for code in mission_codes
            for slot_index in range(len(plan[code]))
        ]

    for code, slot_index, force_unit_access in slot_order:
        reward = None
        prefer_global = (
            (global_index + 1) % GLOBAL_BUFF_REWARD_INTERVAL == 0
        )
        if force_unit_access:
            reward = draw_access(code, unit_only=True)
        if reward is None and not force_unit_access and (
            global_index % 5 == 4 or prefer_global
        ):
            reward = draw_buff(code, prefer_global=prefer_global)
        if reward is None:
            reward = draw_access(code)
        if reward is None:
            reward = draw_buff(code, prefer_global=prefer_global)
        if reward is None:
            reward = draw_repeatable_fallback(code)
        if reward is not None:
            plan[code][slot_index] = reward
            seed_unlocked_tech_ids.update(tech_ids_for_rewards([reward]))
        global_index += 1

    return {
        code: [reward for reward in rewards if reward is not None]
        for code, rewards in plan.items()
    }
