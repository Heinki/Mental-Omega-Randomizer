"""Reviewed mission-specific exceptions consumed by map generation.

Keep mission facts declarative. Generic launch and UI code should only select
and apply these values, following randomizer_mission_houses.py's pattern.
"""

from randomizer_static_config import load_static_config


_MISSION_CONFIG = load_static_config('missions.json')


def _frozenset_mapping(section):
    return {
        key: frozenset(values)
        for key, values in _MISSION_CONFIG[section].items()
    }

# Objects beginning outside the coalition which later become, or affect,
# player-owned mission objects through exact native triggers.
MISSION_NATIVE_TRIGGER_REFERENCE_IDS = _frozenset_mapping('native_trigger_reference_ids')

MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS = _frozenset_mapping('native_techno_clone_exclusions')

MISSION_REWARD_EXCLUDED_PLAYER_HOUSES = _frozenset_mapping('reward_excluded_player_houses')

MISSION_TEAM_HOUSE_OVERRIDES = dict(_MISSION_CONFIG['team_house_overrides'])

# Mission-only production merged after progression locks. These never become
# permanent seed rewards.
MISSION_REQUIRED_ACCESS_RULES = dict(_MISSION_CONFIG['required_access_rules'])

MISSION_TECHNO_BASE_RULES = dict(_MISSION_CONFIG['techno_base_rules'])

MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS = _frozenset_mapping('native_direct_buff_exclusions')

MISSION_NATIVE_VARIANT_BUFF_RULES = {
    code: {
        'source_unit': values['source_unit'],
        'native_units': tuple(values['native_units']),
    }
    for code, values in _MISSION_CONFIG['native_variant_buff_rules'].items()
}

MISSION_NATIVE_TECH_UNLOCK_IDS = _frozenset_mapping('native_tech_unlock_ids')

MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES = dict(
    _MISSION_CONFIG['superweapon_techno_clone_overrides']
)
for mission_values in MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES.values():
    for power_values in mission_values.values():
        for clone_values in power_values.values():
            clone_values['reference_keys'] = tuple(clone_values['reference_keys'])

# Missions needing every earned defense exposed through any Construction Yard.
MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS = frozenset(_MISSION_CONFIG['all_conyard_defense_access_missions'])

STANDARD_STARTER_FAMILIES_BY_CAMPAIGN = {
    campaign: tuple(families)
    for campaign, families in _MISSION_CONFIG['standard_starter_families_by_campaign'].items()
}
