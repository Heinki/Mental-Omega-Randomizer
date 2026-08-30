"""Reviewed mission-specific exceptions consumed by map generation.

Keep mission facts declarative. Generic launch and UI code should only select
and apply these values, following `randomizer/missions/houses.py`.
"""

from randomizer.config.static import load_static_config


_MISSION_CONFIG = load_static_config('missions.json')


def _frozenset_mapping(section):
    return {
        key: frozenset(values)
        for key, values in _MISSION_CONFIG[section].items()
    }

# Objects beginning outside the coalition which later become, or affect,
# player-owned mission objects through exact native triggers.
MISSION_NATIVE_TRIGGER_REFERENCE_IDS = _frozenset_mapping('native_trigger_reference_ids')

MISSION_DISABLED_TRIGGERS = {
    code: frozenset(trigger_ids)
    for code, trigger_ids in _MISSION_CONFIG.get('disabled_triggers', {}).items()
}

MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS = _frozenset_mapping('native_techno_clone_exclusions')

MISSION_REWARD_EXCLUDED_PLAYER_HOUSES = _frozenset_mapping('reward_excluded_player_houses')

# Script-heavy helper Houses whose authored map objects must retain native
# TechnoType identities even when the global allied-helper buff option is on.
MISSION_HELPER_BUFF_EXCLUDED_HOUSES = _frozenset_mapping(
    'helper_buff_excluded_houses'
)

MISSION_CLONE_ONLY_COUNTRY_BUFF_TYPES = _frozenset_mapping(
    'clone_only_country_buff_types'
)

MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCES = _frozenset_mapping(
    'scripted_player_buff_taskforces'
)

MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCE_ACCESS_REQUIREMENTS = {
    code: {
        str(taskforce_id): frozenset(
            str(unit_id).upper() for unit_id in unit_ids
        )
        for taskforce_id, unit_ids in requirements.items()
    }
    for code, requirements in _MISSION_CONFIG.get(
        'scripted_player_buff_taskforce_access_requirements', {}
    ).items()
}

MISSION_TEAM_HOUSE_OVERRIDES = dict(_MISSION_CONFIG['team_house_overrides'])

# Native MCV identities exposed only in configured missions. An empty list
# disables the mission exception; replacing the list changes its MCV types.
MISSION_ORIGINAL_MCV_ACCESS_IDS = {
    code: frozenset(values)
    for code, values in _MISSION_CONFIG.get(
        'original_mcv_access',
        {'FREMNANT': ['AMCV', 'SMCV']},
    ).items()
}

# Some scripted TeamTypes are refused when their native unit carries the
# exact-House negative production gate. These reviewed identities retain their
# authored/global production restrictions but never receive the hidden gate
# prerequisite.
MISSION_NATIVE_PRODUCTION_GATE_EXCLUSIONS = {
    code: frozenset(values)
    for code, values in _MISSION_CONFIG.get(
        'native_production_gate_exclusions',
        {'SRED': ['SAPC']},
    ).items()
}

# Map-local sidebar aliases which duplicate an earned native source. When that
# source has a player production clone, keep the alias usable by authored map
# logic but block it from player factories through the same native gate.
MISSION_NATIVE_PRODUCTION_ALIASES = {
    code: {
        str(alias_id).upper(): str(source_id).upper()
        for alias_id, source_id in values.items()
    }
    for code, values in _MISSION_CONFIG.get(
        'native_production_aliases', {}
    ).items()
}

# Objective-completion actions whose immediate transition is unsafe to extend
# with marker-team creation. The target action must be a later authored signal
# in the same successful sequence, after the fragile transition has settled.
MISSION_OBJECTIVE_HOOK_ACTION_REDIRECTS = {
    code: {
        str(source_action_id): str(target_action_id)
        for source_action_id, target_action_id in redirects.items()
    }
    for code, redirects in _MISSION_CONFIG.get(
        'objective_hook_action_redirects', {}
    ).items()
}

# Map-local factories that intentionally serve only authored mission units.
# They must not become generic randomizer Barracks alternatives.
MISSION_SPECIAL_INFANTRY_FACTORY_EXCLUSIONS = {
    code: frozenset(values)
    for code, values in _MISSION_CONFIG.get(
        'special_infantry_factory_exclusions', {}
    ).items()
}

# Reviewed authored Action groups which prove mission victory before the final
# End Scenario action can stop asynchronous debug-marker creation.
MISSION_VICTORY_HOOK_ACTION_IDS = {
    code: tuple(action_ids)
    for code, action_ids in _MISSION_CONFIG.get(
        'victory_hook_action_ids', {}
    ).items()
}

# Mission-authored runtime identities whose complete map section must survive
# player-clone production isolation unchanged. These remain native only for
# scripted placements/TaskForces; player production uses its separate clone.
MISSION_NATIVE_RUNTIME_PRESERVE_ACTION_TEAMS = frozenset(
    _MISSION_CONFIG.get('native_runtime_preserve_action_teams', ())
)

MISSION_NATIVE_RUNTIME_ACTION_TEAM_FACTORY_FORBIDDEN_HOUSES = (
    _frozenset_mapping(
        'native_runtime_action_team_factory_forbidden_houses'
    )
)

# Native story identities whose player-owned TaskForces have been reviewed for
# clone rewriting. Their native copy may retain only the exact player-country
# ForbiddenHouses production exclusion after the full authored section restore.
MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS = _frozenset_mapping(
    'native_runtime_player_forbidden_ids'
)

# Physical launch-provider buildings owned by a transient campaign House can
# be deleted during a stage handoff while an enemy scan still holds a pointer.
# Defer only reviewed provider-backed powers for that map; earned power access
# remains available in every other mission.
MISSION_UNSAFE_STATIC_PROVIDER_SUPERWEAPON_IDS = _frozenset_mapping(
    'unsafe_static_provider_superweapon_ids'
)

MISSION_NATIVE_RUNTIME_WEAPON_PRESERVE_IDS = _frozenset_mapping(
    'native_runtime_weapon_preserve_ids'
)

MISSION_NATIVE_RUNTIME_IDENTITY_PRESERVE_IDS = {
    code: frozenset(values)
    for code, values in _MISSION_CONFIG.get(
        'native_runtime_identity_preserve_ids', {}
    ).items()
}

# Exact player-objective Events which must follow a separately buildable clone
# while enemy placements and scripted TaskForces retain the native identity.
MISSION_OBJECTIVE_CLONE_EVENT_REFS = {
    code: {
        str(unit_id).upper(): tuple(event_ids)
        for unit_id, event_ids in values.items()
    }
    for code, values in _MISSION_CONFIG.get(
        'objective_clone_event_refs', {}
    ).items()
}

# Extra physical factories that may build an always-available amphibious
# transport in one reviewed mission. Normal naval production remains valid.
MISSION_TRANSPORT_FACTORY_EXCEPTIONS = {
    code: {
        str(unit_id).upper(): tuple(factory_ids)
        for unit_id, factory_ids in values.items()
    }
    for code, values in _MISSION_CONFIG.get(
        'transport_factory_exceptions', {}
    ).items()
}

# Mission-only production merged after progression locks. These never become
# permanent seed rewards.
MISSION_REQUIRED_ACCESS_RULES = dict(_MISSION_CONFIG['required_access_rules'])

MISSION_TECHNO_BASE_RULES = dict(_MISSION_CONFIG['techno_base_rules'])

# Final map-section edits. Values may be literals/null or CSV add/remove
# patches resolved against the extracted mission map before bulk injection.
MISSION_MAP_SECTION_RULES = dict(_MISSION_CONFIG['map_section_rules'])

MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS = _frozenset_mapping('native_direct_buff_exclusions')

# Native hostile mission units whose authored opening behavior is objective
# critical and must not receive tier weapon/stat clones.
MISSION_ENEMY_NATIVE_BUFF_EXCLUSIONS = _frozenset_mapping(
    'enemy_native_buff_exclusions'
)

MISSION_NATIVE_VARIANT_BUFF_RULES = {
    code: tuple(
        {
            'source_unit': rule['source_unit'],
            'native_units': tuple(rule['native_units']),
        }
        for rule in (values if isinstance(values, list) else [values])
    )
    for code, values in _MISSION_CONFIG['native_variant_buff_rules'].items()
}

MISSION_NATIVE_TECH_UNLOCK_IDS = _frozenset_mapping('native_tech_unlock_ids')

# Some authored unlock pairs swap a story-only identity against the native
# production identity.  When the production side is cloned, mirror its
# TechLevel change to the clone while keeping the native source unavailable to
# that trigger House.  This preserves the authored alternation without ever
# showing source and clone together.
MISSION_NATIVE_TECH_UNLOCK_KEEP_SOURCE_DISABLED_IDS = _frozenset_mapping(
    'native_tech_unlock_keep_source_disabled_ids'
)

MISSION_NATIVE_UNLOCK_OWNED_ACCESS_RULES = dict(
    _MISSION_CONFIG['native_unlock_owned_access_rules']
)

MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES = dict(
    _MISSION_CONFIG['superweapon_techno_clone_overrides']
)
for mission_values in MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES.values():
    for power_values in mission_values.values():
        for clone_values in power_values.values():
            clone_values['reference_keys'] = tuple(clone_values['reference_keys'])

MISSION_TIME_FREEZE_IMMUNE_TECHNO_IDS = {
    code: tuple(str(unit_id).upper() for unit_id in unit_ids)
    for code, unit_ids in _MISSION_CONFIG.get(
        'time_freeze_immune_techno_ids', {}
    ).items()
}

# Missions needing every earned defense exposed through any Construction Yard.
MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS = frozenset(_MISSION_CONFIG['all_conyard_defense_access_missions'])

STANDARD_STARTER_FAMILIES_BY_CAMPAIGN = {
    campaign: tuple(families)
    for campaign, families in _MISSION_CONFIG['standard_starter_families_by_campaign'].items()
}
