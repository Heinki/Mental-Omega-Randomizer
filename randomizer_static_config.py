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
        'engineer_by_family': dict,
        'engineer_installed_forbidden_houses': dict,
        'conyard_by_mcv': dict,
        'stalins_fist_factory': str,
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
    if str(Path(relative_path)).replace('\\', '/') == 'rewards/unit_data.json':
        for index, group in enumerate(sections['unit_role_equivalence_groups']):
            if not isinstance(group, list) or not group or not all(
                isinstance(unit_id, str) and unit_id for unit_id in group
            ):
                raise StaticConfigError(
                    f'Invalid unit role equivalence group {index} in {path}'
                )


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
