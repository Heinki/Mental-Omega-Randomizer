"""Mission retry assistance and country-scoped stacked buff values."""

from ._shared import (
    ALWAYS_AVAILABLE_UNIT_IDS,
    BUFF_TARGETS,
    buff_stack_limit,
    FACTION_UNIT_ROSTERS,
    HOUSE_SCOPED_BUFF_TYPES,
    MAX_COUNTRY_VETERAN_VALUE_LENGTH,
    MISSION_ASSISTANCE,
    MISSION_ASSISTANCE_CATEGORIES,
    all_section_value_maps,
    buffs_with_unlocked_access,
    build_unit_usage_index,
    comma_items,
    country_family,
    house_category_suffix,
    linked_buff_variant_ids,
    map_house_records,
    movement_speed_ceiling,
    player_controlled_houses,
    player_house_from_map,
    resolve_configured_helper_houses,
    scripted_enemy_house_pairs,
    section_lines,
    section_value_map_preserve,
    stacking_amount,
    stacking_multiplier,
    taskforce_usage_houses,
    unique_in_order,
    unit_role_equivalents,
    unsafe_country_houses,
)
from .base import (
    format_multiplier,
    merge_unique_csv_bounded,
    parse_float,
)


def _country_armor_multiplier(received_damage_multiplier):
    """Convert reward damage reduction to the engine's armor divisor."""
    multiplier = float(received_damage_multiplier)
    if multiplier <= 0:
        raise ValueError('Country armor damage multiplier must be positive')
    return 1.0 / multiplier


def stacked_house_buff_values(
    rewards,
    base_values=None,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    veteran_priority_unit_ids=None,
    max_veteran_value_length=MAX_COUNTRY_VETERAN_VALUE_LENGTH,
    excluded_buff_types=(),
):
    base_values = base_values or {}
    excluded_buff_types = {
        str(buff_type).lower() for buff_type in excluded_buff_types
    }
    category_counts = {}
    veteran_units = {}
    for reward in buffs_with_unlocked_access(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
    ):
        if reward.get('kind') != 'buff' or not reward.get('unit') or not reward.get('buff_type'):
            continue
        buff_type = reward.get('buff_type')
        if str(buff_type).lower() in excluded_buff_types:
            continue
        if buff_type not in HOUSE_SCOPED_BUFF_TYPES:
            continue
        target = BUFF_TARGETS.get(reward.get('unit'))
        if not target:
            continue
        if (
            unit_specific_mode
            and buff_type in {'production', 'cost', 'speed', 'armor'}
            and not target.get('global_production')
        ):
            continue
        if buff_type == 'production' and target.get('global_production'):
            for global_suffix in ('Infantry', 'Units', 'Aircraft', 'Buildings', 'Defenses'):
                key = (buff_type, global_suffix)
                category_counts[key] = category_counts.get(key, 0) + 1
                limit = buff_stack_limit(reward)
                if limit is not None:
                    category_counts[key] = min(category_counts[key], limit)
            continue
        suffix = house_category_suffix(target)
        if buff_type == 'veteran':
            if not target.get('trainable', True):
                continue
            # Ares calls the country flag VeteranBuildings, including for
            # defenses. VeteranDefenses is not an engine key.
            if target.get('category') == 'defenses':
                if not target.get('trainable'):
                    continue
                suffix = 'Buildings'
            # ROBO/ROBOW and future linked forms are two production identities
            # of one reward target. They always share veterancy; curated role
            # peers (such as faction transports) remain opt-in.
            units = set(linked_buff_variant_ids(reward['unit']))
            if share_basic_equivalent_buffs:
                for equivalent in unit_role_equivalents(reward['unit']):
                    units.update(linked_buff_variant_ids(equivalent))
            for unit_id in units:
                equivalent_target = BUFF_TARGETS.get(unit_id, target)
                if not equivalent_target.get('trainable', True):
                    continue
                if (
                    equivalent_target.get('category') == 'defenses'
                    and not equivalent_target.get('trainable')
                ):
                    continue
                # Ares uses VeteranBuildings for trainable defenses. There is
                # no VeteranDefenses country key.
                equivalent_suffix = (
                    'Buildings'
                    if equivalent_target.get('category') == 'defenses'
                    else house_category_suffix(equivalent_target)
                )
                veteran_units.setdefault(equivalent_suffix, []).append(unit_id)
            continue
        suffixes = {suffix}
        if share_basic_equivalent_buffs:
            suffixes.update(
                house_category_suffix(BUFF_TARGETS[unit_id])
                for unit_id in unit_role_equivalents(reward['unit'])
                if unit_id in BUFF_TARGETS
            )
        for equivalent_suffix in suffixes:
            key = (buff_type, equivalent_suffix)
            category_counts[key] = category_counts.get(key, 0) + 1
            limit = buff_stack_limit(reward)
            if limit is not None:
                category_counts[key] = min(category_counts[key], limit)

    values = {}
    for (buff_type, suffix), count in category_counts.items():
        if buff_type == 'production':
            key = f'BuildTime{suffix}Mult'
            multiplier = stacking_multiplier('production', count)
        elif buff_type == 'cost':
            key = f'Cost{suffix}Mult'
            multiplier = stacking_multiplier('cost', count)
        elif buff_type == 'armor':
            key = f'Armor{suffix}Mult'
            # RA2/YR divides incoming damage by CountryType Armor*Mult.
            # Reward tuning stores the desired received-damage multiplier,
            # so x0.9 damage must be emitted as an engine divisor of 1/0.9.
            multiplier = _country_armor_multiplier(
                stacking_multiplier('armor', count)
            )
        else:
            continue
        existing_key = next((key_name for key_name in base_values if key_name.lower() == key.lower()), key)
        base = parse_float(base_values.get(existing_key), 1.0)
        values[key] = format_multiplier(base * multiplier)

    country_side = str(
        next(
            (
                value
                for key, value in base_values.items()
                if str(key).lower() == 'side'
            ),
            '',
        )
    ).lower()
    country_faction = {
        'gdi': 'Allies',
        'nod': 'Soviets',
        'thirdside': 'Epsilon',
        'fourthside': 'Foehn',
    }.get(country_side, '')
    veteran_priority = {
        str(unit_id).upper(): index
        for index, unit_id in enumerate(veteran_priority_unit_ids or ())
    }
    for suffix, units in veteran_units.items():
        key = f'Veteran{suffix}'
        existing_key = next((key_name for key_name in base_values if key_name.lower() == key.lower()), key)
        if country_faction or veteran_priority:
            # Standard-mode role sharing can add equivalents from all four
            # factions. Keep proven helper-production clones first, then the
            # current country's native roster, when the one-value limit hits.
            units = sorted(
                unique_in_order(units),
                key=lambda unit_id: (
                    unit_id.upper() not in veteran_priority,
                    veteran_priority.get(unit_id.upper(), len(veteran_priority)),
                    country_faction
                    not in BUFF_TARGETS.get(unit_id, {}).get('factions', ()),
                ),
            )
        if max_veteran_value_length is None:
            values[key] = ','.join(unique_in_order(
                comma_items(base_values.get(existing_key, '')) + list(units)
            ))
        else:
            values[key] = merge_unique_csv_bounded(
                base_values.get(existing_key, ''),
                units,
                max_veteran_value_length,
            )

    return values

def mission_assistance_multipliers(stacks):
    """Return the cumulative player-only multipliers for failed-mission retries."""
    try:
        stacks = max(0, int(stacks))
    except (TypeError, ValueError):
        stacks = 0
    return {
        'production': stacking_multiplier('production', stacks),
        'cost': stacking_multiplier('cost', stacks),
        'speed': stacking_multiplier('speed', stacks),
        'armor': stacking_multiplier('armor', stacks),
        # Display/clone multiplier only. Never write this onto CountryType.
        'rof': stacking_multiplier('reload', stacks),
        'health': stacking_multiplier('health', stacks),
        'damage': stacking_multiplier('damage', stacks),
        'range': stacking_amount('range', stacks),
    }

def mission_assistance_direct_rewards(
    unit_ids,
    stacks,
    include_house_scoped=False,
):
    """Build guarded direct buffs for accessible retry units.

    These stats live on global TechnoType/WeaponType sections rather than a
    country.  ``unit_weapon_buff_rules`` therefore remains responsible for
    rejecting a type whenever a non-assisted house uses it in this map.
    """
    try:
        stacks = max(0, int(stacks))
    except (TypeError, ValueError):
        stacks = 0
    rewards = []
    if not stacks:
        return rewards
    for unit_id in unique_in_order(
        str(unit_id or '').upper() for unit_id in (unit_ids or [])
    ):
        target = BUFF_TARGETS.get(unit_id)
        if not target:
            continue
        for _ in range(stacks):
            buff_types = list(MISSION_ASSISTANCE['direct_buff_types'])
            if include_house_scoped:
                # A shared player CountryType cannot safely receive the normal
                # category values. Force these four effects onto isolated
                # player clones so retry help does not silently disappear.
                buff_types.extend(('production', 'cost', 'speed', 'armor'))
            # Fire-rate assistance must modify cloned WeaponTypes. Country ROF
            # is a difficulty field, not a supported CountryType multiplier.
            if any(
                stats.get('rof', 0) > float(
                    MISSION_ASSISTANCE['reload_when_weapon_rof_above']
                )
                for stats in target.get('weapons', {}).values()
            ):
                buff_types.append('reload')
            if (
                MISSION_ASSISTANCE['add_safe_movement_speed']
                and movement_speed_ceiling(target) is not None
                and int(round(float(target.get('speed', 1))))
                < movement_speed_ceiling(target)
            ):
                buff_types.append('speed')
            for buff_type in unique_in_order(buff_types):
                rewards.append({
                    'kind': 'buff',
                    'unit': unit_id,
                    'buff_type': buff_type,
                    'global_buff': True,
                    'mission_assistance': True,
                    'force_direct_unit_buff': include_house_scoped,
                })
    return rewards

def mission_assistance_buff_values(base_values, stacks):
    """Build category/country overrides for one mission's assistance stacks."""
    try:
        stacks = max(0, int(stacks))
    except (TypeError, ValueError):
        stacks = 0
    multipliers = mission_assistance_multipliers(stacks)
    if not stacks:
        return {}

    values = {}
    fields = (
        ('BuildTime', 'production'),
        ('Cost', 'cost'),
        ('Armor', 'armor'),
    )
    for prefix, multiplier_name in fields:
        for suffix in MISSION_ASSISTANCE_CATEGORIES:
            key = f'{prefix}{suffix}Mult'
            existing_key = next(
                (key_name for key_name in base_values if key_name.lower() == key.lower()),
                key,
            )
            base = parse_float(base_values.get(existing_key), 1.0)
            multiplier = multipliers[multiplier_name]
            if multiplier_name == 'armor':
                multiplier = _country_armor_multiplier(multiplier)
            values[key] = format_multiplier(base * multiplier)

    return values

def mission_assistance_buff_rules(
    lines,
    stacks,
    configured_helper_houses=(),
    excluded_player_houses=(),
):
    """Scope retry assistance without changing a campaign house's country.

    Trigger owners in campaign maps are country IDs (for example ``Guild1``
    or ``UnitedStates``). Reassigning a house to a private clone disconnects
    every trigger owned by the original country and can break scripted unit
    transfers or the mission itself. Country-level assistance is therefore
    applied only when every house in that country family is an assisted house.
    Global unit/weapon assistance is guarded separately by
    :func:`unit_weapon_buff_rules`.
    """
    try:
        stacks = max(0, int(stacks))
    except (TypeError, ValueError):
        stacks = 0
    if not stacks:
        return ({}, [], [])

    records = map_house_records(lines)
    primary_house = player_house_from_map(lines, records=records)
    if not primary_house:
        return ({}, [], [])
    excluded_house_names = {
        str(house or '').lower() for house in excluded_player_houses
    }
    player_houses = [
        house
        for house in (
            player_controlled_houses(lines, records=records) or [primary_house]
        )
        if house.lower() not in excluded_house_names
    ]
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    helper_houses, _ = resolve_configured_helper_houses(
        records,
        configured_helper_houses,
        player_houses,
    )
    assisted_houses = unique_in_order(player_houses + helper_houses)
    usage_index = build_unit_usage_index(lines)
    country_houses = {}
    for house in assisted_houses:
        country = records.get(house, {}).get('country') or house.replace(' House', '')
        country_houses.setdefault(country, []).append(house)

    rule_sections = {}
    skipped_countries = []
    for country, houses in country_houses.items():
        original_values = section_value_map_preserve(lines, country)
        assistance_values = mission_assistance_buff_values(original_values, stacks)
        shared_houses = unsafe_country_houses(
            lines,
            country,
            assisted_houses,
            records=records,
            usage_index=usage_index,
            scripted_enemies=scripted_enemies,
        )
        if shared_houses:
            skipped_countries.append((country, list(houses), shared_houses))
            continue
        rule_sections[country] = assistance_values

    return (rule_sections, assisted_houses, skipped_countries)

def mission_assistance_unit_ids(
    lines,
    unlocked_unit_ids=None,
    additional_unit_ids=None,
    randomized_access=True,
    fallback_faction='',
    configured_helper_houses=(),
):
    """Return units the player can use through progression or this mission.

    Randomized-access runs use earned/always-available units plus units placed
    or scripted for the player in this map. Buffs-only runs additionally show
    the complete normal roster for the player faction.
    """
    combat_categories = {'infantry', 'units', 'aircraft'}

    def is_unit(unit_id):
        return BUFF_TARGETS.get(str(unit_id or '').upper(), {}).get('category') in combat_categories

    records = map_house_records(lines)
    player_houses = player_controlled_houses(lines, records=records)
    primary_house = player_house_from_map(lines, records=records)
    if not player_houses and primary_house:
        player_houses = [primary_house]
    helper_houses, _ = resolve_configured_helper_houses(
        records,
        configured_helper_houses,
        player_houses,
    )

    allowed_names = set()
    for house in unique_in_order(player_houses + helper_houses):
        record = records.get(house, {})
        allowed_names.update({
            house.lower(),
            house.replace(' House', '').lower(),
            (record.get('country') or '').lower(),
        })
    allowed_names.discard('')

    unit_ids = {
        str(unit_id).upper()
        for unit_id in (unlocked_unit_ids or [])
        if is_unit(unit_id)
    }
    unit_ids.update(
        str(unit_id).upper()
        for unit_id in (additional_unit_ids or [])
        if is_unit(unit_id)
    )

    # Include units already placed for the player. This is especially
    # important for the first mission, before any access rewards exist.
    for section in ('Infantry', 'Units', 'Aircraft'):
        for line in section_lines(lines, section):
            if '=' not in line:
                continue
            _, value = line.split('=', 1)
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2 and tokens[0].lower() in allowed_names and is_unit(tokens[1]):
                unit_ids.add(tokens[1].upper())

    # Include player-owned TaskForce units used by reinforcements and other
    # scripted teams, without repeatedly reparsing the whole map per roster ID.
    sections = all_section_value_maps(lines)
    sections_by_lower = {name.lower(): values for name, values in sections.items()}
    taskforce_owners = taskforce_usage_houses(lines, sections=sections)
    for taskforce, owners in taskforce_owners.items():
        if not {owner.lower() for owner in owners}.intersection(allowed_names):
            continue
        for value in sections_by_lower.get(taskforce, {}).values():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2 and is_unit(tokens[1]):
                unit_ids.add(tokens[1].upper())

    family_names = {
        'allies': 'Allies',
        'soviets': 'Soviets',
        'epsilon': 'Epsilon',
        'foehn': 'Foehn',
    }
    player_factions = set()
    for house in player_houses:
        family = country_family(records.get(house, {}))
        if family in family_names:
            player_factions.add(family_names[family])
    if fallback_faction in FACTION_UNIT_ROSTERS:
        player_factions.add(fallback_faction)

    for faction in player_factions:
        roster_ids = {
            unit_id.upper()
            for category in FACTION_UNIT_ROSTERS.get(faction, {}).values()
            for unit_id in category
        }
        if randomized_access:
            roster_ids.intersection_update(ALWAYS_AVAILABLE_UNIT_IDS)
        unit_ids.update(unit_id for unit_id in roster_ids if is_unit(unit_id))

    return sorted(unit_ids)
