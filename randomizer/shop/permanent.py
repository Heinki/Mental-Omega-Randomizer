"""Freeze personal buffs at run start; activate them only with current access."""

from dataclasses import replace

from randomizer.rewards.rules import unlocked_reward_tech_ids
from .archipelago import ap_automatic_reward_ids
from .catalogue import canonical_reward_for_id, catalogue_entry
from .model import RunStatus, ShopRewardType


SNAPSHOT_SETTING = 'permanent_buff_snapshot_complete'


def complete_permanent_buff_snapshot(run, profile):
    """Repair older active runs once, retaining their already frozen stacks.

    Unselected units can be bought later. Keep their buffs in the snapshot
    without granting access or applying buffs to a locked unit. Future profile
    changes never alter a run after this snapshot has been completed.
    """
    if (run is None or run.status is not RunStatus.ACTIVE
            or run.reward_settings.get(SNAPSHOT_SETTING)):
        return run
    buffs = {item.reward_id: item for item in profile.permanent_buffs}
    buffs.update({item.reward_id: item for item in run.permanent_buffs_snapshot})
    disabled = run.reward_settings.get('disable_permanent_unit_buffs', False)
    frozen = []
    for item in buffs.values():
        entry = catalogue_entry(canonical_reward_for_id(item.reward_id))
        if entry is None:
            continue
        if entry.reward_type is ShopRewardType.POWER_BUFF or (
                entry.reward_type is ShopRewardType.UNIT_BUFF and not disabled):
            frozen.append(item)
    return replace(run, permanent_buffs_snapshot=tuple(frozen),
                   reward_settings={**run.reward_settings, SNAPSHOT_SETTING: True})


def active_permanent_buffs(run, starter_tech_ids, *, equivalent_units=None):
    """Resolve buffs using access receipts, never using buffs as access."""
    if run is None:
        return ()
    rewards = [canonical_reward_for_id(reward_id) for reward_id in (
        *run.selected_permanent_units,
        *run.random_starting_unit_unlocks,
        *run.permanent_power_unlocks_snapshot,
        *ap_automatic_reward_ids(run.ap_entitlements_snapshot),
        *(item.reward_id for item in run.run_purchases),
    )]
    tech_ids = set(starter_tech_ids) | set(unlocked_reward_tech_ids(rewards))
    if equivalent_units is not None:
        tech_ids.update(peer for unit in tuple(tech_ids) for peer in equivalent_units(unit))
    power_ids = {entry.target_id for reward in rewards
                 if (entry := catalogue_entry(reward)) is not None
                 and entry.reward_type is ShopRewardType.POWER_ACCESS}
    return tuple(item for item in run.permanent_buffs_snapshot
                 if (entry := catalogue_entry(canonical_reward_for_id(item.reward_id))) is not None
                 and ((entry.reward_type is ShopRewardType.UNIT_BUFF
                       and not run.reward_settings.get('disable_permanent_unit_buffs', False)
                       and (entry.target_id in tech_ids
                            or canonical_reward_for_id(item.reward_id).get('global_buff')))
                      or (entry.reward_type is ShopRewardType.POWER_BUFF
                          and entry.target_id in power_ids)))
