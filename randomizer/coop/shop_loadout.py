"""Validate and project personal Shop loadouts for native RA2 co-op maps."""

from __future__ import annotations

import math
import re
from pathlib import Path

from randomizer.coop.archipelago import received_rewards
from randomizer.maps.ini import all_section_value_maps
from randomizer.rewards.arsenal import arsenal_unit_type
from randomizer.rewards.catalogue import BUFF_TARGETS, REWARD_POOL, canonical_reward
from randomizer.rewards.display import starting_credit_bonus
from randomizer.rewards.power_buff_definitions import power_buff_stack_limit
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.rewards.rules import tech_ids_for_rewards
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.mission_modifiers import shop_enemy_scaling_entries
from randomizer.shop.modifiers import (
    PRODUCTION_RESTRICTIONS, modifier_effects, stage_production_restrictions,
)
from randomizer.ui.cameos import installed_rules_registry


SHOP_MULTIPLIER_FIELDS = (
    'player_damage_percent', 'player_armor_percent', 'production_time_percent',
    'combat_production_time_percent', 'player_cost_percent', 'support_recharge_percent',
)
# These effects rewrite every native actor/weapon, including scripted armies.
# The campaign implementation is not suitable for personal multiplayer loadouts.
UNSUPPORTED_SHOP_MODIFIERS = frozenset({
    'demolition_charges', 'melee_fighters', 'one_shot_one_kill',
})
# The wire list contains one entry per buff stack, not per distinct power.
# Size it for the full supported catalogue, including permanent loadouts.
MAX_SHOP_POWER_REWARDS = sum(
    power_buff_stack_limit(reward) or 1
    for reward in REWARD_POOL
    if reward.get('kind') == 'superweapon'
    or reward.get('kind') == 'buff' and reward.get('power_buff_type')
)


def validate_shop_modifiers(modifiers):
    unsupported = sorted(set(modifiers) & UNSUPPORTED_SHOP_MODIFIERS)
    if unsupported:
        names = ', '.join(SHOP_CONFIG.modifiers[key].display_name for key in unsupported)
        raise ValueError(f'Unsupported co-op Shop modifiers: {names}. Start a run without them.')


def _registered_unit_types(source: Path) -> frozenset[str]:
    """Index this installed map once per launch/replay, rather than per reward."""
    _powers, installed = installed_rules_registry(synchronous=True)
    map_sections = all_section_value_maps(source.read_bytes().decode('latin-1').splitlines())
    registered = set()
    for sections in (installed, map_sections):
        names = {str(name).lower(): name for name in sections}
        registered.update(
            str(value).upper()
            for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
            for value in sections.get(names.get(category.lower()), {}).values()
            if str(value).lower() in names
        )
    _, clone_ids, templates = randomizer_unit_roster()
    registered.update(unit_id for unit_id in clone_ids if templates.get(unit_id))
    return frozenset(registered)


def _require_registered_type(source: Path, unit_id: str, registered_types=None) -> None:
    """Reject map-only rewards absent from this co-op map's type registry."""
    if registered_types is None:
        registered_types = _registered_unit_types(source)
    if unit_id.upper() in registered_types:
        return
    raise ValueError(
        f'{unit_id} is absent from installed and co-op map type lists; '
        'choose another unit for the prototype.'
    )


def _validate_shop_loadout(source: Path, loadout: dict, *, allow_empty=False,
                            registered_types=None) -> dict:
    if (not isinstance(loadout, dict)
            or not {'access_ids', 'buff_counts'} <= set(loadout)
            or set(loadout) - {
                'access_ids', 'buff_counts', 'production_restrictions',
                'building_ids', 'starting_credit_bonus', 'power_reward_ids',
                'enemy_reward_ids',
                'shop_settings',
            }):
        raise ValueError('Shop loadout needs access_ids and buff_counts.')
    access_ids = loadout['access_ids']
    buff_counts = loadout['buff_counts']
    if (not isinstance(access_ids, list) or (not access_ids and not allow_empty)
            or len(access_ids) > (2048 if allow_empty else 100)
            or any(not isinstance(item, str) or not re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                   for item in access_ids)
            or access_ids != sorted(set(access_ids))
            or not isinstance(buff_counts, dict)
            or any(not isinstance(counts, dict) for counts in buff_counts.values())):
        raise ValueError('Invalid co-op Shop unit access or buff loadout.')
    if registered_types is None:
        registered_types = _registered_unit_types(source)
    for unit_id in access_ids:
        _require_registered_type(source, unit_id, registered_types)
        if not arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
            raise ValueError(f'Unsupported co-op Shop unit: {unit_id}')
    for unit_id, counts in buff_counts.items():
        if any(not isinstance(buff_type, str) or not isinstance(amount, int)
               or isinstance(amount, bool) or not 1 <= amount <= 100
               for buff_type, amount in counts.items()):
            raise ValueError(f'Invalid co-op Shop buffs for {unit_id}.')
    restrictions = loadout.get('production_restrictions', [])
    if (not isinstance(restrictions, list)
            or any(not isinstance(item, str)
                   or item not in PRODUCTION_RESTRICTIONS for item in restrictions)
            or restrictions != sorted(set(restrictions))
            ):
        raise ValueError('Invalid co-op Shop production restrictions.')
    building_ids = loadout.get('building_ids', [])
    if (not isinstance(building_ids, list)
            or len(building_ids) > (2048 if allow_empty else 100)
            or any(not isinstance(item, str)
                   or not re.fullmatch(r'[A-Z0-9_]{2,24}', item)
                   or BUFF_TARGETS.get(item, {}).get('category') not in {
                       'defenses', 'special_buildings',
                   } for item in building_ids)
            or building_ids != sorted(set(building_ids))):
        raise ValueError('Invalid co-op Shop building access.')
    if set(buff_counts) - (set(access_ids) | set(building_ids)):
        raise ValueError('Co-op buffs require earned unit or building access.')
    credit_bonus = loadout.get('starting_credit_bonus', 0)
    if type(credit_bonus) is not int or not -10000 <= credit_bonus <= 50000:
        raise ValueError('Invalid co-op Shop starting credit bonus.')
    power_reward_ids = loadout.get('power_reward_ids', [])
    if not isinstance(power_reward_ids, list):
        raise ValueError('Invalid co-op Shop power rewards: expected a list.')
    if len(power_reward_ids) > MAX_SHOP_POWER_REWARDS:
        raise ValueError(
            f'Invalid co-op Shop power rewards: {len(power_reward_ids)} entries '
            f'exceed catalogue limit {MAX_SHOP_POWER_REWARDS}.'
        )
    for item in power_reward_ids:
        if not isinstance(item, str) or len(item) > 120:
            raise ValueError('Invalid co-op Shop power rewards: invalid reward name.')
        reward = canonical_reward({'name': item})
        if (reward.get('kind') != 'superweapon'
                and not (reward.get('kind') == 'buff' and reward.get('power_buff_type'))):
            raise ValueError(
                f'Invalid co-op Shop power rewards: {item!r} is not a supported '
                'power or power buff. Both players must use matching launcher '
                'versions and reward configs.'
            )
    if power_reward_ids != sorted(power_reward_ids):
        raise ValueError('Invalid co-op Shop power rewards: reward list is not sorted.')
    enemy_reward_ids = loadout.get('enemy_reward_ids', [])
    if (not isinstance(enemy_reward_ids, list) or len(enemy_reward_ids) > 150
            or any(not isinstance(item, str) or len(item) > 120
                   or not canonical_reward({'name': item}).get('enemy_reward')
                   for item in enemy_reward_ids)
            or enemy_reward_ids != sorted(enemy_reward_ids)):
        raise ValueError('Invalid co-op Shop enemy rewards.')
    settings = loadout.get('shop_settings', {})
    if (not isinstance(settings, dict)
            or set(settings) - {f'shop_{key}' for key in SHOP_MULTIPLIER_FIELDS}
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   or not 0.01 <= value <= 100 for value in settings.values())):
        raise ValueError('Invalid co-op Shop modifier settings.')
    result = {'access_ids': list(access_ids),
              'buff_counts': {unit_id: dict(counts) for unit_id, counts in buff_counts.items()}}
    if 'production_restrictions' in loadout:
        result['production_restrictions'] = list(restrictions)
    if 'building_ids' in loadout:
        result['building_ids'] = list(building_ids)
    if 'starting_credit_bonus' in loadout:
        result['starting_credit_bonus'] = credit_bonus
    if 'power_reward_ids' in loadout:
        result['power_reward_ids'] = list(power_reward_ids)
    if 'enemy_reward_ids' in loadout:
        result['enemy_reward_ids'] = list(enemy_reward_ids)
    if 'shop_settings' in loadout:
        result['shop_settings'] = dict(settings)
    return result


def shop_unit_loadout(run, profile=None, *, state=None, mission=None) -> dict:
    """Project one player's Shop rewards and stage effects for the map."""
    from randomizer.coop.prototype import (
        _buff_counts, _building_ids, _grid_enemy_reward_ids, _power_reward_ids,
    )
    from randomizer.shop.active import (
        active_shop_rewards, active_shop_starter_defense_ids,
        active_shop_starter_unit_ids,
    )
    from randomizer.shop.catalogue import canonical_reward_for_id
    from randomizer.shop.mission_modifiers import active_mission_modifier

    validate_shop_modifiers(run.modifiers)
    effects = modifier_effects(run.modifiers)
    rewards = list(active_shop_rewards(run))
    challenge_definition = SHOP_CONFIG.permanent_upgrades['permanent_challenge_slots']
    challenge_slots = (
        profile.upgrade_level('permanent_challenge_slots')
        * int(challenge_definition.effects['slots_per_level'])
        if profile else 0
    )
    mission_modifier = active_mission_modifier(run, challenge_slots=challenge_slots)
    if mission_modifier:
        rewards.extend(
            canonical_reward_for_id(reward_id)
            for reward_id in mission_modifier.player_reward_ids
        )
    access_ids = {str(unit_id).upper() for unit_id in active_shop_starter_unit_ids(run)}
    for reward in rewards:
        if reward.get('kind') in {'buff', 'superweapon', 'message', 'retired'}:
            continue
        for unit_id in tech_ids_for_rewards([reward]):
            if arsenal_unit_type(unit_id, BUFF_TARGETS.get(unit_id)):
                access_ids.add(unit_id)
    access_ids = sorted(access_ids)
    if not access_ids:
        raise ValueError('Co-op Shop player has no supported unit access.')
    veteran_targets = set()
    if profile and profile.upgrade_level('veteran_academy'):
        for reward_id in run.selected_permanent_units:
            veteran_targets.update(
                unit_id for unit_id in tech_ids_for_rewards([
                    canonical_reward_for_id(reward_id)
                ]) if unit_id in access_ids
            )
    if modifier_effects(run.modifiers)['starter_veteran']:
        veteran_targets.update(active_shop_starter_unit_ids(run))
    for unit_id in sorted(veteran_targets):
        target = BUFF_TARGETS.get(unit_id, {})
        reward_name = f'{target.get("label", unit_id)} Veteran Training I'
        reward = canonical_reward_for_id(reward_name)
        if reward.get('buff_type') == 'veteran':
            rewards.append(reward)
    building_ids = sorted(set(_building_ids(rewards))
                          | set(active_shop_starter_defense_ids(run)))
    loadout = {'access_ids': access_ids,
               'buff_counts': _buff_counts(rewards, access_ids, building_ids)}
    settings = {f'shop_{key}': float(effects[key]) for key in SHOP_MULTIPLIER_FIELDS}
    production_level = profile.upgrade_level('global_production_speed') if profile else 0
    settings['shop_production_time_percent'] /= 1 + production_level / 10
    settings = {key: value for key, value in settings.items() if value != 1.0}
    if settings:
        loadout['shop_settings'] = settings
    if building_ids:
        loadout['building_ids'] = building_ids
    power_reward_ids = _power_reward_ids(rewards)
    if power_reward_ids:
        loadout['power_reward_ids'] = power_reward_ids
    offer = next((
        item for item in run.mission_offers
        if item.mission_code == run.selected_mission_code
    ), None)
    if offer is not None:
        entries = shop_enemy_scaling_entries(
            run, offer, mission if mission is not None else {
                         'no_build': False, 'true_no_build': False,
                         'no_build_production': False},
            challenge_slots=challenge_slots,
        )
        enemy_reward_ids = sorted(str(entry['reward']['name']) for entry in entries)
        if enemy_reward_ids:
            loadout['enemy_reward_ids'] = enemy_reward_ids
    if state is not None and received_rewards(state) is not None:
        traps = _grid_enemy_reward_ids(state)
        if traps:
            loadout['enemy_reward_ids'] = sorted([
                *loadout.get('enemy_reward_ids', ()), *traps,
            ])
    credit_level = profile.upgrade_level('mission_starting_credits') if profile else 0
    credits_per_level = int(SHOP_CONFIG.permanent_upgrades[
        'mission_starting_credits'
    ].effects['credits_per_level'])
    credit_bonus = (
        starting_credit_bonus(rewards)
        + credit_level * credits_per_level
        + int(modifier_effects(run.modifiers)['mission_starting_credits_flat'])
    )
    if credit_bonus:
        loadout['starting_credit_bonus'] = credit_bonus
    restrictions = stage_production_restrictions(run)
    if restrictions:
        loadout['production_restrictions'] = sorted(restrictions)
    return loadout


