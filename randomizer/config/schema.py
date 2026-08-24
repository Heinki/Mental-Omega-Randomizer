"""Schemas and focused validators for editable static configuration.

Keep validation separate from file discovery/caching. Contributors changing one
config family can now find its contract without reading packaging behavior.
"""

from pathlib import Path

from randomizer.config.mission_rewards import validate_mission_reward_config
from randomizer.config.shop_mode import validate_shop_mode_config


class StaticConfigError(RuntimeError):
    """Raised when required static configuration is missing or malformed."""


REQUIRED_SECTIONS = {
    'default_player_config.json': {
        'defaults': dict,
    },
    'missions.json': {
        'catalogue': dict,
        'mission_reward_multipliers': dict,
        'build_classifications': dict,
        'house_config': dict,
        'helper_buff_excluded_houses': dict,
        'player_production_houses': dict,
        'player_power_houses': dict,
        'native_trigger_reference_ids': dict,
        'native_techno_clone_exclusions': dict,
        'reward_excluded_player_houses': dict,
        'clone_only_country_buff_types': dict,
        'scripted_player_buff_taskforces': dict,
        'scripted_player_buff_taskforce_access_requirements': dict,
        'native_runtime_player_forbidden_ids': dict,
        'team_house_overrides': dict,
        'native_runtime_identity_preserve_ids': dict,
        'native_production_aliases': dict,
        'objective_hook_action_redirects': dict,
        'special_infantry_factory_exclusions': dict,
        'victory_hook_action_ids': dict,
        'objective_clone_event_refs': dict,
        'required_access_rules': dict,
        'techno_base_rules': dict,
        'map_section_rules': dict,
        'native_direct_buff_exclusions': dict,
        'native_variant_buff_rules': dict,
        'native_tech_unlock_ids': dict,
        'native_unlock_owned_access_rules': dict,
        'superweapon_techno_clone_overrides': dict,
        'time_freeze_immune_techno_ids': dict,
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
    'shop_mode.json': {
        'settings': dict,
        'mission_rewards': dict,
        'stage_class_weights': list,
        'run_unit_prices': dict,
        'run_buff_prices': dict,
        'permanent_unit_prices': dict,
        'permanent_upgrades': dict,
        'modifiers': dict,
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
        'unit_sidebar_images': dict,
        'unit_base_stats': dict,
        'unit_role_equivalence_groups': list,
        'linked_buff_variants': dict,
        'faction_defense_rosters': dict,
        'defense_base_stats': dict,
        'defense_weapon_stats': dict,
        'buff_targets': dict,
        'unit_labels': dict,
        'limited_hero_build_limits': dict,
        'standalone_weapon_templates': dict,
        'standalone_unit_rule_templates': dict,
        'special_damage_fields': dict,
    },
    'rewards/catalogue.json': {
        'unit_unlock_rewards': list,
        'extra_unit_unlock_rewards': list,
        'faction_access_rules': dict,
        'buff_types': list,
        'global_buff_rewards': list,
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
    'rewards/power_buffs.json': {
        'buff_types': list,
        'recharge': dict,
        'cost': dict,
        'area': dict,
        'damage': dict,
        'health': dict,
        'duration': dict,
        'effect': dict,
        'targeting': dict,
        'vision': dict,
        'payload': dict,
    },
    'rewards/enemy_scaling.json': {
        'defaults': dict,
        'buffs': list,
        'tier_unit_buff_templates': list,
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

    validate_mission_reward_config(sections, path, _invalid)

    for section in (
        'helper_buff_excluded_houses',
        'original_mcv_access',
        'native_production_gate_exclusions',
        'special_infantry_factory_exclusions',
        'victory_hook_action_ids',
        'native_runtime_identity_preserve_ids',
        'time_freeze_immune_techno_ids',
    ):
        for code, unit_ids in sections.get(section, {}).items():
            if (
                not _is_nonempty_string(code)
                or code not in sections['build_classifications']
                or not isinstance(unit_ids, list)
                or any(not _is_nonempty_string(unit_id) for unit_id in unit_ids)
            ):
                _invalid(f'Invalid {section} entry for {code!r}', path)

    for code, unit_events in sections.get(
        'objective_clone_event_refs', {}
    ).items():
        if (
            not _is_nonempty_string(code)
            or code not in sections['build_classifications']
            or not isinstance(unit_events, dict)
            or not unit_events
        ):
            _invalid(
                f'Invalid objective_clone_event_refs entry for {code!r}', path
            )
        for unit_id, event_ids in unit_events.items():
            if (
                not _is_nonempty_string(unit_id)
                or not isinstance(event_ids, list)
                or not event_ids
                or any(not _is_nonempty_string(event_id) for event_id in event_ids)
            ):
                _invalid(
                    'Invalid objective clone Event list for '
                    f'{code!r}/{unit_id!r}',
                    path,
                )

    for code, aliases in sections.get('native_production_aliases', {}).items():
        if (
            not _is_nonempty_string(code)
            or code not in sections['build_classifications']
            or not isinstance(aliases, dict)
            or not aliases
            or any(
                not _is_nonempty_string(alias_id)
                or not _is_nonempty_string(source_id)
                for alias_id, source_id in aliases.items()
            )
        ):
            _invalid(
                f'Invalid native_production_aliases entry for {code!r}',
                path,
            )

    for code, redirects in sections.get(
        'objective_hook_action_redirects', {}
    ).items():
        if (
            not _is_nonempty_string(code)
            or code not in sections['build_classifications']
            or not isinstance(redirects, dict)
            or not redirects
            or any(
                not _is_nonempty_string(source_action_id)
                or not _is_nonempty_string(target_action_id)
                for source_action_id, target_action_id in redirects.items()
            )
        ):
            _invalid(
                f'Invalid objective_hook_action_redirects entry for {code!r}',
                path,
            )

    country_buff_types = {'production', 'cost', 'speed', 'armor'}
    for code, buff_types in sections['clone_only_country_buff_types'].items():
        if (
            not _is_nonempty_string(code)
            or not isinstance(buff_types, list)
            or not buff_types
            or any(
                not _is_nonempty_string(buff_type)
                or buff_type not in country_buff_types
                for buff_type in buff_types
            )
        ):
            _invalid(f'Invalid clone-only country buff types for {code}', path)

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
                if str(section).lower() == 'actions' and isinstance(value, str):
                    tokens = [token.strip() for token in value.split(',')]
                    try:
                        action_count = int(tokens[0])
                    except (IndexError, ValueError):
                        _invalid(
                            f'Invalid action count for {code}:{section}:{key}',
                            path,
                        )
                    serialized_count = (len(tokens) - 1) // 8
                    if (
                        (len(tokens) - 1) % 8
                        or action_count != serialized_count
                        or len(value.encode('utf-8')) > 511
                    ):
                        _invalid(
                            f'Invalid action groups for {code}:{section}:{key}',
                            path,
                        )
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


def _validate_shop_mode(sections, path):
    validate_shop_mode_config(sections, path, _invalid)


def _validate_unit_data(sections, path):
    for unit_id, config in sections['unit_sidebar_images'].items():
        if not _is_nonempty_string(unit_id) or not isinstance(config, dict):
            _invalid(
                f'Invalid custom unit sidebar image mapping for {unit_id!r}',
                path,
            )
        image_path = Path(str(config.get('image', '')))
        sidebar_pcx = Path(str(config.get('pcx', '')))
        source_pcx = Path(str(config.get('source_pcx', '')))
        art_id = str(config.get('art_id', '')).strip()
        custom_pair = (
            set(config) in ({'image', 'pcx'}, {'image', 'pcx', 'art_id'})
            and image_path.name == str(config.get('image', ''))
            and image_path.suffix.lower() == '.png'
            and sidebar_pcx.name == str(config.get('pcx', ''))
            and sidebar_pcx.suffix.lower() == '.pcx'
            and sidebar_pcx.name.lower().startswith('mor')
            and (
                'art_id' not in config
                or (art_id and Path(art_id).name == art_id)
            )
        )
        mix_source = (
            set(config) in ({'source_pcx'}, {'source_pcx', 'art_id'})
            and source_pcx.name == str(config.get('source_pcx', ''))
            and source_pcx.suffix.lower() == '.pcx'
            and (
                'art_id' not in config
                or (art_id and Path(art_id).name == art_id)
            )
        )
        if not custom_pair and not mix_source:
            _invalid(
                f'Invalid custom unit sidebar image mapping for {unit_id!r}',
                path,
            )

    for weapon_id, values in sections['standalone_weapon_templates'].items():
        if (
            not _is_nonempty_string(weapon_id)
            or not isinstance(values, dict)
            or not values
            or not all(
                _is_nonempty_string(key) and isinstance(value, str)
                for key, value in values.items()
            )
        ):
            _invalid(f'Invalid standalone weapon template for {weapon_id!r}', path)

    for unit_id, lists in sections['standalone_unit_rule_templates'].items():
        if not _is_nonempty_string(unit_id) or not isinstance(lists, dict):
            _invalid(f'Invalid standalone unit rules for {unit_id!r}', path)
        for list_name, templates in lists.items():
            if (
                list_name not in {'WeaponTypes', 'Warheads', 'Projectiles'}
                or not isinstance(templates, dict)
                or not templates
            ):
                _invalid(f'Invalid standalone rule list for {unit_id!r}', path)
            for section_id, values in templates.items():
                if (
                    not _is_nonempty_string(section_id)
                    or not isinstance(values, dict)
                    or not all(
                        _is_nonempty_string(key) and isinstance(value, str)
                        for key, value in values.items()
                    )
                ):
                    _invalid(
                        f'Invalid standalone rule template {section_id!r}', path
                    )

    missile_range_support = sections.get('spawned_missile_range_support', {})
    if not isinstance(missile_range_support, dict):
        _invalid('Invalid spawned missile range support', path)
    for unit_id, support in missile_range_support.items():
        if (
            not _is_nonempty_string(unit_id)
            or unit_id not in sections['unit_base_stats']
            or not isinstance(support, dict)
            or set(support) != {'missile_id', 'base_guard_range'}
            or not _is_nonempty_string(support['missile_id'])
            or isinstance(support['base_guard_range'], bool)
            or not isinstance(support['base_guard_range'], (int, float))
            or support['base_guard_range'] <= 0
        ):
            _invalid(
                f'Invalid spawned missile range support for {unit_id!r}', path
            )

    transport_base_stats = sections.get('transport_base_stats', {})
    if not isinstance(transport_base_stats, dict):
        _invalid('Invalid transport base stats', path)
    for unit_id, stats in transport_base_stats.items():
        required_keys = {'passengers', 'open_topped'}
        allowed_keys = required_keys | {'open_topped_blocked'}
        if (
            not _is_nonempty_string(unit_id)
            or unit_id not in sections['unit_base_stats']
            or not isinstance(stats, dict)
            or not required_keys.issubset(stats)
            or not set(stats).issubset(allowed_keys)
            or not isinstance(stats['passengers'], int)
            or isinstance(stats['passengers'], bool)
            or stats['passengers'] < 1
            or not isinstance(stats['open_topped'], bool)
            or not isinstance(stats.get('open_topped_blocked', False), bool)
        ):
            _invalid(f'Invalid transport base stats for {unit_id!r}', path)

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
            and source_id not in sections['defense_base_stats']
            or not isinstance(variants, dict)
            or not variants
        ):
            _invalid(f'Invalid linked buff variants for {source_id!r}', path)
        for variant_id, variant in variants.items():
            weapons = variant.get('weapons') if isinstance(variant, dict) else None
            if (
                not _is_nonempty_string(variant_id)
                or not isinstance(weapons, dict)
                or (
                    variant.get('category') is not None
                    and variant.get('category') not in {
                        'infantry', 'units', 'aircraft', 'defenses',
                        'special_buildings',
                    }
                )
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
    progression_modes = sections['progression_modes']
    required_progression_modes = {
        'Classic', 'Mission List', 'Grid Mode', 'Shop Mode'
    }
    if (
        not all(_is_nonempty_string(mode) for mode in progression_modes)
        or len(progression_modes) != len(set(progression_modes))
        or not required_progression_modes.issubset(progression_modes)
        or sections['default_progression_mode'] not in progression_modes
    ):
        _invalid('Invalid progression mode choices', path)

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
    minimum_multiplier_effects = ('production', 'cost', 'armor')
    for effect in minimum_multiplier_effects:
        values = effects[effect]
        minimum = values.get('minimum_multiplier')
        if (
            not isinstance(minimum, (int, float))
            or isinstance(minimum, bool)
            or minimum < 0
            or (effect != 'cost' and minimum == 0)
            or minimum >= 1
            or values['factor_per_stack'] >= 1
        ):
            _invalid(
                f'Invalid minimum multiplier for buff effect {effect!r}',
                path,
            )
    for effect in ('health', 'damage'):
        maximum = effects[effect].get('maximum_multiplier')
        if (
            not isinstance(maximum, (int, float))
            or isinstance(maximum, bool)
            or maximum <= 1
            or effects[effect]['factor_per_stack'] <= 1
        ):
            _invalid(
                f'Invalid maximum multiplier for {effect} buff effect',
                path,
            )

    for effect in ('range', 'sight', 'ammo', 'storage', 'income'):
        values = effects.get(effect)
        if (
            not isinstance(values, dict)
            or not isinstance(values.get('amount_per_stack'), (int, float))
            or values['amount_per_stack'] < 0
        ):
            _invalid(f'Invalid additive buff effect {effect!r}', path)
    for effect in ('range', 'sight'):
        values = effects[effect]
        maximum = values.get('maximum_amount')
        if (
            not isinstance(maximum, (int, float))
            or isinstance(maximum, bool)
            or maximum < values['amount_per_stack']
        ):
            _invalid(f'Invalid maximum amount for buff effect {effect!r}', path)
    for effect in (
        'production', 'cost', 'armor', 'health', 'damage', 'reload', 'range',
        'sight', 'ammo', 'storage', 'income',
    ):
        stack_limit = effects[effect].get('stack_limit')
        if (
            not isinstance(stack_limit, int)
            or isinstance(stack_limit, bool)
            or stack_limit < 1
        ):
            _invalid(f'Invalid stack limit for buff effect {effect!r}', path)

    for key in (
        'sensor_sight_bonus',
        'defense_self_heal_fraction',
        'maximum_self_heal_fraction',
    ):
        if not isinstance(effects.get(key), (int, float)) or effects[key] < 0:
            _invalid(f'Invalid buff tuning {key!r}', path)
    if (
        effects['defense_self_heal_fraction'] <= 0
        or effects['maximum_self_heal_fraction']
        < effects['defense_self_heal_fraction']
    ):
        _invalid('Invalid self-healing buff cap', path)

    movement_speed = effects.get('movement_speed')
    movement_ceilings = (
        movement_speed.get('safe_ceilings')
        if isinstance(movement_speed, dict)
        else None
    )
    if (
        not isinstance(movement_ceilings, dict)
        or set(movement_ceilings) != {'infantry', 'units', 'aircraft'}
        or not all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
            for value in movement_ceilings.values()
        )
    ):
        _invalid('Invalid movement speed tuning', path)

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
        or not isinstance(assistance.get('add_safe_movement_speed'), bool)
    ):
        _invalid('Invalid mission assistance policy', path)

    planning = sections['reward_planning']
    planning_keys = (
        'default_rewards_per_check',
        'maximum_rewards_per_check',
        'global_buff_reward_interval',
    )
    for key in planning_keys:
        if not isinstance(planning.get(key), int) or planning[key] <= 0:
            _invalid(f'Invalid reward planning value {key!r}', path)
    if planning['default_rewards_per_check'] > planning['maximum_rewards_per_check']:
        _invalid('Default rewards exceed maximum', path)
    buff_stack_limits = planning.get('buff_stack_limits')
    if (
        not isinstance(buff_stack_limits, dict)
        or set(buff_stack_limits) != {'passenger_capacity', 'build_limit'}
        or not all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
            for value in buff_stack_limits.values()
        )
    ):
        _invalid('Invalid reward-planning buff stack limits', path)


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


def _validate_power_buffs(sections, path):
    buff_types = sections['buff_types']
    required_type_fields = {
        'id', 'name', 'setting_label', 'description', 'maximum_stacks',
    }
    if (
        not buff_types
        or any(
            not isinstance(item, dict)
            or not required_type_fields.issubset(item)
            or not all(
                _is_nonempty_string(item.get(key))
                for key in ('id', 'name', 'setting_label', 'description')
            )
            for item in buff_types
        )
    ):
        _invalid('Invalid power buff type definitions', path)
    buff_ids = [item['id'] for item in buff_types]
    if len(buff_ids) != len(set(buff_ids)):
        _invalid('Duplicate power buff type IDs', path)
    supported_buff_ids = {
        'recharge', 'cost', 'area', 'damage', 'health', 'duration',
        'effect', 'targeting', 'vision', 'payload',
    }
    if set(buff_ids) != supported_buff_ids:
        _invalid('Power buff type definitions do not match supported IDs', path)
    for item in buff_types:
        maximum_stacks = item.get('maximum_stacks')
        if (
            not isinstance(maximum_stacks, int)
            or isinstance(maximum_stacks, bool)
            or maximum_stacks < 1
        ):
            _invalid(
                f'Invalid maximum stacks for power buff {item["id"]!r}',
                path,
            )

    for section_name in ('cost', 'payload'):
        for key, value in sections[section_name].items():
            if key.endswith('_power_ids') or key == 'power_ids':
                if (
                    not isinstance(value, list)
                    or not all(_is_nonempty_string(item) for item in value)
                    or len(value) != len(set(value))
                ):
                    _invalid(
                        f'Invalid power ID list {section_name}.{key}', path
                    )

    drop_pod_additions = sections['payload'].get(
        'drop_pod_type_weight_additions', {}
    )
    if (
        not isinstance(drop_pod_additions, dict)
        or any(
            not _is_nonempty_string(power_id)
            or not isinstance(type_ids, list)
            or not type_ids
            or not all(_is_nonempty_string(type_id) for type_id in type_ids)
            for power_id, type_ids in drop_pod_additions.items()
        )
    ):
        _invalid('Invalid DropPod payload type additions', path)

    buff_unit_ids_by_power = sections['payload'].get(
        'buff_unit_ids_by_power', {}
    )
    if (
        not isinstance(buff_unit_ids_by_power, dict)
        or any(
            not _is_nonempty_string(power_id)
            or not isinstance(unit_ids, list)
            or not unit_ids
            or not all(_is_nonempty_string(unit_id) for unit_id in unit_ids)
            or len(unit_ids) != len(set(unit_ids))
            for power_id, unit_ids in buff_unit_ids_by_power.items()
        )
    ):
        _invalid('Invalid power payload buff-unit mapping', path)

    hero_sources = sections['payload'].get(
        'equivalent_hero_buff_sources', {}
    )
    if (
        not isinstance(hero_sources, dict)
        or any(
            not _is_nonempty_string(power_id)
            or not isinstance(config, dict)
            or not _is_nonempty_string(config.get('payload_unit'))
            or not _is_nonempty_string(config.get('preferred_source'))
            or not isinstance(config.get('sources_by_faction'), dict)
            or not all(
                _is_nonempty_string(faction)
                and _is_nonempty_string(unit_id)
                for faction, unit_id in config.get(
                    'sources_by_faction', {}
                ).items()
            )
            for power_id, config in hero_sources.items()
        )
    ):
        _invalid('Invalid equivalent hero payload mapping', path)

    for section_name in (
        'area', 'damage', 'health', 'duration', 'effect', 'targeting',
        'vision',
    ):
        for key, entries in sections[section_name].items():
            if not key.endswith('_fields'):
                continue
            if not isinstance(entries, dict) or not all(
                _is_nonempty_string(power_id) and isinstance(spec, dict)
                for power_id, spec in entries.items()
            ):
                _invalid(
                    f'Invalid power field mapping {section_name}.{key}', path
                )

    for section_name in (
        'recharge', 'cost', 'damage', 'health', 'duration', 'effect',
    ):
        factor = sections[section_name].get('factor_per_stack')
        if (
            not isinstance(factor, (int, float))
            or isinstance(factor, bool)
            or factor <= 0
        ):
            _invalid(
                f'Invalid power buff factor {section_name}.factor_per_stack',
                path,
            )

    internal_deliveries = sections['payload'].get(
        'internal_unit_delivery_fields', {}
    )
    if (
        not isinstance(internal_deliveries, dict)
        or any(
            not _is_nonempty_string(power_id)
            or not isinstance(spec, dict)
            or not all(
                _is_nonempty_string(spec.get(key))
                for key in ('section', 'field', 'baseline')
            )
            for power_id, spec in internal_deliveries.items()
        )
    ):
        _invalid('Invalid internal power payload mapping', path)

    effect_fields = sections['effect'].get('multiplier_fields', {})
    if any(
        spec.get('mode') not in {'bonus', 'reduction'}
        or not all(
            _is_nonempty_string(spec.get(key))
            for key in ('source', 'field', 'reference_key', 'effect_label')
        )
        or not isinstance(spec.get('baseline'), (int, float))
        or isinstance(spec.get('baseline'), bool)
        or spec['baseline'] <= 0
        for spec in effect_fields.values()
    ):
        _invalid('Invalid power status-effect multiplier mapping', path)

    vehicle_fields = sections['targeting'].get('vehicle_armor_fields', {})
    if any(
        not _is_nonempty_string(spec.get('source'))
        or not _is_nonempty_string(spec.get('clone_key'))
        or not _is_nonempty_string(spec.get('verses'))
        or (
            'clear_designators' in spec
            and not isinstance(spec['clear_designators'], bool)
        )
        for spec in vehicle_fields.values()
    ):
        _invalid('Invalid all-vehicle power targeting mapping', path)

    health_fields = sections['health'].get('techno_fields', {})
    if any(
        not all(
            _is_nonempty_string(spec.get(key))
            for key in ('source', 'clone_key', 'field')
        )
        for spec in health_fields.values()
    ):
        _invalid('Invalid delivered power health mapping', path)

    draining_fields = sections['duration'].get(
        'draining_techno_fields', {}
    )
    if any(
        not all(
            _is_nonempty_string(spec.get(key))
            for key in (
                'source', 'clone_key', 'strength_field', 'armor',
                'armor_parent', 'damage_warhead',
            )
        )
        or not isinstance(spec.get('base_verses_percent'), (int, float))
        or isinstance(spec.get('base_verses_percent'), bool)
        or spec['base_verses_percent'] <= 0
        for spec in draining_fields.values()
    ):
        _invalid('Invalid draining power lifetime mapping', path)


def _validate_enemy_scaling(sections, path):
    defaults = sections['defaults']
    required_defaults = {
        'stack_model_version',
        'maximum_total_buffs',
        'allowed_buff_ids', 'caps',
    }
    if not required_defaults.issubset(defaults):
        _invalid('Invalid AI reward defaults', path)
    if defaults['stack_model_version'] != 6:
        _invalid('Invalid AI reward stack model version', path)
    maximum_total = defaults['maximum_total_buffs']
    if (
        not isinstance(maximum_total, int)
        or isinstance(maximum_total, bool)
        or maximum_total < 0
        or maximum_total > 999
    ):
        _invalid('Invalid maximum total enemy buffs', path)
    seen = set()
    for index, definition in enumerate(sections['buffs']):
        required = {
            'id', 'name', 'type', 'category', 'effect', 'maximum_stacks',
            'per_stack_percent',
        }
        if not isinstance(definition, dict) or not required.issubset(definition):
            _invalid(f'Invalid AI reward {index}', path)
        effect_id = definition['id']
        maximum = definition['maximum_stacks']
        per_stack = definition['per_stack_percent']
        if (
            not _is_nonempty_string(effect_id)
            or effect_id in seen
            or not all(_is_nonempty_string(definition[key]) for key in (
                'name', 'type', 'category', 'effect',
            ))
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or maximum < 1
            or not isinstance(per_stack, (int, float))
            or isinstance(per_stack, bool)
            or per_stack <= 0
        ):
            _invalid(f'Invalid AI reward {effect_id!r}', path)
        seen.add(effect_id)
        if definition['effect'] == 'power':
            faction_families = definition.get('faction_families')
            if (
                not _is_nonempty_string(definition.get('superweapon'))
                or not _is_nonempty_string(definition.get('ai_targeting'))
                or str(definition.get('ai_targeting')).lower() == 'none'
                or maximum != 1
                or not isinstance(faction_families, list)
                or not faction_families
                or any(
                    family not in {'allies', 'soviets', 'epsilon', 'foehn'}
                    for family in faction_families
                )
            ):
                _invalid(f'Invalid enemy AI power {effect_id!r}', path)
        elif definition['effect'] == 'unit':
            _invalid(
                f'Unit effects belong in tier_unit_buff_templates: '
                f'{effect_id!r}', path
            )
        elif (
            definition['effect'] not in {'armor', 'production'}
            or not _is_nonempty_string(definition.get('country_suffix'))
        ):
            _invalid(f'Invalid AI-only house reward {effect_id!r}', path)
        if definition['effect'] == 'production':
            minimum = definition.get('minimum_engine_multiplier')
            if (
                not isinstance(minimum, (int, float))
                or isinstance(minimum, bool)
                or minimum <= 0
                or minimum >= 1
            ):
                _invalid(
                    f'Invalid enemy production clamp {effect_id!r}', path
                )
    templates = sections['tier_unit_buff_templates']
    template_ids = set()
    valid_unit_buff_types = {
        'health', 'armor', 'speed', 'sight', 'damage', 'reload', 'range',
        'ammo', 'self_healing', 'cloak', 'sensors',
    }
    for index, template in enumerate(templates):
        required = {
            'id', 'name', 'unit_buff_type', 'per_stack_value', 'value_unit',
            'maximum_stacks',
        }
        if not isinstance(template, dict) or not required.issubset(template):
            _invalid(f'Invalid tier AI unit buff template {index}', path)
        template_id = template['id']
        if (
            not _is_nonempty_string(template_id)
            or template_id in template_ids
            or template['unit_buff_type'] not in valid_unit_buff_types
            or not _is_nonempty_string(template['name'])
            or not _is_nonempty_string(template['value_unit'])
            or not isinstance(template['per_stack_value'], (int, float))
            or isinstance(template['per_stack_value'], bool)
            or template['per_stack_value'] <= 0
            or not isinstance(template['maximum_stacks'], int)
            or isinstance(template['maximum_stacks'], bool)
            or template['maximum_stacks'] < 1
        ):
            _invalid(f'Invalid tier AI unit buff template {template_id!r}', path)
        template_ids.add(template_id)
    generated_ids = {
        f'tier{tier}_{template_id}'
        for tier in (1, 2, 3)
        for template_id in template_ids
    }
    all_ids = seen | generated_ids
    if set(defaults['allowed_buff_ids']) - all_ids - {'*'}:
        _invalid('Unknown default AI reward IDs', path)
    if set(defaults['caps']) - all_ids:
        _invalid('AI reward caps contain unknown reward IDs', path)
    for effect_id, cap in defaults['caps'].items():
        if effect_id in generated_ids:
            template_id = effect_id.split('_', 1)[1]
            maximum = next(
                item['maximum_stacks'] for item in templates
                if item['id'] == template_id
            )
        else:
            maximum = next(
                item['maximum_stacks'] for item in sections['buffs']
                if item['id'] == effect_id
            )
        if (
            not isinstance(cap, int) or isinstance(cap, bool)
            or cap < 0 or cap > maximum
        ):
            _invalid(f'Invalid AI reward cap {effect_id!r}', path)


def _validate_catalogue(sections, path):
    global_reward_names = set()
    for reward in sections['global_buff_rewards']:
        if (
            not isinstance(reward, dict)
            or not _is_nonempty_string(reward.get('name'))
            or reward.get('kind') != 'buff'
            or reward.get('global_buff') is not True
        ):
            _invalid('Invalid global buff reward entry', path)
        normalized_name = reward['name'].casefold()
        if normalized_name in global_reward_names:
            _invalid('Duplicate global buff reward name', path)
        global_reward_names.add(normalized_name)
        if reward.get('buff_type') == 'starting_credits':
            per_stack = reward.get('credits_per_stack')
            maximum = reward.get('maximum_credits')
            if (
                not isinstance(per_stack, int)
                or isinstance(per_stack, bool)
                or per_stack <= 0
                or per_stack % 100
                or not isinstance(maximum, int)
                or isinstance(maximum, bool)
                or maximum < per_stack
                or maximum % per_stack
            ):
                _invalid('Invalid starting-credits reward limits', path)

    aid_reward_names = []
    aid_reward_powers = []
    for definition in sections['aid_power_rewards']:
        if not isinstance(definition, dict):
            _invalid('Invalid aid-power reward entry', path)
        aid_reward_names.append(str(definition.get('name') or '').casefold())
        aid_reward_powers.append(
            str(definition.get('superweapon') or '').casefold()
        )
        required_any = definition.get('requires_any_tech_ids')
        if required_any is not None and (
            not isinstance(required_any, list)
            or not required_any
            or not all(_is_nonempty_string(item) for item in required_any)
            or len({item.upper() for item in required_any}) != len(required_any)
        ):
            _invalid(
                'Invalid requires_any_tech_ids for '
                f'{definition.get("superweapon")!r}',
                path,
            )
    if (
        len(aid_reward_names) != len(set(aid_reward_names))
        or len(aid_reward_powers) != len(set(aid_reward_powers))
    ):
        _invalid('Duplicate aid-power reward name or SuperWeaponType', path)

    configured_powers = []
    for config in sections['aid_power_map_configs']:
        configured_powers.append(
            str(config.get('superweapon') or '').casefold()
        )
        if (
            'provider_only' in config
            and not isinstance(config['provider_only'], bool)
        ):
            _invalid(
                'Invalid provider-only flag for '
                f'{config.get("superweapon")!r}',
                path,
            )
        if (
            'ignore_foreign_tech_gate' in config
            and not isinstance(config['ignore_foreign_tech_gate'], bool)
        ):
            _invalid(
                'Invalid foreign-tech gate override for '
                f'{config.get("superweapon")!r}',
                path,
            )
        delivery_clone_ids = config.get('delivery_player_clone_ids')
        if delivery_clone_ids is not None and (
            not isinstance(delivery_clone_ids, list)
            or not delivery_clone_ids
            or not all(
                _is_nonempty_string(unit_id)
                for unit_id in delivery_clone_ids
            )
            or len({
                unit_id.upper() for unit_id in delivery_clone_ids
            }) != len(delivery_clone_ids)
        ):
            _invalid(
                'Invalid delivery player-clone IDs for '
                f'{config.get("superweapon")!r}',
                path,
            )
        reference_fields = config.get('player_clone_reference_fields')
        if reference_fields is not None and (
            not isinstance(reference_fields, dict)
            or not reference_fields
            or any(
                not _is_nonempty_string(field)
                or not isinstance(unit_ids, list)
                or not unit_ids
                or not all(_is_nonempty_string(unit_id) for unit_id in unit_ids)
                or len({unit_id.upper() for unit_id in unit_ids}) != len(unit_ids)
                for field, unit_ids in reference_fields.items()
            )
        ):
            _invalid(
                'Invalid player-clone reference fields for '
                f'{config.get("superweapon")!r}',
                path,
            )
        clone_overrides = config.get('player_clone_value_overrides')
        if clone_overrides is not None and (
            not isinstance(clone_overrides, dict)
            or not clone_overrides
            or any(
                not _is_nonempty_string(unit_id)
                or not isinstance(values, dict)
                or not values
                or not all(_is_nonempty_string(field) for field in values)
                for unit_id, values in clone_overrides.items()
            )
        ):
            _invalid(
                'Invalid player-clone value overrides for '
                f'{config.get("superweapon")!r}',
                path,
            )
        referenced_clone_ids = {
            str(unit_id).upper()
            for unit_ids in (reference_fields or {}).values()
            for unit_id in unit_ids
        }
        override_clone_ids = {
            str(unit_id).upper() for unit_id in (clone_overrides or {})
        }
        if not override_clone_ids.issubset(referenced_clone_ids):
            _invalid(
                'Player-clone value overrides must target referenced IDs for '
                f'{config.get("superweapon")!r}',
                path,
            )
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
    if len(configured_powers) != len(set(configured_powers)):
        _invalid('Duplicate aid-power map SuperWeaponType config', path)


CONFIG_VALIDATORS = {
    'missions.json': _validate_missions,
    'shop_mode.json': _validate_shop_mode,
    'rewards/unit_data.json': _validate_unit_data,
    'rewards/unit_policy.json': _validate_unit_policy,
    'rewards/special_buildings.json': _validate_special_buildings,
    'ui.json': _validate_ui,
    'rewards/tuning.json': _validate_tuning,
    'tier_one.json': _validate_tier_one,
    'rewards/buff_exceptions.json': _validate_buff_exceptions,
    'rewards/power_buffs.json': _validate_power_buffs,
    'rewards/catalogue.json': _validate_catalogue,
    'rewards/enemy_scaling.json': _validate_enemy_scaling,
}


def validate_sections(relative_path, sections, path):
    """Validate required shapes plus one config family's detailed contract."""
    config_key = normalized_config_path(relative_path)
    _validate_required_sections(config_key, sections, path)
    validator = CONFIG_VALIDATORS.get(config_key)
    if validator is not None:
        validator(sections, path)
