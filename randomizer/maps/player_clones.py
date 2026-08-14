"""Player-owned TechnoType clone construction and isolation."""

from ._shared import (
    BUFF_TARGETS,
    LIMITED_HERO_UNIT_IDS,
    MAX_COUNTRY_VETERAN_VALUE_LENGTH,
    MAX_MAP_ACTION_LINE_LENGTH,
    NONTRAINABLE_UNIT_IDS,
    UNLOCKED_TECH_LEVEL,
    all_section_value_maps,
    build_unit_usage_index,
    canonical_house_name,
    comma_items,
    player_controlled_houses,
    player_house_from_map,
    resolve_configured_helper_houses,
    section_value_map_preserve,
    unique_in_order,
    unit_usage_houses,
    unsafe_country_houses,
)
from .clone_builder import PlayerCloneContext, build_player_clone_sections
from .buff_values import (
    _active_direct_buff_counts,
    _allowed_buff_house_names,
)
from .helper_ai import _registered_techno_categories
from .clone_references import (
    _clone_reference_rules,
    _positive_build_limit,
    _standalone_clone_values_from_maps,
)
from .base import (
    _value_case_insensitive,
    compact_player_clone_ids,
    merge_unique_csv_bounded,
)
from .assistance import stacked_house_buff_values

def player_unit_clone_rules(
    lines,
    rewards,
    installed_sections,
    native_ai_helper_houses=(),
    buffed_helper_houses=(),
    native_map_sections=None,
    require_unlocked_access=True,
    additional_unlocked_tech_ids=None,
    buildable_tech_ids=None,
    build_owner_ids=(),
    helper_autobuild_support=None,
    forced_buildable_clone_ids=(),
    forced_isolated_clone_ids=(),
    forced_compact_clone_ids=(),
    unlimited_build_limit_unit_ids=(),
    share_basic_equivalent_buffs=False,
    unit_specific_mode=False,
    native_trigger_reference_ids=(),
    objective_clone_event_refs=None,
    scripted_player_buff_taskforces=(),
    excluded_unit_ids=(),
    build_only_excluded_unit_ids=(),
    excluded_player_houses=(),
    owned_clone_ids=None,
    owned_clone_templates=None,
    owned_clone_rule_overlays=None,
    force_direct_house_scoped_fallback_types=(),
):
    """Build player-only TechnoTypes from static owned templates.

    Mapper-reviewed/static MORP sections provide player identities. Only
    mission production gates are overlaid for buildable types. Map-only
    variants retain the legacy complete-copy fallback. Player-owned references
    can be rewritten. Helper TaskForces and defense base plans use buffed owned
    types; enemy consumers and native dynamic-AI requests remain original.
    """
    installed_sections = installed_sections or {}
    owned_clone_ids = {
        str(source).upper(): str(clone)
        for source, clone in (owned_clone_ids or {}).items()
    }
    owned_clone_templates = {
        str(source).upper(): dict(values)
        for source, values in (owned_clone_templates or {}).items()
    }
    owned_clone_rule_overlays = {
        str(source).upper(): dict(values)
        for source, values in (owned_clone_rule_overlays or {}).items()
    }
    buildable_ids = {
        str(item).upper() for item in (buildable_tech_ids or ())
    }
    records, allowed_houses = _allowed_buff_house_names(
        lines,
        (),
        excluded_player_houses=excluded_player_houses,
    )
    if not records or not allowed_houses:
        return {}, [], {}, [], []

    player_house = player_house_from_map(lines, records=records)
    excluded_house_names = {
        str(house or '').lower() for house in excluded_player_houses
    }
    player_houses = [
        house
        for house in player_controlled_houses(lines, records=records)
        if house.lower() not in excluded_house_names
    ]
    if not player_houses and player_house:
        player_houses = [player_house]
    native_helper_houses, _ = resolve_configured_helper_houses(
        records,
        native_ai_helper_houses,
        player_houses,
    )
    buffed_helper_houses, _ = resolve_configured_helper_houses(
        records,
        buffed_helper_houses,
        player_houses,
    )
    native_helper_names = set()
    for house in native_helper_houses:
        record = records.get(house, {})
        country = record.get('country') or house.replace(' House', '')
        native_helper_names.update({
            house.lower(),
            house.replace(' House', '').lower(),
            str(country).lower(),
        })
    buffed_helper_names = set()
    for house in buffed_helper_houses:
        record = records.get(house, {})
        country = record.get('country') or house.replace(' House', '')
        buffed_helper_names.update({
            house.lower(),
            house.replace(' House', '').lower(),
            str(country).lower(),
        })
    # Only opted-in helpers may consume buffed clones. Native helper identities
    # are still retained separately for unmodified dynamic-AI fallback rules.
    allowed_houses.update(buffed_helper_names)

    usage_index = build_unit_usage_index(lines)
    # Some campaign child countries share their ParentCountry with scripted
    # enemies. Country/category production, cost, and armor multipliers are
    # then intentionally skipped to prevent leakage. Bake those effects into
    # isolated player clones so rewards do not silently disappear. Speed is
    # always clone-direct because every mobile category has a hard ceiling.
    player_country_buff_unsafe = any(
        unsafe_country_houses(
            lines,
            records.get(house, {}).get('country')
            or house.replace(' House', ''),
            list(allowed_houses),
            records=records,
            usage_index=usage_index,
        )
        for house in player_houses
    )
    direct_house_scoped_fallback = bool(player_country_buff_unsafe)
    forced_house_scoped_fallback_types = {
        str(buff_type).lower()
        for buff_type in force_direct_house_scoped_fallback_types
        if str(buff_type).lower() in {
            'production', 'cost', 'speed', 'armor',
        }
    }
    counts_by_unit = _active_direct_buff_counts(
        rewards,
        require_unlocked_access=require_unlocked_access,
        additional_unlocked_tech_ids=additional_unlocked_tech_ids,
        share_basic_equivalent_buffs=share_basic_equivalent_buffs,
        unit_specific_mode=unit_specific_mode,
        global_production_unit_ids=buildable_ids,
    )
    excluded_unit_ids = {
        str(unit_id or '').upper() for unit_id in excluded_unit_ids
    }
    build_only_excluded_unit_ids = {
        str(unit_id or '').upper()
        for unit_id in build_only_excluded_unit_ids
        if str(unit_id or '').upper() in excluded_unit_ids
    }
    for unit_id in excluded_unit_ids - build_only_excluded_unit_ids:
        counts_by_unit.pop(unit_id, None)
    if (
        (direct_house_scoped_fallback or forced_house_scoped_fallback_types)
        and not unit_specific_mode
    ):
        # Standard role sharing already receives direct health/weapon peers.
        # Keep this last-resort country-buff replacement on the earned native
        # unit IDs; expanding four more categories to every role peer creates
        # hundreds of unnecessary clones in large campaign maps.
        fallback_counts = _active_direct_buff_counts(
            rewards,
            require_unlocked_access=require_unlocked_access,
            additional_unlocked_tech_ids=additional_unlocked_tech_ids,
            share_basic_equivalent_buffs=False,
            include_house_scoped_fallback=True,
            house_scoped_only=True,
        )
        for unit_id, counts in fallback_counts.items():
            selected_counts = (
                dict(counts)
                if direct_house_scoped_fallback
                else {
                    buff_type: count
                    for buff_type, count in counts.items()
                    if buff_type in forced_house_scoped_fallback_types
                }
            )
            if selected_counts:
                counts_by_unit.setdefault(unit_id, {}).update(selected_counts)
    for unit_id in excluded_unit_ids - build_only_excluded_unit_ids:
        counts_by_unit.pop(unit_id, None)
    map_sections = all_section_value_maps(lines)
    native_map_sections = native_map_sections or map_sections
    installed_name_by_lower = {
        str(section).lower(): section for section in installed_sections
    }
    map_name_by_lower = {str(section).lower(): section for section in map_sections}
    native_map_name_by_lower = {
        str(section).lower(): section for section in native_map_sections
    }
    reserved_ids = {str(section).lower() for section in installed_sections}
    reserved_ids.update(str(section).lower() for section in map_sections)
    forced_clone_ids = {
        str(item).upper()
        for item in (forced_buildable_clone_ids or ())
        if str(item).upper() in buildable_ids
    }
    forced_clone_ids.update(
        str(item).upper()
        for item in (forced_isolated_clone_ids or ())
        if str(item).upper() in BUFF_TARGETS
    )
    source_by_owned_clone = {
        str(clone_id).upper(): str(source_id).upper()
        for source_id, clone_id in owned_clone_ids.items()
    }
    initial_payload_source_ids = set()
    for carrier_id in buildable_ids:
        payload_types = comma_items(_value_case_insensitive(
            owned_clone_templates.get(carrier_id, {}),
            'InitialPayload.Types',
            '',
        ))
        raw_payload_counts = comma_items(_value_case_insensitive(
            owned_clone_templates.get(carrier_id, {}),
            'InitialPayload.Nums',
            '',
        ))
        payload_counts = []
        for raw_count in raw_payload_counts:
            try:
                payload_counts.append(int(raw_count))
            except (TypeError, ValueError):
                payload_counts.append(0)
        for index, payload_type in enumerate(payload_types):
            payload_count = (
                payload_counts[min(index, len(payload_counts) - 1)]
                if payload_counts else 1
            )
            if payload_count <= 0:
                continue
            payload_source = source_by_owned_clone.get(
                str(payload_type).upper(),
                str(payload_type).upper(),
            )
            if payload_source in BUFF_TARGETS:
                initial_payload_source_ids.add(payload_source)
    # Initial payloads must use registered player-owned identities even when
    # their support types have no independent access or buff reward.
    forced_clone_ids.update(initial_payload_source_ids)
    unlimited_limit_ids = {
        str(item).upper()
        for item in (unlimited_build_limit_unit_ids or ())
        if str(item).upper() in buildable_ids
        and str(item).upper() in LIMITED_HERO_UNIT_IDS
    }
    owner_ids = [str(item) for item in build_owner_ids if item]
    helper_autobuild_support = {
        str(unit_id).upper(): {
            'countries': list(values.get('countries', ())),
            'prerequisites': list(values.get('prerequisites', ())),
        }
        for unit_id, values in (helper_autobuild_support or {}).items()
    }
    # Native fallback ownership is required even when helper buffs are off,
    # but it must never broaden clone ownership or helper veterancy. Keep the
    # two support channels independent.
    native_helper_support = {
        unit_id: {
            'countries': list(values.get('countries', ())),
            'prerequisites': list(values.get('prerequisites', ())),
        }
        for unit_id, values in helper_autobuild_support.items()
    }
    # Snapshot map/additive TaskForce demand before generic country-roster
    # discovery broadens this support table. Under the 480-byte Veteran* limit,
    # clones that the helper is proven to produce must be listed first.
    helper_priority_units_by_country = {}
    for unit_id, support in helper_autobuild_support.items():
        for country in support.get('countries', ()):
            key = str(country).lower()
            helper_priority_units_by_country.setdefault(key, []).append(unit_id)
    helper_priority_units_by_country = {
        country: unique_in_order(unit_ids)
        for country, unit_ids in helper_priority_units_by_country.items()
    }
    main_player_countries = unique_in_order(
        records.get(house, {}).get('country') or house.replace(' House', '')
        for house in player_houses
    )
    veteran_clone_source_ids = set()
    for country in main_player_countries:
        country_values = section_value_map_preserve(lines, country)
        earned_veterancy = stacked_house_buff_values(
            rewards,
            {'Side': _value_case_insensitive(country_values, 'Side', '')},
            require_unlocked_access=require_unlocked_access,
            additional_unlocked_tech_ids=additional_unlocked_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=unit_specific_mode,
            max_veteran_value_length=None,
        )
        for field in (
            'VeteranInfantry', 'VeteranUnits', 'VeteranAircraft',
            'VeteranBuildings',
        ):
            veteran_clone_source_ids.update(
                unit_id.upper()
                for unit_id in comma_items(
                    _value_case_insensitive(earned_veterancy, field, '')
                )
                if (
                    unit_id.upper() in buildable_ids
                    and unit_id.upper() in owned_clone_templates
                    and unit_id.upper() not in NONTRAINABLE_UNIT_IDS
                )
            )
    compact_veteran_clone_ids = compact_player_clone_ids(
        veteran_clone_source_ids,
        reserved_ids,
    )
    compact_payload_source_ids = {
        str(unit_id).upper()
        for unit_id in (forced_compact_clone_ids or ())
        if str(unit_id).upper() not in compact_veteran_clone_ids
    }
    if compact_payload_source_ids:
        compact_veteran_clone_ids.update(compact_player_clone_ids(
            compact_payload_source_ids,
            set(reserved_ids) | set(compact_veteran_clone_ids.values()),
        ))
    defense_helper_houses = []
    defense_helper_country_names = set()
    for house in buffed_helper_houses:
        country = str(
            records.get(house, {}).get('country') or house.replace(' House', '')
        )
        if not country:
            continue
        # Unlike country-section buffs, a standalone defense clone is gated by
        # exact concrete Owner/RequiredHouses IDs. ParentCountry descendants do
        # not need to be rejected: enemy base plans stay on the native type.
        # Rejecting them skipped the Europeans/Pacific bases in AWITHER.
        defense_helper_houses.append(house)
        defense_helper_country_names.add(country.lower())
    shared_player_veteran_ids = set()
    for country in main_player_countries:
        if not unsafe_country_houses(
            lines,
            country,
            list(allowed_houses),
            records=records,
            sections=map_sections,
            usage_index=usage_index,
        ):
            continue
        country_values = section_value_map_preserve(lines, country)
        country_side = _value_case_insensitive(country_values, 'Side', '')
        earned_veterancy = stacked_house_buff_values(
            rewards,
            {'Side': country_side},
            require_unlocked_access=require_unlocked_access,
            additional_unlocked_tech_ids=additional_unlocked_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=unit_specific_mode,
        )
        for field in (
            'VeteranInfantry', 'VeteranUnits', 'VeteranAircraft',
            'VeteranBuildings',
        ):
            shared_player_veteran_ids.update(
                unit_id.upper()
                for unit_id in comma_items(
                    _value_case_insensitive(earned_veterancy, field, '')
                )
                if unit_id.upper() in buildable_ids
            )
    clone_context = PlayerCloneContext(
        allowed_houses=allowed_houses,
        buffed_helper_names=buffed_helper_names,
        build_only_excluded_unit_ids=build_only_excluded_unit_ids,
        buildable_ids=buildable_ids,
        compact_veteran_clone_ids=compact_veteran_clone_ids,
        counts_by_unit=counts_by_unit,
        defense_helper_country_names=defense_helper_country_names,
        defense_helper_houses=defense_helper_houses,
        direct_house_scoped_fallback=direct_house_scoped_fallback,
        excluded_unit_ids=excluded_unit_ids,
        forced_clone_ids=forced_clone_ids,
        initial_payload_source_ids=initial_payload_source_ids,
        helper_autobuild_support=helper_autobuild_support,
        installed_name_by_lower=installed_name_by_lower,
        installed_sections=installed_sections,
        lines=lines,
        map_name_by_lower=map_name_by_lower,
        map_sections=map_sections,
        native_helper_houses=native_helper_houses,
        native_helper_names=native_helper_names,
        native_helper_support=native_helper_support,
        native_map_name_by_lower=native_map_name_by_lower,
        native_map_sections=native_map_sections,
        native_trigger_reference_ids={
            str(unit_id).upper()
            for unit_id in native_trigger_reference_ids
            if unit_id
        },
        objective_clone_source_ids={
            str(unit_id).upper()
            for unit_id in (objective_clone_event_refs or {})
            if unit_id
        },
        owned_clone_ids=owned_clone_ids,
        owned_clone_rule_overlays=owned_clone_rule_overlays,
        owned_clone_templates=owned_clone_templates,
        owner_ids=owner_ids,
        player_houses=player_houses,
        records=records,
        reserved_ids=reserved_ids,
        scripted_player_buff_taskforces={
            str(taskforce_id).lower()
            for taskforce_id in scripted_player_buff_taskforces
            if taskforce_id
        },
        shared_player_veteran_ids=shared_player_veteran_ids,
        unit_specific_mode=unit_specific_mode,
        unlimited_limit_ids=unlimited_limit_ids,
        usage_index=usage_index,
    )
    clone_result = build_player_clone_sections(clone_context)
    section_rules = clone_result.section_rules
    replacements = clone_result.replacements
    direct_replacements = clone_result.direct_replacements
    reference_clone_id_by_source = (
        clone_result.reference_clone_id_by_source
    )
    cloned_source_ids = clone_result.cloned_source_ids
    taskforce_replacements = clone_result.taskforce_replacements
    structure_plan_allowed_houses_by_unit = clone_result.structure_plan_allowed_houses_by_unit
    player_veterancy_replacements = clone_result.player_veterancy_replacements
    cloned_labels = clone_result.cloned_labels
    handled_by_unit = clone_result.handled_by_unit
    unsupported = clone_result.unsupported
    missing = clone_result.missing
    native_helper_source_ids = clone_result.native_helper_source_ids


    # Preserve valid originals for enemy/shared consumers and native helper
    # TeamTypes. Helper factories must be able to satisfy both map TaskForces
    # and dynamically selected country-roster requests using these native IDs.
    native_category_by_unit = _registered_techno_categories(
        lines,
        installed_sections,
    )
    native_restore_ids = (
        set() if owned_clone_templates else native_helper_source_ids
    )
    for unit_id in sorted(native_restore_ids):
        if unit_id not in native_category_by_unit:
            continue
        installed_unit = installed_name_by_lower.get(unit_id.lower())
        native_section = native_map_name_by_lower.get(unit_id.lower())
        native_values = _standalone_clone_values_from_maps(
            installed_sections.get(installed_unit, {}) if installed_unit else {},
            native_map_sections.get(native_section, {}) if native_section else {},
        )
        if not native_values:
            continue
        native_build_limit = _positive_build_limit(native_values)
        ai_owner_ids = comma_items(
            _value_case_insensitive(native_values, 'Owner', '')
        )
        ai_owner_ids.extend(comma_items(
            _value_case_insensitive(native_values, 'RequiredHouses', '')
        ))
        ai_owner_ids.extend(
            str(country)
            for country in native_helper_support.get(unit_id, {}).get(
                'countries', ()
            )
            if country
        )
        for usage_house in unit_usage_houses(lines, unit_id, usage_index):
            if usage_house.lower() not in native_helper_names:
                continue
            canonical = canonical_house_name(records, usage_house)
            country = (
                records.get(canonical, {}).get('country')
                if canonical else usage_house.replace(' House', '')
            )
            if country:
                ai_owner_ids.append(country)
        if unit_id in buildable_ids and unit_id not in cloned_source_ids:
            # No player clone exists for this helper-used source. Keep its
            # earned player access alongside native AI access; no cloned buff
            # is attached to this original type.
            ai_owner_ids.extend(owner_ids)
        player_owner_names = {item.lower() for item in owner_ids}
        ai_owner_ids = unique_in_order(
            item for item in ai_owner_ids
            if item and (
                item.lower() not in player_owner_names
                or (unit_id in buildable_ids and unit_id not in cloned_source_ids)
            )
        )
        if not ai_owner_ids:
            continue
        original_rules = section_rules.setdefault(unit_id, {})
        owners = ','.join(ai_owner_ids)
        original_rules.update({
            'Owner': owners,
            'RequiredHouses': owners,
            # Generic campaign AI can request native roster IDs directly,
            # outside map TaskForces. Keep those originals factory-buildable
            # for concrete helper countries. Positive ownership hides them
            # from the player; a parent-country negative also blocks children.
            'ForbiddenHouses': None,
            'BuildLimit': native_build_limit,
            'TechLevel': _value_case_insensitive(
                native_values, 'TechLevel', UNLOCKED_TECH_LEVEL
            ),
            'PrerequisiteOverride': (
                _value_case_insensitive(native_values, 'PrerequisiteOverride', '')
                if str(_value_case_insensitive(
                    native_values, 'PrerequisiteOverride', ''
                ) or '').strip().lower() not in {'', 'none', '<none>'}
                else None
            ),
        })
        for key in list(section_value_map_preserve(lines, unit_id)):
            lowered = str(key).lower()
            if (
                lowered.startswith('prerequisite.list')
                or lowered in {
                    'prerequisite.negative',
                    'prerequisite.stolentechs',
                    'factoryowners',
                    'factoryowners.forbidden',
                }
            ):
                original_rules[key] = None
        for key, value in native_values.items():
            lowered = str(key).lower()
            if (
                lowered == 'techlevel'
                and unit_id in cloned_source_ids
                and unit_id in buildable_ids
            ):
                continue
            if (
                lowered in {'techlevel', 'prerequisite', 'factoryowners', 'factoryowners.forbidden'}
                or lowered.startswith('prerequisite.list')
                or lowered in {'prerequisite.negative', 'prerequisite.stolentechs'}
            ):
                original_rules[key] = value

    reference_rules, rewritten, mixed_taskforces = _clone_reference_rules(
        lines,
        replacements,
        allowed_houses,
        installed_sections,
        reserved_ids,
        taskforce_replacements=taskforce_replacements,
        # Helper TeamTypes should field the same buffed clones as the player.
        # Their native originals remain factory-buildable below as a fallback
        # for dynamic country-roster requests that do not use a map TaskForce.
        taskforce_allowed_houses=allowed_houses,
        structure_plan_allowed_houses_by_unit=(
            structure_plan_allowed_houses_by_unit
        ),
        native_trigger_reference_ids=native_trigger_reference_ids,
        direct_replacements=direct_replacements,
    )
    for section, values in reference_rules.items():
        section_rules.setdefault(section, {}).update(values)

    # Some mission objectives count player-built copies of a type also used by
    # enemy placements/TaskForces. Those sources deliberately use build-only
    # clones, so broad reference rewriting remains disabled. Retarget only the
    # exact reviewed Event IDs to the concrete clone allocated for this launch
    # (which may be a compact two-character veteran identity).
    event_values = section_value_map_preserve(lines, 'Events')
    runtime_placement_clone_ids = {}
    for placement_section in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        original_values = section_value_map_preserve(lines, placement_section)
        patched_values = section_rules.get(placement_section, {})
        for placement_id, original in original_values.items():
            patched = patched_values.get(placement_id)
            if patched is None:
                continue
            original_tokens = [
                token.strip() for token in str(original).split(',')
            ]
            patched_tokens = [
                token.strip() for token in str(patched).split(',')
            ]
            if (
                len(original_tokens) >= 2
                and len(patched_tokens) >= 2
                and original_tokens[1].upper() != patched_tokens[1].upper()
            ):
                runtime_placement_clone_ids[
                    original_tokens[1].upper()
                ] = patched_tokens[1]
    for source_id, event_ids in (objective_clone_event_refs or {}).items():
        source_id = str(source_id).upper()
        details = handled_by_unit.get(source_id, {})
        clone_id = str(
            runtime_placement_clone_ids.get(source_id)
            or reference_clone_id_by_source.get(source_id)
            or direct_replacements.get(source_id)
            or details.get('reference_clone_id')
            or details.get('clone_id')
            or ''
        ).strip()
        if not clone_id:
            # This launch has no isolated copy of the reviewed source. Keep
            # the authored event on its native identity; the override becomes
            # active automatically on launches where a clone is allocated.
            continue
        for event_id in event_ids:
            event_id = str(event_id)
            original = section_rules.get('Events', {}).get(
                event_id,
                event_values.get(event_id),
            )
            if original is None:
                mixed_taskforces.append(
                    f'Event {event_id} for {source_id} is missing'
                )
                continue
            tokens = [token.strip() for token in str(original).split(',')]
            replacement_count = sum(
                token.upper() == source_id for token in tokens
            )
            if not replacement_count:
                mixed_taskforces.append(
                    f'Event {event_id} does not reference {source_id}'
                )
                continue
            tokens = [
                clone_id if token.upper() == source_id else token
                for token in tokens
            ]
            replacement = ','.join(tokens)
            if len(f'{event_id}={replacement}'.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
                mixed_taskforces.append(
                    f'Event {event_id} clone rewrite exceeds parser limit'
                )
                continue
            section_rules.setdefault('Events', {})[event_id] = replacement
            rewritten += 1

    # Country veterancy lists contain exact TechnoType IDs. Replace originals
    # with the clone each country actually produces. Never append the whole
    # clone inventory: Phobos rejects oversized INI values (FBEYOND reached
    # 755 characters and logged VeteranUnits=M parse failures).
    veteran_field_by_category = {
        'infantry': 'VeteranInfantry',
        'units': 'VeteranUnits',
        'aircraft': 'VeteranAircraft',
        'defenses': 'VeteranBuildings',
    }
    player_countries = unique_in_order(
        main_player_countries
        + [
            str(country)
            for values in helper_autobuild_support.values()
            for country in values.get('countries', ())
            if country
        ]
    )
    main_player_country_names = {
        country.lower() for country in main_player_countries
    }
    for country in player_countries:
        is_main_player_country = country.lower() in main_player_country_names
        if is_main_player_country:
            country_replacements = player_veterancy_replacements
        else:
            country_replacements = {
                unit_id: clone_id
                for unit_id, clone_id in player_veterancy_replacements.items()
                if country.lower() in {
                    str(item).lower()
                    for item in helper_autobuild_support.get(
                        unit_id, {}
                    ).get('countries', ())
                }
            }
        country_values = section_value_map_preserve(lines, country)
        earned_clone_veterancy = {}
        if country_replacements:
            reward_veterancy = stacked_house_buff_values(
                rewards,
                {'Side': _value_case_insensitive(country_values, 'Side', '')},
                require_unlocked_access=require_unlocked_access,
                additional_unlocked_tech_ids=additional_unlocked_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=unit_specific_mode,
                veteran_priority_unit_ids=helper_priority_units_by_country.get(
                    country.lower(), ()
                ),
                max_veteran_value_length=None,
            )
            for category, field in veteran_field_by_category.items():
                reward_unit_ids = [
                    item.upper()
                    for item in comma_items(
                        _value_case_insensitive(reward_veterancy, field, '')
                    )
                    if item.upper() in country_replacements
                    and BUFF_TARGETS.get(item.upper(), {}).get('category') == category
                ]
                priority_ids = [
                    unit_id
                    for unit_id in helper_priority_units_by_country.get(
                        country.lower(), ()
                    )
                    if unit_id in reward_unit_ids
                ]
                ordered_unit_ids = unique_in_order(priority_ids + reward_unit_ids)
                earned_clone_veterancy[field] = [
                    country_replacements[unit_id]
                    for unit_id in ordered_unit_ids
                ]
        for category, field in veteran_field_by_category.items():
            current = _value_case_insensitive(country_values, field, '')
            clone_additions = earned_clone_veterancy.get(field, [])
            if not current and not clone_additions:
                continue
            items = [item.strip() for item in str(current).split(',') if item.strip()]
            rewritten_items = []
            for item in items:
                target_category = BUFF_TARGETS.get(item.upper(), {}).get('category')
                replacement = country_replacements.get(item.upper())
                if replacement and target_category == category:
                    rewritten_items.append(replacement)
                    if (
                        is_main_player_country
                        and item.upper() not in replacements
                    ):
                        # Build-only clones isolate factory production while
                        # mission placements and scripted TaskForces deliberately
                        # keep the native identity. Preserve that already-safe
                        # native Veteran* entry after the clone so both creation
                        # paths receive the earned rank. Normal reference clones
                        # still replace the native ID outright.
                        rewritten_items.append(item)
                    if not is_main_player_country:
                        # Helpers can still receive native fallback production
                        # outside TaskForces. Preserve veteran status for those
                        # originals after prioritizing the buffed clone ID.
                        rewritten_items.append(item)
                else:
                    rewritten_items.append(item)
            rewritten_value = merge_unique_csv_bounded(
                '',
                (
                    rewritten_items + clone_additions
                    if is_main_player_country
                    else clone_additions + rewritten_items
                ),
                MAX_COUNTRY_VETERAN_VALUE_LENGTH,
            )
            if rewritten_value != current:
                section_rules.setdefault(country, {})[field] = rewritten_value
    if replacements and not rewritten and not buildable_ids.intersection(replacements):
        unsupported.append('no friendly placement or exclusive TaskForce references rewritten')
    if mixed_taskforces:
        unsupported.append(
            'shared friendly/enemy TaskForces left on original types: '
            + ', '.join(mixed_taskforces)
        )
    return (
        section_rules,
        sorted(cloned_source_ids),
        handled_by_unit,
        unique_in_order(cloned_labels),
        unique_in_order(unsupported + [f'missing source {item}' for item in missing]),
    )
