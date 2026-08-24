"""Resolve the active standalone Shop loadout from persisted state."""

from randomizer.missions.tier_one import (
    expanded_tier_one_defense_ids,
    expanded_tier_one_unit_ids,
)
from randomizer.rewards.rules import tech_ids_for_rewards

from .catalogue import canonical_reward_for_id
from .archipelago import ap_automatic_reward_ids


def active_shop_reward_ids(run):
    """Return canonical reward IDs selected or purchased for this run."""
    if run is None:
        return ()
    reward_ids = [
        *run.selected_permanent_units,
        *ap_automatic_reward_ids(run.ap_entitlements_snapshot),
        *(buff.reward_id for buff in run.permanent_buffs_snapshot),
        *(purchase.reward_id for purchase in run.run_purchases),
        *(buff.reward_id for buff in run.run_buffs),
        *(buff.reward_id for buff in run.starting_draft_buffs),
    ]
    return tuple(dict.fromkeys(str(reward_id) for reward_id in reward_ids))


def active_shop_rewards(run):
    """Return canonical launch rewards, preserving purchased stack counts."""
    if run is None:
        return ()
    reward_ids = [
        *run.selected_permanent_units,
        *ap_automatic_reward_ids(run.ap_entitlements_snapshot),
    ]
    for buff in run.permanent_buffs_snapshot:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    for purchase in run.run_purchases:
        reward_ids.extend([purchase.reward_id] * purchase.quantity)
    for buff in run.run_buffs:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    for buff in run.starting_draft_buffs:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    return tuple(canonical_reward_for_id(reward_id) for reward_id in reward_ids)


def active_shop_tech_ids(run):
    if run is None:
        return ()
    tech_ids = set(expanded_tier_one_unit_ids(run.starting_unit_ids))
    tech_ids.update(expanded_tier_one_defense_ids(run.starting_defense_ids))
    rewards = [
        canonical_reward_for_id(reward_id)
        for reward_id in active_shop_reward_ids(run)
    ]
    tech_ids.update(tech_ids_for_rewards(rewards))
    return tuple(sorted(tech_ids))


def active_shop_power_ids(run):
    power_ids = set()
    for reward_id in active_shop_reward_ids(run):
        reward = canonical_reward_for_id(reward_id)
        power_id = str(reward.get('superweapon') or '').upper()
        if power_id and reward.get('kind') != 'buff':
            power_ids.add(power_id)
    return tuple(sorted(power_ids))
