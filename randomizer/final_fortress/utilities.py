"""Player-only utility perks using established reward eligibility and math."""

from functools import lru_cache
from math import ceil

from randomizer.config.tuning import stacked_self_heal_amount
from randomizer.maps.buff_values import apply_unit_buff_value, resolved_safe_strength
from randomizer.maps.clone_references import _target_with_effective_unit_stats
from randomizer.rewards.catalogue import (
    BUFF_TARGETS, REWARD_POOL, MANDATORY_EXCLUDED_BUFF_TYPE_IDS, linked_buff_variant_ids,
)


@lru_cache(maxsize=1)
def supported_pairs():
    return frozenset((variant, entry['buff_type']) for entry in REWARD_POOL
                     if entry.get('kind') == 'buff' and entry.get('unit') and entry.get('buff_type')
                     for variant in linked_buff_variant_ids(entry['unit'])
                     if not BUFF_TARGETS.get(variant, {}).get('linked_buff_weapon_only')
                     and variant not in MANDATORY_EXCLUDED_BUFF_TYPE_IDS.get(entry['buff_type'], ()))


def infrastructure_building(row, *, defense=False):
    """Production and economy structures, excluding defenses and the Lab."""
    return not defense and float(row.get('Strength', '0')) > 1 and (
        row.get('Factory', '').lower() in ('buildingtype', 'infantrytype', 'unittype', 'aircrafttype')
        or any(row.get(field, 'no').lower() == 'yes'
               for field in ('Refinery', 'Grinding', 'Cloning', 'OrePurifier', 'FactoryPlant'))
        or float(row.get('Power', '0')) > 0 or float(row.get('ProduceCashAmount', '0')) > 0)


def transport_buff_allowed(original, row, kind):
    """Reuse catalogue policy and reject live gunner/sealed-payload changes."""
    sealed = (row.get('InitialPayload.Types', '').lower() not in ('', 'none')
              and row.get('NoManualEnter', 'no').lower() == 'yes'
              and row.get('NoManualUnload', 'no').lower() == 'yes')
    return ((original, kind) in supported_pairs() and int(row.get('Passengers', '0')) > 0
            and row.get('Gunner', 'no').lower() != 'yes' and not sealed)


def utility_updates(original, row, effects, *, building=False, defense=False):
    """Preserve live baselines and exclusions rather than broad native overrides."""
    power = effects.get('generator_power_percent', 0)
    generation = {field: str(ceil(float(row[field]) * (1 + power / 100)))
                  for field in ('Power', 'ExtraPower')
                  if building and power and float(row.get('Power', '0')) > 0
                  and float(row.get(field, '0')) > 0}
    updates = dict(generation)
    health = effects.get('infrastructure_health_percent', 0)
    if building and health and infrastructure_building(row, defense=defense):
        updates['Strength'] = str(int(row['Strength']) * (100 + health) // 100)
    limit = effects.get('special_building_limit_stacks', 0)
    # Structure Capacity also covers capped defenses and their linked mobile
    # forms (War Rig). Combat category does not determine capacity eligibility.
    if limit and (original, 'building_limit') in supported_pairs():
        native = int(row.get('BuildLimit', '0'))
        if native > 0:
            updates['BuildLimit'] = str(native + min(limit, 3))
    if not any(effects.get(field) for field in ('healing_stacks', 'recon_stacks',
                                              'unique_limit_stacks', 'income_stacks',
                                              'transport_capacity_stacks', 'open_topped')):
        return updates
    metadata = BUFF_TARGETS.get(original)
    if not metadata:
        return updates
    pairs = supported_pairs()
    target = _target_with_effective_unit_stats(metadata, row)
    mobile_or_defense = not building or defense
    capacity = effects.get('transport_capacity_stacks', 0)
    if not building and capacity and transport_buff_allowed(original, row, 'passenger_capacity'):
        apply_unit_buff_value(updates, target, 'passenger_capacity', capacity)
    if not building and effects.get('open_topped') and transport_buff_allowed(original, row, 'open_topped'):
        apply_unit_buff_value(updates, target, 'open_topped', 1)
    healing = effects.get('healing_stacks', 0)
    if mobile_or_defense and healing and any(
            (original, kind) in pairs for kind in ('self_healing', 'self_healing_rate')):
        # Healing needs the full native baseline without erasing capacity or
        # generator improvements already accumulated above.
        updates = {**row, **updates}
        apply_unit_buff_value(updates, target, 'self_healing', max(2, healing))
        apply_unit_buff_value(updates, target, 'self_healing_cap', 1)
        # Rookie healing is intentional from rank one. Already stronger
        # native healing is retained; Tier perks contribute their actual HP.
        updates['SelfHealing'] = 'yes'
        updates['SelfHealing.Amount'] = str(max(int(float(row.get('SelfHealing.Amount', '0'))),
            stacked_self_heal_amount(resolved_safe_strength(target, row), healing)))
        apply_unit_buff_value(updates, target, 'self_healing_rate', 0)
    recon = effects.get('recon_stacks', 0)
    if mobile_or_defense and recon:
        if (original, 'sight') in pairs:
            apply_unit_buff_value(updates, target, 'sight', recon)
        if (original, 'sensors') in pairs:
            sensor_target = _target_with_effective_unit_stats(metadata, {**row, **updates})
            apply_unit_buff_value(updates, sensor_target, 'sensors', 1)
            updates['SensorsSight'] = str(max(int(float(row.get('SensorsSight', '0'))),
                                             int(updates['SensorsSight'])))
    limit = effects.get('unique_limit_stacks', 0)
    if not building and limit and (original, 'build_limit') in pairs:
        native = int(row.get('BuildLimit', '0'))
        if native > 0:
            updates['BuildLimit'] = str(native + limit)
    income = effects.get('income_stacks', 0)
    if building and income and (original, 'income') in pairs:
        if float(row.get('ProduceCashAmount', '0')) > 0:
            apply_unit_buff_value(updates, target, 'income', income)
    updates.update(generation)
    return {key: value for key, value in updates.items() if row.get(key) != value}
