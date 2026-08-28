"""Shop-facing adapters over canonical reward catalogue data."""

from functools import lru_cache

from randomizer.config.schema import StaticConfigError
from randomizer.rewards.arsenal import arsenal_tier_for_tech_level
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    REWARD_POOL,
    buff_stack_limit,
    canonical_reward,
)
from randomizer.rewards.roster import randomizer_unit_template_values
from randomizer.rewards.rules import tech_ids_for_rewards

from .model import ShopCatalogueEntry, ShopRewardType
from .config import SHOP_CONFIG


def canonical_reward_id(reward):
    source = {'name': reward} if isinstance(reward, str) else reward
    canonical = canonical_reward(source)
    return str(canonical.get('name') or '')


def canonical_reward_for_id(reward_id):
    return canonical_reward({'name': str(reward_id)})


@lru_cache(maxsize=1)
def _unit_tiers():
    tiers = {}
    for unit_id, values in randomizer_unit_template_values().items():
        raw_level = next(
            (
                value for key, value in values.items()
                if str(key).lower() == 'techlevel'
            ),
            1,
        )
        tiers[unit_id.upper()] = arsenal_tier_for_tech_level(raw_level)
    return tiers


def _root_access_unit(reward):
    tech_ids = sorted(tech_ids_for_rewards([reward]))
    return next((unit_id for unit_id in tech_ids if unit_id in BUFF_TARGETS), '')


def catalogue_entry(reward):
    canonical = canonical_reward(reward)
    reward_id = str(canonical.get('name') or '')
    kind = canonical.get('kind')
    if (
        not reward_id
        or kind in {'message', 'retired'}
        or canonical.get('enemy_reward')
    ):
        return None
    factions = tuple(str(item) for item in canonical.get('factions') or ())
    if kind == 'superweapon':
        target_id = str(canonical.get('superweapon') or '').upper()
        if not target_id:
            return None
        return ShopCatalogueEntry(
            reward_id,
            ShopRewardType.POWER_ACCESS,
            target_id,
            None,
            None,
            factions,
        )
    if kind == 'buff' and canonical.get('power_buff_type'):
        target_id = str(canonical.get('superweapon') or '').upper()
        if not target_id:
            return None
        return ShopCatalogueEntry(
            reward_id,
            ShopRewardType.POWER_BUFF,
            target_id,
            None,
            buff_stack_limit(canonical),
            factions,
        )
    if kind == 'buff':
        target_id = str(canonical.get('unit') or '').upper()
        if not target_id or canonical.get('global_buff'):
            return None
        return ShopCatalogueEntry(
            reward_id,
            ShopRewardType.UNIT_BUFF,
            target_id,
            _unit_tiers().get(target_id, 'tier_1'),
            buff_stack_limit(canonical),
            factions,
        )
    target_id = _root_access_unit(canonical)
    if not target_id:
        return None
    return ShopCatalogueEntry(
        reward_id,
        ShopRewardType.UNIT_ACCESS,
        target_id,
        _unit_tiers().get(target_id, 'tier_1'),
        None,
        factions,
    )


def _validate_unit_target_prices(entries):
    access_targets = {
        entry.target_id for entry in entries
        if entry.reward_type is ShopRewardType.UNIT_ACCESS
    }
    buff_targets = {
        entry.target_id for entry in entries
        if entry.reward_type is ShopRewardType.UNIT_BUFF
    }
    expected_targets = access_targets | buff_targets
    configured_targets = set(SHOP_CONFIG.unit_target_prices)
    missing = sorted(expected_targets - configured_targets)
    unknown = sorted(configured_targets - expected_targets)
    if missing or unknown:
        raise StaticConfigError(
            'Shop Mode unit_target_prices must exactly cover shop unit '
            f'targets; missing={missing}, unknown={unknown} in shop_mode.json'
        )
    invalid_access = sorted(
        target_id for target_id, definition
        in SHOP_CONFIG.unit_target_prices.items()
        if (definition.run_access is not None) != (target_id in access_targets)
    )
    invalid_buffs = sorted(
        target_id for target_id, definition
        in SHOP_CONFIG.unit_target_prices.items()
        if (definition.run_buff is not None) != (target_id in buff_targets)
    )
    if invalid_access or invalid_buffs:
        raise StaticConfigError(
            'Shop Mode unit_target_prices availability does not match shop '
            f'catalogue; access={invalid_access}, buffs={invalid_buffs} '
            'in shop_mode.json'
        )


def _validate_power_target_prices(entries):
    access_targets = {
        entry.target_id for entry in entries
        if entry.reward_type is ShopRewardType.POWER_ACCESS
    }
    buff_targets = {
        entry.target_id for entry in entries
        if entry.reward_type is ShopRewardType.POWER_BUFF
    }
    expected_targets = access_targets | buff_targets
    configured_targets = set(SHOP_CONFIG.power_target_prices)
    missing = sorted(expected_targets - configured_targets)
    unknown = sorted(configured_targets - expected_targets)
    if missing or unknown:
        raise StaticConfigError(
            'Shop Mode power_target_prices must exactly cover shop power '
            f'targets; missing={missing}, unknown={unknown} in shop_mode.json'
        )
    invalid_access = sorted(
        target_id for target_id, definition
        in SHOP_CONFIG.power_target_prices.items()
        if (definition.run_access is not None) != (target_id in access_targets)
    )
    invalid_buffs = sorted(
        target_id for target_id, definition
        in SHOP_CONFIG.power_target_prices.items()
        if (definition.run_buff is not None) != (target_id in buff_targets)
    )
    if invalid_access or invalid_buffs:
        raise StaticConfigError(
            'Shop Mode power_target_prices availability does not match shop '
            f'catalogue; access={invalid_access}, buffs={invalid_buffs} '
            'in shop_mode.json'
        )


@lru_cache(maxsize=1)
def shop_catalogue():
    entries = []
    seen = set()
    excluded = set(SHOP_CONFIG.excluded_reward_ids)
    for reward in REWARD_POOL:
        entry = catalogue_entry(reward)
        if (
            entry is None
            or entry.reward_id in seen
            or entry.reward_id in excluded
        ):
            continue
        seen.add(entry.reward_id)
        entries.append(entry)
    _validate_unit_target_prices(entries)
    _validate_power_target_prices(entries)
    return tuple(entries)


@lru_cache(maxsize=1)
def shop_catalogue_by_reward_id():
    return {entry.reward_id: entry for entry in shop_catalogue()}


def shop_entry_available(
    entry, *, campaign_filter, reward_mode, strict_faction=False
):
    """Return whether current mode can use entry's canonical faction scope."""
    if strict_faction and str(campaign_filter) != 'All Campaigns':
        allowed = {str(campaign_filter), 'Neutral'}
        return bool(
            not entry.factions or allowed.intersection(entry.factions)
        )
    if reward_mode in {'Chaos', 'Randomizer Arsenal'}:
        return True
    allowed = {
        'Allies': {'Allies', 'Neutral'},
        'Soviets': {'Soviets', 'Neutral'},
        'Epsilon': {'Epsilon', 'Neutral'},
        'Foehn': {'Allies', 'Soviets', 'Foehn', 'Neutral'},
    }.get(str(campaign_filter))
    return bool(
        allowed is None
        or not entry.factions
        or allowed.intersection(entry.factions)
    )
