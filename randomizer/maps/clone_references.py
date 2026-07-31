"""Clone source resolution and safe mission-reference rewriting."""

from ._shared import (
    CLONE_POLICY,
    MAX_MAP_ACTION_LINE_LENGTH,
    TECHNO_TYPE_LISTS,
    _ENGINEER_CLONE_SAFETY,
    ai_trigger_team_usage_houses,
    all_section_value_maps,
    build_unit_usage_index,
    directly_created_team_ids,
    section_value_map_preserve,
    taskforce_usage_houses,
    unit_usage_houses,
)
from .base import (
    _collision_safe_type_id,
    _remove_case_insensitive,
    _value_case_insensitive,
    safe_engineer_identity_values,
)
from .buff_values import (
    _register_map_type,
)

def _sanitize_engineer_clone_values(values, target):
    """Remove mission/cache Chrono mutations from player Engineer clones."""
    values = dict(values)
    for field in _ENGINEER_CLONE_SAFETY['removed_fields']:
        _remove_case_insensitive(values, field)
    values.update(safe_engineer_identity_values(target))
    # Always restart health from the reviewed roster baseline. Earned health
    # stacks are applied later, so this cannot erase a legitimate reward.
    return values

def _clone_reference_rules(
    lines,
    replacements,
    allowed_houses,
    installed_sections,
    reserved_ids,
    taskforce_replacements=None,
    taskforce_allowed_houses=None,
    structure_plan_allowed_houses_by_unit=None,
    native_trigger_reference_ids=(),
    direct_replacements=None,
):
    """Rewrite friendly placements, base plans, and TaskForce consumers."""
    section_rules = {}
    taskforce_replacements = (
        replacements
        if taskforce_replacements is None
        else taskforce_replacements
    )
    taskforce_allowed_houses = (
        allowed_houses
        if taskforce_allowed_houses is None
        else taskforce_allowed_houses
    )
    structure_plan_allowed_houses_by_unit = {
        str(unit_id).upper(): {
            str(house).lower() for house in houses if house
        }
        for unit_id, houses in (
            structure_plan_allowed_houses_by_unit or {}
        ).items()
    }
    native_trigger_reference_ids = {
        str(unit_id).upper() for unit_id in native_trigger_reference_ids
    }
    direct_replacements = (
        replacements if direct_replacements is None else direct_replacements
    )
    rewritten = 0
    mixed_taskforces = []
    for section in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for key, value in section_value_map_preserve(lines, section).items():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) < 2 or tokens[0].lower() not in allowed_houses:
                continue
            replacement = direct_replacements.get(tokens[1].upper())
            if not replacement:
                continue
            tokens[1] = replacement
            section_rules.setdefault(section, {})[key] = ','.join(tokens)
            rewritten += 1

    sections = all_section_value_maps(lines)
    sections_by_lower = {
        str(section).lower(): values for section, values in sections.items()
    }
    trigger_values = sections_by_lower.get('triggers', {})
    usage_index = build_unit_usage_index(lines)
    globally_friendly_replacement_ids = set()
    for source_id in replacements:
        usage_houses = {
            str(house).lower()
            for house in unit_usage_houses(lines, source_id, usage_index)
            if house
        }
        if usage_houses and usage_houses.issubset(allowed_houses):
            globally_friendly_replacement_ids.add(source_id)
    # Events such as "TechnoType does not exist" and actions such as
    # "create/delete TechnoType" carry exact IDs. Mission triggers are often
    # owned by a story/enemy house unrelated to the watched player hero
    # (EMIGDAL watches PsiCorps LIBRA from a UnitedStates trigger). When every
    # actual consumer of a cloned type is friendly, all exact trigger
    # references are therefore safe and necessary to retarget. Shared types
    # remain restricted to player/buffed-helper-owned trigger lists.
    for section in ('Events', 'Actions'):
        for key, value in section_value_map_preserve(lines, section).items():
            trigger = trigger_values.get(str(key).lower(), '')
            trigger_owner = str(trigger).split(',', 1)[0].strip().lower()
            tokens = [token.strip() for token in value.split(',')]
            replaced = False
            for index, token in enumerate(tokens):
                source_id = token.upper()
                if (
                    source_id not in replacements
                    or source_id in native_trigger_reference_ids
                ):
                    continue
                if (
                    source_id not in globally_friendly_replacement_ids
                    and trigger_owner not in allowed_houses
                ):
                    continue
                tokens[index] = replacements[source_id]
                replaced = True
            if not replaced:
                continue
            replacement = ','.join(tokens)
            if len(f'{key}={replacement}'.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
                mixed_taskforces.append(
                    f'{section} {key} TechnoType clone rewrite exceeds parser limit'
                )
                continue
            section_rules.setdefault(section, {})[key] = replacement
            rewritten += 1

    # Campaign AI base plans store ``BuildingType,...`` under numbered keys in
    # each House section. Rewrite only player and opted-in buffed-helper plans;
    # enemy plans must retain the unbuffed original defense ID.
    for section, values in sections.items():
        section_lower = str(section).lower()
        for key, value in values.items():
            if not str(key).isdigit():
                continue
            tokens = [token.strip() for token in value.split(',')]
            if not tokens:
                continue
            source_id = tokens[0].upper()
            replacement = replacements.get(source_id)
            if not replacement or section_lower not in (
                structure_plan_allowed_houses_by_unit.get(source_id, set())
            ):
                continue
            tokens[0] = replacement
            section_rules.setdefault(section, {})[key] = ','.join(tokens)
            rewritten += 1

    taskforce_owners = taskforce_usage_houses(lines, sections=sections)
    ai_team_houses = ai_trigger_team_usage_houses(lines)
    directly_created = directly_created_team_ids(lines)
    placeholder_houses = {'neutral', 'neutral house', '<none>', 'none'}
    for taskforce_id, owners in taskforce_owners.items():
        owner_names = {owner.lower() for owner in owners if owner}
        taskforce_values = section_value_map_preserve(lines, taskforce_id)
        cloned_values = dict(taskforce_values)
        replaced_values = 0
        for key, value in taskforce_values.items():
            tokens = [token.strip() for token in value.split(',')]
            if len(tokens) < 2:
                continue
            replacement = taskforce_replacements.get(tokens[1].upper())
            if not replacement:
                continue
            tokens[1] = replacement
            cloned_values[key] = ','.join(tokens)
            replaced_values += 1
        if not replaced_values:
            continue
        if not owner_names or not owner_names.issubset(taskforce_allowed_houses):
            if not owner_names.intersection(taskforce_allowed_houses):
                continue

            friendly_team_types = []
            unresolved_team_types = []
            for team_id, values in sections.items():
                if str(values.get('taskforce') or '').lower() != taskforce_id.lower():
                    continue
                section_key = team_id.lower()
                runtime_houses = set(ai_team_houses.get(section_key, set()))
                house = str(values.get('house') or '')
                if (
                    house
                    and (
                        house.lower() not in placeholder_houses
                        or not runtime_houses
                        or section_key in directly_created
                    )
                ):
                    runtime_houses.add(house)
                runtime_names = {
                    item.lower() for item in runtime_houses if item
                }
                if runtime_names and runtime_names.issubset(taskforce_allowed_houses):
                    friendly_team_types.append(team_id)
                elif runtime_names.intersection(taskforce_allowed_houses):
                    unresolved_team_types.append(team_id)

            if friendly_team_types:
                clone_id = _collision_safe_type_id(
                    f'MORTF{taskforce_id}',
                    f'player-taskforce:{taskforce_id}',
                    reserved_ids,
                )
                _register_map_type(
                    section_rules,
                    lines,
                    installed_sections,
                    'TaskForces',
                    clone_id,
                )
                section_rules[clone_id] = cloned_values
                for team_id in friendly_team_types:
                    section_rules.setdefault(team_id, {})['TaskForce'] = clone_id
                rewritten += replaced_values
            if unresolved_team_types:
                mixed_taskforces.append(
                    f'{taskforce_id} ({", ".join(unresolved_team_types)})'
                )
            continue

        section_rules[taskforce_id] = cloned_values
        rewritten += replaced_values
    return section_rules, rewritten, mixed_taskforces

def _standalone_clone_values(
    lines,
    installed_sections,
    installed_section,
    map_section,
):
    """Return a complete map-local copy without Ares inheritance.

    Ares accepts ``$Inherits`` in a map section, but live testing showed that a
    cloned WeaponType can still be constructed before inherited core fields are
    available. Merge installed values with map-local overrides instead so fields
    such as Projectile and Warhead physically exist on the clone.
    """
    values = {}
    key_by_lower = {}
    for source_values in (
        installed_sections.get(installed_section, {}) if installed_section else {},
        section_value_map_preserve(lines, map_section) if map_section else {},
    ):
        for key, value in source_values.items():
            lowered = str(key).lower()
            previous = key_by_lower.get(lowered)
            if previous is not None and previous != key:
                values.pop(previous, None)
            values[key] = value
            key_by_lower[lowered] = key
    inherited_key = key_by_lower.get('$inherits')
    if inherited_key is not None:
        values.pop(inherited_key, None)
    return values

def _standalone_clone_values_from_maps(installed_values, map_values):
    """Merge installed values with an unmodified pre-launch map section."""
    values = {}
    key_by_lower = {}
    for source_values in (installed_values or {}, map_values or {}):
        for key, value in source_values.items():
            lowered = str(key).lower()
            previous = key_by_lower.get(lowered)
            if previous is not None and previous != key:
                values.pop(previous, None)
            values[key] = value
            key_by_lower[lowered] = key
    inherited_key = key_by_lower.get('$inherits')
    if inherited_key is not None:
        values.pop(inherited_key, None)
    return values

def _positive_build_limit(values):
    """Return a live-unit cap while discarding locks and one-build limits."""
    raw_value = _value_case_insensitive(values, 'BuildLimit')
    try:
        return str(raw_value).strip() if int(str(raw_value).strip()) > 0 else None
    except (TypeError, ValueError):
        return None

def _target_with_effective_unit_stats(target, effective_values):
    """Use a variant's own base stats while retaining curated buff metadata."""
    result = dict(target)
    for target_key, rules_key in (
        ('strength', 'Strength'),
        ('sight', 'Sight'),
        ('ammo', 'Ammo'),
        ('passengers', 'Passengers'),
        ('cost', 'Cost'),
        ('speed', 'Speed'),
    ):
        raw_value = _value_case_insensitive(effective_values, rules_key)
        if raw_value is None:
            continue
        try:
            result[target_key] = float(str(raw_value).strip())
        except (TypeError, ValueError):
            pass
    if 'passengers' in target:
        raw_passengers = _value_case_insensitive(
            effective_values, 'Passengers'
        )
        try:
            if int(float(str(raw_passengers).strip())) < 1:
                result.pop('passengers', None)
        except (TypeError, ValueError):
            result.pop('passengers', None)
    return result

def _friendly_variant_clone_candidates(
    lines,
    installed_sections,
    map_sections,
    counts_by_unit,
    allowed_houses,
    usage_index,
):
    """Find registered AI/map variants explicitly using a buff target's art."""
    installed_name_by_lower = {
        str(section).lower(): section for section in installed_sections
    }
    map_name_by_lower = {str(section).lower(): section for section in map_sections}
    candidates = []
    seen = set(counts_by_unit)
    for list_section in TECHNO_TYPE_LISTS.values():
        registered = list(installed_sections.get(list_section, {}).values())
        registered.extend(section_value_map_preserve(lines, list_section).values())
        for candidate in registered:
            candidate_id = str(candidate).strip()
            candidate_upper = candidate_id.upper()
            if (
                not candidate_id
                or candidate_upper in seen
                or candidate_upper.startswith(
                    str(CLONE_POLICY['unit_id_prefix']).upper()
                )
            ):
                continue
            installed_name = installed_name_by_lower.get(candidate_id.lower())
            map_name = map_name_by_lower.get(candidate_id.lower())
            effective_values = _standalone_clone_values(
                lines,
                installed_sections,
                installed_name,
                map_name,
            )
            base_id = str(
                _value_case_insensitive(effective_values, 'Image', '')
            ).strip().upper()
            if base_id not in counts_by_unit or base_id == candidate_upper:
                continue
            usage_houses = unit_usage_houses(lines, candidate_id, usage_index)
            if not any(house.lower() in allowed_houses for house in usage_houses):
                continue
            candidates.append((candidate_id, base_id, counts_by_unit[base_id]))
            seen.add(candidate_upper)
    return candidates

def _helper_autocreate_taskforce_units(lines, helper_house_names):
    """Return combat-production TaskForces used by configured helper AIs."""
    sections = all_section_value_maps(lines)
    sections_by_lower = {name.lower(): values for name, values in sections.items()}
    ai_team_houses = ai_trigger_team_usage_houses(lines)
    directly_created = directly_created_team_ids(lines)
    placeholder_houses = {'neutral', 'neutral house', '<none>', 'none'}
    result = {}
    for team_id, values in sections.items():
        if str(values.get('autocreate') or '').lower() != 'yes':
            continue
        taskforce_id = str(values.get('taskforce') or '').strip()
        if not taskforce_id:
            continue
        runtime_houses = set(ai_team_houses.get(team_id.lower(), set()))
        house = str(values.get('house') or '').strip()
        if (
            house
            and (
                house.lower() not in placeholder_houses
                or not runtime_houses
                or team_id.lower() in directly_created
            )
        ):
            runtime_houses.add(house)
        if not {
            owner.lower() for owner in runtime_houses if owner
        }.intersection(helper_house_names):
            continue
        units = result.setdefault(taskforce_id.lower(), set())
        for key, value in sections_by_lower.get(taskforce_id.lower(), {}).items():
            tokens = [token.strip() for token in value.split(',')]
            if str(key).isdigit() and len(tokens) >= 2 and tokens[1]:
                units.add(tokens[1].upper())
    return result

def _techno_production_class(
    unit_id,
    categories,
    installed_sections,
    map_sections,
):
    """Return the factory/movement class relevant to an AI TaskForce slot."""
    unit_id = str(unit_id or '').upper()
    category = categories.get(unit_id)
    if category == 'infantry':
        return 'infantry'
    if category == 'aircraft':
        return 'aircraft'
    if category != 'units':
        return ''

    installed_name = next(
        (name for name in installed_sections if str(name).upper() == unit_id),
        None,
    )
    map_name = next(
        (name for name in map_sections if str(name).upper() == unit_id),
        None,
    )
    values = _standalone_clone_values_from_maps(
        installed_sections.get(installed_name, {}) if installed_name else {},
        map_sections.get(map_name, {}) if map_name else {},
    )
    return (
        'naval'
        if str(_value_case_insensitive(values, 'Naval', 'no')).lower() == 'yes'
        else 'units'
    )

def _helper_prerequisite_alternative(unit_values):
    """Copy one proven native AI prerequisite path for an unlocked clone."""
    override = str(
        _value_case_insensitive(unit_values, 'PrerequisiteOverride', '') or ''
    ).strip()
    if override and override.lower() not in {'none', '<none>'}:
        return override
    prerequisite = str(
        _value_case_insensitive(unit_values, 'Prerequisite', '') or ''
    ).strip()
    return prerequisite if prerequisite.lower() not in {'none', '<none>'} else ''
