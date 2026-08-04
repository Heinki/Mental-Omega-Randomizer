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
from randomizer.rewards.weights import (
    main_reward_weight_type,
    normalize_reward_weights,
    power_buff_weight_type,
    reward_selection_weight,
    reward_weights_are_default,
    unit_buff_weight_type,
)


GLOBAL_BUFF_REWARD_INTERVAL = int(
    REWARD_PLANNING['global_buff_reward_interval']
)
MAX_REWARDS_ACHIEVED_MESSAGE = 'Max rewards achieved.'
MAX_REWARDS_ACHIEVED_REWARD = {
    'name': MAX_REWARDS_ACHIEVED_MESSAGE,
    'description': (
        'Every enabled reward is already unlocked or at its maximum level.'
    ),
    'rules': {},
    'factions': [],
    'kind': 'message',
    'max_rewards_achieved': True,
}


def is_max_rewards_achieved_reward(reward):
    return bool(
        isinstance(reward, dict)
        and reward.get('max_rewards_achieved') is True
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
    reward_pool_cache_key_for_code=None,
    allow_cross_pool_fallback=True,
    starting_unlocked_tech_ids=(),
    starting_unlocked_power_ids=(),
    initial_rewards=(),
    require_access_for_unit_buffs=True,
    share_role_buffs=False,
    reward_weights=None,
    rng_namespace='seed-rewards',
    avoid_unlocked_access=False,
    blocked_reward_names=(),
    reserved_rewards=(),
):
    """Assign rewards without reading GUI or mutable launcher state.

    Callback inputs expose existing reward-pool policy while keeping RNG order
    and planner state isolated. Callers may therefore test planning without Tk.
    """
    rng = random.Random(f'{seed}:{rng_namespace}')
    used_access_names = set()
    seed_unlocked_tech_ids = (
        set(starting_unlocked_tech_ids)
        | set(ALWAYS_AVAILABLE_TECH_IDS)
    )
    seed_unlocked_power_ids = {
        str(power_id).upper()
        for power_id in starting_unlocked_power_ids
        if str(power_id).strip()
    }
    buff_counts = {}
    unit_buff_counts = {}
    power_buff_counts = {}
    reward_weights = normalize_reward_weights(reward_weights)
    use_weighted_draws = not reward_weights_are_default(reward_weights)
    blocked_names = {
        canonical_reward({'name': str(name)}).get('name', str(name))
        for name in blocked_reward_names
        if str(name).strip()
    }
    reward_metadata = {}
    buff_eligible_unit_ids = set(seed_unlocked_tech_ids)
    buff_equivalents_by_unit = {}
    plan = {
        code: [None] * max(0, int(slots_by_code.get(code, 0)))
        for code in mission_codes
    }
    global_index = 0

    def track_buff_target_access(unit):
        if not unit or unit in buff_equivalents_by_unit:
            return
        equivalents = (
            unit_role_equivalents(unit)
            if share_role_buffs
            else frozenset((unit,))
        )
        buff_equivalents_by_unit[unit] = equivalents
        if not equivalents.isdisjoint(seed_unlocked_tech_ids):
            buff_eligible_unit_ids.add(unit)

    def reward_prerequisites_met(reward):
        metadata = reward_metadata.get(id(reward), {})
        required_any = metadata.get('required_any')
        if required_any is None:
            required_any = frozenset(
                str(unit_id).upper()
                for unit_id in reward.get('requires_any_tech_ids', ())
                if str(unit_id).strip()
            )
        return not required_any or any(
            unit_id in buff_eligible_unit_ids for unit_id in required_any
        )

    def access_already_unlocked(reward):
        if not avoid_unlocked_access or reward.get('kind') == 'buff':
            return False
        power_id = str(reward.get('superweapon') or '').upper()
        if power_id and power_id in (
            seed_unlocked_power_ids | reserved_power_ids
        ):
            return True
        metadata = reward_metadata.get(id(reward), {})
        reward_tech_ids = metadata.get('tech_ids')
        if reward_tech_ids is None:
            reward_tech_ids = tech_ids_for_rewards([reward])
        return bool(set(reward_tech_ids).intersection(
            seed_unlocked_tech_ids | reserved_tech_ids
        ))

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

    def buff_target_count(reward):
        power_id = str(reward.get('superweapon') or '').upper()
        if reward.get('power_buff_type') and power_id:
            return power_buff_counts.get(power_id, 0)
        return unit_buff_counts.get(reward.get('unit'), 0)

    def record_buff_target(reward):
        power_id = str(reward.get('superweapon') or '').upper()
        if reward.get('power_buff_type') and power_id:
            power_buff_counts[power_id] = power_buff_counts.get(power_id, 0) + 1
            return
        unit = reward.get('unit')
        if unit:
            record_unit_buff(unit)

    # Regeneration can preserve already released checks. Seed planner state from
    # those rewards so future slots cannot repeat access or exceed buff caps.
    canonical_initial_rewards = tuple(
        canonical_reward(reward)
        for reward in initial_rewards
        if not is_max_rewards_achieved_reward(reward)
    )
    seed_unlocked_tech_ids.update(
        tech_ids_for_rewards(canonical_initial_rewards)
    )
    for reward in canonical_initial_rewards:
        if reward.get('kind') == 'buff':
            count_key = buff_count_key(reward)
            buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
            record_buff_target(reward)
            continue
        name = reward.get('name')
        if name:
            used_access_names.add(name)
        if reward.get('kind') == 'superweapon' and reward.get('superweapon'):
            seed_unlocked_power_ids.add(
                str(reward['superweapon']).upper()
            )

    # Future rewards can reserve unique access names and finite buff capacity
    # without making their technology available to this draw. Mission bonus
    # streams use this to stay valid at their own completion point while never
    # duplicating base-plan access or exceeding later stack caps.
    canonical_reserved_rewards = tuple(
        canonical_reward(reward)
        for reward in reserved_rewards
        if not is_max_rewards_achieved_reward(reward)
    )
    reserved_tech_ids = set(tech_ids_for_rewards(
        canonical_reserved_rewards
    ))
    reserved_power_ids = {
        str(reward.get('superweapon') or '').upper()
        for reward in canonical_reserved_rewards
        if reward.get('kind') == 'superweapon'
        and str(reward.get('superweapon') or '').strip()
    }
    for reward in canonical_reserved_rewards:
        if reward.get('kind') == 'buff':
            count_key = buff_count_key(reward)
            buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
            record_buff_target(reward)
            continue
        name = reward.get('name')
        if name:
            used_access_names.add(name)

    # Cache each faction pool once. Canonicalization and metadata are static
    # during one draw.
    pool_cache = {}
    pool_by_code = {}
    access_by_code = {}
    buffs_by_code = {}
    active_buff_pool_by_key = {}
    active_buff_pools_by_id = {}
    buff_pool_ids_by_count_key = {}
    buff_pool_id_by_code = {}
    global_buff_entries_by_pool_id = {}
    balanced_candidates_by_pool_id = {}
    for code in mission_codes:
        pool_key = (
            reward_pool_cache_key_for_code(code)
            if reward_pool_cache_key_for_code is not None
            else tuple(sorted(reward_factions_for_code(code)))
        )
        if pool_key not in pool_cache:
            canonical_pool = tuple(
                reward
                for reward in map(canonical_reward, reward_pool_for_code(code))
                if reward.get('name') not in blocked_names
            )
            access_template = tuple(
                reward
                for reward in canonical_pool
                if reward.get('kind') != 'buff'
            )
            buff_metadata = []
            for reward in canonical_pool:
                tech_ids = frozenset(tech_ids_for_rewards([reward]))
                unit = reward.get('unit')
                power_id = str(reward.get('superweapon') or '').upper()
                main_type = (
                    main_reward_weight_type(reward)
                    if use_weighted_draws
                    else None
                )
                metadata = {
                    'tech_ids': tech_ids,
                    'unit_access': any(
                        BUFF_TARGETS.get(unit_id, {}).get('category')
                        in {'infantry', 'units', 'aircraft'}
                        for unit_id in tech_ids
                    ),
                    'is_buff': reward.get('kind') == 'buff',
                    'name': reward.get('name'),
                    'required_any': frozenset(
                        str(unit_id).upper()
                        for unit_id in reward.get(
                            'requires_any_tech_ids', ()
                        )
                        if str(unit_id).strip()
                    ),
                    'selection_weight': reward_selection_weight(
                        reward, reward_weights
                    ) if use_weighted_draws else 1,
                    'main_type': main_type,
                    'target_key': (
                        ('power', power_id)
                        if reward.get('power_buff_type') and power_id
                        else ('unit', unit)
                    ),
                    'sub_type': (
                        unit_buff_weight_type(reward.get('buff_type'))
                        if main_type == 'unit_buffs'
                        else power_buff_weight_type(
                            reward.get('power_buff_type')
                        )
                        if main_type == 'power_buffs'
                        else None
                    ),
                }
                track_buff_target_access(unit)
                for required_unit_id in metadata['required_any']:
                    track_buff_target_access(required_unit_id)
                reward_metadata[id(reward)] = metadata
                if reward.get('kind') != 'buff':
                    continue
                is_global = bool(
                    reward.get('global_buff')
                    or (not unit and not reward.get('power_buff_type'))
                )
                metadata.update({
                    'limit': buff_stack_limit(reward),
                    'count_key': buff_count_key(reward),
                    'unit': unit,
                    'power_id': power_id,
                    'is_global': is_global,
                    'is_power_buff': bool(reward.get('power_buff_type')),
                })
                buff_metadata.append((
                    reward,
                    metadata['limit'],
                    metadata['count_key'],
                    unit,
                    power_id,
                    is_global,
                    metadata['is_power_buff'],
                ))
            buff_metadata = tuple(buff_metadata)
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
        active_buffs = active_buff_pool_by_key.get(pool_key)
        if active_buffs is None:
            active_buffs = [
                entry
                for entry in buff_metadata
                if (
                    entry[1] is None
                    or buff_counts.get(entry[2], 0) < entry[1]
                )
            ]
            active_buff_pool_by_key[pool_key] = active_buffs
            pool_id = id(active_buffs)
            active_buff_pools_by_id[pool_id] = active_buffs
            for entry in active_buffs:
                buff_pool_ids_by_count_key.setdefault(
                    entry[2], set()
                ).add(pool_id)
            global_buff_entries_by_pool_id[pool_id] = [
                entry for entry in active_buffs if entry[5]
            ]
        buffs_by_code[code] = active_buffs
        buff_pool_id_by_code[code] = id(active_buffs)

    def retire_capped_buff(count_key, limit):
        if limit is None or buff_counts.get(count_key, 0) < limit:
            return
        pool_ids = buff_pool_ids_by_count_key.get(count_key, ())
        count = buff_counts.get(count_key, 0)
        still_active = False
        for pool_id in pool_ids:
            active_buffs = active_buff_pools_by_id[pool_id]
            active_buffs[:] = [
                entry for entry in active_buffs
                if (
                    entry[2] != count_key
                    or entry[1] is None
                    or count < entry[1]
                )
            ]
            still_active = still_active or any(
                entry[2] == count_key for entry in active_buffs
            )
        if not still_active:
            buff_pool_ids_by_count_key.pop(count_key, None)

    def affected_target_keys(target_key):
        target_type, target_id = target_key
        if target_type == 'power':
            return {(target_type, target_id)}
        units = (
            unit_role_equivalents(target_id)
            if share_role_buffs and target_id
            else (target_id,)
        )
        return {('unit', unit) for unit in units}

    def balanced_candidates(code):
        pool_id = buff_pool_id_by_code[code]
        cached = balanced_candidates_by_pool_id.get(pool_id)
        if cached is not None:
            return cached
        candidates = []
        least_buffs = None
        for (
            reward,
            limit,
            count_key,
            unit,
            power_id,
            is_global,
            is_power_buff,
        ) in buffs_by_code.get(code, ()):
            if is_global:
                continue
            if limit is not None and buff_counts.get(count_key, 0) >= limit:
                continue
            if is_power_buff:
                if power_id not in seed_unlocked_power_ids:
                    continue
                target_count = power_buff_counts.get(power_id, 0)
            else:
                if (
                    require_access_for_unit_buffs
                    and unit not in buff_eligible_unit_ids
                ):
                    continue
                target_count = unit_buff_counts.get(unit, 0)
            if least_buffs is None or target_count < least_buffs:
                least_buffs = target_count
                candidates = [(reward, reward_metadata[id(reward)]['target_key'])]
            elif target_count == least_buffs:
                candidates.append((
                    reward,
                    reward_metadata[id(reward)]['target_key'],
                ))
        balanced_candidates_by_pool_id[pool_id] = candidates
        return candidates

    def record_drawn_buff(reward):
        metadata = reward_metadata.get(id(reward), {})
        count_key = metadata.get('count_key')
        if count_key is None:
            count_key = buff_count_key(reward)
        buff_counts[count_key] = buff_counts.get(count_key, 0) + 1
        record_buff_target(reward)
        limit = metadata.get('limit')
        if 'limit' not in metadata:
            limit = buff_stack_limit(reward)
        retire_capped_buff(count_key, limit)

    def is_unit_access(reward):
        metadata = reward_metadata.get(id(reward))
        if metadata is not None:
            return metadata['unit_access']
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
            if not reward_prerequisites_met(reward):
                continue
            if access_already_unlocked(reward):
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

        pool_id = buff_pool_id_by_code[code]
        global_candidates = [
            reward
            for reward, limit, count_key, *_rest
            in global_buff_entries_by_pool_id.get(pool_id, ())
            if limit is None or buff_counts.get(count_key, 0) < limit
        ]
        unit_candidates = balanced_candidates(code)

        if prefer_global and global_candidates:
            candidates = global_candidates
        elif unit_candidates:
            candidates = unit_candidates
        else:
            candidates = global_candidates
        if not candidates:
            return None
        if candidates is unit_candidates:
            source_reward, selected_target_key = rng.choice(candidates)
        else:
            source_reward = rng.choice(candidates)
            selected_target_key = None
        reward = dict(source_reward)
        record_drawn_buff(reward)
        if candidates is unit_candidates:
            affected = affected_target_keys(selected_target_key)
            remaining_candidates = [
                candidate for candidate in unit_candidates
                if candidate[1] not in affected
            ]
            if remaining_candidates:
                balanced_candidates_by_pool_id[pool_id] = remaining_candidates
            else:
                balanced_candidates_by_pool_id.pop(pool_id, None)
            for other_pool_id in tuple(balanced_candidates_by_pool_id):
                if other_pool_id != pool_id:
                    balanced_candidates_by_pool_id.pop(other_pool_id, None)
        return reward

    configured_buff_metadata = None

    def configured_buffs():
        nonlocal configured_buff_metadata
        if configured_buff_metadata is None:
            configured_buff_metadata = []
            for configured in configured_reward_pool():
                reward = canonical_reward(configured)
                if (
                    reward.get('kind') != 'buff'
                    or reward.get('name') in blocked_names
                ):
                    continue
                configured_buff_metadata.append((
                    reward,
                    buff_stack_limit(reward),
                    buff_count_key(reward),
                    reward.get('unit'),
                    str(reward.get('superweapon') or '').upper(),
                ))
                track_buff_target_access(reward.get('unit'))
            configured_buff_metadata = tuple(configured_buff_metadata)
        return configured_buff_metadata

    def draw_repeatable_fallback(code):
        pool = pool_by_code.get(code, ())
        buffs = [reward for reward in pool if reward.get('kind') == 'buff']
        candidates = []
        for reward in buffs or pool:
            metadata = reward_metadata.get(id(reward), {})
            limit = metadata.get('limit')
            if reward.get('kind') != 'buff':
                limit = buff_stack_limit(reward)
            name = reward.get('name')
            if (
                reward.get('kind') != 'buff'
                and name in used_access_names
            ):
                continue
            if not reward_prerequisites_met(reward):
                continue
            if access_already_unlocked(reward):
                continue
            count_key = metadata.get('count_key', name)
            if limit is not None and buff_counts.get(count_key, 0) >= limit:
                continue
            if reward.get('kind') == 'buff':
                unit = metadata.get('unit')
                power_id = metadata.get('power_id', '')
                if (
                    reward.get('power_buff_type')
                    and power_id not in seed_unlocked_power_ids
                ):
                    continue
                if (
                    require_access_for_unit_buffs
                    and unit
                    and not reward.get('global_buff')
                    and unit not in buff_eligible_unit_ids
                ):
                    continue
            candidates.append(reward)
        if not candidates and allow_cross_pool_fallback:
            for reward, limit, count_key, unit, power_id in configured_buffs():
                if not reward_prerequisites_met(reward):
                    continue
                if (
                    limit is not None
                    and buff_counts.get(count_key, 0) >= limit
                ):
                    continue
                if (
                    reward.get('power_buff_type')
                    and power_id not in seed_unlocked_power_ids
                ):
                    continue
                if (
                    require_access_for_unit_buffs
                    and unit
                    and not reward.get('global_buff')
                    and not reward.get('power_buff_type')
                    and unit not in buff_eligible_unit_ids
                ):
                    continue
                candidates.append(reward)
        if not candidates:
            return None
        reward = dict(rng.choice(candidates))
        if reward.get('kind') == 'buff':
            record_drawn_buff(reward)
            balanced_candidates_by_pool_id.clear()
        else:
            used_access_names.add(reward.get('name'))
        return reward

    def weighted_choice(items, weight_for):
        """Draw from relative weights normalized by their active total."""
        weighted = [
            (item, max(0, int(weight_for(item))))
            for item in items
        ]
        weighted = [(item, weight) for item, weight in weighted if weight > 0]
        total = sum(weight for _item, weight in weighted)
        if total <= 0:
            return None
        roll = rng.randrange(total)
        for item, weight in weighted:
            if roll < weight:
                return item
            roll -= weight
        return weighted[-1][0]

    def eligible_weighted_rewards(code, unit_only=False):
        candidates = []
        for reward in pool_by_code.get(code, ()):
            metadata = reward_metadata[id(reward)]
            if metadata['selection_weight'] <= 0:
                continue
            if not metadata['is_buff']:
                if metadata['name'] in used_access_names:
                    continue
                if not reward_prerequisites_met(reward):
                    continue
                if access_already_unlocked(reward):
                    continue
                if unit_only and not metadata['unit_access']:
                    continue
                candidates.append(reward)
                continue
            if unit_only:
                continue
            limit = metadata['limit']
            count_key = metadata['count_key']
            if limit is not None and buff_counts.get(count_key, 0) >= limit:
                continue
            power_id = metadata['power_id']
            if (
                metadata['is_power_buff']
                and power_id not in seed_unlocked_power_ids
            ):
                continue
            unit = metadata['unit']
            if (
                require_access_for_unit_buffs
                and unit
                and not metadata['is_global']
                and unit not in buff_eligible_unit_ids
            ):
                continue
            candidates.append(reward)
        return candidates

    def draw_weighted(code, unit_only=False):
        candidates = eligible_weighted_rewards(code, unit_only=unit_only)
        groups = {}
        for candidate in candidates:
            groups.setdefault(
                reward_metadata[id(candidate)]['main_type'], []
            ).append(candidate)
        main_type = weighted_choice(
            list(groups),
            lambda item: reward_weights['main'][item],
        )
        if main_type is None:
            return None
        candidates = groups[main_type]

        if main_type == 'unit_buffs':
            subgroups = {}
            for candidate in candidates:
                subgroups.setdefault(
                    reward_metadata[id(candidate)]['sub_type'], []
                ).append(candidate)
            sub_type = weighted_choice(
                list(subgroups),
                lambda item: reward_weights['unit_buffs'][item],
            )
            candidates = subgroups.get(sub_type, [])
        elif main_type == 'power_buffs':
            subgroups = {}
            for candidate in candidates:
                subgroups.setdefault(
                    reward_metadata[id(candidate)]['sub_type'],
                    [],
                ).append(candidate)
            sub_type = weighted_choice(
                list(subgroups),
                lambda item: reward_weights['power_buffs'][item],
            )
            candidates = subgroups.get(sub_type, [])

        if not candidates:
            return None
        if main_type in {'unit_buffs', 'power_buffs'}:
            least_buffs = None
            least_candidates = []
            for candidate in candidates:
                metadata = reward_metadata[id(candidate)]
                target_count = (
                    power_buff_counts.get(metadata['power_id'], 0)
                    if metadata['is_power_buff']
                    else unit_buff_counts.get(metadata['unit'], 0)
                )
                if least_buffs is None or target_count < least_buffs:
                    least_buffs = target_count
                    least_candidates = [candidate]
                elif target_count == least_buffs:
                    least_candidates.append(candidate)
            candidates = least_candidates
        reward = dict(rng.choice(candidates))
        if reward.get('kind') == 'buff':
            record_drawn_buff(reward)
            balanced_candidates_by_pool_id.clear()
        else:
            used_access_names.add(reward.get('name'))
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
        if use_weighted_draws:
            reward = draw_weighted(code, unit_only=force_unit_access)
            if reward is None and force_unit_access:
                reward = draw_weighted(code)
        else:
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
            unlocked_tech_ids = tech_ids_for_rewards([reward])
            if not unlocked_tech_ids.issubset(seed_unlocked_tech_ids):
                new_tech_ids = unlocked_tech_ids - seed_unlocked_tech_ids
                seed_unlocked_tech_ids.update(unlocked_tech_ids)
                buff_eligible_unit_ids.update(new_tech_ids)
                for unit, equivalents in buff_equivalents_by_unit.items():
                    if not new_tech_ids.isdisjoint(equivalents):
                        buff_eligible_unit_ids.add(unit)
                balanced_candidates_by_pool_id.clear()
            if (
                reward.get('kind') == 'superweapon'
                and reward.get('superweapon')
            ):
                power_id = str(reward['superweapon']).upper()
                if power_id not in seed_unlocked_power_ids:
                    seed_unlocked_power_ids.add(power_id)
                    balanced_candidates_by_pool_id.clear()
        else:
            # Preserve slot positions so one exhausted draw cannot shift later
            # mission/check assignments. UI compacts repeated markers to one
            # visible message per check.
            plan[code][slot_index] = dict(MAX_REWARDS_ACHIEVED_REWARD)
        global_index += 1

    return plan
