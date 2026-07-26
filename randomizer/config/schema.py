"""Schemas and focused validators for editable static configuration.

Keep validation separate from file discovery/caching. Contributors changing one
config family can now find its contract without reading packaging behavior.
"""

from pathlib import Path


class StaticConfigError(RuntimeError):
    """Raised when required static configuration is missing or malformed."""


REQUIRED_SECTIONS = {
    'default_player_config.json': {
        'defaults': dict,
    },
    'missions.json': {
        'catalogue': dict,
        'build_classifications': dict,
        'house_config': dict,
        'player_production_houses': dict,
        'player_power_houses': dict,
        'native_trigger_reference_ids': dict,
        'native_techno_clone_exclusions': dict,
        'reward_excluded_player_houses': dict,
        'team_house_overrides': dict,
        'required_access_rules': dict,
        'techno_base_rules': dict,
        'map_section_rules': dict,
        'native_direct_buff_exclusions': dict,
        'native_variant_buff_rules': dict,
        'native_tech_unlock_ids': dict,
        'superweapon_techno_clone_overrides': dict,
        'all_conyard_defense_access_missions': list,
        'standard_starter_families_by_campaign': dict,
    },
    'map_rules.json': {
        'extra_tech_locks': list,
        'scripted_tech_lock_exclusions': list,
        'techno_type_lists': dict,
        'engine_limits': dict,
    },
    'factions.json': {
        'default_unlock_build_houses': str,
        'engineer_by_family': dict,
        'engineer_installed_forbidden_houses': dict,
        'conyard_by_mcv': dict,
        'stalins_fist_factory': str,
        'stalins_fist_placement_ids': list,
        'stalins_fist_taskforce_ids': list,
        'stalins_fist_families': list,
        'amphibious_transports': dict,
        'production_buildings': dict,
        'chaos_primary_production': dict,
        'tech_order': list,
    },
    'tier_one.json': {
        'role_units': dict,
        'role_markers': dict,
        'defense_marker': str,
        'defense_role_units': dict,
        'defense_roles': list,
        'defense_units': dict,
        'subfaction_units': dict,
        'ground_roles': list,
        'standard_families': list,
        'airfields': dict,
        'production_aliases': dict,
    },
    'ui.json': {
        'difficulties': list,
        'game_speeds': list,
        'campaign_filters': list,
        'reward_modes': list,
        'progression_modes': list,
        'default_progression_mode': str,
        'player_colors': list,
        'rainbowizer_colors': list,
        'eva_voice_tags': dict,
        'rewards_per_check_messages': dict,
        'faction_tile_colors': dict,
        'light_palette': dict,
        'dark_palette': dict,
    },
    'rewards/unit_data.json': {
        'faction_unit_rosters': dict,
        'unit_base_stats': dict,
        'unit_role_equivalence_groups': list,
        'linked_buff_variants': dict,
        'faction_defense_rosters': dict,
        'defense_base_stats': dict,
        'defense_weapon_stats': dict,
        'buff_targets': dict,
        'unit_labels': dict,
        'limited_hero_build_limits': dict,
        'special_damage_fields': dict,
    },
    'rewards/catalogue.json': {
        'unit_unlock_rewards': list,
        'extra_unit_unlock_rewards': list,
        'faction_access_rules': dict,
        'buff_types': list,
        'superweapon_unlock_rewards': list,
        'secondary_superweapon_unlock_rewards': list,
        'aid_power_rewards': list,
        'aid_power_map_configs': list,
        'retired_reward_by_name': dict,
        'access_reward_aliases': dict,
    },
    'rewards/tuning.json': {
        'buff_effects': dict,
        'clone_policy': dict,
        'mission_assistance': dict,
        'reward_planning': dict,
    },
    'rewards/unit_policy.json': {
        'existing_capability_ids': dict,
        'noncombat_weapon_target_ids': list,
        'nontrainable_unit_ids': list,
        'always_available_core_unit_ids': list,
        'always_available_building_ids': list,
        'trainable_defense_ids': list,
        'naval_unit_ids': list,
        'additional_production_prerequisites': dict,
        'linked_access_variants': dict,
        'ammo_display_labels': dict,
    },
    'rewards/special_buildings.json': {
        'buildings': list,
    },
    'rewards/buff_exceptions.json': {
        'excluded_buff_type_ids': dict,
    },
}


def normalized_config_path(relative_path):
    """Return one platform-independent config key."""
    return str(Path(relative_path)).replace('\\', '/')


def _invalid(message, path):
    raise StaticConfigError(f'{message} in {path}')


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value)


def _validate_required_sections(config_key, sections, path):
    for section, expected_type in REQUIRED_SECTIONS.get(config_key, {}).items():
        if section not in sections:
            _invalid(f'Missing section {section!r}', path)
        if not isinstance(sections[section], expected_type):
            _invalid(
                f'Section {section!r} must be {expected_type.__name__}',
                path,
            )


def _validate_missions(sections, path):
    allowed = {'base_build', 'true_no_build', 'no_build_production'}
    invalid = {
        code: value
        for code, value in sections['build_classifications'].items()
        if value not in allowed
    }
    if invalid:
        _invalid(f'Invalid mission build classifications: {invalid}', path)

    operation_codes = sections['catalogue'].get('operation_mission_codes')
    if not isinstance(operation_codes, list) or not all(
        _is_nonempty_string(code) and code in sections['build_classifications']
        for code in operation_codes
    ):
        _invalid('Invalid operation mission codes', path)

    for code, configured_rules in sections['native_variant_buff_rules'].items():
        rules = configured_rules if isinstance(configured_rules, list) else [configured_rules]
        if not rules:
            _invalid(f'Invalid native variant rule for {code}', path)
        for rule in rules:
            if not isinstance(rule, dict) or not _is_nonempty_string(
                rule.get('source_unit')
            ):
                _invalid(f'Invalid native variant rule for {code}', path)
            if not isinstance(rule.get('native_units'), list) or not all(
                _is_nonempty_string(unit_id) for unit_id in rule['native_units']
            ):
                _invalid(f'Invalid native variant units for {code}', path)

    for code, section_rules in sections['map_section_rules'].items():
        if not _is_nonempty_string(code) or not isinstance(section_rules, dict):
            _invalid(f'Invalid map section rules for {code!r}', path)
        for section, values in section_rules.items():
            if not _is_nonempty_string(section) or not isinstance(values, dict):
                _invalid(f'Invalid map section {section!r} for {code}', path)
            for key, value in values.items():
                if not _is_nonempty_string(key):
                    _invalid(f'Invalid map key {key!r} for {code}:{section}', path)
                if not isinstance(value, dict):
                    continue
                if not value or not set(value).issubset({'add', 'remove'}):
                    _invalid(
                        f'Invalid CSV patch for {code}:{section}:{key}',
                        path,
                    )
                for operation in ('add', 'remove'):
                    items = value.get(operation, [])
                    if not isinstance(items, list) or not all(
                        _is_nonempty_string(item) for item in items
                    ):
                        _invalid(
                            f'Invalid CSV {operation} list for '
                            f'{code}:{section}:{key}',
                            path,
                        )


def _validate_unit_data(sections, path):
    seen_equivalence_ids = set()
    known_equivalence_ids = {
        str(unit_id).upper()
        for unit_id in (
            set(sections['unit_base_stats'])
            | set(sections['defense_base_stats'])
        )
    }
    for index, group in enumerate(sections['unit_role_equivalence_groups']):
        if not isinstance(group, list) or not group or not all(
            _is_nonempty_string(unit_id) for unit_id in group
        ):
            _invalid(f'Invalid unit role equivalence group {index}', path)
        normalized_group = {unit_id.upper() for unit_id in group}
        duplicates = seen_equivalence_ids.intersection(normalized_group)
        if duplicates:
            _invalid(
                'Unit role equivalence IDs occur in multiple groups: '
                + ', '.join(sorted(duplicates)),
                path,
            )
        unknown = normalized_group - known_equivalence_ids
        if unknown:
            _invalid(
                'Unknown unit role equivalence IDs: ' + ', '.join(sorted(unknown)),
                path,
            )
        seen_equivalence_ids.update(normalized_group)

    for source_id, variants in sections['linked_buff_variants'].items():
        if (
            source_id not in sections['unit_base_stats']
            or not isinstance(variants, dict)
            or not variants
        ):
            _invalid(f'Invalid linked buff variants for {source_id!r}', path)
        for variant_id, variant in variants.items():
            weapons = variant.get('weapons') if isinstance(variant, dict) else None
            if (
                not _is_nonempty_string(variant_id)
                or not isinstance(weapons, dict)
            ):
                _invalid(f'Invalid linked buff variant {variant_id!r}', path)
            for weapon_id, stats in weapons.items():
                if (
                    not _is_nonempty_string(weapon_id)
                    or not isinstance(stats, dict)
                    or not set(stats).issubset({'damage', 'rof', 'range'})
                    or not all(
                        isinstance(value, (int, float)) and value > 0
                        for value in stats.values()
                    )
                ):
                    _invalid(f'Invalid linked variant weapon {weapon_id!r}', path)


def _validate_unit_policy(sections, path):
    for unit_id, prerequisites in sections[
        'additional_production_prerequisites'
    ].items():
        if (
            not _is_nonempty_string(unit_id)
            or not isinstance(prerequisites, list)
            or not prerequisites
            or not all(_is_nonempty_string(item) for item in prerequisites)
        ):
            _invalid(
                f'Invalid additional production prerequisites for {unit_id!r}',
                path,
            )

    for unit_id, variants in sections['linked_access_variants'].items():
        if (
            not _is_nonempty_string(unit_id)
            or not isinstance(variants, dict)
            or not variants
            or not all(
                _is_nonempty_string(variant_id)
                and _is_nonempty_string(prerequisite)
                for variant_id, prerequisite in variants.items()
            )
        ):
            _invalid(f'Invalid linked access variants for {unit_id!r}', path)

    policy_lists = (
        'noncombat_weapon_target_ids',
        'nontrainable_unit_ids',
        'always_available_core_unit_ids',
        'always_available_building_ids',
        'trainable_defense_ids',
        'naval_unit_ids',
    )
    for key in policy_lists:
        if not all(_is_nonempty_string(value) for value in sections[key]):
            _invalid(f'Invalid unit policy list {key!r}', path)
    if not all(
        isinstance(values, list)
        and all(_is_nonempty_string(value) for value in values)
        for values in sections['existing_capability_ids'].values()
    ):
        _invalid('Invalid capability policy', path)


def _validate_special_buildings(sections, path):
    required_fields = {'id', 'name', 'faction', 'prerequisite'}
    valid_factions = {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
    seen_ids = set()
    for index, building in enumerate(sections['buildings']):
        if not isinstance(building, dict) or not required_fields.issubset(building):
            _invalid(f'Invalid special building entry {index}', path)
        building_id = building['id']
        normalized_id = str(building_id).upper()
        if (
            not _is_nonempty_string(building_id)
            or normalized_id in seen_ids
            or building.get('faction') not in valid_factions
            or not _is_nonempty_string(building.get('name'))
            or not _is_nonempty_string(building.get('prerequisite'))
            or not isinstance(building.get('capacity_rewards', False), bool)
            or not isinstance(building.get('build_category', 'Tech'), str)
            or not isinstance(building.get('cameo_priority', -1000), int)
        ):
            _invalid(f'Invalid special building entry {index}', path)
        seen_ids.add(normalized_id)


def _validate_ui(sections, path):
    messages = sections['rewards_per_check_messages']
    if (
        not isinstance(messages.get('maximum'), str)
        or not isinstance(messages.get('thresholds'), list)
        or not all(
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], int)
            and isinstance(item[1], str)
            for item in messages['thresholds']
        )
    ):
        _invalid('Invalid rewards-per-check messages', path)

    voice_tags = sections['eva_voice_tags']
    if not voice_tags or not all(
        _is_nonempty_string(label) and _is_nonempty_string(tag)
        for label, tag in voice_tags.items()
    ):
        _invalid('Invalid EVA voice tags', path)
    normalized_labels = [label.casefold() for label in voice_tags]
    if len(normalized_labels) != len(set(normalized_labels)):
        _invalid('Duplicate case-insensitive EVA voice labels', path)
    reserved = {'mission default', 'random'}
    if reserved.intersection(normalized_labels):
        _invalid('EVA voice labels use reserved Mission default/Random names', path)

    appearance_profiles = sections.get('eva_appearance_profiles', {})
    if not isinstance(appearance_profiles, dict):
        _invalid('Invalid EVA appearance profiles', path)
    allowed_profile_fields = {
        'sidebar_mix_file_index',
        'sidebar_yuri_file_names',
        'message_text_color',
    }
    for label, profile in appearance_profiles.items():
        if (
            not _is_nonempty_string(label)
            or not isinstance(profile, dict)
            or set(profile) != allowed_profile_fields
            or not isinstance(profile['sidebar_mix_file_index'], int)
            or isinstance(profile['sidebar_mix_file_index'], bool)
            or profile['sidebar_mix_file_index'] < 0
            or not isinstance(profile['sidebar_yuri_file_names'], bool)
            or not _is_nonempty_string(profile['message_text_color'])
        ):
            _invalid(f'Invalid EVA appearance profile {label!r}', path)


def _validate_tuning(sections, path):
    effects = sections['buff_effects']
    multiplier_effects = (
        'production',
        'cost',
        'speed',
        'armor',
        'health',
        'damage',
        'reload',
    )
    for effect in multiplier_effects:
        values = effects.get(effect)
        if (
            not isinstance(values, dict)
            or not isinstance(values.get('factor_per_stack'), (int, float))
            or values['factor_per_stack'] <= 0
        ):
            _invalid(f'Invalid buff effect {effect!r}', path)

    effect_bounds = {
        'production': 'minimum_multiplier',
        'cost': 'minimum_multiplier',
        'speed': 'maximum_multiplier',
        'armor': 'minimum_multiplier',
        'health': 'maximum_multiplier',
        'damage': 'maximum_multiplier',
        'reload': 'minimum_multiplier',
    }
    for effect, key in effect_bounds.items():
        value = effects[effect].get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            _invalid(f'Invalid {key!r} for buff effect {effect!r}', path)

    for effect in ('range', 'sight', 'ammo'):
        values = effects.get(effect)
        if not isinstance(values, dict) or not all(
            isinstance(values.get(key), (int, float)) and values[key] >= 0
            for key in ('amount_per_stack', 'maximum_amount')
        ):
            _invalid(f'Invalid additive buff effect {effect!r}', path)

    for key in (
        'sensor_sight_bonus',
        'defense_self_heal_fraction',
        'maximum_veterancy_stacks',
    ):
        if not isinstance(effects.get(key), (int, float)) or effects[key] < 0:
            _invalid(f'Invalid buff tuning {key!r}', path)

    infantry_speed = effects.get('infantry_speed')
    if not isinstance(infantry_speed, dict) or not all(
        isinstance(infantry_speed.get(key), (int, float))
        and infantry_speed[key] > 0
        for key in ('factor_per_stack', 'safe_ceiling')
    ):
        _invalid('Invalid infantry speed tuning', path)

    clone_policy = sections['clone_policy']
    for key in ('unit_id_prefix', 'weapon_id_prefix'):
        if not _is_nonempty_string(clone_policy.get(key)):
            _invalid(f'Invalid clone policy {key!r}', path)
    for key in (
        'production_gate_keys',
        'production_gate_prefixes',
        'required_weapon_fields',
    ):
        if not isinstance(clone_policy.get(key), list) or not all(
            _is_nonempty_string(value) for value in clone_policy[key]
        ):
            _invalid(f'Invalid clone policy {key!r}', path)

    assistance = sections['mission_assistance']
    if (
        not isinstance(assistance.get('maximum_direct_stacks'), int)
        or assistance['maximum_direct_stacks'] < 0
    ):
        _invalid('Invalid mission assistance stack limit', path)
    if not isinstance(assistance.get('direct_buff_types'), list) or not all(
        _is_nonempty_string(value)
        for value in assistance['direct_buff_types']
    ):
        _invalid('Invalid mission assistance buff types', path)
    if (
        not isinstance(
            assistance.get('reload_when_weapon_rof_above'),
            (int, float),
        )
        or not isinstance(assistance.get('add_safe_infantry_speed'), bool)
    ):
        _invalid('Invalid mission assistance policy', path)

    planning = sections['reward_planning']
    planning_keys = (
        'default_rewards_per_check',
        'maximum_rewards_per_check',
        'maximum_global_buff_repeats_per_seed',
        'global_buff_reward_interval',
    )
    for key in planning_keys:
        if not isinstance(planning.get(key), int) or planning[key] <= 0:
            _invalid(f'Invalid reward planning value {key!r}', path)
    if planning['default_rewards_per_check'] > planning['maximum_rewards_per_check']:
        _invalid('Default rewards exceed maximum', path)


def _validate_tier_one(sections, path):
    roles = sections['role_units']
    markers = sections['role_markers']
    if set(roles) != set(markers) or not all(
        _is_nonempty_string(marker) for marker in markers.values()
    ):
        _invalid('Invalid Tier 1 role markers', path)

    entry_groups = [roles, *sections['subfaction_units'].values()]
    if not all(
        isinstance(entry, list)
        and len(entry) == 2
        and all(_is_nonempty_string(value) for value in entry)
        for group in entry_groups
        for entries in group.values()
        for entry in (entries.values() if isinstance(entries, dict) else [entries])
    ):
        _invalid('Invalid Tier 1 unit mapping', path)
    if not set(sections['ground_roles']).issubset(roles):
        _invalid('Invalid Tier 1 ground roles', path)

    expected_families = set(sections['standard_families']) | {'foehn'}
    invalid_defenses = (
        not sections['defense_marker']
        or not sections['defense_roles']
        or set(sections['defense_roles']) != set(sections['defense_role_units'])
        or any(
            set(families) != expected_families
            for families in sections['defense_role_units'].values()
        )
        or any(
            not _is_nonempty_string(unit_id)
            for families in sections['defense_role_units'].values()
            for unit_id in families.values()
        )
        or set(sections['defense_units']) != expected_families
        or not all(
            isinstance(unit_ids, list)
            and unit_ids
            and all(_is_nonempty_string(unit_id) for unit_id in unit_ids)
            for unit_ids in sections['defense_units'].values()
        )
    )
    if invalid_defenses:
        _invalid('Invalid Tier 1 defense mapping', path)


def _validate_buff_exceptions(sections, path):
    if not all(
        _is_nonempty_string(buff_type)
        and isinstance(values, list)
        and all(_is_nonempty_string(value) for value in values)
        for buff_type, values in sections['excluded_buff_type_ids'].items()
    ):
        _invalid('Invalid buff exclusion policy', path)


def _validate_catalogue(sections, path):
    for config in sections['aid_power_map_configs']:
        image_name = config.get('sidebar_image')
        if not image_name:
            continue
        image_path = Path(str(image_name))
        sidebar_pcx = Path(str((config.get('values') or {}).get('SidebarPCX', '')))
        if (
            image_path.name != str(image_name)
            or image_path.suffix.lower() != '.png'
            or sidebar_pcx.name != str(sidebar_pcx)
            or sidebar_pcx.suffix.lower() != '.pcx'
            or not sidebar_pcx.name.lower().startswith('mor')
        ):
            _invalid(
                'Invalid custom sidebar image mapping for '
                f'{config.get("superweapon")!r}',
                path,
            )


CONFIG_VALIDATORS = {
    'missions.json': _validate_missions,
    'rewards/unit_data.json': _validate_unit_data,
    'rewards/unit_policy.json': _validate_unit_policy,
    'rewards/special_buildings.json': _validate_special_buildings,
    'ui.json': _validate_ui,
    'rewards/tuning.json': _validate_tuning,
    'tier_one.json': _validate_tier_one,
    'rewards/buff_exceptions.json': _validate_buff_exceptions,
    'rewards/catalogue.json': _validate_catalogue,
}


def validate_sections(relative_path, sections, path):
    """Validate required shapes plus one config family's detailed contract."""
    config_key = normalized_config_path(relative_path)
    _validate_required_sections(config_key, sections, path)
    validator = CONFIG_VALIDATORS.get(config_key)
    if validator is not None:
        validator(sections, path)
