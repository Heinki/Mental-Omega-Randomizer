"""Safe player-country cloning and country-scoped buffs."""

from ._shared import (
    all_section_value_maps,
    build_unit_usage_index,
    map_house_records,
    merge_ini_section_values,
    player_controlled_houses,
    player_house_from_map,
    resolve_configured_helper_houses,
    scripted_enemy_house_pairs,
    section_value_map,
    section_value_map_preserve,
    unique_in_order,
    unsafe_country_houses,
)
from .assistance import (
    stacked_house_buff_values,
)

def clone_player_country_for_house_buffs(
    lines,
    rewards,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    excluded_buff_types=(),
):
    player_house = player_house_from_map(lines)
    if not player_house:
        return ('', {})

    house_values = section_value_map(lines, player_house)
    original_country = house_values.get('country') or player_house.replace(' House', '')
    original_values = section_value_map_preserve(lines, original_country)
    house_buff_values = stacked_house_buff_values(
        rewards,
        original_values,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
        excluded_buff_types=excluded_buff_types,
    )
    if not house_buff_values:
        return (player_house, {})

    # Campaign triggers are owned by the house's Country ID. Never replace it
    # with a private clone: doing so silently detaches the original triggers.
    unsafe_houses = unsafe_country_houses(lines, original_country, [player_house])
    if unsafe_houses:
        return (player_house, {})
    merge_ini_section_values(lines, {original_country: house_buff_values})
    return (player_house, house_buff_values)

def player_country_buff_rules(
    lines,
    rewards,
    configured_helper_houses=(),
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    excluded_player_houses=(),
    excluded_buff_types=(),
):
    sections = all_section_value_maps(lines)
    sections_by_lower = {name.lower(): values for name, values in sections.items()}
    records = map_house_records(lines, sections=sections)
    player_house = player_house_from_map(lines, records=records)
    if not player_house:
        return ('', '', {}, [], [], [])

    excluded_house_names = {
        str(house or '').lower() for house in excluded_player_houses
    }
    player_houses = [
        house
        for house in (
            player_controlled_houses(lines, records=records) or [player_house]
        )
        if house.lower() not in excluded_house_names
    ]
    house_values = sections_by_lower.get(player_house.lower(), {})
    player_country = house_values.get('country') or player_house.replace(' House', '')
    scripted_enemies = scripted_enemy_house_pairs(lines, records=records)
    helper_houses, _ = resolve_configured_helper_houses(
        records,
        configured_helper_houses,
        player_houses,
    )
    allowed_houses = unique_in_order(player_houses + helper_houses)
    usage_index = build_unit_usage_index(lines)
    shared_houses = unsafe_country_houses(
        lines,
        player_country,
        allowed_houses,
        records=records,
        sections=sections,
        usage_index=usage_index,
        scripted_enemies=scripted_enemies,
    )
    rule_sections = {}
    buffed_allies = []
    skipped_allies = []
    original_values = section_value_map_preserve(lines, player_country)
    house_buff_values = stacked_house_buff_values(
        rewards,
        original_values,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
        excluded_buff_types=excluded_buff_types,
    )
    if house_buff_values:
        if not shared_houses:
            rule_sections[player_country] = house_buff_values

    # Every player-controlled house participates automatically, even when it
    # belongs to another faction. The UI option only adds AI-controlled allied
    # helpers to this mandatory player-house set.
    allied_targets = unique_in_order(
        [house for house in player_houses if house.lower() != player_house.lower()]
        + helper_houses
    )
    if allied_targets:
        for helper in allied_targets:
            helper_country = records.get(helper, {}).get('country') or helper.replace(' House', '')
            if helper_country.lower() == player_country.lower():
                if player_country in rule_sections:
                    buffed_allies.append(helper)
                else:
                    skipped_allies.append(helper)
                continue

            unsafe_houses = unsafe_country_houses(
                lines,
                helper_country,
                allowed_houses,
                records=records,
                sections=sections,
                usage_index=usage_index,
                scripted_enemies=scripted_enemies,
            )
            if unsafe_houses:
                skipped_allies.append(helper)
                continue

            original_values = section_value_map_preserve(lines, helper_country)
            helper_buff_values = stacked_house_buff_values(
                rewards,
                original_values,
                require_unlocked_access=require_unlocked_access,
                additional_unlocked_tech_ids=additional_unlocked_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=unit_specific_mode,
                excluded_buff_types=excluded_buff_types,
            )
            if helper_buff_values:
                rule_sections[helper_country] = helper_buff_values
                buffed_allies.append(helper)

    return (player_house, player_country, rule_sections, shared_houses, buffed_allies, skipped_allies)
