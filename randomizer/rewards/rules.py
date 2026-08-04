"""Translate serialized rewards into launch-time technology/buff scope."""

from randomizer.rewards.catalogue import (
    canonical_reward,
    canonical_rewards,
    unit_role_equivalents,
)


def tech_ids_for_rewards(rewards):
    """Return TechnoType sections unlocked by reward rule payloads."""
    tech_ids = set()
    for reward in rewards:
        reward = canonical_reward(reward)
        for section, values in reward.get('rules', {}).items():
            if any(key.lower() == 'techlevel' for key in values):
                tech_ids.add(section.upper())
    return tech_ids


def unlocked_reward_tech_ids(rewards):
    """Return access IDs, excluding stat-only buff rewards."""
    tech_ids = set()
    for reward in canonical_rewards(rewards):
        if reward.get('kind') == 'buff':
            continue
        tech_ids.update(tech_ids_for_rewards([reward]))
    return tech_ids


def buffs_with_unlocked_access(
    rewards,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
):
    """Filter unit buffs to tech already available for this launch."""
    unlocked = unlocked_reward_tech_ids(rewards)
    unlocked.update(
        str(unit_id).upper()
        for unit_id in (additional_unlocked_tech_ids or [])
    )
    filtered = []
    for reward in canonical_rewards(rewards):
        if reward.get('kind') != 'buff':
            filtered.append(reward)
            continue
        unit_id = (reward.get('unit') or '').upper()
        equivalents = unit_role_equivalents(unit_id)
        equivalent_is_buff_eligible = (
            share_basic_equivalent_buffs
            and len(equivalents) > 1
            and bool(unlocked.intersection(equivalents))
        )
        if (
            not require_unlocked_access
            or reward.get('global_buff')
            or not unit_id
            or unit_id in unlocked
            or equivalent_is_buff_eligible
        ):
            filtered.append(reward)
    return filtered


def expand_equivalent_role_buffs(rewards, enabled=False, allowed_unit_ids=None):
    """Apply each active unit buff to allowed cross-faction role peers.

    Expanded copies are launch-only canonical rewards. Keeping that marker is
    important: later canonicalization by serialized reward name would otherwise
    turn every peer back into the original unit and lose the access boundary.
    """
    if not enabled:
        return list(rewards)
    allowed = (
        None
        if allowed_unit_ids is None
        else {str(unit_id).upper() for unit_id in allowed_unit_ids}
    )
    expanded = []
    for reward in rewards:
        expanded.append(reward)
        if reward.get('kind') != 'buff' or reward.get('mission_assistance'):
            continue
        for unit_id in sorted(unit_role_equivalents(reward.get('unit'))):
            if unit_id == reward.get('unit'):
                continue
            if allowed is not None and unit_id.upper() not in allowed:
                continue
            equivalent = dict(reward)
            equivalent['unit'] = unit_id
            equivalent['_runtime_canonical'] = True
            expanded.append(equivalent)
    return expanded
