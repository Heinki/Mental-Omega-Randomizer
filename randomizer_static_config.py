"""Validated loader for editable, packaged static randomizer configuration."""

import json
import shutil
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from randomizer_paths import APP_DIR, FROZEN, SOURCE_DIR


BUNDLED_CONFIG_DIR = SOURCE_DIR / 'configs'
STATIC_CONFIG_DIR = APP_DIR / 'configs'
SUPPORTED_SCHEMA_VERSION = 1
REQUIRED_STATIC_CONFIGS = (
    'default_player_config.json',
    'missions.json',
    'map_rules.json',
    'factions.json',
    'ui.json',
    'rewards/unit_data.json',
    'rewards/catalogue.json',
    'rewards/tuning.json',
    'rewards/unit_policy.json',
)
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
        'native_direct_buff_exclusions': dict,
        'native_variant_buff_rules': dict,
        'native_tech_unlock_ids': dict,
        'superweapon_techno_clone_overrides': dict,
        'all_conyard_defense_access_missions': list,
        'standard_starter_families_by_campaign': dict,
    },
    'map_rules.json': {
        'common_build_tab_tech_locks': list,
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
        'tier_one_role_units': dict,
        'tier_one_ground_roles': list,
        'standard_tier_one_families': list,
        'tier_one_airfields': dict,
        'amphibious_transports': dict,
        'production_buildings': dict,
        'chaos_primary_production': dict,
        'tech_order': list,
    },
    'ui.json': {
        'difficulties': list,
        'game_speeds': list,
        'campaign_filters': list,
        'reward_modes': list,
        'progression_modes': list,
        'default_progression_mode': str,
        'rewards_per_check_messages': dict,
        'faction_tile_colors': dict,
        'light_palette': dict,
        'dark_palette': dict,
    },
    'rewards/unit_data.json': {
        'faction_unit_rosters': dict,
        'unit_base_stats': dict,
        'unit_role_equivalence_groups': list,
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
        'lightning_storm_map_rules': dict,
        'chronoshift_map_rules': dict,
        'chronowarp_map_rules': dict,
        'superweapon_unlock_rewards': list,
        'secondary_superweapon_unlock_rewards': list,
        'building_free_support_power_values': dict,
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
        'ammo_display_labels': dict,
    },
}


class StaticConfigError(RuntimeError):
    """Raised when required static configuration is missing or malformed."""


def _config_path(relative_path):
    relative_path = Path(relative_path)
    if relative_path.is_absolute() or '..' in relative_path.parts:
        raise StaticConfigError(f'Invalid static config path: {relative_path}')
    return STATIC_CONFIG_DIR / relative_path


def _ensure_visible_config(relative_path):
    target = _config_path(relative_path)
    if target.is_file() or not FROZEN:
        return target

    bundled = BUNDLED_CONFIG_DIR / relative_path
    if not bundled.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled, target)
    return target


def _validate_sections(relative_path, sections, path):
    required = REQUIRED_SECTIONS.get(str(Path(relative_path)).replace('\\', '/'), {})
    for section, expected_type in required.items():
        if section not in sections:
            raise StaticConfigError(f'Missing section {section!r} in {path}')
        if not isinstance(sections[section], expected_type):
            raise StaticConfigError(
                f'Section {section!r} in {path} must be {expected_type.__name__}'
            )

    if str(Path(relative_path)).replace('\\', '/') == 'missions.json':
        allowed = {'base_build', 'true_no_build', 'no_build_production'}
        invalid = {
            code: value
            for code, value in sections['build_classifications'].items()
            if value not in allowed
        }
        if invalid:
            raise StaticConfigError(
                f'Invalid mission build classifications in {path}: {invalid}'
            )
        for code, rule in sections['native_variant_buff_rules'].items():
            if not isinstance(rule, dict) or not isinstance(
                rule.get('source_unit'), str
            ):
                raise StaticConfigError(
                    f'Invalid native variant rule for {code} in {path}'
                )
            if not isinstance(rule.get('native_units'), list) or not all(
                isinstance(unit_id, str) and unit_id
                for unit_id in rule['native_units']
            ):
                raise StaticConfigError(
                    f'Invalid native variant units for {code} in {path}'
                )
    if str(Path(relative_path)).replace('\\', '/') == 'rewards/unit_data.json':
        for index, group in enumerate(sections['unit_role_equivalence_groups']):
            if not isinstance(group, list) or not group or not all(
                isinstance(unit_id, str) and unit_id for unit_id in group
            ):
                raise StaticConfigError(
                    f'Invalid unit role equivalence group {index} in {path}'
                )
    if str(Path(relative_path)).replace('\\', '/') == 'ui.json':
        messages = sections['rewards_per_check_messages']
        if not isinstance(messages.get('maximum'), str) or not isinstance(
            messages.get('thresholds'), list
        ) or not all(
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], int)
            and isinstance(item[1], str)
            for item in messages['thresholds']
        ):
            raise StaticConfigError(f'Invalid rewards-per-check messages in {path}')
    if str(Path(relative_path)).replace('\\', '/') == 'rewards/tuning.json':
        effects = sections['buff_effects']
        for effect in (
            'production', 'cost', 'speed', 'armor', 'health', 'damage',
            'reload',
        ):
            values = effects.get(effect)
            if not isinstance(values, dict) or not isinstance(
                values.get('factor_per_stack'), (int, float)
            ) or values['factor_per_stack'] <= 0:
                raise StaticConfigError(f'Invalid buff effect {effect!r} in {path}')
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
                raise StaticConfigError(
                    f'Invalid {key!r} for buff effect {effect!r} in {path}'
                )
        for effect in ('range', 'sight', 'ammo'):
            values = effects.get(effect)
            if not isinstance(values, dict) or not all(
                isinstance(values.get(key), (int, float)) and values[key] >= 0
                for key in ('amount_per_stack', 'maximum_amount')
            ):
                raise StaticConfigError(
                    f'Invalid additive buff effect {effect!r} in {path}'
                )
        for key in (
            'sensor_sight_bonus', 'defense_self_heal_fraction',
            'maximum_veterancy_stacks',
        ):
            if not isinstance(effects.get(key), (int, float)) or effects[key] < 0:
                raise StaticConfigError(f'Invalid buff tuning {key!r} in {path}')
        infantry_speed = effects.get('infantry_speed')
        if not isinstance(infantry_speed, dict) or not all(
            isinstance(infantry_speed.get(key), (int, float))
            and infantry_speed[key] > 0
            for key in ('factor_per_stack', 'safe_ceiling')
        ):
            raise StaticConfigError(f'Invalid infantry speed tuning in {path}')
        clone_policy = sections['clone_policy']
        for key in ('unit_id_prefix', 'weapon_id_prefix'):
            if not isinstance(clone_policy.get(key), str) or not clone_policy[key]:
                raise StaticConfigError(f'Invalid clone policy {key!r} in {path}')
        for key in (
            'production_gate_keys', 'production_gate_prefixes',
            'required_weapon_fields',
        ):
            if not isinstance(clone_policy.get(key), list) or not all(
                isinstance(value, str) and value for value in clone_policy[key]
            ):
                raise StaticConfigError(f'Invalid clone policy {key!r} in {path}')
        assistance = sections['mission_assistance']
        if not isinstance(
            assistance.get('maximum_direct_stacks'), int
        ) or assistance['maximum_direct_stacks'] < 0:
            raise StaticConfigError(f'Invalid mission assistance stack limit in {path}')
        if not isinstance(assistance.get('direct_buff_types'), list) or not all(
            isinstance(value, str) and value
            for value in assistance['direct_buff_types']
        ):
            raise StaticConfigError(
                f'Invalid mission assistance buff types in {path}'
            )
        if not isinstance(
            assistance.get('reload_when_weapon_rof_above'), (int, float)
        ) or not isinstance(assistance.get('add_safe_infantry_speed'), bool):
            raise StaticConfigError(f'Invalid mission assistance policy in {path}')
        planning = sections['reward_planning']
        for key in (
            'default_rewards_per_check', 'maximum_rewards_per_check',
            'maximum_global_buff_repeats_per_seed',
            'global_buff_reward_interval',
        ):
            if not isinstance(planning.get(key), int) or planning[key] <= 0:
                raise StaticConfigError(
                    f'Invalid reward planning value {key!r} in {path}'
                )
        if (
            planning['default_rewards_per_check']
            > planning['maximum_rewards_per_check']
        ):
            raise StaticConfigError(f'Default rewards exceed maximum in {path}')
    if str(Path(relative_path)).replace('\\', '/') == 'rewards/unit_policy.json':
        policy_lists = (
            'noncombat_weapon_target_ids', 'nontrainable_unit_ids',
            'always_available_core_unit_ids',
            'always_available_building_ids', 'trainable_defense_ids',
            'naval_unit_ids',
        )
        for key in policy_lists:
            if not all(
                isinstance(value, str) and value for value in sections[key]
            ):
                raise StaticConfigError(
                    f'Invalid unit policy list {key!r} in {path}'
                )
        if not all(
            isinstance(values, list)
            and all(isinstance(value, str) and value for value in values)
            for values in sections['existing_capability_ids'].values()
        ):
            raise StaticConfigError(f'Invalid capability policy in {path}')


@lru_cache(maxsize=None)
def _load_static_config_cached(relative_path):
    """Load one static JSON document and validate its common envelope."""
    path = _ensure_visible_config(relative_path)
    if not path.is_file():
        raise StaticConfigError(f'Required static config is missing: {path}')
    try:
        document = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise StaticConfigError(f'Cannot load static config {path}: {exc}') from exc
    if not isinstance(document, dict):
        raise StaticConfigError(f'Static config root must be an object: {path}')
    version = document.get('schema_version')
    if version != SUPPORTED_SCHEMA_VERSION:
        raise StaticConfigError(
            f'Unsupported schema_version {version!r} in {path}; '
            f'expected {SUPPORTED_SCHEMA_VERSION}'
        )
    sections = document.get('sections')
    if not isinstance(sections, dict):
        raise StaticConfigError(f'Static config sections must be an object: {path}')
    _validate_sections(relative_path, sections, path)
    return sections


def load_static_config(relative_path):
    """Return an isolated copy so runtime derivation cannot mutate cached data."""
    return deepcopy(_load_static_config_cached(relative_path))


load_static_config.cache_clear = _load_static_config_cached.cache_clear


def static_config_section(relative_path, section, expected_type):
    """Return one required section with a clear type-validation error."""
    sections = load_static_config(relative_path)
    if section not in sections:
        raise StaticConfigError(f'Missing section {section!r} in {relative_path}')
    value = sections[section]
    if not isinstance(value, expected_type):
        expected_name = getattr(expected_type, '__name__', str(expected_type))
        raise StaticConfigError(
            f'Section {section!r} in {relative_path} must be {expected_name}'
        )
    return value


def validate_static_configs(relative_paths):
    """Load required documents, returning their resolved visible paths."""
    paths = []
    for relative_path in relative_paths:
        load_static_config(relative_path)
        paths.append(_config_path(relative_path))
    return paths
