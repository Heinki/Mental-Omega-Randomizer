"""Allied helper AI production discovery and map rules."""

from ._shared import (
    BUFF_TARGETS,
    ENGINEER_UNIT_IDS,
    TECHNO_TYPE_LISTS,
    all_section_value_maps,
    country_family,
    map_house_records,
    player_controlled_houses,
    re,
    resolve_configured_helper_houses,
    section_value_map_preserve,
    unique_in_order,
)
from .base import (
    _collision_safe_type_id,
    _value_case_insensitive,
)
from .clone_references import (
    _helper_prerequisite_alternative,
    _positive_build_limit,
    _standalone_clone_values_from_maps,
    _techno_production_class,
)
from .buff_values import (
    _register_map_type,
)

def helper_ai_autobuild_plan(
    lines,
    helper_houses,
    unlocked_unit_ids,
    rewards,
    installed_sections,
    native_map_sections=None,
    allow_cross_faction=False,
):
    """Plan native production support and additive helper AI teams.

    Each enabled helper Autocreate source supplies a known-good TeamType,
    ScriptType, TaskForce shape, owner, and prerequisite path. Existing helper
    production stays on native IDs; parallel variants add earned clone types.
    Native timing/scripts remain intact.
    """
    installed_sections = installed_sections or {}
    native_map_sections = native_map_sections or all_section_value_maps(lines)
    records = map_house_records(lines)
    player_houses = player_controlled_houses(lines, records=records)
    resolved_helpers, _ = resolve_configured_helper_houses(
        records,
        helper_houses,
        player_houses,
    )
    if not resolved_helpers:
        return {'variants': [], 'support': {}}

    helper_aliases = {}
    for house in resolved_helpers:
        record = records.get(house, {})
        country = record.get('country') or house.replace(' House', '')
        for alias in (house, house.replace(' House', ''), country):
            if alias:
                helper_aliases[str(alias).lower()] = (house, country)

    categories = _registered_techno_categories(lines, installed_sections)
    unlocked = {
        str(unit_id or '').upper()
        for unit_id in (unlocked_unit_ids or ())
        if str(unit_id or '').upper() in BUFF_TARGETS
        and BUFF_TARGETS[str(unit_id or '').upper()].get('category')
        in {'infantry', 'units', 'aircraft'}
        and str(unit_id or '').upper() in categories
    }
    if not unlocked:
        return {'variants': [], 'support': {}}

    installed_name_by_lower = {
        str(name).lower(): name for name in installed_sections
    }
    native_name_by_lower = {
        str(name).lower(): name for name in native_map_sections
    }

    def effective_values(type_id):
        installed_name = installed_name_by_lower.get(str(type_id).lower())
        native_name = native_name_by_lower.get(str(type_id).lower())
        return _standalone_clone_values_from_maps(
            installed_sections.get(installed_name, {}) if installed_name else {},
            native_map_sections.get(native_name, {}) if native_name else {},
        )

    def unit_family(unit_id):
        factions = BUFF_TARGETS.get(str(unit_id or '').upper(), {}).get(
            'factions', ()
        )
        if len(factions) != 1:
            return ''
        return {
            'allies': 'allies',
            'soviets': 'soviets',
            'epsilon': 'epsilon',
            'foehn': 'foehn',
        }.get(str(factions[0]).lower(), '')

    buffed_units = {
        str(reward.get('unit') or '').upper()
        for reward in rewards or ()
        if reward.get('kind') == 'buff' and reward.get('unit')
    }
    pools = {}
    for unit_id in unlocked:
        # Engineers are base-operation essentials, not combat substitutions.
        # Existing native Engineer TaskForces can still receive support below.
        if unit_id in ENGINEER_UNIT_IDS:
            continue
        # A generated additive team must never request multiple copies of a
        # hero/super-unit whose installed or mission cap allows only a small
        # number alive. For an installed access item, use its installed cap:
        # maps sometimes reuse that ID for a different capped scripted hero.
        # Existing native helper teams retain their exact map-authored units.
        installed_name = installed_name_by_lower.get(unit_id.lower())
        limit_values = (
            installed_sections.get(installed_name, {})
            if installed_name
            else effective_values(unit_id)
        )
        if _positive_build_limit(limit_values):
            continue
        production_class = _techno_production_class(
            unit_id,
            categories,
            installed_sections,
            native_map_sections,
        )
        if production_class:
            pools.setdefault(production_class, []).append(unit_id)
    for production_class in pools:
        pools[production_class].sort(
            key=lambda unit_id: (unit_id not in buffed_units, unit_id)
        )
        # Broad cloning previously caused severe mission-load slowdown. Eight
        # distinct earned types per production class gives every capable helper
        # a varied extra roster while bounding each map to at most 32 forced
        # combat clones.
        pools[production_class] = pools[production_class][:8]

    sections = all_section_value_maps(lines)
    sections_by_lower = {
        str(name).lower(): values for name, values in sections.items()
    }
    ai_triggers = section_value_map_preserve(lines, 'AITriggerTypes')
    enabled = {
        str(key).lower(): str(value).strip().lower()
        for key, value in section_value_map_preserve(
            lines, 'AITriggerTypesEnable'
        ).items()
    }
    placeholder_houses = {'neutral', 'neutral house', '<none>', 'none', '<all>', 'all'}
    cursors = {}
    variants = []
    support = {}
    used_team_ids = set()
    variant_counts = {}

    def helper_factory_classes():
        result = {
            (records.get(house, {}).get('country') or house.replace(' House', '')).lower(): set()
            for house in resolved_helpers
        }

        def add_factory(owner, building_id):
            helper = helper_aliases.get(str(owner or '').lower())
            if not helper:
                return
            values = effective_values(building_id)
            factory = str(_value_case_insensitive(values, 'Factory', '')).lower()
            if factory == 'infantrytype':
                production_class = 'infantry'
            elif factory == 'aircrafttype':
                production_class = 'aircraft'
            elif factory == 'unittype':
                production_class = (
                    'naval'
                    if str(_value_case_insensitive(values, 'Naval', 'no')).lower() == 'yes'
                    else 'units'
                )
            else:
                return
            result.setdefault(helper[1].lower(), set()).add(production_class)

        for value in sections_by_lower.get('structures', {}).values():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) >= 2:
                add_factory(tokens[0], tokens[1])
        for house in resolved_helpers:
            for key, value in sections_by_lower.get(house.lower(), {}).items():
                if str(key).isdigit():
                    add_factory(house, value.split(',', 1)[0].strip())
        return result

    factory_classes = helper_factory_classes()

    def append_variant(
        trigger_id,
        trigger_tokens,
        team_id,
        helper_owner,
        allowed_classes=None,
        synthetic=False,
    ):
        helper_house, helper_country = helper_owner
        country_key = helper_country.lower()
        if variant_counts.get(country_key, 0) >= 8:
            return
        team_values = sections_by_lower.get(team_id.lower(), {})
        if str(team_values.get('autocreate') or '').lower() != 'yes':
            return
        taskforce_id = str(team_values.get('taskforce') or '').strip()
        if not taskforce_id:
            return
        taskforce_name = next(
            (
                name
                for name in sections
                if str(name).lower() == taskforce_id.lower()
            ),
            taskforce_id,
        )
        taskforce_values = section_value_map_preserve(lines, taskforce_name)
        assignments = {}
        for key, value in sorted(
            taskforce_values.items(),
            key=lambda item: (
                0 if str(item[0]).isdigit() else 1,
                int(item[0]) if str(item[0]).isdigit() else str(item[0]),
            ),
        ):
            if not str(key).isdigit():
                continue
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) < 2:
                continue
            source_id = tokens[1].upper()
            production_class = _techno_production_class(
                source_id,
                categories,
                installed_sections,
                native_map_sections,
            )
            if allowed_classes is not None and production_class not in allowed_classes:
                continue
            source_family = unit_family(source_id)
            if not source_family:
                source_family = country_family(records.get(helper_house, {}))
            pool = [
                unit_id
                for unit_id in pools.get(production_class, ())
                if allow_cross_faction or unit_family(unit_id) == source_family
            ]
            if not pool:
                continue
            cursor_key = (
                helper_country.lower(),
                production_class,
                '*' if allow_cross_faction else source_family,
            )
            cursor = cursors.get(cursor_key, 0)
            if cursor >= len(pool):
                continue
            unlocked_id = pool[cursor]
            cursors[cursor_key] = cursor + 1
            assignments[str(key)] = unlocked_id

            alternative = _helper_prerequisite_alternative(
                effective_values(source_id)
            )
            unit_support = support.setdefault(
                unlocked_id,
                {'countries': [], 'prerequisites': []},
            )
            unit_support['countries'] = unique_in_order(
                unit_support['countries'] + [helper_country]
            )
            if alternative:
                unit_support['prerequisites'] = unique_in_order(
                    unit_support['prerequisites'] + [alternative]
                )

        if not assignments:
            return
        used_team_ids.add(team_id.lower())
        variant_counts[country_key] = variant_counts.get(country_key, 0) + 1
        variants.append({
            'source_trigger_id': str(trigger_id),
            'trigger_tokens': list(trigger_tokens),
            'source_team_id': team_id,
            'team_values': section_value_map_preserve(lines, team_id),
            'source_taskforce_id': taskforce_id,
            'taskforce_values': taskforce_values,
            'assignments': assignments,
            'helper_house': helper_house,
            'helper_country': helper_country,
            'synthetic_trigger': bool(synthetic),
        })

    def record_native_team_support(team_id, helper_owner):
        """Make the helper's existing team members buildable as player clones."""
        _helper_house, helper_country = helper_owner
        team_values = sections_by_lower.get(str(team_id).lower(), {})
        taskforce_id = str(team_values.get('taskforce') or '').strip()
        if not taskforce_id:
            return
        taskforce_values = sections_by_lower.get(taskforce_id.lower(), {})
        for key, value in taskforce_values.items():
            if not str(key).isdigit():
                continue
            tokens = [token.strip() for token in str(value).split(',')]
            if len(tokens) < 2:
                continue
            source_id = tokens[1].upper()
            if source_id not in unlocked:
                continue
            unit_support = support.setdefault(
                source_id,
                {'countries': [], 'prerequisites': []},
            )
            unit_support['countries'] = unique_in_order(
                unit_support['countries'] + [helper_country]
            )
            alternative = _helper_prerequisite_alternative(
                effective_values(source_id)
            )
            if alternative:
                unit_support['prerequisites'] = unique_in_order(
                    unit_support['prerequisites'] + [alternative]
                )

    for trigger_id, trigger_value in ai_triggers.items():
        if enabled.get(str(trigger_id).lower(), 'yes') == 'no':
            continue
        trigger_tokens = [token.strip() for token in trigger_value.split(',')]
        if len(trigger_tokens) < 3:
            continue
        team_id = trigger_tokens[1]
        team_values = sections_by_lower.get(team_id.lower(), {})

        owner_candidates = []
        trigger_owner = trigger_tokens[2]
        team_owner = str(team_values.get('house') or '').strip()
        if trigger_owner.lower() not in placeholder_houses:
            owner_candidates.append(trigger_owner)
        if team_owner.lower() not in placeholder_houses:
            owner_candidates.append(team_owner)
        helper_owner = next(
            (
                helper_aliases[candidate.lower()]
                for candidate in owner_candidates
                if candidate.lower() in helper_aliases
            ),
            None,
        )
        if not helper_owner:
            continue
        record_native_team_support(team_id, helper_owner)
        append_variant(trigger_id, trigger_tokens, team_id, helper_owner)

    # Many campaign helpers use map-authored Autocreate TeamTypes without a
    # dedicated AITriggerTypes entry. When that helper owns a matching physical
    # factory, create a parallel TeamType only; the map's existing action 13
    # controls both native and generated Autocreate teams.
    side_numbers = {
        'gdi': '1',
        'nod': '2',
        'thirdside': '3',
        'fourthside': '4',
    }
    for team_id, team_values in sections.items():
        if team_id.lower() in used_team_ids:
            continue
        if str(team_values.get('autocreate') or '').lower() != 'yes':
            continue
        team_owner = str(team_values.get('house') or '').strip()
        helper_owner = helper_aliases.get(team_owner.lower())
        if not helper_owner:
            continue
        record_native_team_support(team_id, helper_owner)
        helper_house, helper_country = helper_owner
        available_classes = factory_classes.get(helper_country.lower(), set())
        if not available_classes:
            continue
        side = side_numbers.get(
            str(records.get(helper_house, {}).get('side') or '').lower(),
            '0',
        )
        synthetic_tokens = [
            f'MOR unlocked helper {helper_country}',
            team_id,
            helper_country,
            '1',
            '-1',
            '<none>',
            '0000000000000000000000000000000000000000000000000000000000000000',
            '40.000000',
            '20.000000',
            '50.000000',
            '1',
            '0',
            side,
            '0',
            '<none>',
            '1',
            '1',
            '1',
        ]
        append_variant(
            f'synthetic:{team_id}',
            synthetic_tokens,
            team_id,
            helper_owner,
            allowed_classes=available_classes,
            synthetic=True,
        )

    return {'variants': variants, 'support': support}

def _append_prerequisite_alternatives(values, alternatives):
    existing_values = {
        str(value).strip().lower()
        for key, value in values.items()
        if str(key).lower() == 'prerequisite'
        or str(key).lower().startswith('prerequisite.list')
    }
    used_indexes = {
        int(match.group(1))
        for key in values
        for match in [re.fullmatch(r'prerequisite\.list(\d+)', str(key), re.IGNORECASE)]
        if match
    }
    # Ares reserves List0 as an optional replacement for the normal
    # Prerequisite field. Additional alternatives are 1-based and
    # Prerequisite.Lists stores the highest enabled extra-list index.
    next_index = 1
    for alternative in alternatives or ():
        alternative = str(alternative or '').strip()
        if not alternative or alternative.lower() in existing_values:
            continue
        while next_index in used_indexes:
            next_index += 1
        values[f'Prerequisite.List{next_index}'] = alternative
        used_indexes.add(next_index)
        existing_values.add(alternative.lower())
        next_index += 1
    extra_indexes = [index for index in used_indexes if index > 0]
    if extra_indexes:
        values['Prerequisite.Lists'] = str(max(extra_indexes))

def helper_ai_autobuild_rules(
    lines,
    plan,
    clone_handled,
    installed_sections,
):
    """Create parallel helper TaskForce/TeamType/AITrigger definitions."""
    variants = list((plan or {}).get('variants') or ())
    if not variants:
        return {}, [], []
    clone_ids = {
        str(unit_id).upper(): str(values.get('clone_id') or '')
        for unit_id, values in (clone_handled or {}).items()
        if values.get('clone_id')
    }
    map_sections = all_section_value_maps(lines)
    reserved_ids = {str(section).lower() for section in installed_sections or {}}
    reserved_ids.update(str(section).lower() for section in map_sections)
    for section in ('TaskForces', 'TeamTypes'):
        reserved_ids.update(
            str(value).lower()
            for value in section_value_map_preserve(lines, section).values()
        )
    reserved_ids.update(
        str(key).lower()
        for key in section_value_map_preserve(lines, 'AITriggerTypes')
    )

    section_rules = {}
    built_units = []
    skipped = []
    for index, variant in enumerate(variants, 1):
        source_taskforce_values = dict(variant['taskforce_values'])
        # A copied template can contain campaign-only members (for example a
        # hidden MAMM). Keeping any untouched slot lets that invalid request
        # stall the additive team's queue. Preserve TaskForce metadata, but
        # populate numeric members exclusively with verified player clones.
        taskforce_values = {
            key: value
            for key, value in source_taskforce_values.items()
            if not str(key).isdigit()
        }
        replaced = 0
        for key, unlocked_id in sorted(
            variant['assignments'].items(),
            key=lambda item: int(item[0]),
        ):
            clone_id = clone_ids.get(str(unlocked_id).upper())
            original = source_taskforce_values.get(key)
            if not clone_id or original is None:
                skipped.append(str(unlocked_id))
                continue
            tokens = [token.strip() for token in original.split(',')]
            if len(tokens) < 2:
                skipped.append(str(unlocked_id))
                continue
            tokens[1] = clone_id
            taskforce_values[str(replaced)] = ','.join(tokens)
            replaced += 1
            built_units.append(str(unlocked_id).upper())
        if not replaced:
            continue

        identity = (
            f"helper-ai:{variant['source_trigger_id']}:"
            f"{variant['helper_country']}:{index}"
        )
        taskforce_id = _collision_safe_type_id(
            f'MORHTF{index:04d}',
            identity + ':taskforce',
            reserved_ids,
        )
        team_id = _collision_safe_type_id(
            f'MORHTM{index:04d}',
            identity + ':team',
            reserved_ids,
        )
        trigger_id = _collision_safe_type_id(
            f'MORHTR{index:04d}',
            identity + ':trigger',
            reserved_ids,
        )
        _register_map_type(
            section_rules, lines, installed_sections, 'TaskForces', taskforce_id
        )
        _register_map_type(
            section_rules, lines, installed_sections, 'TeamTypes', team_id
        )
        taskforce_values['Name'] = (
            f"MOR unlocked helper {variant['helper_country']} {index}"
        )
        section_rules[taskforce_id] = taskforce_values

        team_values = dict(variant['team_values'])
        team_values['TaskForce'] = taskforce_id
        team_values['Name'] = (
            f"MOR unlocked helper {variant['helper_country']} {index}"
        )
        team_values['Autocreate'] = 'yes'
        section_rules[team_id] = team_values

        trigger_tokens = list(variant['trigger_tokens'])
        trigger_tokens[0] = (
            f"MOR unlocked helper {variant['helper_country']} {index}"
        )
        trigger_tokens[1] = team_id
        if not variant.get('synthetic_trigger'):
            section_rules.setdefault('AITriggerTypes', {})[trigger_id] = ','.join(
                trigger_tokens
            )
            section_rules.setdefault('AITriggerTypesEnable', {})[trigger_id] = 'yes'

    return (
        section_rules,
        unique_in_order(built_units),
        unique_in_order(skipped),
    )

def _registered_techno_categories(lines, installed_sections):
    categories = {}
    for category, list_section in TECHNO_TYPE_LISTS.items():
        registered = list(installed_sections.get(list_section, {}).values())
        registered.extend(section_value_map_preserve(lines, list_section).values())
        for type_id in registered:
            if str(type_id).strip():
                categories[str(type_id).strip().upper()] = category
    return categories
