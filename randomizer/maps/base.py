"""Core map-rule constants, IDs, backups, locks, and superweapon plans."""

from ._shared import (
    ALWAYS_AVAILABLE_TECH_IDS,
    BACKUP_DIR,
    EXTRA_TECH_LOCKS,
    HOOKED_MAP_MARKER,
    MAX_ARES_TYPE_ID_LENGTH,
    RANDOMIZED_SUPERWEAPON_BUILDINGS,
    RANDOMIZER_RULES_MARKER,
    RANDOMIZER_SUPERWEAPON_CAMEO_PRIORITY,
    RANDOMIZER_SUPERWEAPON_PREFIX,
    RANDOMIZER_TYPE_LIST_KEY_START,
    REWARD_POOL,
    UNLOCKED_TECH_LEVEL,
    _COMPACT_CLONE_ID_FIRST,
    _COMPACT_CLONE_ID_SECOND,
    _ENGINEER_CLONE_SAFETY,
    _FIXED_PLAYER_CLONE_IDS,
    action_group_tokens,
    all_section_value_maps,
    canonical_reward,
    canonical_rewards,
    comma_items,
    datetime,
    find_section_bounds,
    hashlib,
    parse_action_groups,
    re,
    read_text,
    section_value_map_preserve,
    shutil,
    unique_in_order,
)

def suppressed_superweapon_building_ids(reward_settings):
    """Native power structures hidden while equivalent rewards are randomized."""
    building_ids = set()
    if reward_settings.get('include_superweapon_rewards', False):
        building_ids.update(RANDOMIZED_SUPERWEAPON_BUILDINGS.get('offensive', ()))
    if reward_settings.get('include_secondary_superweapon_rewards', False):
        building_ids.update(RANDOMIZED_SUPERWEAPON_BUILDINGS.get('secondary', ()))
    return building_ids

def safe_engineer_identity_values(target, remove_unsafe=False):
    """Return the reviewed normal Engineer identity from editable policy."""
    values = dict(_ENGINEER_CLONE_SAFETY['identity_fields'])
    values['Strength'] = str(int(target.get('strength', 90)))
    if remove_unsafe:
        values.update({field: None for field in _ENGINEER_CLONE_SAFETY['removed_fields']})
    return values

def compact_player_clone_ids(unit_ids, reserved_ids):
    """Allocate deterministic two-character IDs for veteran player clones.

    Country Veteran* values are parser-bounded. The normal MORP-prefixed IDs
    can overflow that value when a high-reward Chaos seed grants veterancy to
    most of the roster. Two-character aliases let every current reward target
    fit while keeping native and non-veteran clone identities unchanged.
    """
    unavailable = {str(item).lower() for item in reserved_ids}
    candidates = (
        first + second
        for first in _COMPACT_CLONE_ID_FIRST
        for second in _COMPACT_CLONE_ID_SECOND
    )
    result = {}
    for unit_id in sorted({
        str(item).upper() for item in unit_ids
        if str(item).upper() not in _FIXED_PLAYER_CLONE_IDS
    }):
        candidate = next(
            (
                value for value in candidates
                if value.lower() not in unavailable
            ),
            None,
        )
        if candidate is None:
            raise ValueError('No compact player-clone TechnoType IDs remain.')
        unavailable.add(candidate.lower())
        result[unit_id] = candidate
    return result

def resolved_academy_clone_rules(
    power_rule_sections,
    clone_handled,
    owned_clone_ids,
):
    """Point Academy.Types at the player TechnoTypes registered for this map.

    Veteran player units use compact IDs to keep Country Veteran* lists within
    Ares' parser limit. Static MORP IDs in a delivered Academy are therefore
    either stale or unregistered. Keep native entries for mission fallbacks,
    discard stale MORP entries, and add each source unit's actual map clone.
    """
    handled = {
        str(source).upper(): details
        for source, details in (clone_handled or {}).items()
        if isinstance(details, dict)
    }
    source_by_owned_clone = {
        str(clone_id).upper(): str(source).upper()
        for source, clone_id in (owned_clone_ids or {}).items()
    }
    updates = {}
    for section, values in (power_rule_sections or {}).items():
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if str(key).lower() != 'academy.types':
                continue
            resolved = []
            for type_id in comma_items(value):
                type_upper = type_id.upper()
                source = source_by_owned_clone.get(type_upper)
                if source is None:
                    resolved.append(type_id)
                    source = type_upper
                details = handled.get(source)
                clone_id = str((details or {}).get('clone_id') or '').strip()
                if clone_id:
                    resolved.append(clone_id)
            resolved_value = ','.join(unique_in_order(resolved))
            if resolved_value != str(value):
                updates.setdefault(section, {})[key] = resolved_value
    return updates

def now_stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')

def backup_file_once(path, label):
    if not path.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f'{path.name}.{label}.bak'
    if not target.exists():
        shutil.copy2(path, target)
    return target

def is_generated_rules_file(path):
    if not path.exists():
        return False
    try:
        return read_text(path).startswith(RANDOMIZER_RULES_MARKER)
    except OSError:
        return False

def is_generated_hooked_map(path):
    if not path.exists():
        return False
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as handle:
            return handle.readline().strip() == HOOKED_MAP_MARKER
    except OSError:
        return False

def remove_locked_techlevel_actions(lines, unlocked_tech_ids, randomized_tech_ids=None):
    start, end = find_section_bounds(lines, 'Actions')
    if start is None:
        return 0

    controlled = {
        section.upper()
        for section in (
            controlled_tech_ids() if randomized_tech_ids is None else randomized_tech_ids
        )
    }
    unlocked = {section.upper() for section in unlocked_tech_ids}
    removed = 0

    for index in range(start + 1, end):
        line = lines[index]
        if '=' not in line:
            continue

        key, value = line.split('=', 1)
        count, groups = parse_action_groups(value)
        if not count or not groups:
            continue

        kept = []
        for group in groups:
            if len(group) >= 3 and group[0] == '106':
                tech_id = group[2].strip().upper()
                if tech_id in controlled and tech_id not in unlocked:
                    removed += 1
                    continue
            kept.append(group)

        if len(kept) != len(groups):
            tokens = action_group_tokens(kept)
            lines[index] = f'{key.strip()}={len(kept)}' + (',' + ','.join(tokens) if tokens else '')

    return removed

def randomizer_clone_type_id(source_type):
    source_type = str(source_type or '').strip()
    short_source = re.sub(r'Special$', '', source_type, flags=re.IGNORECASE)
    preferred = f'{RANDOMIZER_SUPERWEAPON_PREFIX}{short_source}'
    if len(preferred) <= MAX_ARES_TYPE_ID_LENGTH:
        return preferred
    digest = hashlib.sha1(source_type.lower().encode('utf-8')).hexdigest()[:10].upper()
    return f'{RANDOMIZER_SUPERWEAPON_PREFIX}{short_source[:10]}{digest}'

def _collision_safe_type_id(preferred, identity, reserved_ids):
    preferred = re.sub(r'[^A-Za-z0-9_]', '', str(preferred or ''))
    if (
        preferred
        and len(preferred) <= MAX_ARES_TYPE_ID_LENGTH
        and preferred.lower() not in reserved_ids
    ):
        reserved_ids.add(preferred.lower())
        return preferred

    stem = re.sub(r'^MOR', '', preferred, flags=re.IGNORECASE)[:10] or 'TYPE'
    for salt in range(10000):
        digest = hashlib.sha1(
            f'{identity.lower()}:{salt}'.encode('utf-8')
        ).hexdigest()[:10].upper()
        candidate = f'{RANDOMIZER_SUPERWEAPON_PREFIX}{stem}{digest}'
        if candidate.lower() not in reserved_ids:
            reserved_ids.add(candidate.lower())
            return candidate
    raise RuntimeError(f'Could not allocate a collision-free type ID for {identity}.')

def _next_reserved_type_key(existing_keys, next_key):
    while str(next_key).lower() in existing_keys:
        next_key += 1
    key = str(next_key)
    existing_keys.add(key.lower())
    return key, next_key + 1

def _replace_list_type(value, source_type, clone_type):
    items = [item.strip() for item in str(value or '').split(',')]
    return ','.join(
        clone_type if item.lower() == source_type.lower() else item
        for item in items
        if item
    )

def cloned_superweapon_plan(
    lines,
    rewards,
    installed_superweapon_types,
    installed_sections,
    superweapon_rule_overrides=None,
    superweapon_techno_clone_overrides=None,
    superweapon_required_houses=(),
):
    """Create isolated map-local copies and safe grants.

    Scenario SuperWeaponTypes are allocated after installed types regardless
    of their numeric INI labels. Existing campaign additions are therefore
    counted first, then randomizer clones are appended and granted by their
    actual runtime indices.
    """
    installed_superweapon_types = tuple(installed_superweapon_types or ())
    superweapon_rule_overrides = superweapon_rule_overrides or {}
    superweapon_techno_clone_overrides = (
        superweapon_techno_clone_overrides or {}
    )
    if not installed_superweapon_types:
        return {}, [], [], [], ['SuperWeaponTypes']
    installed_lookup = {type_id.lower() for type_id in installed_superweapon_types}
    runtime_types = list(installed_superweapon_types)
    runtime_lookup = set(installed_lookup)

    map_sections = all_section_value_maps(lines)
    reserved_type_ids = {str(section).lower() for section in installed_sections}
    reserved_type_ids.update(str(section).lower() for section in map_sections)
    for list_section in (
        'SuperWeaponTypes',
        'VehicleTypes',
        'InfantryTypes',
        'AircraftTypes',
        'BuildingTypes',
    ):
        reserved_type_ids.update(
            str(value).lower()
            for value in installed_sections.get(list_section, {}).values()
        )
        reserved_type_ids.update(
            str(value).lower()
            for value in map_sections.get(list_section, {}).values()
        )
    allocated_type_ids = {}

    def allocate_type_id(preferred, identity):
        identity_key = identity.lower()
        if identity_key not in allocated_type_ids:
            allocated_type_ids[identity_key] = _collision_safe_type_id(
                preferred, identity, reserved_type_ids
            )
        return allocated_type_ids[identity_key]

    map_superweapon_entries = section_value_map_preserve(lines, 'SuperWeaponTypes')
    for type_id in map_superweapon_entries.values():
        type_id = str(type_id or '').strip()
        if type_id and type_id.lower() not in runtime_lookup:
            runtime_lookup.add(type_id.lower())
            runtime_types.append(type_id)

    section_rules = {}
    list_rules = {}
    actions = []
    clone_names = []
    startup_buildings = []
    missing = []
    granted_indices = set()
    list_keys = {str(key).lower() for key in map_superweapon_entries}
    next_list_key = RANDOMIZER_TYPE_LIST_KEY_START

    def register_superweapon(type_id, values):
        nonlocal next_list_key
        type_key = type_id.lower()
        if type_key not in runtime_lookup:
            key, next_list_key = _next_reserved_type_key(list_keys, next_list_key)
            list_rules[key] = type_id
            runtime_lookup.add(type_key)
            runtime_types.append(type_id)
        registered_values = dict(values)
        registered_values['CameoPriority'] = (
            RANDOMIZER_SUPERWEAPON_CAMEO_PRIORITY
        )
        section_rules[type_id] = registered_values
        return next(
            index for index, candidate in enumerate(runtime_types)
            if candidate.lower() == type_key
        )

    for reward in canonical_rewards(rewards):
        if reward.get('kind') != 'superweapon':
            continue
        source_type = str(reward.get('superweapon') or '').strip()
        if not source_type:
            continue
        preferred_clone_type = str(
            reward.get('superweapon_clone') or randomizer_clone_type_id(source_type)
        ).strip()
        clone_type = allocate_type_id(
            preferred_clone_type, f'superweapon:{source_type}'
        )
        custom = bool(reward.get('superweapon_custom'))
        source_values = installed_sections.get(source_type)
        if not isinstance(source_values, dict):
            if not custom:
                missing.append(source_type)
                continue
            source_values = {}

        clone_values = dict(source_values)
        overrides = reward.get('superweapon_rules')
        if isinstance(overrides, dict):
            clone_values.update(overrides)
        mission_overrides = superweapon_rule_overrides.get(source_type)
        if isinstance(mission_overrides, dict):
            clone_values.update(mission_overrides)
        clone_values['SW.AllowPlayer'] = 'yes'
        clone_values['SW.AllowAI'] = 'no'

        techno_clones = dict(reward.get('superweapon_techno_clones') or {})
        mission_techno_clones = superweapon_techno_clone_overrides.get(
            source_type
        )
        if isinstance(mission_techno_clones, dict):
            techno_clones.update(mission_techno_clones)
        if isinstance(techno_clones, dict):
            for techno_source, clone_spec in techno_clones.items():
                if not isinstance(clone_spec, dict):
                    continue
                list_section = str(clone_spec.get('list') or '').strip()
                template_source = str(
                    clone_spec.get('source') or techno_source
                ).strip()
                techno_source_values = installed_sections.get(template_source)
                if not list_section or not isinstance(techno_source_values, dict):
                    missing.append(template_source)
                    continue
                preferred_techno_clone = str(
                    clone_spec.get('clone')
                    or randomizer_clone_type_id(template_source)
                ).strip()
                techno_clone = allocate_type_id(
                    preferred_techno_clone, f'{list_section}:{techno_source}'
                )
                techno_values = dict(techno_source_values)
                techno_values.update(clone_spec.get('values') or {})
                section_rules[techno_clone] = techno_values

                map_entries = section_value_map_preserve(lines, list_section)
                installed_entries = installed_sections.get(list_section, {})
                registered = {
                    str(value).lower()
                    for value in list(installed_entries.values()) + list(map_entries.values())
                }
                registered.update(
                    str(value).lower()
                    for value in section_rules.get(list_section, {}).values()
                )
                if techno_clone.lower() not in registered:
                    type_keys = {str(key).lower() for key in map_entries}
                    type_keys.update(
                        str(key).lower() for key in section_rules.get(list_section, {})
                    )
                    type_key, _ = _next_reserved_type_key(
                        type_keys, RANDOMIZER_TYPE_LIST_KEY_START
                    )
                    section_rules.setdefault(list_section, {})[type_key] = techno_clone
                if 'Deliver.Types' in clone_values:
                    clone_values['Deliver.Types'] = _replace_list_type(
                        clone_values['Deliver.Types'],
                        template_source,
                        techno_clone,
                    )
                for reference_key in clone_spec.get('reference_keys') or ():
                    clone_values[str(reference_key)] = techno_clone
                try:
                    startup_count = max(
                        0, int(clone_spec.get('startup_count') or 0)
                    )
                except (TypeError, ValueError):
                    startup_count = 0
                if (
                    startup_count
                    and list_section.lower() == 'buildingtypes'
                    and superweapon_required_houses
                ):
                    startup_owners = ','.join(
                        unique_in_order(superweapon_required_houses)
                    )
                    techno_values['Owner'] = startup_owners
                    techno_values['RequiredHouses'] = startup_owners
                    techno_values['ForbiddenHouses'] = 'none'
                    techno_values['FactoryOwners'] = None
                startup_buildings.extend([techno_clone] * startup_count)

        # Weapon/warhead/projectile helpers are ordinary INI sections, not
        # registered TechnoTypes or SuperWeaponTypes. Clone them without list
        # registration and point explicit superweapon fields at the isolated
        # copy. This prevents mission-local overrides from changing a copied
        # reward effect when no engine type-list registration is required.
        auxiliary_clones = reward.get('superweapon_auxiliary_clones')
        if isinstance(auxiliary_clones, dict):
            for auxiliary_source, clone_spec in auxiliary_clones.items():
                if not isinstance(clone_spec, dict):
                    continue
                auxiliary_source_values = installed_sections.get(auxiliary_source)
                if not isinstance(auxiliary_source_values, dict):
                    missing.append(auxiliary_source)
                    continue
                preferred_auxiliary_clone = str(
                    clone_spec.get('clone')
                    or randomizer_clone_type_id(auxiliary_source)
                ).strip()
                auxiliary_clone = allocate_type_id(
                    preferred_auxiliary_clone,
                    f'auxiliary:{auxiliary_source}',
                )
                auxiliary_values = dict(auxiliary_source_values)
                auxiliary_values.update(clone_spec.get('values') or {})
                section_rules[auxiliary_clone] = auxiliary_values
                for reference_key in clone_spec.get('reference_keys') or ():
                    clone_values[str(reference_key)] = auxiliary_clone

        extra_sections = reward.get('superweapon_rule_sections')
        if isinstance(extra_sections, dict):
            for dependent_source, dependent_overrides in extra_sections.items():
                dependent_values = installed_sections.get(dependent_source)
                if not isinstance(dependent_values, dict):
                    missing.append(dependent_source)
                    continue
                dependent_clone = allocate_type_id(
                    randomizer_clone_type_id(dependent_source),
                    f'superweapon:{dependent_source}',
                )
                dependent_clone_values = dict(dependent_values)
                if isinstance(dependent_overrides, dict):
                    dependent_clone_values.update(dependent_overrides)
                dependent_clone_values['SW.AllowPlayer'] = 'yes'
                dependent_clone_values['SW.AllowAI'] = 'no'
                register_superweapon(dependent_clone, dependent_clone_values)
                for key, value in list(clone_values.items()):
                    if str(value).lower() == str(dependent_source).lower():
                        clone_values[key] = dependent_clone

        grant_buildings = tuple(reward.get('superweapon_grant_buildings') or ())
        if grant_buildings and superweapon_required_houses:
            clone_values['SW.RequiredHouses'] = ','.join(
                unique_in_order(superweapon_required_houses)
            )
        runtime_index = register_superweapon(clone_type, clone_values)
        if runtime_index in granted_indices:
            continue
        granted_indices.add(runtime_index)
        if grant_buildings:
            for building_id in grant_buildings:
                building_id = str(building_id or '').strip()
                if not building_id:
                    continue
                pending = section_rules.setdefault(building_id, {})
                existing = _value_case_insensitive(pending, 'SuperWeapons')
                if existing is None:
                    existing = _value_case_insensitive(
                        section_value_map_preserve(lines, building_id),
                        'SuperWeapons',
                    )
                if existing is None:
                    existing = _value_case_insensitive(
                        installed_sections.get(building_id, {}),
                        'SuperWeapons',
                    )
                attached = unique_in_order(comma_items(existing) + [clone_type])
                _remove_case_insensitive(pending, 'SuperWeapons')
                pending['SuperWeapons'] = ','.join(attached)
            clone_names.append(clone_type)
            continue
        clone_names.append(clone_type)
        actions.append(['34', '0', str(runtime_index), '0', '0', '0', '0', 'A'])

    if list_rules:
        section_rules.setdefault('SuperWeaponTypes', {}).update(list_rules)
    return section_rules, actions, clone_names, startup_buildings, missing

def techlevel_rules_for_reward(reward):
    reward = canonical_reward(reward)
    rule_sections = {}
    for section, values in reward.get('rules', {}).items():
        for key, value in values.items():
            if key.lower() == 'techlevel':
                rule_sections.setdefault(section, {})[key] = UNLOCKED_TECH_LEVEL
            else:
                rule_sections.setdefault(section, {})[key] = value
    return rule_sections

def launch_rules_for_reward(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff':
        return {
            section: dict(values)
            for section, values in reward.get('rules', {}).items()
        }
    return techlevel_rules_for_reward(reward)

def parse_float(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def format_multiplier(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.')

def merge_unique_csv(existing, additions):
    merged = []
    seen = set()
    for item in comma_items(existing) + list(additions):
        key = item.upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return ','.join(merged)

def resolved_map_section_rules(lines, configured_rules):
    """Resolve editable per-mission literals and CSV patches."""
    resolved = {}
    for section, values in (configured_rules or {}).items():
        source_values = section_value_map_preserve(lines, section)
        source_by_lower = {
            str(key).lower(): value for key, value in source_values.items()
        }
        for key, value in values.items():
            if not isinstance(value, dict):
                resolved.setdefault(section, {})[key] = value
                continue
            existing = comma_items(source_by_lower.get(str(key).lower(), ''))
            removals = {
                str(item).upper() for item in value.get('remove', ())
            }
            kept = [item for item in existing if item.upper() not in removals]
            resolved.setdefault(section, {})[key] = merge_unique_csv(
                ','.join(kept), value.get('add', ())
            )
    return resolved

def merge_unique_csv_bounded(existing, additions, max_length):
    """Merge CSV IDs without crossing the engine's single-value parser limit."""
    merged = []
    seen = set()
    for item in comma_items(existing) + list(additions):
        item = str(item or '').strip()
        key = item.upper()
        if not item or key in seen:
            continue
        candidate = ','.join(merged + [item])
        if len(candidate.encode('utf-8')) > max_length:
            continue
        seen.add(key)
        merged.append(item)
    return ','.join(merged)

def _value_case_insensitive(values, key, default=None):
    lowered = str(key).lower()
    return next(
        (value for name, value in values.items() if str(name).lower() == lowered),
        default,
    )

def _remove_case_insensitive(values, *keys):
    lowered = {str(key).lower() for key in keys}
    for existing in list(values):
        if str(existing).lower() in lowered:
            values.pop(existing, None)

def controlled_tech_ids():
    tech_ids = set(EXTRA_TECH_LOCKS)
    for reward in REWARD_POOL:
        tech_ids.update(techlevel_rules_for_reward(reward))
    return tech_ids - {tech_id.upper() for tech_id in ALWAYS_AVAILABLE_TECH_IDS}
