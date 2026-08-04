"""Player production essentials and native/clone sidebar isolation."""

from ._shared import (
    comma_items,
    section_value_map_preserve,
    unique_in_order,
)
from .buff_values import _register_map_type


PLAYER_ORIGINAL_PRODUCTION_GATE_ID = 'MORPOriginalGate'


def _value_case_insensitive(values, key, default=None):
    lowered = str(key).lower()
    return next(
        (
            value
            for name, value in (values or {}).items()
            if str(name).lower() == lowered
        ),
        default,
    )


def original_player_production_gate_rules(
    lines,
    installed_sections,
    native_source_ids,
    existing_rule_sections=None,
    native_sections=None,
    negative_gate_exclusions=(),
    player_forbidden_houses=(),
):
    """Block native production for houses owning the hidden player gate.

    Native ownership, AI production, placements, TeamTypes, and exact campaign
    references remain unchanged. Ares evaluates ``Prerequisite.Negative`` for
    normal, alternate-prerequisite, captured-factory, and reverse-engineered
    production. Restore the authored native TechLevel and BuildLimit here:
    campaign Autocreate teams obey both fields, so leaving randomizer locks on
    the shared original silently disables AI paradrops and air attacks. The
    exact-House hidden negative prerequisite keeps the human on isolated
    clones without changing AI production eligibility.
    """
    native_source_ids = {
        str(source_id).upper()
        for source_id in (native_source_ids or ())
        if str(source_id).strip()
    }
    if not native_source_ids:
        return {}
    negative_gate_exclusions = {
        str(source_id).upper()
        for source_id in (negative_gate_exclusions or ())
        if str(source_id).strip()
    }
    player_forbidden_houses = unique_in_order(
        str(house).strip()
        for house in (player_forbidden_houses or ())
        if str(house).strip()
    )

    installed_by_lower = {
        str(section).lower(): values
        for section, values in (installed_sections or {}).items()
    }
    native_by_lower = {
        str(section).lower(): values
        for section, values in (native_sections or {}).items()
    }
    dummy_values = installed_by_lower.get('dummydummy')
    if not dummy_values:
        raise ValueError('Installed DUMMYDUMMY rules unavailable for player production gate.')

    rules = {}
    _register_map_type(
        rules,
        lines,
        installed_sections,
        'BuildingTypes',
        PLAYER_ORIGINAL_PRODUCTION_GATE_ID,
    )
    gate_values = dict(dummy_values)
    gate_values.update({
        'Name': 'Randomizer Original Production Gate',
        'UIName': 'NAME:DUMMYDUMMY',
        'Image': 'DUMMYDUMMY',
        'InvisibleInGame': 'yes',
        'SuperWeapon': None,
        'SuperWeapon2': None,
        'TechLevel': '-1',
        'BuildLimit': '0',
        'AIBuildThis': 'no',
        'Power': '0',
        'Powered': 'false',
        'Immune': 'yes',
        'Capturable': 'false',
        'NeedsEngineer': 'no',
        'Selectable': 'no',
        'Unsellable': 'yes',
        'LegalTarget': 'no',
        'Insignificant': 'yes',
        'ImmuneToEMP': 'yes',
        'DontScore': 'yes',
        'KeepAlive': 'no',
        'BaseNormal': 'no',
        'AIBaseNormal': 'no',
        'IsBaseDefense': 'no',
        'RadarInvisible': 'yes',
        'IsPassable': 'yes',
        'Firestorm.Wall': 'no',
        'Sight': '0',
    })
    rules[PLAYER_ORIGINAL_PRODUCTION_GATE_ID] = gate_values

    existing_rule_sections = existing_rule_sections or {}
    for source_id in sorted(native_source_ids):
        negatives = []
        for values in (
            installed_by_lower.get(source_id.lower(), {}),
            section_value_map_preserve(lines, source_id),
            existing_rule_sections.get(source_id, {}),
        ):
            negatives.extend(comma_items(
                _value_case_insensitive(values, 'Prerequisite.Negative', '')
            ))
        source_rules = rules.setdefault(source_id, {})
        negatives = [
            prerequisite
            for prerequisite in unique_in_order(negatives)
            if prerequisite.upper() != PLAYER_ORIGINAL_PRODUCTION_GATE_ID.upper()
        ]
        source_rules['Prerequisite.Negative'] = (
            ','.join(negatives)
            if source_id in negative_gate_exclusions
            else ','.join(negatives + [PLAYER_ORIGINAL_PRODUCTION_GATE_ID])
        ) or None
        # DropPod payload identities cannot carry the hidden negative gate:
        # Ares can reject their TeamType before creating the transport. Use
        # Ares' production-specific initial-factory-owner filter instead.
        # This blocks factories originally built by the player countries,
        # keeps enemy/script DropPods valid, and still permits captured enemy
        # technology whose factory was initially built by another country.
        if source_id in negative_gate_exclusions:
            factory_forbidden = []
            for values in (
                installed_by_lower.get(source_id.lower(), {}),
                section_value_map_preserve(lines, source_id),
                existing_rule_sections.get(source_id, {}),
            ):
                factory_forbidden.extend(comma_items(
                    _value_case_insensitive(
                        values, 'FactoryOwners.Forbidden', ''
                    )
                ))
            source_rules['FactoryOwners.Forbidden'] = ','.join(
                unique_in_order(
                    factory_forbidden + list(player_forbidden_houses)
                )
            ) or None
        installed_values = installed_by_lower.get(source_id.lower(), {})
        native_values = native_by_lower.get(source_id.lower(), {})
        # Clone discovery finishes after the earlier native-overlay pass.  Add
        # the player-country exclusion here, where every actual registered
        # clone source is known.  This hides originals exposed by captured
        # factories instead of leaving native and MORP cameos side by side.
        effective_forbidden = _value_case_insensitive(
            native_values,
            'ForbiddenHouses',
            _value_case_insensitive(installed_values, 'ForbiddenHouses', ''),
        )
        source_rules['ForbiddenHouses'] = ','.join(unique_in_order(
            comma_items(effective_forbidden) + list(player_forbidden_houses)
        )) or 'none'
        source_rules['TechLevel'] = _value_case_insensitive(
            native_values,
            'TechLevel',
            _value_case_insensitive(installed_values, 'TechLevel'),
        )
        source_rules['BuildLimit'] = _value_case_insensitive(
            native_values,
            'BuildLimit',
            _value_case_insensitive(installed_values, 'BuildLimit'),
        )
    return rules
