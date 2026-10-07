"""Co-op production isolation and mode-specific physical factory access."""

from randomizer.core.collections import comma_items, unique_in_order
from randomizer.maps.base import controlled_tech_ids
from randomizer.maps.ini import all_section_value_maps_preserve, merge_ini_section_values
from randomizer.maps.production import (
    PLAYER_ORIGINAL_PRODUCTION_GATE_ID, original_player_production_gate_rules,
)
from randomizer.missions.access import (
    _alternative_prerequisite_rules, _native_access_prerequisites, access_catalog,
    STANDARD_TIER_ONE_FAMILIES,
)
from randomizer.missions.tier_one import (
    _selected_tier_one_roles, _standard_tier_one_entry,
    expanded_tier_one_defense_ids,
)
from randomizer.ui.cameos import installed_rules_registry


def standard_coop_access_rules(source_id: str) -> dict:
    """Use the same exact earned identity and factory alternatives as Standard."""
    for tech_id, level, _family, _category, prerequisite, _owners in access_catalog():
        if tech_id == source_id:
            return {
                'TechLevel': level,
                **_alternative_prerequisite_rules(
                    _native_access_prerequisites(source_id, prerequisite)
                ),
            }
    raise ValueError(f'No Standard production rules for co-op reward: {source_id}')


def coop_starting_rewards(state, country=''):
    """Project saved starters into access; Standard resolves roles per faction."""
    units = set(state.get('starting_unit_ids') or ())
    defenses = set(state.get('starting_defense_ids') or ())
    if state.get('reward_mode') == 'Standard':
        units = {
            _standard_tier_one_entry(role, family, [country])[0]
            for role in _selected_tier_one_roles(units)
            for family in STANDARD_TIER_ONE_FAMILIES
        }
        defenses = expanded_tier_one_defense_ids(defenses)
    excluded = set((state.get('reward_settings') or {}).get('excluded_unit_access_ids', ()))
    return [
        {'name': f'{source_id} co-op starting access',
         'rules': {source_id: {'TechLevel': '1'}}}
        for source_id in sorted((units | defenses) - excluded)
    ]


def apply_coop_native_production_gate(lines, manifest):
    """Keep authored originals out of both human production queues.

    Unlike country exclusions, the hidden prerequisite follows each actual
    human House and also blocks captured-factory and reverse-engineered access.
    Native runtime ownership, positive prerequisites, levels, limits, and map
    references remain authored. Enemy Houses never receive the gate.
    """
    # Import here: reward_map uses the Standard access adapter above.
    from randomizer.coop.reward_map import _append_grid_power_providers

    _powers, installed = installed_rules_registry(synchronous=True)
    native = all_section_value_maps_preserve(lines)
    names = {str(name).lower(): values for name, values in native.items()}
    installed_names = {str(name).lower(): values for name, values in installed.items()}
    registered = {
        str(value).upper()
        for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')
        for sections in (installed_names, names)
        for value in sections.get(category.lower(), {}).values()
    }
    rewarded = set(manifest.get('access_ids', ())) | set(manifest.get('building_ids', ()))
    for loadout in manifest.get('player_loadouts', {}).values():
        rewarded.update(loadout.get('access_ids', ()))
        rewarded.update(loadout.get('building_ids', ()))
    source_ids = (controlled_tech_ids() | rewarded) & registered
    rules = original_player_production_gate_rules(
        lines, installed, source_ids, native_sections=native,
    )
    if not rules:
        return
    # Multiplayer script actors must remain controllable after transfer to A/B.
    # Do not add country ForbiddenHouses/FactoryOwners filters to their identity.
    for source_id in source_ids:
        rules[source_id].pop('ForbiddenHouses', None)
    gate = rules[PLAYER_ORIGINAL_PRODUCTION_GATE_ID]
    gate.update({'Owner': manifest['player_country'], 'RequiredHouses': 'none',
                 'ForbiddenHouses': 'none'})
    merge_ini_section_values(lines, rules)
    _append_grid_power_providers(
        lines, manifest['player_country'], [], [PLAYER_ORIGINAL_PRODUCTION_GATE_ID],
        [], installed, label='Original Production Gate',
    )


def clone_production_owners(native_values, country):
    """Keep foreign factory ownership compatible with exact Standard access."""
    owners = next((value for key, value in native_values.items()
                   if key.lower() == 'owner'), '')
    return ','.join(unique_in_order([*comma_items(owners), country]))
