"""Discover safe clone candidates and construct isolated player sections."""

from dataclasses import dataclass
from typing import Any

from ._shared import (
    BUFF_TARGETS,
    CLONE_POLICY,
    ENGINEER_UNIT_IDS,
    LIMITED_HERO_UNIT_IDS,
    LOCKED_TECH_LEVEL,
    NONTRAINABLE_UNIT_IDS,
    SHARED_WEAPON_USER_IDS,
    TECHNO_TYPE_LISTS,
    UNLOCKED_TECH_LEVEL,
    WEAPON_STAT_BUFF_TYPES,
    comma_items,
    linked_buff_variant_ids,
    production_owner_countries,
    re,
    section_value_map_preserve,
    script_referenced_taskforce_unit_ids,
    techno_type_possible_houses,
    unique_in_order,
    unit_usage_houses,
)
from .buff_values import (
    _register_map_type,
    apply_unit_buff_value,
    apply_weapon_buff_value,
    normalize_unit_strength,
)
from .helper_ai import (
    _append_prerequisite_alternatives,
)
from .clone_references import (
    _friendly_variant_clone_candidates,
    _helper_autocreate_taskforce_units,
    _helper_prerequisite_alternative,
    _positive_build_limit,
    _sanitize_engineer_clone_values,
    _standalone_clone_values,
    _standalone_clone_values_from_maps,
    _target_with_effective_unit_stats,
)
from .base import (
    _collision_safe_type_id,
    _remove_case_insensitive,
    _value_case_insensitive,
    parse_float,
)

LINKED_CLONE_REFERENCE_KEYS = {
    'convert.deploy',
    'convert.deploy.reversedas',
    'reversedas',
    'deploysinto',
    'undeploysinto',
    'passengers.allowed',
    'initialpayload.types',
}


@dataclass(slots=True)
class PlayerCloneContext:
    """Prepared map, ownership, helper, and reward inputs for clone building."""

    allowed_houses: set[str]
    buffed_helper_names: set[str]
    build_only_excluded_unit_ids: set[str]
    buildable_ids: set[str]
    compact_veteran_clone_ids: dict[str, str]
    counts_by_unit: dict[str, dict[str, int]]
    defense_helper_country_names: set[str]
    defense_helper_houses: list[str]
    direct_house_scoped_fallback: bool
    excluded_unit_ids: set[str]
    forced_clone_ids: set[str]
    initial_payload_source_ids: set[str]
    helper_autobuild_support: dict[str, dict[str, list[str]]]
    installed_name_by_lower: dict[str, str]
    installed_sections: dict[str, dict[str, Any]]
    lines: list[str]
    map_name_by_lower: dict[str, str]
    map_sections: dict[str, dict[str, Any]]
    native_helper_houses: list[str]
    native_helper_names: set[str]
    native_helper_support: dict[str, dict[str, list[str]]]
    native_map_name_by_lower: dict[str, str]
    native_map_sections: dict[str, dict[str, Any]]
    native_trigger_reference_ids: set[str]
    owned_clone_ids: dict[str, str]
    owned_clone_rule_overlays: dict[str, dict[str, Any]]
    owned_clone_templates: dict[str, dict[str, Any]]
    owner_ids: list[str]
    player_houses: list[str]
    records: dict[str, dict[str, Any]]
    reserved_ids: set[str]
    scripted_player_buff_taskforces: set[str]
    shared_player_veteran_ids: set[str]
    unit_specific_mode: bool
    unlimited_limit_ids: set[str]
    usage_index: dict[str, Any]


@dataclass(slots=True)
class PlayerCloneBuildResult:
    """Clone sections plus reference metadata consumed by finalization."""

    section_rules: dict[str, dict[str, Any]]
    replacements: dict[str, str]
    direct_replacements: dict[str, str]
    cloned_source_ids: set[str]
    taskforce_replacements: dict[str, str]
    structure_plan_allowed_houses_by_unit: dict[str, list[str]]
    player_veterancy_replacements: dict[str, str]
    cloned_labels: list[str]
    handled_by_unit: dict[str, dict[str, Any]]
    unsupported: list[str]
    missing: list[str]
    native_helper_source_ids: set[str]


def _is_direct_weapon_reference_key(key: object) -> bool:
    """Return whether a TechnoType key directly names one of its weapons."""
    lowered = str(key).lower()
    return (
        lowered in {
            'primary', 'secondary', 'eliteprimary', 'elitesecondary',
        }
        or re.fullmatch(r'(?:elite)?weapon\d+', lowered) is not None
    )


def build_player_clone_sections(
    context: PlayerCloneContext,
) -> PlayerCloneBuildResult:
    """Build owned clone sections while preserving native AI identities."""
    allowed_houses = context.allowed_houses
    buffed_helper_names = context.buffed_helper_names
    build_only_excluded_unit_ids = context.build_only_excluded_unit_ids
    buildable_ids = context.buildable_ids
    compact_veteran_clone_ids = context.compact_veteran_clone_ids
    counts_by_unit = context.counts_by_unit
    defense_helper_country_names = context.defense_helper_country_names
    defense_helper_houses = context.defense_helper_houses
    direct_house_scoped_fallback = context.direct_house_scoped_fallback
    excluded_unit_ids = context.excluded_unit_ids
    forced_clone_ids = context.forced_clone_ids
    initial_payload_source_ids = context.initial_payload_source_ids
    helper_autobuild_support = context.helper_autobuild_support
    installed_name_by_lower = context.installed_name_by_lower
    installed_sections = context.installed_sections
    lines = context.lines
    map_name_by_lower = context.map_name_by_lower
    map_sections = context.map_sections
    native_helper_houses = context.native_helper_houses
    native_helper_names = context.native_helper_names
    native_helper_support = context.native_helper_support
    native_map_name_by_lower = context.native_map_name_by_lower
    native_map_sections = context.native_map_sections
    native_trigger_reference_ids = context.native_trigger_reference_ids
    owned_clone_ids = context.owned_clone_ids
    owned_clone_rule_overlays = context.owned_clone_rule_overlays
    owned_clone_templates = context.owned_clone_templates
    owner_ids = context.owner_ids
    player_houses = context.player_houses
    records = context.records
    reserved_ids = context.reserved_ids
    scripted_player_buff_taskforces = context.scripted_player_buff_taskforces
    shared_player_veteran_ids = context.shared_player_veteran_ids
    unit_specific_mode = context.unit_specific_mode
    unlimited_limit_ids = context.unlimited_limit_ids
    usage_index = context.usage_index

    section_rules = {}
    replacements = {}
    direct_replacements = {}
    clone_id_by_source = {}
    reference_clone_id_by_source = {}
    cloned_source_ids = set()
    taskforce_replacements = {}
    structure_plan_allowed_houses_by_unit = {}
    player_veterancy_replacements = {}
    cloned_labels = []
    handled_by_unit = {}
    unsupported = []
    missing = []
    ownership_sections_by_lower = {
        str(name).lower(): values for name, values in map_sections.items()
    }
    possible_house_cache = {}

    def possible_native_houses(unit_id, effective_values=None):
        unit_upper = str(unit_id).upper()
        if unit_upper in possible_house_cache:
            return possible_house_cache[unit_upper]
        if effective_values is None:
            installed_name = installed_name_by_lower.get(unit_upper.lower())
            native_name = native_map_name_by_lower.get(unit_upper.lower())
            effective_values = _standalone_clone_values_from_maps(
                installed_sections.get(installed_name, {})
                if installed_name else {},
                native_map_sections.get(native_name, {})
                if native_name else {},
            )
        possible = set(techno_type_possible_houses(
            lines,
            effective_values,
            records=records,
            sections=map_sections,
            sections_by_lower=ownership_sections_by_lower,
        ))
        possible_house_cache[unit_upper] = possible
        return possible

    # Event 61 is the campaign's exact TechnoType-destroyed/nonexistent test.
    # Its Trigger owner is often only a story executor and does not identify
    # which House's object is being watched. If a type has both friendly and
    # non-friendly consumers and such an event is owned outside the assisted
    # coalition, neither globally retargeting it nor leaving it on the source
    # is safe after cloning. Keep that map's type native instead. Direct global
    # buffs will then be rejected by the normal usage guard, but hero loss and
    # objective scripts cannot fire merely because the clone changed identity.
    ambiguous_mission_event_ids = set()
    trigger_values = {
        str(key).lower(): value
        for key, value in section_value_map_preserve(lines, 'Triggers').items()
    }
    for key, value in section_value_map_preserve(lines, 'Events').items():
        tokens = [token.strip().upper() for token in str(value).split(',')]
        if '61' not in tokens:
            continue
        trigger_owner = str(
            trigger_values.get(str(key).lower(), '')
        ).split(',', 1)[0].strip().lower()
        if trigger_owner in allowed_houses:
            continue
        for unit_id in set(tokens).intersection(BUFF_TARGETS):
            usage_houses = {
                str(house).lower()
                for house in unit_usage_houses(lines, unit_id, usage_index)
                if house
            }
            if (
                usage_houses.intersection(allowed_houses)
                and not usage_houses.issubset(allowed_houses)
            ):
                ambiguous_mission_event_ids.add(unit_id)

    # Story reinforcements use several map actions (Create Team, Reinforcement
    # Team, reinforcement-at-waypoint variants, and more). Replacing a type in
    # one of those TaskForces can stop transports/paradrops, break later
    # ownership hand-offs, or invalidate exact identity checks. Keep every
    # action-referenced team's source identities native. An earned/buildable
    # copy is still created independently below.
    scripted_team_unit_ids = script_referenced_taskforce_unit_ids(
        lines,
        map_sections,
    )
    # Reviewed player-start TaskForces may safely use isolated buffed clones.
    # Keep blanket story-team preservation everywhere else: transports,
    # paradrops, hand-offs, and exact-ID events can depend on native identity.
    scripted_player_clone_unit_ids = set()
    sections_by_lower = {
        str(section).lower(): values
        for section, values in map_sections.items()
    }
    for taskforce_id in scripted_player_buff_taskforces:
        for value in sections_by_lower.get(taskforce_id, {}).values():
            tokens = [token.strip() for token in str(value).split(',')]
            if (
                len(tokens) >= 2
                and tokens[0].isdigit()
                and tokens[1]
                and tokens[1].lower() not in {'none', '<none>'}
            ):
                scripted_player_clone_unit_ids.add(tokens[1].upper())
    scripted_team_unit_ids.difference_update(scripted_player_clone_unit_ids)

    direct_friendly_ids = set()
    for section in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for value in section_value_map_preserve(lines, section).values():
            tokens = [token.strip() for token in str(value).split(',')]
            if len(tokens) >= 2 and tokens[0].lower() in allowed_houses:
                direct_friendly_ids.add(tokens[1].upper())
    exact_reference_ids = set()
    for section in ('Events', 'Actions'):
        for value in section_value_map_preserve(lines, section).values():
            tokens = [token.strip() for token in str(value).split(',')]
            exact_reference_ids.update(
                token.upper()
                for index, token in enumerate(tokens)
                if token
                # Every Action is serialized as eight fields after its count;
                # field eight is a waypoint. A waypoint such as EHEAD's `FV`
                # can equal a TechnoType ID but is never an exact type reference.
                and not (
                    section == 'Actions'
                    and index > 0
                    and (index - 1) % 8 == 7
                )
            )

    native_helper_taskforces = _helper_autocreate_taskforce_units(
        lines,
        native_helper_names,
    )
    native_helper_source_ids = {
        unit_id
        for unit_ids in native_helper_taskforces.values()
        for unit_id in unit_ids
        if 'DUMMY' not in unit_id and not unit_id.endswith('MCV')
    }

    # Campaign AI also selects units from its country roster without naming
    # every choice in a map TaskForce. If launch ownership removes that helper
    # from an earned original, the AI can repeatedly request the now-illegal
    # type and block its factory queue. Treat every buildable type whose native
    # Owner/RequiredHouses names a configured helper as a helper source too.
    helper_country_ancestry = {}
    for house in native_helper_houses:
        country = str(
            records.get(house, {}).get('country') or house.replace(' House', '')
        )
        ancestry = []
        current = country
        while current and current.lower() not in {item.lower() for item in ancestry}:
            ancestry.append(current)
            installed_country = installed_name_by_lower.get(current.lower())
            native_country = native_map_name_by_lower.get(current.lower())
            country_values = _standalone_clone_values_from_maps(
                installed_sections.get(installed_country, {}) if installed_country else {},
                native_map_sections.get(native_country, {}) if native_country else {},
            )
            current = str(
                _value_case_insensitive(country_values, 'ParentCountry', '') or ''
            ).strip()
        helper_country_ancestry[country] = {item.lower() for item in ancestry}
    native_helper_country_ids = {
        ancestor
        for ancestry in helper_country_ancestry.values()
        for ancestor in ancestry
    }
    for unit_id in sorted(buildable_ids):
        installed_unit = installed_name_by_lower.get(unit_id.lower())
        native_unit = native_map_name_by_lower.get(unit_id.lower())
        native_values = _standalone_clone_values_from_maps(
            installed_sections.get(installed_unit, {}) if installed_unit else {},
            native_map_sections.get(native_unit, {}) if native_unit else {},
        )
        native_owners = {
            item.lower()
            for item in comma_items(_value_case_insensitive(native_values, 'Owner', ''))
            + comma_items(_value_case_insensitive(native_values, 'RequiredHouses', ''))
        }
        if native_owners.intersection(native_helper_country_ids):
            native_helper_source_ids.add(unit_id)
            matching_countries = [
                country
                for country, ancestry in helper_country_ancestry.items()
                if ancestry.intersection(native_owners)
            ]
            native_support = native_helper_support.setdefault(
                unit_id,
                {'countries': [], 'prerequisites': []},
            )
            native_support['countries'] = unique_in_order(
                list(native_support.get('countries', ())) + matching_countries
            )
            buffed_countries = [
                country
                for country in matching_countries
                if country.lower() in buffed_helper_names
                and (
                    BUFF_TARGETS.get(unit_id, {}).get('category') != 'defenses'
                    or country.lower() in defense_helper_country_names
                )
            ]
            unit_support = None
            if buffed_countries:
                unit_support = helper_autobuild_support.setdefault(
                    unit_id,
                    {'countries': [], 'prerequisites': []},
                )
                unit_support['countries'] = unique_in_order(
                    list(unit_support.get('countries', ())) + buffed_countries
                )
            alternative = _helper_prerequisite_alternative(native_values)
            if alternative:
                native_support['prerequisites'] = unique_in_order(
                    list(native_support.get('prerequisites', ())) + [alternative]
                )
                if unit_support is not None:
                    unit_support['prerequisites'] = unique_in_order(
                        list(unit_support.get('prerequisites', ())) + [alternative]
                    )

    # Numbered helper House entries are exact defense construction requests.
    # Concrete RequiredHouses ownership isolates opted-in helper clones while
    # enemy plans retain native IDs.
    for house in defense_helper_houses:
        country = str(
            records.get(house, {}).get('country') or house.replace(' House', '')
        )
        for key, value in section_value_map_preserve(lines, house).items():
            if not str(key).isdigit():
                continue
            unit_id = str(value).split(',', 1)[0].strip().upper()
            if (
                unit_id not in buildable_ids
                or BUFF_TARGETS.get(unit_id, {}).get('category') != 'defenses'
            ):
                continue
            native_helper_source_ids.add(unit_id)
            installed_unit = installed_name_by_lower.get(unit_id.lower())
            native_unit = native_map_name_by_lower.get(unit_id.lower())
            native_values = _standalone_clone_values_from_maps(
                installed_sections.get(installed_unit, {}) if installed_unit else {},
                native_map_sections.get(native_unit, {}) if native_unit else {},
            )
            alternative = _helper_prerequisite_alternative(native_values)
            for support_table in (
                native_helper_support,
                helper_autobuild_support,
            ):
                support = support_table.setdefault(
                    unit_id, {'countries': [], 'prerequisites': []}
                )
                support['countries'] = unique_in_order(
                    list(support.get('countries', ())) + [country]
                )
                if alternative:
                    support['prerequisites'] = unique_in_order(
                        list(support.get('prerequisites', ())) + [alternative]
                    )

    clone_candidates = [
        (
            unit_id,
            str(
                BUFF_TARGETS.get(unit_id, {}).get('linked_buff_source')
                or unit_id
            ).upper(),
            counts,
        )
        for unit_id, counts in counts_by_unit.items()
    ]
    clone_candidates.extend(
        _friendly_variant_clone_candidates(
            lines,
            installed_sections,
            map_sections,
            counts_by_unit,
            allowed_houses,
            usage_index,
        )
    )
    existing_candidate_ids = {
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    }
    # Deploying/converting units and initial-payload support identities must
    # exist even when access was earned without any matching buff. Keep those
    # forms tied to the source reward so later stacks affect every mode.
    for target_unit_id in sorted(buildable_ids):
        if target_unit_id not in BUFF_TARGETS:
            continue
        for unit_id in sorted(
            linked_buff_variant_ids(target_unit_id) - {target_unit_id}
        ):
            if unit_id in existing_candidate_ids or unit_id not in BUFF_TARGETS:
                continue
            clone_candidates.append((
                unit_id,
                target_unit_id,
                counts_by_unit.get(
                    unit_id,
                    counts_by_unit.get(target_unit_id, {}),
                ),
            ))
            existing_candidate_ids.add(unit_id)
    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(native_helper_source_ids.intersection(buildable_ids))
        if unit_id in BUFF_TARGETS
        and unit_id not in existing_candidate_ids
        and (
            BUFF_TARGETS[unit_id].get('category') != 'defenses'
            or unit_id in counts_by_unit
            or unit_id in shared_player_veteran_ids
        )
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )

    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(helper_autobuild_support)
        if unit_id in buildable_ids
        and unit_id in BUFF_TARGETS
        and unit_id not in existing_candidate_ids
        and (
            BUFF_TARGETS[unit_id].get('category') != 'defenses'
            or unit_id in counts_by_unit
            or unit_id in shared_player_veteran_ids
        )
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )
    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(shared_player_veteran_ids)
        if unit_id in BUFF_TARGETS and unit_id not in existing_candidate_ids
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )
    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(forced_clone_ids)
        if unit_id in BUFF_TARGETS and unit_id not in existing_candidate_ids
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )
    # Every player-buildable identity uses the owned roster, even with no
    # direct buff. Otherwise unbuffed access falls back to the native ID and
    # campaign AI/player production still share one global TechnoType.
    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(buildable_ids)
        if unit_id in BUFF_TARGETS and unit_id not in existing_candidate_ids
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )
    clone_candidates.extend(
        (unit_id, unit_id, counts_by_unit.get(unit_id, {}))
        for unit_id in sorted(unlimited_limit_ids)
        if unit_id in BUFF_TARGETS and unit_id not in existing_candidate_ids
    )
    existing_candidate_ids.update(
        str(unit_id).upper() for unit_id, _target_id, _counts in clone_candidates
    )

    # Clone graphs are closed in both directions. Mission exclusions can
    # remove the root count/build candidate while its deployed form still
    # needs an isolated player clone (or vice versa). Add the missing half as
    # a locked reference-only candidate carrying the same earned stacks.
    for unit_id, _target_id, counts in list(clone_candidates):
        for peer_id in sorted(
            linked_buff_variant_ids(unit_id) - {str(unit_id).upper()}
        ):
            if peer_id in existing_candidate_ids or peer_id not in BUFF_TARGETS:
                continue
            peer_target_id = str(
                BUFF_TARGETS[peer_id].get('linked_buff_source') or peer_id
            ).upper()
            clone_candidates.append((peer_id, peer_target_id, dict(counts)))
            existing_candidate_ids.add(peer_id)

    candidate_counts_by_id = {
        str(unit_id).upper(): counts
        for unit_id, _target_id, counts in clone_candidates
    }

    def preserve_native_effects(unit_id, counts, extra_types=()):
        """Keep unsafe effects off native mission units; allow guarded peers."""
        handled_types = {'speed'}.intersection(counts)
        handled_types.update(
            buff_type for buff_type in extra_types if buff_type in counts
        )
        if not handled_types:
            return
        handled_by_unit[unit_id] = {
            'unit_buff_types': handled_types,
            'weapon_ids': set(),
            'clone_id': '',
        }

    for unit_id, target_unit_id, counts in clone_candidates:
        unit_id = str(unit_id).upper()
        linked_peer_ids = linked_buff_variant_ids(unit_id) - {unit_id}
        linked_candidate_clone = any(
            peer_id in candidate_counts_by_id
            for peer_id in linked_peer_ids
        )
        linked_excluded_reference_clone = bool(
            unit_id in excluded_unit_ids
            and any(
                peer_id in candidate_counts_by_id
                for peer_id in linked_peer_ids
            )
        )
        linked_script_reference_clone = bool(
            linked_candidate_clone
            and unit_id not in buildable_ids
            and (
                unit_id in scripted_team_unit_ids
                or unit_id in ambiguous_mission_event_ids
            )
        )
        if linked_excluded_reference_clone and not counts:
            for peer_id in sorted(linked_peer_ids):
                peer_counts = candidate_counts_by_id.get(peer_id, {})
                if peer_counts:
                    counts = dict(peer_counts)
                    break
        # Cloaked mission heroes can disappear from their controlling player's
        # view once their own sight no longer reveals them. Installed Ares 3.0
        # and Phobos 0.3 expose no owner/allied visibility override for cloak.
        # Keep every map-authored hero instance uncloaked. If that hero is also
        # normally buildable, its isolated production clone still receives the
        # earned cloak reward.
        mission_hero_cloak = (
            'cloak' in counts
            and target_unit_id in LIMITED_HERO_UNIT_IDS
            and bool(unit_usage_houses(lines, unit_id, usage_index))
        )
        # Mission-authored operator/passenger/loss chains can require the
        # original TechnoType identity even when access, veterancy, helper, or
        # unlimited-cap logic independently asks for a clone. Filtering only
        # counts_by_unit is insufficient: those later candidate sources can
        # otherwise recreate the excluded clone and rewrite the story
        # TaskForce anyway (ASIREN Tanya and SRED Morales reproduced this).
        excluded_build_only_clone = (
            unit_id in excluded_unit_ids
            and unit_id in build_only_excluded_unit_ids
            and unit_id in buildable_ids
        )
        initial_payload_clone = unit_id in initial_payload_source_ids
        hero_build_only_clone = (
            mission_hero_cloak and unit_id in buildable_ids
        )
        allowed_build_only_clone = (
            excluded_build_only_clone
            or hero_build_only_clone
            or initial_payload_clone
        )
        if (
            unit_id in excluded_unit_ids
            and not allowed_build_only_clone
            and not linked_excluded_reference_clone
        ):
            preserve_native_effects(
                unit_id,
                counts,
                {'cloak'} if mission_hero_cloak else (),
            )
            continue
        scripted_build_only_clone = (
            unit_id in scripted_team_unit_ids
            and (
                unit_id in buildable_ids
                or initial_payload_clone
            )
        )
        if (
            unit_id in scripted_team_unit_ids
            and not scripted_build_only_clone
            and not linked_excluded_reference_clone
            and not linked_script_reference_clone
        ):
            preserve_native_effects(
                unit_id,
                counts,
                {'cloak'} if mission_hero_cloak else (),
            )
            unsupported.append(
                f'{BUFF_TARGETS.get(unit_id, {}).get("label", unit_id)} '
                'scripted reinforcement kept native'
            )
            continue
        target = BUFF_TARGETS.get(target_unit_id, {})
        build_only_clone = (
            excluded_build_only_clone
            or initial_payload_clone
            or linked_excluded_reference_clone
            or linked_script_reference_clone
            or scripted_build_only_clone
            or hero_build_only_clone
            or (
                unit_id in ambiguous_mission_event_ids
                and unit_id in buildable_ids
            )
        )
        if mission_hero_cloak and not build_only_clone:
            preserve_native_effects(unit_id, counts, {'cloak'})
            continue
        if (
            unit_id in ambiguous_mission_event_ids
            and not build_only_clone
            and not linked_excluded_reference_clone
        ):
            preserve_native_effects(unit_id, counts)
            unsupported.append(
                f'{target.get("label", target_unit_id)} shared mission event kept native'
            )
            continue
        identity_target = BUFF_TARGETS.get(unit_id, target)
        list_section = TECHNO_TYPE_LISTS.get(identity_target.get('category'))
        if not list_section:
            continue
        owned_template = owned_clone_templates.get(unit_id)
        source_unit = (
            map_name_by_lower.get(unit_id.lower())
            or installed_name_by_lower.get(unit_id.lower())
        )
        if not source_unit:
            if owned_template:
                # Reviewed map-only reward templates are complete standalone
                # definitions. Their source ID may not exist in installed
                # rules or the selected mission (for example Super Thor).
                source_unit = unit_id
            else:
                missing.append(unit_id)
                continue

        unit_usage = unit_usage_houses(lines, unit_id, usage_index)
        direct_types = set(counts) - WEAPON_STAT_BUFF_TYPES
        weapon_buff_types = WEAPON_STAT_BUFF_TYPES.intersection(counts)
        installed_unit = installed_name_by_lower.get(unit_id.lower())
        map_unit = map_name_by_lower.get(unit_id.lower())
        effective_unit_values = _standalone_clone_values(
            lines,
            installed_sections,
            installed_unit,
            map_unit,
        )
        native_unit_values = _standalone_clone_values_from_maps(
            installed_sections.get(installed_unit, {}) if installed_unit else {},
            native_map_sections.get(
                native_map_name_by_lower.get(unit_id.lower()), {}
            ),
        )
        unsafe_unit_houses = {
            house
            for house in (
                unit_usage
                | possible_native_houses(unit_id, effective_unit_values)
            )
            if house.lower() not in allowed_houses
        }
        # A map may reuse an installed ID for a different scripted hero (for
        # example SHAND [SUPR]=Reznov with BuildLimit=1). Earned buildable
        # clones copy the installed identity, so their cap must also come from
        # installed rules. Map-only types keep their map-authored live cap.
        clone_build_limit = _positive_build_limit(
            installed_sections.get(installed_unit, {})
            if installed_unit
            else native_unit_values
        )
        if not clone_build_limit and target.get('build_limit') is not None:
            # Map/campaign-only production rewards can have no native source
            # in installed rules. Keep their reviewed template cap after the
            # generic production-gate cleanup; NACLONS otherwise became
            # unlimited before its earned building-limit stacks were added.
            clone_build_limit = str(target['build_limit'])
        clone_source_values = dict(owned_template or effective_unit_values)
        mission_player_override = bool(
            owned_template is not None
            and not build_only_clone
            and any(house.lower() in allowed_houses for house in unit_usage)
        )
        native_override_values = {}
        if mission_player_override:
            # Campaign maps commonly strengthen, weaken, rearm, or otherwise
            # retune player units. Starting from only the installed/static
            # template discarded those authored values before rewards were
            # applied (SRECH Volkov: 1350 -> 600). Layer the player's map
            # identity onto its isolated clone, while leaving production and
            # ownership gates to the normal clone-safety path below. Enemy-only
            # map identities never satisfy this ownership guard.
            native_override_values = native_map_sections.get(
                native_map_name_by_lower.get(unit_id.lower()), {}
            )
            for key, value in native_override_values.items():
                lowered = str(key).lower()
                if (
                    lowered in CLONE_POLICY['production_gate_keys']
                    or lowered.startswith(tuple(
                        CLONE_POLICY['production_gate_prefixes']
                    ))
                    or lowered in {
                        'owner', 'requiredhouses', 'forbiddenhouses',
                    }
                ):
                    continue
                _remove_case_insensitive(clone_source_values, key)
                clone_source_values[key] = value
        if unit_id in buildable_ids and installed_unit:
            if owned_template is None and unit_id == target_unit_id:
                clone_source_values = dict(installed_sections.get(installed_unit, {}))
            for key, value in effective_unit_values.items():
                lowered = str(key).lower()
                if (
                    lowered in CLONE_POLICY['production_gate_keys']
                    or lowered.startswith(tuple(CLONE_POLICY['production_gate_prefixes']))
                ):
                    _remove_case_insensitive(clone_source_values, key)
                    clone_source_values[key] = value
            # Chaos access rules set faction bands on the map-local original.
            # Buildable clones otherwise restart from installed values and lose
            # that band, interleaving factions in Infantry/Units/Defenses tabs.
            if unit_specific_mode:
                cameo_priority = _value_case_insensitive(
                    effective_unit_values, 'CameoPriority'
                )
                if cameo_priority is not None:
                    clone_source_values['CameoPriority'] = cameo_priority
        if owned_template is not None:
            for key, value in owned_clone_rule_overlays.get(unit_id, {}).items():
                _remove_case_insensitive(clone_source_values, key)
                if value is not None:
                    clone_source_values[key] = value
            # Mission-authored variants may disable a deploy/conversion link
            # on their native story identity. The separately earned owned
            # clone must retain the complete installed/static reward identity.
            for key, value in owned_template.items():
                if str(key).lower() not in LINKED_CLONE_REFERENCE_KEYS:
                    continue
                _remove_case_insensitive(clone_source_values, key)
                clone_source_values[key] = value
            if (
                unit_id in buildable_ids
                and owned_clone_rule_overlays.get(unit_id)
            ):
                # Installed/map source gates belong to the native AI identity.
                # Keep only gates explicitly emitted by current player access
                # planning. Otherwise FactoryOwners/StolenTech restrictions
                # can survive on the MORP clone and expose the original after
                # capture while hiding its intended replacement.
                explicit_production_keys = {
                    str(key).lower()
                    for key, value in owned_clone_rule_overlays.get(
                        unit_id, {}
                    ).items()
                    if value is not None
                }
                for key in list(clone_source_values):
                    lowered = str(key).lower()
                    if (
                        lowered in CLONE_POLICY['production_gate_keys']
                        or lowered.startswith(tuple(
                            CLONE_POLICY['production_gate_prefixes']
                        ))
                    ) and lowered not in explicit_production_keys:
                        clone_source_values.pop(key, None)
        if target_unit_id in ENGINEER_UNIT_IDS:
            clone_source_values = _sanitize_engineer_clone_values(
                clone_source_values, target
            )
            # Engineer sanitization removes unsafe cached Chrono mutations, but
            # a campaign-authored player Engineer may deliberately have more
            # health. Keep that safe mission value as the reward baseline.
            mission_strength = _value_case_insensitive(
                native_override_values, 'Strength'
            )
            if mission_strength is not None:
                _remove_case_insensitive(clone_source_values, 'Strength')
                clone_source_values['Strength'] = mission_strength
        # Every player/spawn clone must carry one complete, positive health
        # baseline even when a mission section overrides Strength with 0/1,
        # malformed text, or alternate key casing.  Prefer the reviewed owned
        # template before the older reward snapshot when repairing bad input.
        normalize_unit_strength(
            clone_source_values,
            target,
            owned_template or {},
            effective_unit_values,
        )
        effective_target = _target_with_effective_unit_stats(
            target, clone_source_values
        )
        weapon_targets = dict(target.get('weapons', {}))
        if (
            unit_id != target_unit_id
            or target.get('category') == 'defenses'
            or mission_player_override
        ):
            # Trainable defenses switch weapons after promotion, and mission
            # heroes may replace or disable installed weapons. Pull every
            # direct weapon from the effective clone so earned weapon buffs
            # follow the actual mission identity rather than a stale roster
            # weapon. Missing/disabled placeholders are ignored below.
            for key, value in clone_source_values.items():
                if not _is_direct_weapon_reference_key(key):
                    continue
                weapon = str(value or '').strip()
                if (
                    not weapon
                    or weapon.lower() in {'none', '<none>'}
                    or weapon.lower().startswith('nota')
                    or weapon in weapon_targets
                ):
                    continue
                installed_weapon = installed_name_by_lower.get(weapon.lower())
                map_weapon = map_name_by_lower.get(weapon.lower())
                weapon_values = _standalone_clone_values(
                    lines,
                    installed_sections,
                    installed_weapon,
                    map_weapon,
                )
                if not weapon_values:
                    continue
                weapon_targets[weapon] = {
                    'damage': parse_float(
                        _value_case_insensitive(weapon_values, 'Damage', 0), 0
                    ),
                    'range': parse_float(
                        _value_case_insensitive(weapon_values, 'Range', 0), 0
                    ),
                    'rof': parse_float(
                        _value_case_insensitive(weapon_values, 'ROF', 0), 0
                    ),
                }
        direct_weapon_keys = {
            weapon.upper(): [
                key
                for key, value in clone_source_values.items()
                if (
                    _is_direct_weapon_reference_key(key)
                    and str(value).strip().lower() == weapon.lower()
                )
            ]
            for weapon in weapon_targets
        }
        weapon_unsafe = False
        if weapon_buff_types:
            for weapon in weapon_targets:
                if not direct_weapon_keys.get(weapon.upper()):
                    continue
                weapon_users = SHARED_WEAPON_USER_IDS.get(weapon.upper(), {unit_id})
                if any(
                    house.lower() not in allowed_houses
                    for weapon_user in weapon_users
                    for house in (
                        unit_usage_houses(lines, weapon_user, usage_index)
                        | possible_native_houses(weapon_user)
                    )
                ):
                    weapon_unsafe = True
                    break
        is_variant = unit_id != target_unit_id
        linked_buildable_variant = (
            is_variant and target_unit_id in buildable_ids
        )
        native_helper_shared = unit_id in native_helper_source_ids
        helper_autobuild_shared = unit_id in helper_autobuild_support
        shared_player_veteran = unit_id in shared_player_veteran_ids
        defense_buildable = (
            target.get('category') == 'defenses'
            and unit_id in buildable_ids
        )
        owned_player_buildable = (
            unit_id in buildable_ids
            and unit_id == target_unit_id
            and unit_id in owned_clone_templates
        )
        forced_player_clone = unit_id in forced_clone_ids or defense_buildable
        forced_isolated_clone = (
            unit_id in unlimited_limit_ids
            or bool({'build_limit', 'building_limit'}.intersection(direct_types))
            or 'speed' in direct_types
        )
        variant_has_effect = bool(direct_types) or any(
            direct_weapon_keys.get(weapon.upper())
            for weapon in weapon_targets
            if weapon_buff_types
        )
        needs_direct_house_fallback = bool(
            direct_house_scoped_fallback
            and direct_types.intersection(
                {'production', 'cost', 'speed', 'armor'}
            )
        )
        if (
            not is_variant
            and not (unsafe_unit_houses and direct_types)
            and not weapon_unsafe
            and not native_helper_shared
            and not helper_autobuild_shared
            and not shared_player_veteran
            and not owned_player_buildable
            and not forced_player_clone
            and not forced_isolated_clone
            and not needs_direct_house_fallback
            and not linked_excluded_reference_clone
            and not linked_script_reference_clone
        ) or (
            is_variant
            and not variant_has_effect
            and not linked_buildable_variant
            and not native_helper_shared
            and not helper_autobuild_shared
            and not shared_player_veteran
            and not forced_player_clone
            and not forced_isolated_clone
            and not linked_excluded_reference_clone
            and not linked_script_reference_clone
        ):
            continue

        clone_id = _collision_safe_type_id(
            compact_veteran_clone_ids.get(
                unit_id,
                owned_clone_ids.get(
                    unit_id,
                    f'{CLONE_POLICY["unit_id_prefix"]}{unit_id}',
                ),
            ),
            f'player-unit:{unit_id}',
            reserved_ids,
        )
        clone_values = dict(clone_source_values)
        if target.get('category') == 'special_buildings':
            clone_values['BuildCat'] = str(target.get('build_category', 'Tech'))
            clone_values['CameoPriority'] = str(
                target.get('cameo_priority', -1000)
            )
        prerequisite_override = _value_case_insensitive(
            clone_values, 'PrerequisiteOverride', ''
        )
        has_prerequisite_lists = bool(
            comma_items(_value_case_insensitive(
                clone_values, 'Prerequisite.Lists', ''
            ))
        )
        if (
            str(prerequisite_override or '').strip().lower() in {'none', '<none>'}
            and not has_prerequisite_lists
        ):
            _remove_case_insensitive(clone_values, 'PrerequisiteOverride')
        if not any(
            str(key).lower() == 'image' and str(value).strip()
            for key, value in clone_values.items()
        ):
            # TechnoType art defaults to its own section ID. A standalone clone
            # therefore needs the original ID explicitly or it would look for a
            # nonexistent clone-specific art section.
            clone_values['Image'] = source_unit
        handled_unit_types = set()
        handled_weapon_ids = set()
        for buff_type in (
            'health', 'armor', 'sight', 'ammo', 'passenger_capacity',
            'open_topped', 'self_healing', 'cloak', 'sensors', 'production',
            'cost', 'speed',
        ):
            if buff_type in direct_types and apply_unit_buff_value(
                clone_values, effective_target, buff_type, counts[buff_type]
            ):
                handled_unit_types.add(buff_type)
        for weapon, base_stats in weapon_targets.items():
            reference_keys = direct_weapon_keys.get(weapon.upper(), [])
            if not reference_keys:
                continue
            source_weapon = (
                map_name_by_lower.get(weapon.lower())
                or installed_name_by_lower.get(weapon.lower())
            )
            installed_weapon = installed_name_by_lower.get(weapon.lower())
            map_weapon = map_name_by_lower.get(weapon.lower())
            weapon_values = _standalone_clone_values(
                lines,
                installed_sections,
                installed_weapon,
                map_weapon,
            )
            if not source_weapon:
                missing.append(weapon)
                continue
            missing_core = [
                required
                for required in CLONE_POLICY['required_weapon_fields']
                if not any(
                    str(key).lower() == required.lower() and str(value).strip()
                    for key, value in weapon_values.items()
                )
            ]
            if missing_core:
                missing.append(
                    f'{weapon} core field(s) {", ".join(missing_core)}'
                )
                continue
            applied_weapon = False
            for buff_type in ('damage', 'range', 'reload'):
                if buff_type in weapon_buff_types:
                    applied_weapon = (
                        apply_weapon_buff_value(
                            weapon_values, base_stats, buff_type, counts[buff_type]
                        )
                        or applied_weapon
                    )
            if not applied_weapon:
                continue
            weapon_clone = _collision_safe_type_id(
                f'{CLONE_POLICY["weapon_id_prefix"]}{unit_id}{weapon}',
                f'player-weapon:{unit_id}:{weapon}',
                reserved_ids,
            )
            _register_map_type(
                section_rules, lines, installed_sections, 'WeaponTypes', weapon_clone
            )
            section_rules[weapon_clone] = weapon_values
            for key in reference_keys:
                clone_values[key] = weapon_clone
            handled_weapon_ids.add(weapon.upper())

        if target.get('special_damage_fields') and 'damage' in weapon_buff_types:
            unsupported.append(
                f'{target.get("label", unit_id)} spawned-missile damage'
            )
        if unit_id in buildable_ids:
            clone_values['TechLevel'] = UNLOCKED_TECH_LEVEL
            # Preserve positive live-unit caps such as Centurion/Libra/Volkov
            # BuildLimit=1. Launcher locks (0) and one-build-only limits (-1)
            # can deadlock Autocreate teams and remain intentionally removed.
            _remove_case_insensitive(clone_values, 'BuildLimit')
            if target.get('build_limit') is not None:
                limit_buff_type = (
                    'building_limit'
                    if target.get('category') == 'special_buildings'
                    else 'build_limit'
                )
                if unit_id in unlimited_limit_ids:
                    handled_unit_types.add('build_limit')
                elif clone_build_limit:
                    build_limit = int(clone_build_limit)
                    if counts.get(limit_buff_type):
                        build_limit += int(counts[limit_buff_type])
                        handled_unit_types.add(limit_buff_type)
                    clone_values['BuildLimit'] = str(build_limit)
            elif clone_build_limit:
                clone_values['BuildLimit'] = clone_build_limit
            helper_support = helper_autobuild_support.get(unit_id, {})
            helper_owner_ids = [
                str(item)
                for item in helper_support.get('countries', ())
                if item
            ]
            if target.get('category') == 'defenses':
                helper_country_names = {
                    country.lower() for country in helper_owner_ids
                }
                structure_plan_allowed_houses_by_unit[unit_id] = unique_in_order(
                    player_houses
                    + [
                        house
                        for house in defense_helper_houses
                        if str(
                            records.get(house, {}).get('country')
                            or house.replace(' House', '')
                        ).lower() in helper_country_names
                    ]
                )
            clone_owner_ids = unique_in_order(owner_ids + helper_owner_ids)
            if clone_owner_ids:
                # Factories evaluate Owner through the active country's
                # ParentCountry. Campaigns such as SRAVEN use a concrete
                # ``Player`` child of USSR; Owner=Player alone leaves its
                # transferred Soviet barracks/factory empty. Include parent
                # IDs for factory eligibility, while RequiredHouses remains
                # concrete and keeps hostile USSR descendants off the clone.
                production_owners = ','.join(
                    production_owner_countries(
                        lines, clone_owner_ids, sections=map_sections
                    )
                )
                required_houses = ','.join(clone_owner_ids)
                clone_values.update({
                    'Owner': production_owners,
                    'RequiredHouses': required_houses,
                })
                # RequiredHouses is the positive isolation gate. A negative
                # list containing a helper's ParentCountry can make Ares reject
                # the clone even when its concrete campaign country is allowed.
                _remove_case_insensitive(clone_values, 'ForbiddenHouses')
            if helper_owner_ids:
                # Unit ownership restrictions apply to AI factories too. The
                # helper's cloned TeamType already supplies exact ownership;
                # leaving source-faction FactoryOwners here can make its team
                # wait forever on a foreign unlocked type.
                _remove_case_insensitive(
                    clone_values,
                    'FactoryOwners',
                    'FactoryOwners.Forbidden',
                    'Prerequisite.Negative',
                    'Prerequisite.StolenTechs',
                )
                _append_prerequisite_alternatives(
                    clone_values,
                    helper_support.get('prerequisites', ()),
                )
            if (
                not build_only_clone
                and target_unit_id not in ENGINEER_UNIT_IDS
            ):
                # Native type remains campaign AI identity. Exclude current
                # player countries only when no story action still creates
                # that exact source ID. A build-only clone deliberately keeps
                # all mission references native; forbidding their runtime
                # House prevents the reinforcement from spawning and can
                # immediately fire loss triggers (SBLEED Boris).
                native_forbidden_ids = [
                    item
                    for item in comma_items(
                        _value_case_insensitive(
                            native_unit_values, 'ForbiddenHouses', ''
                        )
                    )
                    if item.lower() not in {'none', '<none>'}
                ]
                original_forbidden_ids = unique_in_order(
                    native_forbidden_ids + owner_ids
                )
                original_rules = section_rules.setdefault(unit_id, {})
                original_rules['ForbiddenHouses'] = (
                    ','.join(original_forbidden_ids)
                    if original_forbidden_ids else 'none'
                )
        else:
            # Any clone without earned/mission build access is a reference
            # replacement only. Exact foreign role-buff clones previously
            # inherited their native TechLevel and leaked into the sidebar;
            # this must not depend on whether the source is tagged a variant.
            clone_values['TechLevel'] = LOCKED_TECH_LEVEL
            if unit_id in initial_payload_source_ids:
                # InitialPayload creation must not inherit native faction or
                # prerequisite gates. Keep support types locked, owned by the
                # carrier's player, and unselectable outside their parent.
                if owner_ids:
                    clone_values['Owner'] = ','.join(
                        production_owner_countries(
                            lines,
                            owner_ids,
                            sections=map_sections,
                        )
                    )
                    clone_values['RequiredHouses'] = ','.join(owner_ids)
                clone_values['Selectable'] = 'no'
                _remove_case_insensitive(
                    clone_values,
                    'ForbiddenHouses',
                    'FactoryOwners',
                    'FactoryOwners.Forbidden',
                    'Prerequisite',
                    'PrerequisiteOverride',
                    'Prerequisite.Lists',
                    'Prerequisite.Negative',
                    'Prerequisite.StolenTechs',
                )
                for key in list(clone_values):
                    if str(key).lower().startswith('prerequisite.list'):
                        clone_values.pop(key, None)
            if linked_buildable_variant:
                linked_helper_ids = helper_autobuild_support.get(
                    target_unit_id, {}
                ).get('countries', ())
                linked_owner_ids = unique_in_order(
                    list(owner_ids) + list(linked_helper_ids)
                )
                if linked_owner_ids:
                    clone_values['Owner'] = ','.join(
                        production_owner_countries(
                            lines,
                            linked_owner_ids,
                            sections=map_sections,
                        )
                    )
                    clone_values['RequiredHouses'] = ','.join(
                        linked_owner_ids
                    )
                    _remove_case_insensitive(
                        clone_values,
                        'ForbiddenHouses',
                        'FactoryOwners',
                        'FactoryOwners.Forbidden',
                        'Prerequisite.Negative',
                        'Prerequisite.StolenTechs',
                    )

        if linked_excluded_reference_clone:
            # This identity exists only as the other half of a cloned deploy
            # pair. It must never become a second factory/sidebar entry.
            clone_values['TechLevel'] = LOCKED_TECH_LEVEL

        _register_map_type(
            section_rules, lines, installed_sections, list_section, clone_id
        )
        if unit_id in {'JACKAL', 'JACKALP'}:
            # Map-authored JACKALA works only while the original JACKAL
            # identity supplies its visible mobile turret. A standalone clone
            # must use the complete standard body/turret asset pair. Its
            # prototype cameo remains distinct through the generated art
            # overlay deployed for this launch.
            clone_values['Image'] = 'JACKAL'
        section_rules[clone_id] = clone_values
        clone_id_by_source[unit_id] = clone_id
        cloned_source_ids.add(unit_id)
        usage_names = {
            str(house).lower()
            for house in unit_usage
            if house
        }
        all_usage_friendly = bool(usage_names) and usage_names.issubset(
            allowed_houses
        )
        preserve_native_engineer_references = (
            target_unit_id in ENGINEER_UNIT_IDS
        )
        safe_direct_rewrite = (
            unit_id in direct_friendly_ids
            and not excluded_build_only_clone
            and not preserve_native_engineer_references
            and unit_id not in ambiguous_mission_event_ids
            and (
                unit_id not in exact_reference_ids
                or (
                    all_usage_friendly
                    and unit_id not in native_trigger_reference_ids
                )
            )
        )
        reference_clone_id = clone_id
        if safe_direct_rewrite and 'cloak' in direct_types:
            # A cloaked infantry unit cannot reveal itself through its own
            # Sight. Keep the fully buffed/cloaked production clone, while
            # map-authored player references use a clean locked identity.
            reference_clone_id = _collision_safe_type_id(
                f'MORR{unit_id}',
                f'player-reference:{unit_id}',
                reserved_ids,
            )
            reference_values = dict(clone_values)
            _remove_case_insensitive(
                reference_values,
                'Cloakable',
                'Cloakable.Stages',
                'CloakingSpeed',
                'CloakSound',
                'BuildLimit',
            )
            reference_values['Cloakable'] = 'no'
            reference_values['TechLevel'] = LOCKED_TECH_LEVEL
            _register_map_type(
                section_rules,
                lines,
                installed_sections,
                list_section,
                reference_clone_id,
            )
            section_rules[reference_clone_id] = reference_values
            reference_clone_id_by_source[unit_id] = reference_clone_id
        if safe_direct_rewrite:
            direct_replacements[unit_id] = reference_clone_id
        if not build_only_clone and not preserve_native_engineer_references:
            replacements[unit_id] = (
                reference_clone_id
                if safe_direct_rewrite and all_usage_friendly
                else clone_id
            )
        # Scripted teams must follow every friendly clone, including locked
        # map-local hero variants. Otherwise exact loss triggers can watch the
        # clone while a reinforcement TaskForce still creates the native ID,
        # causing an immediate false mission failure (SNOISE Drakuv escorts).
        # _clone_reference_rules keeps enemy consumers native and splits shared
        # TaskForces, so reference-only clones are safe here.
        if not build_only_clone and not preserve_native_engineer_references:
            taskforce_replacements[unit_id] = reference_clone_id
        elif (
            excluded_build_only_clone
            or scripted_build_only_clone
            or unit_id in ambiguous_mission_event_ids
        ) and not (
            scripted_build_only_clone and safe_direct_rewrite
        ):
            unsupported.append(
                f'{target.get("label", target_unit_id)} build-only clone kept native mission references'
            )
        # A build-only clone serves production but deliberately leaves
        # mission-authored placements and scripted teams on the native ID.
        # Do not tell the guarded native pass that every clone buff was
        # handled: that suppresses health/weapon/etc. bonuses on the units the
        # mission actually gives the player. Movement remains clone-only so
        # those native mission units keep their authored/default Speed.
        native_handled_unit_types = handled_unit_types
        native_handled_weapon_ids = handled_weapon_ids
        if build_only_clone:
            native_handled_unit_types = handled_unit_types.intersection(
                {'speed', 'cloak'} if mission_hero_cloak else {'speed'}
            )
            native_handled_weapon_ids = set()
        handled_by_unit[unit_id] = {
            'unit_buff_types': native_handled_unit_types,
            'clone_unit_buff_types': handled_unit_types,
            'weapon_ids': native_handled_weapon_ids,
            'clone_id': clone_id,
        }
        label = target.get('label', target_unit_id)
        cloned_labels.append(
            f'{label} variant {unit_id}' if is_variant else label
        )
        if (
            unit_id == target_unit_id
            and unit_id in buildable_ids
            and unit_id not in NONTRAINABLE_UNIT_IDS
        ):
            player_veterancy_replacements[unit_id] = clone_id

    # Static owned templates keep deploy/convert/payload links on their stable
    # MORP IDs. Veteran-list compaction can assign a shorter runtime clone ID
    # to a trainable root, so resolve every link after all related clone IDs
    # are known. Otherwise the linked form exists but points to an absent
    # stable root (for example MORPNAGRUM -> MORPGRUMBLE).
    linked_clone_replacements = {}
    for source_id, clone_id in clone_id_by_source.items():
        linked_clone_replacements[source_id.upper()] = clone_id
        stable_clone_id = owned_clone_ids.get(source_id)
        if stable_clone_id:
            linked_clone_replacements[stable_clone_id.upper()] = clone_id
    for clone_id in clone_id_by_source.values():
        clone_values = section_rules.get(clone_id, {})
        for key, value in list(clone_values.items()):
            if str(key).lower() not in LINKED_CLONE_REFERENCE_KEYS:
                continue
            clone_values[key] = ','.join(
                linked_clone_replacements.get(item.upper(), item)
                for item in comma_items(value)
            )

    # A mission-placement reference clone (MORR*) deliberately differs from
    # its production clone, usually by suppressing unsafe live cloak. Give it
    # its own paired transform form. Sharing the production target would make
    # undeploy return a different clone identity and change its buff state.
    for source_id, reference_clone_id in list(
        reference_clone_id_by_source.items()
    ):
        reference_values = section_rules.get(reference_clone_id, {})
        for key, value in list(reference_values.items()):
            lowered_key = str(key).lower()
            if lowered_key not in {'deploysinto', 'undeploysinto'}:
                continue
            target_token = next(iter(comma_items(value)), '')
            target_source = ''
            for candidate_source, candidate_clone in clone_id_by_source.items():
                stable_clone = owned_clone_ids.get(candidate_source, '')
                if target_token.upper() in {
                    candidate_source.upper(),
                    candidate_clone.upper(),
                    stable_clone.upper(),
                }:
                    target_source = candidate_source
                    break
            if not target_source:
                continue
            paired_reference_id = reference_clone_id_by_source.get(
                target_source
            )
            if not paired_reference_id:
                main_target_id = clone_id_by_source.get(target_source)
                main_target_values = section_rules.get(main_target_id, {})
                if not main_target_id or not main_target_values:
                    continue
                paired_reference_id = _collision_safe_type_id(
                    f'MORR{target_source}',
                    f'player-reference:{target_source}',
                    reserved_ids,
                )
                paired_values = dict(main_target_values)
                _remove_case_insensitive(
                    paired_values,
                    'Cloakable',
                    'Cloakable.Stages',
                    'CloakingSpeed',
                    'CloakSound',
                    'BuildLimit',
                )
                paired_values['Cloakable'] = 'no'
                paired_values['TechLevel'] = LOCKED_TECH_LEVEL
                target_category = BUFF_TARGETS.get(
                    target_source, {}
                ).get('category')
                list_section = TECHNO_TYPE_LISTS.get(target_category)
                if list_section:
                    _register_map_type(
                        section_rules,
                        lines,
                        installed_sections,
                        list_section,
                        paired_reference_id,
                    )
                section_rules[paired_reference_id] = paired_values
                reference_clone_id_by_source[
                    target_source
                ] = paired_reference_id
            paired_values = section_rules[paired_reference_id]
            reference_values[key] = paired_reference_id
            reverse_key = (
                'UndeploysInto'
                if lowered_key == 'deploysinto'
                else 'DeploysInto'
            )
            _remove_case_insensitive(paired_values, reverse_key)
            paired_values[reverse_key] = reference_clone_id
            for owner_key in ('Owner', 'RequiredHouses'):
                owner_value = _value_case_insensitive(
                    reference_values, owner_key
                )
                _remove_case_insensitive(paired_values, owner_key)
                if owner_value is not None:
                    paired_values[owner_key] = owner_value
            _remove_case_insensitive(
                paired_values,
                'ForbiddenHouses',
                'FactoryOwners',
                'FactoryOwners.Forbidden',
                'Prerequisite.Negative',
                'Prerequisite.StolenTechs',
            )

    # Production prerequisites must follow cloned deploy targets too.  A
    # placed mobile factory can use a reference clone (for example
    # MORRMWF -> MORRNAFIST when cloak is suppressed on mission placements),
    # while unlocked vehicles still name the authored NAFIST prerequisite.
    # The engine compares exact BuildingType identities, so that mismatch
    # leaves the cloned factory's production sidebar empty.  Retain the native
    # path for launches where the authored factory stays native, and add every
    # actual player factory form prepared for this launch.
    runtime_factory_clones = {}
    for factory_source, factory_clone_id in clone_id_by_source.items():
        factory_values = section_rules.get(factory_clone_id, {})
        factory_kind = str(
            _value_case_insensitive(factory_values, 'Factory', '') or ''
        ).strip()
        if not factory_kind or factory_kind.lower() in {'none', '<none>'}:
            continue
        runtime_factory_clones[factory_source.upper()] = unique_in_order(
            clone_id
            for clone_id in (
                factory_clone_id,
                reference_clone_id_by_source.get(factory_source, ''),
            )
            if clone_id
        )

    # Native mission units can use a GenericPrerequisite rather than an exact
    # BuildingType (SEARTH's Repair Drone uses SOVWEAP).  Rebind those generic
    # factory groups as well, preserving their installed/map-authored members.
    generic_prerequisites = {}
    for source_sections in (installed_sections, map_sections):
        for section_name, values in source_sections.items():
            if str(section_name).lower() != 'genericprerequisites':
                continue
            generic_prerequisites.update(values)
    for generic_id, generic_value in generic_prerequisites.items():
        building_ids = comma_items(generic_value)
        expanded_ids = list(building_ids)
        for factory_source, factory_clone_ids in runtime_factory_clones.items():
            if factory_source not in {
                building_id.upper() for building_id in building_ids
            }:
                continue
            expanded_ids.extend(factory_clone_ids)
        expanded_ids = unique_in_order(expanded_ids)
        if expanded_ids != building_ids:
            section_rules.setdefault('GenericPrerequisites', {})[
                generic_id
            ] = ','.join(expanded_ids)

    for unit_source in sorted(buildable_ids):
        unit_clone_id = clone_id_by_source.get(unit_source)
        unit_values = section_rules.get(unit_clone_id, {})
        if not unit_values:
            continue
        prerequisite_ids = {
            item.upper()
            for key, value in unit_values.items()
            if (
                str(key).lower() == 'prerequisite'
                or re.fullmatch(
                    r'prerequisite\.list\d+', str(key), re.IGNORECASE
                )
            )
            for item in comma_items(value)
        }
        for factory_source, factory_clone_ids in runtime_factory_clones.items():
            if factory_source not in prerequisite_ids:
                continue
            _append_prerequisite_alternatives(
                unit_values,
                factory_clone_ids,
            )

    # A transform target is not factory-buildable, but the engine still
    # validates its ownership when DeploysInto/UndeploysInto changes type.
    # Copy the root clone's exact ownership onto every linked form even when
    # the root itself is reference-only for this mission. Otherwise the link
    # resolves to a clone but deployment can fail or revert through a native
    # country gate.
    for variant_source, variant_clone_id in clone_id_by_source.items():
        root_source = str(
            BUFF_TARGETS.get(variant_source, {}).get('linked_buff_source')
            or ''
        ).upper()
        if not root_source or root_source == variant_source:
            continue
        root_clone_id = clone_id_by_source.get(root_source)
        if not root_clone_id:
            continue
        root_values = section_rules.get(root_clone_id, {})
        variant_values = section_rules.get(variant_clone_id, {})
        for key in ('Owner', 'RequiredHouses'):
            value = _value_case_insensitive(root_values, key)
            _remove_case_insensitive(variant_values, key)
            if value is not None:
                variant_values[key] = value
        _remove_case_insensitive(
            variant_values,
            'ForbiddenHouses',
            'FactoryOwners',
            'FactoryOwners.Forbidden',
            'Prerequisite.Negative',
            'Prerequisite.StolenTechs',
        )
    return PlayerCloneBuildResult(
        section_rules=section_rules,
        replacements=replacements,
        direct_replacements=direct_replacements,
        cloned_source_ids=cloned_source_ids,
        taskforce_replacements=taskforce_replacements,
        structure_plan_allowed_houses_by_unit=structure_plan_allowed_houses_by_unit,
        player_veterancy_replacements=player_veterancy_replacements,
        cloned_labels=cloned_labels,
        handled_by_unit=handled_by_unit,
        unsupported=unsupported,
        missing=missing,
        native_helper_source_ids=native_helper_source_ids,
    )
