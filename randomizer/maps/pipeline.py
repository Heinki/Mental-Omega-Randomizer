"""Generated mission-map pipeline separated from Tk orchestration."""

from randomizer.core.collections import unique_in_order
from randomizer.ui.cameos import installed_rules_registry
from randomizer.maps.assets import deploy_superweapon_sidebar_assets
from randomizer.maps.ini import (
    IniLines,
    all_section_value_maps,
    merge_ini_section_values,
    read_text,
    section_value_map_preserve,
)
from randomizer.maps.ownership import (
    build_unit_usage_index,
    script_referenced_taskforce_unit_ids,
    taskforce_usage_houses,
)
from randomizer.maps.power_buffs import (
    apply_power_buffs_to_unlock_rewards,
    equivalent_payload_unit_buff_rewards,
)
from randomizer.maps.rules import (
    HOOKED_MAP_MARKER,
    LOCKED_TECH_LEVEL,
    MAX_MAP_ACTION_LINE_LENGTH,
    PLAYER_ORIGINAL_PRODUCTION_GATE_ID,
    TECHNO_TYPE_LISTS,
    append_static_startup_buildings,
    append_superweapon_grant_trigger,
    backup_file_once,
    clone_player_country_for_house_buffs,
    cloned_superweapon_plan,
    active_hostile_enemy_houses,
    discover_hostile_ai_houses,
    enemy_country_buff_rules,
    enemy_existing_power_grant_plan,
    enemy_existing_power_rule_overrides,
    enemy_native_unit_buff_rules,
    enemy_power_launch_rewards,
    helper_ai_autobuild_plan,
    helper_ai_autobuild_rules,
    is_generated_hooked_map,
    mission_assistance_buff_rules,
    mission_assistance_direct_rewards,
    mission_assistance_unit_ids,
    native_variant_unit_buff_rules,
    native_variant_veterancy_rules,
    original_player_production_gate_rules,
    validate_native_taskforce_production_filters,
    player_country_buff_rules,
    player_clone_pad_aircraft_rules,
    player_unit_clone_rules,
    validate_player_clone_pad_aircraft,
    validate_player_clone_selection_groups,
    resolved_academy_clone_rules,
    resolved_delivery_clone_rules,
    resolved_native_designator_clone_rules,
    resolved_power_player_clone_rules,
    resolved_map_section_rules,
    remove_locked_techlevel_actions,
    reconcile_generated_techno_registrations,
    rewrite_techlevel_actions,
    scripted_reinforcement_veterancy_rules,
    stacked_house_buff_values,
    suppressed_superweapon_building_ids,
    unit_weapon_buff_rules,
    veteran_armor_safety_rules,
)
from randomizer.maps.buff_validation import (
    validate_generated_unit_buff_changes,
)
from randomizer.maps.access_diagnostics import build_unit_access_report
from randomizer.rewards.rules import (
    expand_equivalent_role_buffs,
    unlocked_reward_tech_ids,
)
from randomizer.rewards.enemy_scaling import enemy_effect_text, enemy_effect_values
from randomizer.maps.progress_hooks import (
    inject_check_markers,
    pending_check_hook_plan,
)
from randomizer.maps.houses import (
    country_family,
    map_house_records,
    player_controlled_houses,
    player_country_from_map,
    player_house_from_map,
    resolve_configured_helper_houses,
)
from randomizer.maps.settings import (
    apply_mission_eva_voice,
    mission_eva_voice_rules,
    mission_house_color_rules,
)
from randomizer.maps.special_buildings import (
    DEFAULT_REFINERY_MINER_IDS,
    ore_purifier_miner_dock_rules,
    reprocessor_bounty_rules,
)
from randomizer.missions.houses import (
    mission_house_config,
    mission_player_power_houses,
    mission_player_production_houses,
)
from randomizer.missions.overrides import (
    MISSION_CLONE_ONLY_COUNTRY_BUFF_TYPES,
    MISSION_DISABLED_TRIGGERS,
    MISSION_HELPER_BUFF_EXCLUDED_HOUSES,
    MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS,
    MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS,
    MISSION_NATIVE_PRODUCTION_GATE_EXCLUSIONS,
    MISSION_NATIVE_PRODUCTION_ALIASES,
    MISSION_NATIVE_RUNTIME_ACTION_TEAM_FACTORY_FORBIDDEN_HOUSES,
    MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS,
    MISSION_NATIVE_RUNTIME_PRESERVE_ACTION_TEAMS,
    MISSION_NATIVE_RUNTIME_IDENTITY_PRESERVE_IDS,
    MISSION_NATIVE_RUNTIME_WEAPON_PRESERVE_IDS,
    MISSION_OBJECTIVE_HOOK_ACTION_REDIRECTS,
    MISSION_ORIGINAL_MCV_ACCESS_IDS,
    MISSION_OBJECTIVE_CLONE_EVENT_REFS,
    MISSION_NATIVE_TECH_UNLOCK_IDS,
    MISSION_NATIVE_TECH_UNLOCK_KEEP_SOURCE_DISABLED_IDS,
    MISSION_NATIVE_UNLOCK_OWNED_ACCESS_RULES,
    MISSION_NATIVE_TRIGGER_REFERENCE_IDS,
    MISSION_NATIVE_VARIANT_BUFF_RULES,
    MISSION_REQUIRED_ACCESS_RULES,
    MISSION_REWARD_EXCLUDED_PLAYER_HOUSES,
    MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCES,
    MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCE_ACCESS_REQUIREMENTS,
    MISSION_MAP_SECTION_RULES,
    MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES,
    MISSION_TIME_FREEZE_IMMUNE_TECHNO_IDS,
    MISSION_TEAM_HOUSE_OVERRIDES,
    MISSION_TECHNO_BASE_RULES,
    MISSION_UNSAFE_STATIC_PROVIDER_SUPERWEAPON_IDS,
    MISSION_VICTORY_HOOK_ACTION_IDS,
)
from randomizer.missions.safety import safe_build_countries
from randomizer.missions.access import PRODUCTION_BUILDINGS
from randomizer.missions.catalogue import normalize_faction
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT, GENERATED_MAP_DIR
from randomizer.rewards.catalogue import (
    ALWAYS_AVAILABLE_TECH_IDS,
    AMPHIBIOUS_TRANSPORT_UNIT_IDS,
    BUFF_TARGETS,
    ENGINEER_UNIT_IDS,
    canonical_rewards,
    reward_display_name,
    starting_credit_bonus,
)
from randomizer.ui.config import (
    EVA_APPEARANCE_PROFILES,
    EVA_VOICE_TAGS,
    RAINBOWIZER_COLORS,
)
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.rewards.arsenal import ARSENAL_MODE


def prepare_hooked_map(self, mission, extra_rules=None):
    fallback_tech_ids = {
        section.upper()
        for section, values in (extra_rules or {}).items()
        if any(key.lower() == 'techlevel' for key in values)
    }
    share_basic_equivalent_buffs = bool(
        (
            self.state
            and self.state.get('campaign_filter') in {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
            and self.active_reward_mode() not in {'Chaos', ARSENAL_MODE}
        )
        or self.share_chaos_role_buffs_enabled()
    )
    chaos_unit_specific_buffs = self.active_reward_mode() in {
        'Chaos', ARSENAL_MODE,
    }
    buff_allied_helpers = bool(self.active_reward_settings().get('buff_allied_helpers', False))

    scenario = mission.get('scenario')
    code = mission.get('code')
    if not scenario or not code:
        return None
    delayed_native_unlock_ids = {
        str(unit_id).upper()
        for unit_id in MISSION_NATIVE_TECH_UNLOCK_IDS.get(code, ())
        if any(
            str(key).lower() == 'techlevel'
            and str(value) == LOCKED_TECH_LEVEL
            for key, value in (extra_rules or {}).get(unit_id, {}).items()
        )
    }
    original_mcv_access_ids = set(
        MISSION_ORIGINAL_MCV_ACCESS_IDS.get(code, ())
    )
    similar_tech_enabled_for_report = share_basic_equivalent_buffs
    similar_tech_reason_for_report = (
        'Single Campaign automatic sharing; buffs only'
        if (
            self.state
            and self.state.get('campaign_filter')
            in {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
            and self.active_reward_mode() not in {'Chaos', ARSENAL_MODE}
        )
        else 'user option; buffs only'
        if share_basic_equivalent_buffs
        else ''
    )
    native_techno_exclusions = frozenset(
        set(MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS.get(code, ()))
        | original_mcv_access_ids
    )
    native_required_access_ids = {
        str(section).upper()
        for section in MISSION_REQUIRED_ACCESS_RULES.get(code, {})
    } | original_mcv_access_ids
    native_build_only_clone_ids = (
        set(native_techno_exclusions) - native_required_access_ids
    )
    excluded_player_houses = MISSION_REWARD_EXCLUDED_PLAYER_HOUSES.get(
        code, ()
    )
    clone_only_country_buff_types = (
        MISSION_CLONE_ONLY_COUNTRY_BUFF_TYPES.get(code, ())
    )
    direct_only_country_buff_types = set(clone_only_country_buff_types)
    direct_only_country_buff_types.add('production')
    if clone_only_country_buff_types:
        self.append_log(
            f'Kept {", ".join(sorted(clone_only_country_buff_types))} '
            f'country buffs clone-only for {code}; native scripted '
            'reinforcements retain mission-authored stats.'
        )

    source_path = self.extract_campaign_map(scenario)
    lines = IniLines(read_text(source_path).splitlines())
    color_rules = mission_house_color_rules(
        lines,
        player_color=self.player_color_var.get(),
        rainbowizer=bool(self.rainbowizer_var.get()),
        rainbow_colors=RAINBOWIZER_COLORS,
        random_key=f'{self.state.get("seed", "") if self.state else ""}|{code}',
    )
    if color_rules:
        merge_ini_section_values(lines, color_rules)
        self.append_log(
            f'Applied map color settings to {len(color_rules)} house(s).'
        )
    (
        eva_rules,
        eva_label,
        eva_action_index,
        eva_appearance_applied,
    ) = mission_eva_voice_rules(
        self.eva_voice_var.get(),
        EVA_VOICE_TAGS,
        appearance_profiles=EVA_APPEARANCE_PROFILES,
        random_key=f'{self.state.get("seed", "") if self.state else ""}|{code}',
    )
    if eva_rules:
        merge_ini_section_values(lines, eva_rules)
        eva_trigger, rewritten_eva_actions = apply_mission_eva_voice(
            lines,
            player_country_from_map(lines),
            eva_action_index,
        )
        if eva_trigger:
            rewrite_note = (
                f' Rebound {rewritten_eva_actions} native EVA re-enable action(s).'
                if rewritten_eva_actions
                else ''
            )
            appearance_note = (
                ', matching sidebar, and mission-text color'
                if eva_appearance_applied
                else ''
            )
            self.append_log(
                f'Applied live {eva_label} EVA voice{appearance_note} '
                'for this mission.'
                f'{rewrite_note}'
            )
        else:
            self.append_log(
                f'Could not create live {eva_label} EVA startup action.',
                error=True,
            )
    team_house_overrides = MISSION_TEAM_HOUSE_OVERRIDES.get(code, {})
    if team_house_overrides:
        available_team_ids = {
            team_id.lower()
            for team_id in section_value_map_preserve(lines, 'TeamTypes').values()
        }
        team_house_rules = {
            team_id: {'House': target_house}
            for team_id, target_house in team_house_overrides.items()
            if team_id.lower() in available_team_ids
        }
        if team_house_rules:
            merge_ini_section_values(lines, team_house_rules)
            self.append_log(
                'Assigned scripted player reinforcements to player house: '
                + ', '.join(sorted(team_house_rules))
                + '.'
            )
    # Preserve map-authored AI production fields before launcher access
    # locks and ownership rewrites are merged into this launch copy.
    native_map_sections = all_section_value_maps(lines)
    native_map_sections_preserve = {
        str(section).upper(): section_value_map_preserve(lines, section)
        for section in native_map_sections
    }
    scripted_story_unit_ids = script_referenced_taskforce_unit_ids(
        lines,
        native_map_sections,
    )
    runtime_identity_preserve_ids = {
        str(source_id).upper()
        for source_id in MISSION_NATIVE_RUNTIME_IDENTITY_PRESERVE_IDS.get(
            code, ()
        )
    }
    if code in MISSION_NATIVE_RUNTIME_PRESERVE_ACTION_TEAMS:
        runtime_identity_preserve_ids.update(scripted_story_unit_ids)
        self.append_log(
            f'{code} preserves {len(scripted_story_unit_ids)} authored '
            'action-created TaskForce identities through every clone, gate, '
            'and buff pass.'
        )
    installed_superweapon_types, installed_rule_sections = installed_rules_registry()
    installed_building_ids = {
        str(building_id).strip()
        for building_id in installed_rule_sections.get(
            'BuildingTypes', {}
        ).values()
        if str(building_id).strip()
    }
    refinery_building_ids = set()
    refinery_free_unit_ids = set()
    refinery_free_unit_by_building = {}
    native_map_names = {
        str(section).lower(): section for section in native_map_sections
    }
    # `Refinery=yes` also appears on economic support structures such as the
    # Ore Purifier. Only the reviewed four faction refineries own a native
    # miner/FreeUnit contract; support structures remain ordinary reward
    # clone candidates.
    for building_id in DEFAULT_REFINERY_MINER_IDS:
        building_values = dict(installed_rule_sections.get(building_id, {}))
        building_values.update(native_map_sections.get(
            native_map_names.get(str(building_id).lower()), {}
        ))
        if str(next(
            (
                value for key, value in building_values.items()
                if str(key).lower() == 'refinery'
            ),
            '',
        )).lower() != 'yes':
            continue
        refinery_building_ids.add(str(building_id).upper())
        for key, value in building_values.items():
            if str(key).lower() != 'freeunit':
                continue
            free_units = [
                unit_id.strip().upper()
                for unit_id in str(value or '').split(',')
                if unit_id.strip()
            ]
            if free_units:
                refinery_free_unit_by_building[
                    str(building_id).upper()
                ] = free_units[0]
                refinery_free_unit_ids.update(free_units)
    # Keep the reviewed four-faction contract available if an editable or
    # preserved installed registry omits one of the source sections.
    refinery_building_ids.update(DEFAULT_REFINERY_MINER_IDS)
    refinery_free_unit_ids.update(DEFAULT_REFINERY_MINER_IDS.values())
    for refinery_id, miner_id in DEFAULT_REFINERY_MINER_IDS.items():
        refinery_free_unit_by_building.setdefault(refinery_id, miner_id)
    veteran_health_rules = veteran_armor_safety_rules(
        lines,
        installed_rule_sections,
    )
    if veteran_health_rules:
        merge_ini_section_values(lines, veteran_health_rules)
        self.append_log(
            'Replaced unsafe map VeteranArmor with the installed positive '
            'veterancy multiplier.'
        )
    (
        _unit_roster_path,
        owned_clone_ids,
        owned_clone_templates,
    ) = randomizer_unit_roster()
    mission_base_rules = MISSION_TECHNO_BASE_RULES.get(code, {})
    native_names_by_lower = {
        str(section).lower(): section for section in native_map_sections
    }
    for section, values in mission_base_rules.items():
        native_section = native_names_by_lower.get(section.lower(), section)
        native_values = native_map_sections.setdefault(native_section, {})
        for key, value in values.items():
            native_values[str(key).lower()] = value
    house_config = mission_house_config(code)
    records = map_house_records(lines)
    mission_effective_tech_ids = self.mission_effective_unlocked_tech_ids(
        mission,
        lines,
        fallback_tech_ids,
    )
    rule_sections = self.map_rules_for_launch(
        extra_rules,
        allowed_unlocked_tech_ids=mission_effective_tech_ids,
    )
    iron_guard_clone = owned_clone_ids.get('NAIRDM')
    if iron_guard_clone and 'NAIRDM' in {
        str(tech_id).upper() for tech_id in mission_effective_tech_ids
    }:
        iron_guard_values = section_value_map_preserve(lines, 'IronGuardSpecial')
        if not iron_guard_values:
            iron_guard_values = installed_rule_sections.get('IronGuardSpecial', {})
        iron_guard_cannons = next(
            (
                value
                for key, value in iron_guard_values.items()
                if str(key).lower() == 'empulse.cannons'
            ),
            'NAIRDM',
        )
        rule_sections.setdefault('IronGuardSpecial', {})[
            'EMPulse.Cannons'
        ] = ','.join(unique_in_order(
            [
                cannon.strip()
                for cannon in str(iron_guard_cannons or 'NAIRDM').split(',')
                if cannon.strip()
            ]
            + [iron_guard_clone]
        ))
    owned_clone_rule_overlays = {}
    for section in list(rule_sections):
        section_upper = str(section).upper()
        if (
            section_upper in owned_clone_ids
            and (
                section_upper not in native_techno_exclusions
                or section_upper in native_build_only_clone_ids
            )
        ):
            owned_clone_rule_overlays.setdefault(section_upper, {}).update(
                rule_sections.pop(section)
            )
    # A reviewed native Action 106 remains available when its randomizer
    # reward is not owned. If the player already owns the isolated copy,
    # narrow only the native identity to its story AI/helper consumers so the
    # later mission action cannot leak a second unbuffed sidebar cameo.
    # Apply this after owned clone overlays are split out: the rule belongs to
    # the native source, not the earned player clone.
    effective_tech_ids_upper = {
        str(unit_id).upper() for unit_id in mission_effective_tech_ids
    }
    for source_id, values in MISSION_NATIVE_UNLOCK_OWNED_ACCESS_RULES.get(
        code, {}
    ).items():
        if source_id.upper() in effective_tech_ids_upper:
            rule_sections.setdefault(source_id, {}).update(values)
    for section, values in mission_base_rules.items():
        rule_sections.setdefault(section, {}).update(values)
    mission_map_rules = resolved_map_section_rules(
        lines, MISSION_MAP_SECTION_RULES.get(code, {})
    )
    for section, values in mission_map_rules.items():
        rule_sections.setdefault(section, {}).update(values)
    if mission_map_rules:
        self.append_log(
            f'Applied reviewed map section overrides for {code}: '
            + ', '.join(sorted(mission_map_rules))
            + '.'
        )
    reward_settings = self.active_reward_settings()
    suppressed_power_buildings = suppressed_superweapon_building_ids(
        reward_settings
    )
    for building_id in suppressed_power_buildings:
        rule_sections.setdefault(building_id, {})['TechLevel'] = LOCKED_TECH_LEVEL

    source_triggers = section_value_map_preserve(lines, 'Triggers')
    for trigger_id in MISSION_DISABLED_TRIGGERS.get(code, ()):
        trigger_value = source_triggers.get(trigger_id)
        if trigger_value is None:
            continue
        tokens = str(trigger_value).split(',')
        if len(tokens) > 3:
            tokens[3] = '1'
            rule_sections.setdefault('Triggers', {})[trigger_id] = ','.join(tokens)
    native_helpers, missing_helpers = resolve_configured_helper_houses(
        records,
        house_config['allies'],
        player_controlled_houses(lines, records=records),
    )
    configured_enemies, missing_enemies = resolve_configured_helper_houses(
        records,
        house_config['enemies'],
        (),
    )
    discovered_enemies, discovered_enemy_skips = discover_hostile_ai_houses(
        lines, excluded_houses=native_helpers
    )
    configured_enemies = unique_in_order(
        list(configured_enemies) + list(discovered_enemies)
    )
    enemy_names = {house.lower() for house in configured_enemies}
    scaled_enemy_houses, phase_enemy_houses = active_hostile_enemy_houses(
        lines, configured_enemies
    )
    native_helpers = [
        house for house in native_helpers if house.lower() not in enemy_names
    ]
    # TechLevel actions are House-scoped mission instructions. Player access
    # isolation may rewrite/remove them only when their trigger belongs to the
    # player or an opted-in helper. Enemy, story, and neutral actions must stay
    # byte-for-byte authored or AI powers/production chains can disappear.
    friendly_trigger_owners = set()
    for house in unique_in_order(
        list(player_controlled_houses(lines, records=records))
        + list(native_helpers)
    ):
        record = records.get(house, {})
        for identity in (
            house,
            str(house).removesuffix(' House'),
            record.get('country', ''),
            record.get('parent_country', ''),
        ):
            if str(identity or '').strip():
                friendly_trigger_owners.add(str(identity).strip().lower())
    preserved_ai_action_ids = {
        str(trigger_id).strip().lower()
        for trigger_id, trigger_value in source_triggers.items()
        if str(trigger_value).split(',', 1)[0].strip().lower()
        not in friendly_trigger_owners
    }
    # Native helper timing, scripts, and triggers stay intact. Compatible
    # TaskForce slots use buffed clones, while native unit IDs remain
    # buildable for dynamic AI requests outside those TaskForces.
    excluded_helper_names = {
        str(house).strip().lower()
        for house in MISSION_HELPER_BUFF_EXCLUDED_HOUSES.get(code, ())
    }
    reward_helpers = (
        tuple(
            house
            for house in native_helpers
            if house.lower() not in excluded_helper_names
        )
        if buff_allied_helpers
        else ()
    )
    country_safety_helpers = tuple(unique_in_order(
        list(reward_helpers)
        + [
            house for house in records
            if house.lower() == 'sellmcv house'
        ]
    ))
    enemy_country_ids = unique_in_order(
        records.get(house, {}).get('country') or house.replace(' House', '')
        for house in configured_enemies
    )
    missing_config = unique_in_order(missing_helpers + missing_enemies)
    if missing_config:
        self.append_log(
            f'{code} house config contains names absent from this map: '
            + ', '.join(missing_config)
            + '.',
            error=True,
        )
    if buff_allied_helpers and house_config['allies']:
        excluded_helpers = [
            house for house in native_helpers
            if house.lower() in excluded_helper_names
        ]
        if reward_helpers:
            self.append_log(
                f'{code} configured allied helper allowlist: '
                + ', '.join(reward_helpers)
                + '. Helper teams use buffed clones; native IDs remain '
                'buildable queue fallbacks.'
            )
        if excluded_helpers:
            self.append_log(
                f'{code} preserved authored helper identities: '
                + ', '.join(excluded_helpers)
                + '.'
            )
    earned_rewards = (
        self.launch_rewards_for_mission(code) if self.state else []
    )
    credit_bonus = starting_credit_bonus(earned_rewards)
    if credit_bonus:
        player_house = player_house_from_map(lines, records=records)
        house_values = section_value_map_preserve(lines, player_house)
        authored_credits = next(
            (
                value for key, value in house_values.items()
                if str(key).lower() == 'credits'
            ),
            '0',
        )
        try:
            authored_credit_units = int(str(authored_credits).strip())
        except (TypeError, ValueError):
            authored_credit_units = None
        if player_house and authored_credit_units is not None:
            # House Credits are stored in hundreds by the game/map format.
            merge_ini_section_values(lines, {
                player_house: {
                    'Credits': str(authored_credit_units + credit_bonus // 100),
                },
            })
            self.append_log(
                f'Applied +{credit_bonus:,} starting credits to {player_house} '
                f'for {code} (authored {authored_credit_units * 100:,}; '
                f'launch total {authored_credit_units * 100 + credit_bonus:,}).'
            )
        else:
            self.append_log(
                f'Could not apply +{credit_bonus:,} starting credits for {code}: '
                f'player house={player_house or "unresolved"}, '
                f'authored Credits={authored_credits!r}.',
                error=True,
            )
    access_report_active_rewards = list(earned_rewards)
    earned_access_tech_ids = unlocked_reward_tech_ids(earned_rewards)
    scripted_taskforce_requirements = (
        MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCE_ACCESS_REQUIREMENTS.get(
            code, {}
        )
    )
    scripted_player_buff_taskforces = {
        taskforce_id
        for taskforce_id in MISSION_SCRIPTED_PLAYER_BUFF_TASKFORCES.get(
            code, ()
        )
        if not scripted_taskforce_requirements.get(taskforce_id)
        or scripted_taskforce_requirements[taskforce_id].issubset(
            earned_access_tech_ids
        )
    }
    enemy_scaling_entries = (
        self.active_enemy_scaling_entries() if self.state else []
    )
    enemy_scaling_rewards = [
        entry['reward'] for entry in enemy_scaling_entries
    ]
    ai_reward_applications = []
    if share_basic_equivalent_buffs:
        # Resolve shared buffs against access already proven for this launch.
        # Standard includes current-house units plus foreign role mappings
        # behind exact physical factory prerequisites. Chaos contains only
        # independently earned identities; Arsenal contains only its selected
        # roster. Serialized rewards retain the other peer buffs for later,
        # but no locked peer can become a buildable/runtime clone merely from
        # sharing.
        earned_rewards = expand_equivalent_role_buffs(
            earned_rewards,
            enabled=True,
            allowed_unit_ids=mission_effective_tech_ids,
        )
        # Every downstream buff pass now receives explicit per-unit runtime
        # rewards. It must not infer access again from role equivalence.
        share_basic_equivalent_buffs = False
    power_aux_buildings = {}
    power_launch_inputs = list(earned_rewards)
    if self.active_reward_mode() not in {'Chaos', ARSENAL_MODE}:
        player_house = player_house_from_map(lines, records=records)
        player_family = country_family(records.get(player_house, {}))
        family_labels = {
            'allies': 'Allies',
            'soviets': 'Soviets',
            'epsilon': 'Epsilon',
            'foehn': 'Foehn',
        }
        player_faction = family_labels.get(
            player_family,
            normalize_faction(mission.get('side', '')),
        )
        faction_families = {
            label: family for family, label in family_labels.items()
        }
        installed_building_ids_upper = {
            str(item).upper() for item in installed_building_ids
        }
        gated_power_names = set()
        for reward in canonical_rewards(earned_rewards):
            if reward.get('kind') != 'superweapon':
                continue
            if reward.get('superweapon_ignore_foreign_tech_gate'):
                continue
            reward_factions = set(reward.get('factions') or ())
            if (
                not reward_factions
                or 'Neutral' in reward_factions
                or player_faction in reward_factions
            ):
                continue
            aux_buildings = unique_in_order(
                building_id
                for faction in reward_factions
                for family in (faction_families.get(faction),)
                if family
                for category_ids in PRODUCTION_BUILDINGS.get(
                    family, {}
                ).values()
                for building_id in sorted(category_ids)
                if str(building_id).upper() in installed_building_ids_upper
            )
            power_id = str(reward.get('superweapon') or '').upper()
            if power_id and aux_buildings:
                power_aux_buildings[power_id] = aux_buildings
                gated_power_names.add(reward_display_name(reward))
        if gated_power_names:
            self.append_log(
                'Gated foreign power rewards behind captured faction tech: '
                + ', '.join(sorted(gated_power_names))
                + '.'
            )
    launch_power_rewards = apply_power_buffs_to_unlock_rewards(
        power_launch_inputs,
        installed_rule_sections,
    )
    unsafe_static_provider_powers = {
        str(power_id).upper()
        for power_id in MISSION_UNSAFE_STATIC_PROVIDER_SUPERWEAPON_IDS.get(
            code, ()
        )
    }
    if unsafe_static_provider_powers:
        deferred_power_rewards = [
            reward
            for reward in canonical_rewards(launch_power_rewards)
            if str(reward.get('superweapon') or '').upper()
            in unsafe_static_provider_powers
        ]
        launch_power_rewards = [
            reward
            for reward in canonical_rewards(launch_power_rewards)
            if str(reward.get('superweapon') or '').upper()
            not in unsafe_static_provider_powers
        ]
        if deferred_power_rewards:
            self.append_log(
                f'Deferred unsafe physical-provider powers for {code}: '
                + ', '.join(
                    reward_display_name(reward)
                    for reward in deferred_power_rewards
                )
                + '. Earned access remains active in other missions.'
            )
    power_player_clone_reference_fields = {}
    power_player_clone_value_overrides = {}
    for reward in canonical_rewards(launch_power_rewards):
        for field, unit_ids in reward.get(
            'superweapon_player_clone_reference_fields', {}
        ).items():
            power_player_clone_reference_fields.setdefault(field, []).extend(
                unit_ids
            )
        for unit_id, values in reward.get(
            'superweapon_player_clone_value_overrides', {}
        ).items():
            power_player_clone_value_overrides.setdefault(
                unit_id, {}
            ).update(values)
    power_player_clone_reference_fields = {
        field: unique_in_order(unit_ids)
        for field, unit_ids in power_player_clone_reference_fields.items()
    }
    expected_generated_techno_types = {
        list_section: []
        for list_section in dict.fromkeys(TECHNO_TYPE_LISTS.values())
    }

    def remember_generated_techno_types(sections):
        for list_section, type_ids in expected_generated_techno_types.items():
            type_ids.extend((sections.get(list_section) or {}).values())

    deployed_sidebar_assets = deploy_superweapon_sidebar_assets(
        canonical_rewards(launch_power_rewards)
    )
    if deployed_sidebar_assets:
        self.append_log(
            'Deployed custom superpower sidebar image(s): '
            + ', '.join(path.name for path in deployed_sidebar_assets)
            + '.'
        )
    configured_power_houses = mission_player_power_houses(code)
    power_house_names = configured_power_houses or (
        player_house_from_map(lines, records=records),
    )
    power_houses = unique_in_order(
        records.get(power_house, {}).get('country')
        or power_house.replace(' House', '')
        for power_house in power_house_names
        if power_house
    )
    if not power_houses:
        power_houses = [player_country_from_map(lines)]
    mission_power_techno_clone_overrides = {
        power_id: {
            source_id: {
                **clone_spec,
                **(
                    {'values': dict(clone_spec.get('values') or {})}
                    if 'values' in clone_spec
                    else {}
                ),
            }
            for source_id, clone_spec in clone_specs.items()
        }
        for power_id, clone_specs in (
            MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES.get(
                code, {}
            )
        ).items()
    }
    time_freeze_immune_ids = MISSION_TIME_FREEZE_IMMUNE_TECHNO_IDS.get(
        code, ()
    )
    time_freeze_immune_armors = []
    time_freeze_protected_types = []
    if time_freeze_immune_ids:
        installed_by_lower = {
            str(section).lower(): values
            for section, values in installed_rule_sections.items()
        }
        map_by_lower = {
            str(section).lower(): values
            for section, values in native_map_sections.items()
        }
        for immunity_index, unit_id in enumerate(time_freeze_immune_ids):
            armor = ''
            for values in (
                map_by_lower.get(unit_id.lower(), {}),
                installed_by_lower.get(unit_id.lower(), {}),
            ):
                armor = next(
                    (
                        str(value).strip()
                        for key, value in values.items()
                        if str(key).lower() == 'armor'
                    ),
                    '',
                )
                if armor:
                    break
            if armor:
                # Ares custom armor aliases inherit every ordinary warhead's
                # verses from the original armor. Give only this exact
                # mission TechnoType a private alias, then make only the
                # private Time Freeze warhead ineffective against it. This
                # avoids making every defense_b building or moral infantry in
                # the mission immune merely because one scripted object is.
                immune_armor = f'MORTF{code}{immunity_index}'
                rule_sections.setdefault('ArmorTypes', {})[
                    immune_armor
                ] = armor
                rule_sections.setdefault(unit_id, {})['Armor'] = immune_armor
                time_freeze_immune_armors.append(immune_armor)
                time_freeze_protected_types.append(
                    f'{unit_id} ({immune_armor} inherits {armor})'
                )
        if time_freeze_immune_armors:
            warhead_spec = mission_power_techno_clone_overrides.setdefault(
                'TimeFreezeSpecial', {}
            ).setdefault('TimeFreezeWH', {
                'clone': 'MORTimeFreezeWH',
                'list': 'Warheads',
            })
            warhead_values = warhead_spec.setdefault('values', {})
            for armor in unique_in_order(time_freeze_immune_armors):
                warhead_values[f'Versus.{armor}'] = '0%'
            self.append_log(
                'Protected exact mission-critical Time Freeze targets: '
                + ', '.join(time_freeze_protected_types)
                + '.'
            )
    (
        cloned_power_rules,
        superweapon_actions,
        _cloned_power_names,
        startup_power_buildings,
        static_startup_power_buildings,
        missing_power_sources,
    ) = cloned_superweapon_plan(
        lines,
        launch_power_rewards,
        installed_superweapon_types,
        installed_rule_sections,
        superweapon_techno_clone_overrides=(
            mission_power_techno_clone_overrides
        ),
        superweapon_required_houses=power_houses,
        superweapon_aux_buildings=power_aux_buildings,
    )
    remember_generated_techno_types(cloned_power_rules)
    for section, values in cloned_power_rules.items():
        rule_sections.setdefault(section, {}).update(values)
    # UnitDelivery and DropPod powers are factories too: their payload must use
    # the same complete, health-validated player clone as production and
    # reinforcements. Compact payload clone IDs also keep repeated type lists
    # inside the engine's 511-byte INI line buffer.
    delivery_clone_ids = unique_in_order(
        [
            unit_id
            for reward in canonical_rewards(launch_power_rewards)
            for unit_id in reward.get(
                'superweapon_delivery_player_clone_ids', ()
            )
        ]
        + [
            type_id.strip().upper()
            for values in cloned_power_rules.values()
            for key, value in values.items()
            if str(key).lower() in {
                'deliver.types', 'droppod.types', 'paradrop.types',
            }
            for type_id in str(value or '').split(',')
            if type_id.strip().upper() in BUFF_TARGETS
        ]
    )
    power_reference_clone_ids = unique_in_order(
        unit_id
        for unit_ids in power_player_clone_reference_fields.values()
        for unit_id in unit_ids
    )
    building_bound_power_names = [
        reward_display_name(reward)
        for reward in canonical_rewards(launch_power_rewards)
        if reward.get('kind') == 'superweapon'
        and reward.get('superweapon_grant_buildings')
    ]
    if building_bound_power_names:
        self.append_log(
            'Prepared isolated Barracks-bound power clone(s): '
            + ', '.join(building_bound_power_names)
            + '. These powers are not granted through map-start action 34.'
        )
    if self.randomized_tech_ids():
        safe_owners = ','.join(
            safe_build_countries(lines, records, ())
        )
        denied_owners = ','.join(enemy_country_ids) if enemy_country_ids else 'none'
        for section in self.randomized_tech_ids():
            values = owned_clone_rule_overlays.get(section)
            if not values:
                continue
            values['Owner'] = safe_owners
            values['RequiredHouses'] = safe_owners
            values['ForbiddenHouses'] = denied_owners
    # Generic randomized ownership must not erase mission-authored recovery
    # access such as Power Hunger's native Burillo.
    for section, values in MISSION_REQUIRED_ACCESS_RULES.get(code, {}).items():
        if (
            section.upper() in owned_clone_ids
            and section.upper() not in native_techno_exclusions
        ):
            owned_clone_rule_overlays.setdefault(section.upper(), {}).update(values)
        else:
            rule_sections.setdefault(section, {}).update(values)

    # Hide native cameos from player countries without rewriting AI production
    # fields. Unregistered MORP sections enforce unearned access; registered
    # MORP sections carry earned/mission production rules.
    player_native_exclusions = safe_build_countries(lines, records, ())
    player_factory_exclusions = unique_in_order(
        list(player_native_exclusions)
        + [
            str(records.get(house_name, {}).get('country') or '').strip()
            for house_name in mission_player_production_houses(code)
            if str(records.get(house_name, {}).get('country') or '').strip()
        ]
    )
    isolated_native_ids = set(owned_clone_rule_overlays)
    isolated_native_ids.update(
        section.upper()
        for section in self.randomized_tech_ids()
        if section.upper() in owned_clone_ids
    )
    installed_names = {
        str(section).lower(): section for section in installed_rule_sections
    }
    native_names = {
        str(section).lower(): section for section in native_map_sections
    }
    # Story references alone do not justify leaving a native player cameo
    # buildable. Many campaign TaskForces belong only to enemies/helpers; the
    # old blanket exemption leaked those unbuffed originals beside the player
    # clone whenever a transferred/captured factory exposed their roster.
    # Preserve access only for types actually used by a player-controlled
    # runtime house. Reviewed player TaskForces that are safely rewritten to
    # clones do not need that exemption either.
    usage_index = build_unit_usage_index(lines)

    controlled_player_usage_names = {
        str(name).lower()
        for name in player_controlled_houses(lines, records=records)
        if name
    }
    player_usage_names = {
        str(name).lower()
        for name in player_native_exclusions
        if name
    } | set(controlled_player_usage_names)
    for house_name, house_values in records.items():
        if not house_values.get('player'):
            continue
        controlled_player_usage_names.add(str(house_name).lower())
        controlled_player_usage_names.add(
            str(house_name).removesuffix(' House').lower()
        )
        if house_values.get('country'):
            controlled_player_usage_names.add(
                str(house_values['country']).lower()
            )
        if house_values.get('parent_country'):
            controlled_player_usage_names.add(
                str(house_values['parent_country']).lower()
            )
    player_usage_names.update(controlled_player_usage_names)
    safe_player_clone_unit_ids = set()
    native_sections_by_lower = {
        str(section).lower(): values
        for section, values in native_map_sections.items()
    }
    for taskforce_id in scripted_player_buff_taskforces:
        for value in native_sections_by_lower.get(
            str(taskforce_id).lower(), {}
        ).values():
            tokens = [token.strip() for token in str(value).split(',')]
            if (
                len(tokens) >= 2
                and tokens[0].isdigit()
                and tokens[1]
                and tokens[1].lower() not in {'none', '<none>'}
            ):
                safe_player_clone_unit_ids.add(tokens[1].upper())
    player_runtime_unit_ids = {
        unit_id
        for unit_id, usage_houses in usage_index.items()
        if {
            str(house).lower()
            for house in usage_houses
        }.intersection(player_usage_names)
    }
    player_story_unit_ids = {
        unit_id
        for unit_id in scripted_story_unit_ids
        if {
            str(house).lower()
            for house in usage_index.get(unit_id, ())
        }.intersection(player_usage_names)
    }
    # Native TechnoTypes used by any non-player placement or TeamType must
    # remain directly spawnable. Ares applies negative prerequisites while
    # assembling campaign teams and ParaDrop payloads even when the owning AI
    # House does not own the player's hidden gate. Exact player
    # ForbiddenHouses still hides these originals from the human sidebar.
    non_player_runtime_unit_ids = {
        unit_id
        for unit_id, usage_houses in usage_index.items()
        if any(
            str(house or '').strip().lower() not in player_usage_names
            for house in usage_houses
        )
    }
    # Static map placements ignore production prerequisites, while campaign
    # TeamType creation does not.  Keep this narrower index so native miner
    # cameos can be hidden when their only non-player use is an authored map
    # placement, without breaking an AI/scripted miner TaskForce.
    non_player_taskforce_unit_ids = set()
    for taskforce_id, usage_houses in taskforce_usage_houses(
        lines,
        sections=native_map_sections,
    ).items():
        if not any(
            str(house or '').strip().lower() not in player_usage_names
            for house in usage_houses
        ):
            continue
        for value in native_sections_by_lower.get(
            str(taskforce_id).lower(), {}
        ).values():
            tokens = [token.strip() for token in str(value).split(',')]
            if (
                len(tokens) >= 2
                and tokens[0].isdigit()
                and tokens[1]
                and tokens[1].lower() not in {'none', '<none>'}
            ):
                non_player_taskforce_unit_ids.add(tokens[1].upper())
    # Droppod TeamTypes are stricter than ordinary production. The engine
    # can refuse Action 7 before creating the transport when a payload's
    # native type receives any player-isolation overlay, even one aimed at a
    # different country. Preserve only these authored non-player payload
    # identities. Player/helper placements and teams must still follow their
    # MORP clone rewrites; restoring every non-player-used native type erases
    # that clone-aware split and breaks exact cloned-unit mission checks.
    non_player_droppod_payload_ids = set()

    def native_value(values, key, default=''):
        wanted = str(key).lower()
        return next(
            (
                value
                for name, value in (values or {}).items()
                if str(name).lower() == wanted
            ),
            default,
        )

    for team_id in native_map_sections.get('TeamTypes', {}).values():
        team_values = native_map_sections.get(str(team_id), {})
        if str(native_value(team_values, 'Droppod')).lower() != 'yes':
            continue
        taskforce_id = str(native_value(team_values, 'TaskForce')).strip()
        for key, value in native_map_sections.get(taskforce_id, {}).items():
            tokens = [token.strip() for token in str(value).split(',')]
            if (
                str(key).isdigit()
                and len(tokens) >= 2
                and tokens[0].isdigit()
                and tokens[1]
                and tokens[1].lower() not in {'none', '<none>'}
            ):
                non_player_droppod_payload_ids.add(tokens[1].upper())
    preserved_native_access_ids = (
        set(native_techno_exclusions)
        | (player_runtime_unit_ids - safe_player_clone_unit_ids)
        # Campaign-authored Engineer placements/teams deliberately stay on
        # their native identity so vehicle boarding, CanDrive behavior, and
        # exact mission triggers use the engine-reviewed type. The hidden
        # negative prerequisite still suppresses its duplicate player cameo.
        | set(ENGINEER_UNIT_IDS)
    )
    for source_id in sorted(
        isolated_native_ids
        - preserved_native_access_ids
        - refinery_free_unit_ids
        - refinery_building_ids
    ):
        installed_source_values = installed_rule_sections.get(
            installed_names.get(source_id.lower()), {}
        )
        native_source_values = native_map_sections.get(
            native_names.get(source_id.lower()), {}
        )

        def forbidden_value(values, missing=None):
            return next(
                (
                    value
                    for key, value in values.items()
                    if str(key).lower() == 'forbiddenhouses'
                ),
                missing,
            )

        # A map-local value, including `none`, intentionally overrides the
        # installed restriction. Unioning both resurrected restrictions that
        # campaign authors explicitly cleared and blocked scripted AI teams.
        effective_forbidden = forbidden_value(
            native_source_values,
            forbidden_value(installed_source_values, ''),
        )
        forbidden = [
            item.strip()
            for item in str(effective_forbidden or '').split(',')
            if item.strip().lower() not in {'', 'none', '<none>'}
        ]
        forbidden = unique_in_order(forbidden + list(player_native_exclusions))
        if forbidden:
            rule_sections.setdefault(source_id, {})['ForbiddenHouses'] = ','.join(
                forbidden
            )
    if missing_power_sources:
        self.append_log(
            'Skipped power clone(s) because installed source rules were unavailable: '
            + ', '.join(sorted(set(missing_power_sources)))
            + '.',
            error=True,
        )
    assistance_unit_ids = []
    mission_buff_unit_ids = []
    if self.state:
        mission_buff_unit_ids = mission_assistance_unit_ids(
            lines,
            unlocked_unit_ids=mission_effective_tech_ids,
            additional_unit_ids=fallback_tech_ids,
            randomized_access=self.randomize_unit_access_enabled(),
            fallback_faction=normalize_faction(mission.get('side', '')),
            configured_helper_houses=reward_helpers,
        )
    if self.state and self.failure_assistance_enabled():
        assistance_unit_ids = mission_buff_unit_ids
        self.cache_mission_assistance_units(code, assistance_unit_ids)
    if rule_sections:
        merge_ini_section_values(lines, rule_sections)
        self.append_log(f'Injected {len(rule_sections)} map rule section(s) into {scenario}.')

    (
        enemy_country_rules,
        scaled_enemy_countries,
        skipped_enemy_countries,
        enemy_country_applications,
    ) = (
        enemy_country_buff_rules(
            lines,
            scaled_enemy_houses,
            enemy_scaling_rewards,
        )
    )
    if enemy_country_rules:
        merge_ini_section_values(lines, enemy_country_rules)
        self.append_log(
            'Applied AI stat bonuses to hostile AI countries: '
            + ', '.join(scaled_enemy_countries)
            + '.'
        )
        applied_country_names = {
            str(country).lower() for country in scaled_enemy_countries
        }
        stat_houses = [
            house for house in scaled_enemy_houses
            if str(
                records.get(house, {}).get('country')
                or house.replace(' House', '')
            ).lower() in applied_country_names
        ]
        entries_by_effect = {}
        for entry in enemy_scaling_entries:
            reward = entry['reward']
            if reward.get('enemy_effect') not in {
                'armor', 'cost', 'production',
            }:
                continue
            effect_id = str(reward.get('enemy_effect_id') or '')
            if effect_id:
                entries_by_effect.setdefault(effect_id, []).append(entry)
        for application in enemy_country_applications:
            effect_id = application['effect_id']
            effect_entries = entries_by_effect.get(effect_id, ())
            if not effect_entries:
                continue
            reward = effect_entries[0]['reward']
            country = str(application['country'])
            sources = unique_in_order(
                entry['source'] for entry in effect_entries
            )
            earned_from = unique_in_order(
                entry['earned_from'] for entry in effect_entries
            )
            for house in stat_houses:
                house_country = str(
                    records.get(house, {}).get('country')
                    or house.replace(' House', '')
                )
                if house_country.lower() != country.lower():
                    continue
                current_stacks = application['current_stacks']
                ai_reward_applications.append({
                    'mission': code,
                    'reward_name': reward.get('name', effect_id),
                    'effect_id': effect_id,
                    'source': ' + '.join(sources),
                    'earned_from': '; '.join(earned_from),
                    'house': house,
                    'country': country,
                    'category': application['category'],
                    'target': (
                        f'{country} / {application["category"]}'
                    ),
                    'effect': enemy_effect_text(
                        reward,
                        current_stacks,
                        application['base_engine_value'],
                    ),
                    'per_stack_value': application['per_stack_value'],
                    'current_stacks': current_stacks,
                    'maximum_stacks': application['maximum_stacks'],
                    'engine_field': application['engine_field'],
                    'base_engine_value': application['base_engine_value'],
                    'final_engine_value': application['final_engine_value'],
                    'displayed_percentage': (
                        application['displayed_percentage']
                    ),
                })
    if skipped_enemy_countries:
        self.append_log(
            'Skipped unsafe enemy countries: '
            + '; '.join(
                (
                    f'{country} has duplicate CountryType sections'
                    if houses == ['duplicate CountryType sections']
                    else f'{country} shared with {", ".join(houses)}'
                )
                for country, houses in skipped_enemy_countries
            )
            + '.'
        )
        skip_reasons = {
            country: (
                'duplicate CountryType sections'
                if houses == ['duplicate CountryType sections']
                else 'CountryType is shared with unsafe House(s): '
                + ', '.join(houses)
            )
            for country, houses in skipped_enemy_countries
        }
        for reward in enemy_scaling_rewards:
            if reward.get('enemy_effect') not in {
                'armor', 'cost', 'production',
            }:
                continue
            for country, reason in skip_reasons.items():
                self.append_log(
                    f'Skipped {reward_display_name(reward)} for {code} '
                    f'country {country}: {reason}.',
                    error=True,
                )
    if phase_enemy_houses and enemy_scaling_rewards:
        self.append_log(
            'Skipped AI rewards for currently human/allied phase houses: '
            + ', '.join(phase_enemy_houses)
            + '.'
        )
    if enemy_scaling_rewards and not scaled_enemy_houses:
        skip_summary = '; '.join(
            f'{house}: {reason}'
            for house, reason in discovered_enemy_skips.items()
        )
        for reward in enemy_scaling_rewards:
            self.append_log(
                f'Skipped {reward_display_name(reward)} for {code}: '
                'no safe active hostile AI House was found.'
                + (f' House audit: {skip_summary}.' if skip_summary else ''),
                error=True,
            )

    enemy_power_rewards = enemy_power_launch_rewards(enemy_scaling_rewards)
    (
        enemy_superweapon_actions,
        enemy_power_names,
        missing_existing_enemy_powers,
    ) = enemy_existing_power_grant_plan(
        lines,
        enemy_scaling_rewards,
        installed_superweapon_types,
    )
    enemy_rewards_by_power = {
        str(reward.get('superweapon') or '').strip().lower(): reward
        for reward in enemy_scaling_rewards
        if reward.get('enemy_effect') == 'power'
        and str(reward.get('superweapon') or '').strip()
    }
    enemy_power_grants = [
        {
            'action': action,
            'name': name,
            'reward': enemy_rewards_by_power.get(str(name).lower(), {}),
        }
        for action, name in zip(
            enemy_superweapon_actions, enemy_power_names, strict=True
        )
    ]
    existing_enemy_power_rules = enemy_existing_power_rule_overrides(
        enemy_scaling_rewards,
        enemy_power_names,
    )
    if existing_enemy_power_rules:
        merge_ini_section_values(lines, existing_enemy_power_rules)
    enemy_startup_power_buildings = []
    enemy_static_power_buildings = []
    existing_power_ids = {
        str(power_id).upper() for power_id in enemy_power_names
    }
    prepared_enemy_power_effect_ids = [
        str(reward.get('enemy_effect_id') or '')
        for reward in enemy_scaling_rewards
        if reward.get('enemy_use_existing_power')
        and str(reward.get('superweapon') or '').upper()
        in existing_power_ids
        and str(reward.get('enemy_effect_id') or '')
    ]
    if missing_existing_enemy_powers:
        self.append_log(
            'Skipped default enemy AI power source(s): '
            + ', '.join(sorted(set(missing_existing_enemy_powers)))
            + '.',
            error=True,
        )
    if enemy_power_rewards and scaled_enemy_houses:
        enemy_power_countries = unique_in_order(
            records.get(house, {}).get('country')
            or house.replace(' House', '')
            for house in scaled_enemy_houses
        )
        (
            enemy_power_rules,
            cloned_enemy_superweapon_actions,
            cloned_enemy_power_names,
            enemy_startup_power_buildings,
            enemy_static_power_buildings,
            missing_enemy_power_sources,
        ) = cloned_superweapon_plan(
            lines,
            enemy_power_rewards,
            installed_superweapon_types,
            installed_rule_sections,
            superweapon_required_houses=enemy_power_countries,
            allow_player=False,
            allow_ai=True,
            force_required_houses=True,
        )
        enemy_superweapon_actions.extend(cloned_enemy_superweapon_actions)
        enemy_power_names.extend(cloned_enemy_power_names)
        if missing_enemy_power_sources:
            self.append_log(
                'Skipped enemy AI power source(s): '
                + ', '.join(sorted(set(missing_enemy_power_sources)))
                + '.',
                error=True,
            )
        missing_enemy_power_ids = {
            str(power_id).upper()
            for power_id in missing_enemy_power_sources
        }
        available_enemy_power_rewards = [
            reward for reward in enemy_power_rewards
            if str(reward.get('superweapon') or '').upper()
            not in missing_enemy_power_ids
        ]
        if not (
            len(available_enemy_power_rewards)
            == len(cloned_enemy_superweapon_actions)
            == len(cloned_enemy_power_names)
        ):
            raise ValueError(
                'Enemy AI power clone grants lost source-order alignment.'
            )
        enemy_power_grants.extend(
            {
                'action': action,
                'name': name,
                'reward': reward,
            }
            for reward, action, name in zip(
                available_enemy_power_rewards,
                cloned_enemy_superweapon_actions,
                cloned_enemy_power_names,
                strict=True,
            )
        )
        prepared_enemy_power_effect_ids.extend([
            str(reward.get('enemy_effect_id') or '')
            for reward in enemy_power_rewards
            if str(reward.get('superweapon') or '').upper()
            not in missing_enemy_power_ids
            and str(reward.get('enemy_effect_id') or '')
        ])
        for clone_name in cloned_enemy_power_names:
            values = enemy_power_rules.get(clone_name, {})
            lowered = {
                str(key).lower(): str(value).lower()
                for key, value in values.items()
            }
            if (
                lowered.get('sw.allowai') != 'yes'
                or lowered.get('sw.allowplayer') != 'no'
                or lowered.get('sw.aitargeting', 'none') in {'', 'none'}
            ):
                raise ValueError(
                    f'Enemy power {clone_name} is not AI-usable: '
                    'requires SW.AllowAI=yes, SW.AllowPlayer=no, and '
                    'non-None SW.AITargeting.'
                )
        remember_generated_techno_types(enemy_power_rules)
        if enemy_power_rules:
            merge_ini_section_values(lines, enemy_power_rules)

    generation_config = self.config.get('generation', {})
    registered_techno_categories = {}
    for category, list_section in TECHNO_TYPE_LISTS.items():
        type_ids = list(installed_rule_sections.get(list_section, {}).values())
        type_ids.extend(section_value_map_preserve(lines, list_section).values())
        for type_id in type_ids:
            if str(type_id).strip():
                registered_techno_categories[str(type_id).strip().upper()] = category
    experimental_house_buffs = bool(generation_config.get('experimental_house_buffs', False))
    safe_player_country_buffs = bool(generation_config.get('safe_player_country_buffs', True))
    require_unlocked_access_for_buffs = self.randomize_unit_access_enabled()
    buff_access_tech_ids = set(fallback_tech_ids) | set(mission_buff_unit_ids)
    # Power-only payloads have no production-access reward. Owning their power
    # is their access proof, so their earned unit/defense buffs stay active.
    buff_access_tech_ids.update(delivery_clone_ids)
    if self.state and experimental_house_buffs:
        player_house, house_buffs = clone_player_country_for_house_buffs(
            lines,
            earned_rewards,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            excluded_buff_types=direct_only_country_buff_types,
            registered_techno_categories=registered_techno_categories,
        )
        if house_buffs:
            buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
            self.append_log(f'Applied trigger-safe player-country buffs to {player_house}: {buff_summary}')
    elif self.state and safe_player_country_buffs:
        player_house, player_country, house_rule_sections, shared_houses, buffed_allies, skipped_allies = player_country_buff_rules(
            lines,
            earned_rewards,
            configured_helper_houses=country_safety_helpers,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            excluded_player_houses=excluded_player_houses,
            excluded_buff_types=direct_only_country_buff_types,
            registered_techno_categories=registered_techno_categories,
        )
        if house_rule_sections:
            merge_ini_section_values(lines, house_rule_sections)
            house_buffs = next(iter(house_rule_sections.values()))
            buff_summary = ', '.join(f'{key}={value}' for key, value in sorted(house_buffs.items()))
            shared_note = f' Shared country houses: {", ".join(shared_houses)}.' if shared_houses else ''
            helper_note = f' Allied player/helper houses buffed: {", ".join(buffed_allies)}.' if buffed_allies else ''
            skipped_note = f' Allied player/helper houses skipped: {", ".join(skipped_allies)}.' if skipped_allies else ''
            if player_country in house_rule_sections:
                lead = f'Applied map-local player-country buffs for {player_house}/{player_country}'
            else:
                lead = f'Skipped shared player country {player_house}/{player_country}; applied safe allied country buffs'
            self.append_log(f'{lead}: {buff_summary}.{shared_note}{helper_note}{skipped_note}')
        elif shared_houses:
            self.append_log(
                f'Skipped player-country buffs for {player_house}/{player_country}: '
                f'non-player house(s) share that country ({", ".join(shared_houses)}).'
            )
    elif self.state:
        pending_house_buffs = stacked_house_buff_values(
            earned_rewards,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
        )
        if pending_house_buffs:
            self.append_log(
                'Experimental player-house buffs are disabled for mission stability; '
                'earned buff rewards are tracked but not injected into this map.'
            )

    assistance_stacks = self.mission_failure_stack(code)
    assistance_direct_rewards = []
    production_gate_rules = {}
    if self.failure_assistance_enabled() and assistance_stacks:
        assistance_rules, assisted_houses, skipped_assistance_countries = mission_assistance_buff_rules(
            lines,
            assistance_stacks,
            configured_helper_houses=reward_helpers,
            excluded_player_houses=excluded_player_houses,
        )
        if assisted_houses:
            if assistance_rules:
                merge_ini_section_values(lines, assistance_rules)
            skip_note = ''
            if skipped_assistance_countries:
                skip_note = ' Country-level bonuses skipped where enemies share the country: ' + ', '.join(
                    f'{country} ({", ".join(shared)})'
                    for country, _, shared in skipped_assistance_countries
                ) + '.'
            self.append_log(
                f'Applied {assistance_stacks} retry assistance stack(s) to {code} for '
                f'{", ".join(assisted_houses)} across {len(assistance_unit_ids)} currently '
                f'accessible or mission-provided unit type(s).{skip_note}'
            )
            # Direct health/damage/range rewards still pass through the
            # global type/weapon ownership guard. If the player's country is
            # one of the skipped shared countries, force category-compatible
            # assistance onto isolated clones as well.
            assistance_direct_rewards = mission_assistance_direct_rewards(
                assistance_unit_ids,
                assistance_stacks,
                include_house_scoped=(
                    player_country_from_map(lines).lower()
                    in {
                        str(country).lower()
                        for country, _houses, _shared
                        in skipped_assistance_countries
                    }
                ),
            )
        else:
            self.append_log(
                f'Could not find a player house for {code}; retry assistance was not injected.',
                error=True,
            )

    if self.state:
        guarded_rewards = list(earned_rewards)
        guarded_rewards.extend(assistance_direct_rewards)
        active_power_ids = {
            str(reward.get('superweapon') or '').upper()
            for reward in canonical_rewards(launch_power_rewards)
            if reward.get('kind') == 'superweapon'
        }
        current_player_house = player_house_from_map(lines, records=records)
        current_player_family = country_family(
            records.get(current_player_house, {})
        )
        player_faction_label = {
            'allies': 'Allies',
            'soviets': 'Soviets',
            'epsilon': 'Epsilon',
            'foehn': 'Foehn',
        }.get(
            current_player_family,
            normalize_faction(mission.get('side', '')),
        )
        guarded_rewards = equivalent_payload_unit_buff_rewards(
            guarded_rewards,
            active_power_ids,
            (
                set(mission_effective_tech_ids)
                | set(fallback_tech_ids)
                | set(mission_buff_unit_ids)
            ),
            player_faction_label,
        )
        buildable_clone_ids = set(fallback_tech_ids)
        buildable_clone_ids.update(mission_effective_tech_ids)
        # Always-available Engineers/transports are deliberately absent from
        # randomized access rewards, but earned buffs still need their owned
        # player identity. Without adding currently usable essentials here,
        # Chaos production buffs had no clone on which to write
        # BuildTimeMultiplier and silently disappeared.
        buildable_clone_ids.update(
            set(mission_buff_unit_ids).intersection(
                set(ENGINEER_UNIT_IDS) | set(AMPHIBIOUS_TRANSPORT_UNIT_IDS)
            )
        )
        if not require_unlocked_access_for_buffs:
            buildable_clone_ids.update(
                unit_id
                for unit_id, target in BUFF_TARGETS.items()
                if target.get('category') in {
                    'infantry', 'units', 'aircraft', 'defenses',
                }
                and not target.get('power_payload_only')
            )
        helper_autobuild = (
            helper_ai_autobuild_plan(
                lines,
                reward_helpers,
                buildable_clone_ids,
                guarded_rewards,
                installed_rule_sections,
                native_map_sections=native_map_sections,
                allow_cross_faction=chaos_unit_specific_buffs,
            )
            if reward_helpers
            else {'variants': [], 'support': {}}
        )
        player_build_owner_ids = safe_build_countries(lines, records, ())
        (
            clone_rule_sections,
            _cloned_source_unit_ids,
            clone_handled,
            cloned_unit_names,
            clone_warnings,
        ) = player_unit_clone_rules(
            lines,
            guarded_rewards,
            installed_rule_sections,
            native_ai_helper_houses=native_helpers,
            buffed_helper_houses=reward_helpers,
            native_map_sections=native_map_sections,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            buildable_tech_ids=buildable_clone_ids,
            build_owner_ids=player_build_owner_ids,
            helper_autobuild_support=helper_autobuild.get('support'),
            forced_buildable_clone_ids=(
                fallback_tech_ids.intersection(ENGINEER_UNIT_IDS)
            ),
            forced_isolated_clone_ids=unique_in_order(
                delivery_clone_ids
                + power_reference_clone_ids
                + sorted(safe_player_clone_unit_ids)
            ),
            forced_compact_clone_ids=delivery_clone_ids,
            unlimited_build_limit_unit_ids=(
                mission_buff_unit_ids
                if self.active_reward_settings().get('unlimited_hero_units', False)
                else ()
            ),
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            native_trigger_reference_ids=(
                MISSION_NATIVE_TRIGGER_REFERENCE_IDS.get(code, ())
            ),
            objective_clone_event_refs=(
                MISSION_OBJECTIVE_CLONE_EVENT_REFS.get(code, {})
            ),
            scripted_player_buff_taskforces=(
                scripted_player_buff_taskforces
            ),
            excluded_unit_ids=(
                set(native_techno_exclusions)
                | (refinery_free_unit_ids - set(fallback_tech_ids))
            ),
            build_only_excluded_unit_ids=native_build_only_clone_ids,
            excluded_player_houses=excluded_player_houses,
            owned_clone_ids=owned_clone_ids,
            owned_clone_templates=owned_clone_templates,
            owned_clone_rule_overlays=owned_clone_rule_overlays,
            force_direct_house_scoped_fallback_types=(
                direct_only_country_buff_types
            ),
        )
        mission_unlock_clone_replacements = {
            source_id: str(clone_handled.get(source_id, {}).get('clone_id') or '')
            for source_id in MISSION_NATIVE_TECH_UNLOCK_IDS.get(code, ())
            if str(clone_handled.get(source_id, {}).get('clone_id') or '')
        }
        for source_id in sorted(delayed_native_unlock_ids):
            clone_id = mission_unlock_clone_replacements.get(source_id)
            if not clone_id or clone_id not in clone_rule_sections:
                self.append_log(
                    f'Could not prepare delayed player clone for native unlock {source_id}.',
                    error=True,
                )
                continue
            clone_rule_sections[clone_id]['TechLevel'] = LOCKED_TECH_LEVEL

        actual_clone_source_ids = {
            str(source_id).upper()
            for source_id, details in clone_handled.items()
            if str((details or {}).get('clone_id') or '').strip()
        }
        build_only_clone_source_ids = {
            str(source_id).upper()
            for source_id, details in clone_handled.items()
            if bool((details or {}).get('build_only'))
        }
        production_alias_ids = {
            alias_id
            for alias_id, source_id in MISSION_NATIVE_PRODUCTION_ALIASES.get(
                code, {}
            ).items()
            if source_id in actual_clone_source_ids
        }
        production_gate_source_ids = (
            (set(isolated_native_ids) - set(preserved_native_access_ids))
            | actual_clone_source_ids
            | production_alias_ids
            | set(MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS.get(code, ()))
            | {
                str(unit_id).upper()
                for unit_id in self.randomized_tech_ids()
                if str(unit_id).upper() in registered_techno_categories
            }
        ) - (
            set(MISSION_NATIVE_PRODUCTION_GATE_EXCLUSIONS.get(code, ()))
            | refinery_building_ids
        )
        production_gate_rules = original_player_production_gate_rules(
            lines,
            installed_rule_sections,
            production_gate_source_ids,
            existing_rule_sections=clone_rule_sections,
            native_sections=native_map_sections,
            negative_gate_exclusions=(
                non_player_droppod_payload_ids
                | runtime_identity_preserve_ids
            ) - set(ENGINEER_UNIT_IDS),
            native_taskforce_ids=(
                non_player_taskforce_unit_ids - set(ENGINEER_UNIT_IDS)
            ),
            # A mission can hand the player a friendly barracks whose initial
            # map owner is an allied helper House. FactoryOwners.Forbidden
            # then mistakes that barracks for captured enemy technology and
            # exposes the native Engineer beside its player clone. Engineers
            # always use the exact-player-House negative gate instead; this
            # leaves authored placements and scripted creation intact.
            factory_owner_only_ids=(
                (
                    build_only_clone_source_ids
                    | (player_runtime_unit_ids - safe_player_clone_unit_ids)
                )
                - non_player_taskforce_unit_ids
                - set(ENGINEER_UNIT_IDS)
            ),
            player_runtime_ids=(
                player_runtime_unit_ids - safe_player_clone_unit_ids
            ),
            player_forbidden_houses=player_native_exclusions,
            player_factory_forbidden_houses=player_factory_exclusions,
        )
        if production_alias_ids:
            aliases = MISSION_NATIVE_PRODUCTION_ALIASES.get(code, {})
            self.append_log(
                'Blocked mission production aliases duplicating player '
                'clones: '
                + ', '.join(
                    f'{alias_id} -> {aliases[alias_id]}'
                    for alias_id in sorted(production_alias_ids)
                )
                + '.'
            )
        # Every registered player clone gets one final native-source exclusion
        # here, after clone discovery. Earlier passes cannot know the complete
        # map-local clone set and leaked captured-factory originals beside E1,
        # GGI, miners, and other player copies.
        # A campaign commonly has several concrete runtime HouseTypes. A
        # HouseType's ParentCountry grants roster ancestry, but does not make
        # the child House equal to its parent for ForbiddenHouses. For every
        # non-player runtime consumer, remove only those player-added forbidden
        # identities that match its concrete authored House/country aliases.
        # Player-owned placements and teams must not
        # participate in this collision set: including them removed the exact
        # player country from the native gate and exposed original cameos
        # beside their MORP clones.
        player_forbidden_lower = {
            str(owner).strip().lower()
            for owner in player_native_exclusions
            if str(owner).strip()
        }
        for source_id in sorted(
            non_player_runtime_unit_ids.intersection(
                production_gate_source_ids
            )
        ):
            runtime_aliases = set()
            for runtime_house in usage_index.get(source_id, ()):
                runtime_house = str(runtime_house or '').strip()
                if not runtime_house or runtime_house.lower() in {
                    '<all>', '<none>', 'none',
                }:
                    continue
                if runtime_house.lower() in player_usage_names:
                    continue
                runtime_aliases.add(runtime_house.lower())
                matching_records = [
                    (house_name, house_values)
                    for house_name, house_values in records.items()
                    if runtime_house.lower() in {
                        house_name.lower(),
                        house_name.removesuffix(' House').lower(),
                        str(house_values.get('country', '')).lower(),
                    }
                ]
                for house_name, house_values in matching_records:
                    runtime_aliases.add(house_name.lower())
                    runtime_aliases.add(
                        house_name.removesuffix(' House').lower()
                    )
                    if house_values.get('country'):
                        runtime_aliases.add(
                            str(house_values['country']).lower()
                        )
            colliding_forbidden = (
                runtime_aliases & player_forbidden_lower
            )
            if not colliding_forbidden:
                continue
            pending_forbidden = next(
                (
                    value
                    for key, value in production_gate_rules.get(
                        source_id, {}
                    ).items()
                    if str(key).lower() == 'forbiddenhouses'
                ),
                None,
            )
            current_forbidden = next(
                (
                    value
                    for key, value in section_value_map_preserve(
                        lines, source_id
                    ).items()
                    if str(key).lower() == 'forbiddenhouses'
                ),
                '',
            )
            existing_forbidden = [
                item.strip()
                for item in str(
                    current_forbidden
                    if pending_forbidden is None
                    else pending_forbidden
                ).split(',')
                if item.strip().lower() not in {'', 'none', '<none>'}
            ]
            remaining_forbidden = [
                owner
                for owner in unique_in_order(existing_forbidden)
                if owner.lower() not in colliding_forbidden
            ]
            production_gate_rules.setdefault(source_id, {})[
                'ForbiddenHouses'
            ] = ','.join(remaining_forbidden) or 'none'
        # Keep each refinery's native BuildingType identity. Only retarget its
        # one authored FreeUnit to the matching final player clone. The clone's
        # Owner/RequiredHouses now match the refinery owner, while the native
        # miner can be hidden like every other cloned production identity.
        for refinery_id, miner_id in sorted(
            refinery_free_unit_by_building.items()
        ):
            clone_id = str(
                clone_handled.get(miner_id, {}).get('clone_id') or ''
            ).strip()
            if not clone_id or clone_id not in clone_rule_sections:
                continue
            production_gate_rules.setdefault(refinery_id, {})[
                'FreeUnit'
            ] = clone_id
        remember_generated_techno_types(production_gate_rules)
        for section, values in production_gate_rules.items():
            clone_rule_sections.setdefault(section, {}).update(values)
        for source_id in sorted(runtime_identity_preserve_ids):
            original_values = native_map_sections.get(source_id, {})
            current_values = section_value_map_preserve(lines, source_id)
            pending_values = clone_rule_sections.get(source_id, {})
            if not original_values and not current_values and not pending_values:
                continue
            restored_values = {
                key: None
                for key in set(current_values) | set(pending_values)
                if key not in original_values
            }
            restored_values.update(original_values)
            clone_rule_sections[source_id] = restored_values
        if code == 'FKILL':
            repaired_defenses = []
            for source_id, details in clone_handled.items():
                if BUFF_TARGETS.get(source_id, {}).get('category') != 'defenses':
                    continue
                clone_id = str((details or {}).get('clone_id') or '').strip()
                values = clone_rule_sections.get(clone_id)
                if not clone_id or not isinstance(values, dict):
                    continue
                for key in tuple(values):
                    if str(key).lower().startswith('prerequisite'):
                        values.pop(key)
                values['Prerequisite'] = 'NACNST'
                values['BuildCat'] = 'Combat'
                values['TechLevel'] = '1'
                for field in ('Owner', 'RequiredHouses'):
                    owners = [
                        owner.strip()
                        for owner in str(values.get(field, '')).split(',')
                        if owner.strip().lower() not in {
                            '', 'none', '<none>', 'guild1',
                        }
                    ]
                    values[field] = ','.join(
                        unique_in_order(owners + ['Guild1'])
                    )
                forbidden = [
                    owner.strip()
                    for owner in str(values.get('ForbiddenHouses', '')).split(',')
                    if owner.strip().lower() not in {
                        '', 'none', '<none>', 'guild1',
                    }
                ]
                values['ForbiddenHouses'] = ','.join(
                    unique_in_order(forbidden)
                ) or 'none'
                repaired_defenses.append(clone_id)
            if repaired_defenses:
                self.append_log(
                    'Foehn 02 defense access: bound '
                    f'{len(repaired_defenses)} granted defense clone(s) to '
                    'Guild1 native NACNST construction.'
                )
        for source_id, details in clone_handled.items():
            clone_id = str((details or {}).get('clone_id') or '').strip()
            list_section = TECHNO_TYPE_LISTS.get(
                BUFF_TARGETS.get(source_id, {}).get('category')
            )
            if clone_id and list_section:
                expected_generated_techno_types[list_section].append(clone_id)
        remember_generated_techno_types(clone_rule_sections)
        pad_aircraft_rules, pad_aircraft_clone_ids = (
            player_clone_pad_aircraft_rules(
                lines,
                installed_rule_sections,
                clone_handled,
            )
        )
        for section, values in pad_aircraft_rules.items():
            clone_rule_sections.setdefault(section, {}).update(values)
        if pad_aircraft_clone_ids:
            self.append_log(
                'Registered pad-bound player aircraft clones in '
                '[General] PadAircraft: '
                + ', '.join(pad_aircraft_clone_ids)
                + '.'
            )
        if clone_rule_sections:
            production_trace = {}
            for source_id, details in clone_handled.items():
                if 'production' not in set(
                    (details or {}).get('clone_unit_buff_types', ())
                ):
                    continue
                clone_id = str((details or {}).get('clone_id') or '')
                clone_values = clone_rule_sections.get(clone_id, {})
                multiplier = next(
                    (
                        str(value)
                        for key, value in clone_values.items()
                        if str(key).lower() == 'buildtimemultiplier'
                    ),
                    '',
                )
                if not multiplier:
                    continue
                category = str(
                    BUFF_TARGETS.get(source_id, {}).get('category')
                    or 'other'
                )
                production_trace.setdefault(category, {}).setdefault(
                    multiplier, 0
                )
                production_trace[category][multiplier] += 1
            if production_trace:
                trace_parts = []
                for category in sorted(production_trace):
                    values = production_trace[category]
                    value_summary = '/'.join(sorted(values))
                    count = sum(values.values())
                    trace_parts.append(
                        f'{category}={value_summary} ({count} clone(s))'
                    )
                self.append_log(
                    'Applied live clone BuildTimeMultiplier values: '
                    + '; '.join(trace_parts)
                    + '.'
                )
            merge_ini_section_values(lines, clone_rule_sections)
            self.append_log(
                'Prepared isolated standalone player unit/defense clones for: '
                + ', '.join(cloned_unit_names)
                + '. Compatible helper references use the same buffed clones; '
                'native IDs remain AI/script fallbacks only.'
            )
        production_gate_houses = player_controlled_houses(
            lines, records=records
        )
        if not production_gate_houses:
            fallback_gate_house = player_house_from_map(lines, records=records)
            production_gate_houses = (
                [fallback_gate_house] if fallback_gate_house else []
            )
        placed_production_gates = append_static_startup_buildings(
            lines,
            production_gate_houses,
            [PLAYER_ORIGINAL_PRODUCTION_GATE_ID]
            if production_gate_source_ids else (),
        )
        if production_gate_source_ids:
            expected_gate_count = len(unique_in_order(production_gate_houses))
            if len(placed_production_gates) != expected_gate_count:
                self.append_log(
                    'Could not place every exact-House original-production gate; '
                    f'placed {len(placed_production_gates)} of {expected_gate_count}.',
                    error=True,
                )
            else:
                self.append_log(
                    'Blocked native player production behind isolated clone mapping: '
                    f'{len(production_gate_source_ids)} source type(s), '
                    f'{len(placed_production_gates)} player house gate(s).'
                )
        ore_dock_rules, ore_dock_report = ore_purifier_miner_dock_rules(
            lines,
            clone_handled,
        )
        if ore_dock_rules:
            merge_ini_section_values(lines, ore_dock_rules)
        if ore_dock_report['purifier_id']:
            self.append_log(
                f'Bound {len(ore_dock_report["miner_ids"])} player ore miner '
                f'clone(s) to {ore_dock_report["purifier_id"]}.'
                + (
                    ' Issues: ' + '; '.join(ore_dock_report['issues']) + '.'
                    if ore_dock_report['issues']
                    else ''
                ),
                error=bool(ore_dock_report['issues']),
            )
        reprocessor_rules, reprocessor_report = reprocessor_bounty_rules(
            lines,
            installed_rule_sections,
            clone_handled,
            buildable_tech_ids=buildable_clone_ids,
        )
        if reprocessor_rules:
            merge_ini_section_values(lines, reprocessor_rules)
        if reprocessor_report['clone_id']:
            faction_counts = ', '.join(
                f'{faction}={len(unit_ids)}'
                for faction, unit_ids
                in reprocessor_report['eligible_by_faction'].items()
            ) or 'none'
            self.append_log(
                'Reprocessor bounty trigger '
                + (
                    'enabled'
                    if reprocessor_report['trigger_enabled']
                    else 'invalid'
                )
                + f' for {reprocessor_report["clone_id"]}; '
                f'Bounty=yes player-unit detection: {faction_counts}; '
                f'authored exclusions={len(reprocessor_report["excluded_unit_ids"])}.'
                + (
                    ' Issues: '
                    + '; '.join(reprocessor_report['issues'])
                    + '.'
                    if reprocessor_report['issues']
                    else ''
                ),
                error=bool(reprocessor_report['issues']),
            )
        academy_clone_rules = resolved_academy_clone_rules(
            cloned_power_rules,
            clone_handled,
            owned_clone_ids,
        )
        if academy_clone_rules:
            merge_ini_section_values(lines, academy_clone_rules)
            self.append_log(
                'Resolved delivered Academy targets to current player clone IDs.'
            )
        delivery_clone_rules = resolved_delivery_clone_rules(
            cloned_power_rules,
            clone_handled,
            delivery_clone_ids,
        )
        if delivery_clone_rules:
            merge_ini_section_values(lines, delivery_clone_rules)
            self.append_log(
                'Resolved unit-delivery payloads to current player clone IDs.'
            )
        (
            power_player_clone_rules,
            power_player_clone_overrides,
        ) = resolved_power_player_clone_rules(
            cloned_power_rules,
            clone_handled,
            power_player_clone_reference_fields,
            power_player_clone_value_overrides,
        )
        if power_player_clone_rules or power_player_clone_overrides:
            merge_ini_section_values(
                lines,
                {
                    **power_player_clone_rules,
                    **power_player_clone_overrides,
                },
            )
            self.append_log(
                'Resolved power target/designator restrictions to current '
                'player clone IDs.'
            )
        native_designator_clone_rules = resolved_native_designator_clone_rules(
            installed_rule_sections,
            native_map_sections,
            clone_handled,
        )
        if native_designator_clone_rules:
            merge_ini_section_values(lines, native_designator_clone_rules)
            self.append_log(
                'Extended native power designators to current player clone IDs.'
            )
        if clone_warnings:
            self.append_log(
                'Player unit/defense clone limitations: '
                + '; '.join(clone_warnings)
                + '.',
                error=True,
            )
        (
            helper_ai_rules,
            helper_built_units,
            helper_ai_skipped,
        ) = helper_ai_autobuild_rules(
            lines,
            helper_autobuild,
            clone_handled,
            installed_rule_sections,
        )
        if helper_ai_rules:
            merge_ini_section_values(lines, helper_ai_rules)
            self.append_log(
                'Added parallel allied-helper Autocreate teams for unlocked units: '
                + ', '.join(helper_built_units)
                + '. Native timing/scripts remain active and dynamic native-ID production stays valid.'
            )
        elif reward_helpers:
            self.append_log(
                'No compatible parallel allied-helper unlock variants were found; '
                'native helper timing remains active.'
            )
        if helper_ai_skipped:
            self.append_log(
                'Skipped allied-helper unit clones without a complete player clone: '
                + ', '.join(helper_ai_skipped)
                + '.',
                error=True,
            )
        reward_veterancy = stacked_house_buff_values(
            guarded_rewards,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            max_veteran_value_length=None,
        )
        scripted_veteran_ids = {
            unit_id.upper()
            for field in (
                'VeteranInfantry', 'VeteranUnits', 'VeteranAircraft',
                'VeteranBuildings',
            )
            for unit_id in str(reward_veterancy.get(field, '')).split(',')
            if unit_id
        }
        scripted_veteran_ids.update(
            values.get('clone_id', '')
            for unit_id, values in clone_handled.items()
            if unit_id in scripted_veteran_ids and values.get('clone_id')
        )
        for native_variant_buff_config in MISSION_NATIVE_VARIANT_BUFF_RULES.get(code, ()):
            source_unit_id = native_variant_buff_config['source_unit']
            native_variant_ids = native_variant_buff_config['native_units']
            if source_unit_id in scripted_veteran_ids:
                scripted_veteran_ids.update(native_variant_ids)
            native_variant_rules, native_buffed_ids = native_variant_unit_buff_rules(
                guarded_rewards,
                installed_rule_sections,
                native_map_sections,
                source_unit_id,
                native_variant_ids,
                require_unlocked_access=require_unlocked_access_for_buffs,
                additional_unlocked_tech_ids=buff_access_tech_ids,
                share_basic_equivalent_buffs=share_basic_equivalent_buffs,
                unit_specific_mode=chaos_unit_specific_buffs,
            )
            if native_variant_rules:
                merge_ini_section_values(lines, native_variant_rules)
                self.append_log(
                    f'Applied earned {source_unit_id} buffs to native '
                    'mission identities: '
                    + ', '.join(native_buffed_ids)
                    + '.'
                )
            native_veterancy_rules, native_veteran_ids = (
                native_variant_veterancy_rules(
                    lines,
                    source_unit_id,
                    native_variant_ids,
                    source_clone_id=clone_handled.get(
                        source_unit_id, {}
                    ).get('clone_id', ''),
                    configured_helper_houses=reward_helpers,
                    excluded_player_houses=excluded_player_houses,
                )
            )
            if native_veterancy_rules:
                merge_ini_section_values(lines, native_veterancy_rules)
                self.append_log(
                    f'Applied earned {source_unit_id} veterancy to native '
                    'mission identities: '
                    + ', '.join(native_veteran_ids)
                    + '.'
                )
        (
            scripted_veterancy_sections,
            scripted_veteran_team_ids,
        ) = scripted_reinforcement_veterancy_rules(
            lines,
            scripted_veteran_ids,
            configured_helper_houses=reward_helpers,
            excluded_player_houses=excluded_player_houses,
        )
        if scripted_veterancy_sections:
            merge_ini_section_values(lines, scripted_veterancy_sections)
            self.append_log(
                'Applied earned veterancy to scripted reinforcement teams: '
                + ', '.join(scripted_veteran_team_ids)
                + '.'
            )
        (
            weapon_rule_sections,
            weapon_buffed_units,
            weapon_skipped_units,
        ) = unit_weapon_buff_rules(
            lines,
            guarded_rewards,
            installed_sections=installed_rule_sections,
            native_map_sections=native_map_sections,
            configured_helper_houses=reward_helpers,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            clone_handled=clone_handled,
            excluded_unit_ids=MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS.get(
                code, ()
            ),
            excluded_player_houses=excluded_player_houses,
        )
        if weapon_rule_sections:
            merge_ini_section_values(lines, weapon_rule_sections)
            self.append_log(
                'Applied guarded unit/weapon buffs for: '
                + ', '.join(weapon_buffed_units)
                + '.'
            )
        if weapon_skipped_units:
            self.append_log(
                'Skipped guarded unit/weapon buffs because unsafe houses use the affected '
                'unit or a shared weapon: '
                + '; '.join(weapon_skipped_units)
                + '.',
                error=True,
            )

    # Restore reviewed native exceptions and strict non-player Droppod
    # payloads after every clone, gate, direct-buff, weapon, and assistance
    # pass. Do not broaden this to every non-player runtime identity: mixed
    # player/helper story flows deliberately use rewritten clone references.
    final_runtime_restore_ids = (
        set(runtime_identity_preserve_ids)
        | set(non_player_droppod_payload_ids)
        | set(MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS.get(code, ()))
    ) - set(refinery_free_unit_ids)
    if final_runtime_restore_ids:
        # Reviewed player story TaskForces are rewritten to clone identities
        # before native originals receive a player-country sidebar exclusion.
        # Recompute from the final references and fail safely: if any player
        # TeamType still contains the native ID, keep that ID unrestricted so
        # the campaign team can form, even though the access report will flag
        # its duplicate cameo.
        final_sections = all_section_value_maps(lines)
        final_sections_by_lower = {
            str(section).lower(): values
            for section, values in final_sections.items()
        }
        final_player_taskforce_unit_ids = set()
        for taskforce_id, usage_houses in taskforce_usage_houses(
            lines,
            sections=final_sections,
        ).items():
            if not {
                str(house or '').strip().lower()
                for house in usage_houses
            }.intersection(controlled_player_usage_names):
                continue
            for value in final_sections_by_lower.get(
                str(taskforce_id).lower(), {}
            ).values():
                tokens = [token.strip() for token in str(value).split(',')]
                if (
                    len(tokens) >= 2
                    and tokens[0].isdigit()
                    and tokens[1]
                    and tokens[1].lower() not in {'none', '<none>'}
                ):
                    final_player_taskforce_unit_ids.add(tokens[1].upper())
        final_runtime_identity_rules = {}
        for source_id in sorted(final_runtime_restore_ids):
            original_values = native_map_sections_preserve.get(
                str(source_id).upper(), {}
            )
            current_values = section_value_map_preserve(lines, source_id)
            if (
                not original_values
                and not current_values
                and source_id not in (
                    MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS.get(code, ())
                )
            ):
                continue
            original_keys = {
                str(key).lower()
                for key in original_values
            }
            restored_values = {
                key: None
                for key in current_values
                if str(key).lower() not in original_keys
            }
            restored_values.update(original_values)
            # Droppod payloads need their authored production prerequisites,
            # but a player-country ForbiddenHouses value does not affect a
            # payload owned by another country. Preserve that safe sidebar
            # exclusion; clearing the entire section restored native E1/GGI
            # cameos beside their player clones in Golden Gate.
            runtime_aliases = set()
            for runtime_house in usage_index.get(source_id, ()):
                runtime_house = str(runtime_house or '').strip()
                if not runtime_house or runtime_house.lower() in {
                    '<all>', '<none>', 'none',
                }:
                    continue
                if runtime_house.lower() in player_usage_names:
                    continue
                runtime_aliases.add(runtime_house.lower())
                for house_name, house_values in records.items():
                    if runtime_house.lower() not in {
                        house_name.lower(),
                        house_name.removesuffix(' House').lower(),
                        str(house_values.get('country', '')).lower(),
                    }:
                        continue
                    runtime_aliases.add(house_name.lower())
                    runtime_aliases.add(
                        house_name.removesuffix(' House').lower()
                    )
                    if house_values.get('country'):
                        runtime_aliases.add(
                            str(house_values['country']).lower()
                        )
            preserve_player_forbidden = (
                source_id in MISSION_NATIVE_RUNTIME_PLAYER_FORBIDDEN_IDS.get(
                    code, ()
                )
                and source_id in production_gate_rules
                and source_id not in final_player_taskforce_unit_ids
            )
            if (
                (
                    source_id not in runtime_identity_preserve_ids
                    or preserve_player_forbidden
                )
                and (
                    preserve_player_forbidden
                    or not runtime_aliases.intersection({
                        str(owner).strip().lower()
                        for owner in player_native_exclusions
                        if str(owner).strip()
                    })
                )
            ):
                current_forbidden = next(
                    (
                        value
                        for key, value in current_values.items()
                        if str(key).lower() == 'forbiddenhouses'
                    ),
                    None,
                )
                if current_forbidden is None and preserve_player_forbidden:
                    current_forbidden = next(
                        (
                            value
                            for key, value in production_gate_rules.get(
                                source_id, {}
                            ).items()
                            if str(key).lower() == 'forbiddenhouses'
                        ),
                        None,
                    )
                if current_forbidden is not None:
                    for key in list(restored_values):
                        if str(key).lower() == 'forbiddenhouses':
                            restored_values.pop(key, None)
                    restored_values['ForbiddenHouses'] = current_forbidden
            # Keep the production-only player-factory exclusion prepared for
            # DropPod payloads. Unlike TechLevel, BuildLimit, house filters,
            # or negative prerequisites, this does not alter the payload's
            # scripted identity and still allows captured enemy factories.
            current_factory_forbidden = next(
                (
                    value
                    for key, value in current_values.items()
                    if str(key).lower() == 'factoryowners.forbidden'
                ),
                None,
            )
            if current_factory_forbidden is None:
                current_factory_forbidden = next(
                    (
                        value
                        for key, value in production_gate_rules.get(
                            source_id, {}
                        ).items()
                        if str(key).lower() == 'factoryowners.forbidden'
                    ),
                    None,
                )
            action_team_factory_forbidden = (
                MISSION_NATIVE_RUNTIME_ACTION_TEAM_FACTORY_FORBIDDEN_HOUSES.get(
                    code, ()
                )
            )
            if (
                source_id in scripted_story_unit_ids
                and source_id in production_gate_rules
                and action_team_factory_forbidden
            ):
                original_factory_forbidden = native_value(
                    original_values,
                    'FactoryOwners.Forbidden',
                    native_value(
                        installed_rule_sections.get(
                            installed_names.get(source_id.lower()), {}
                        ),
                        'FactoryOwners.Forbidden',
                        '',
                    ),
                )
                current_factory_forbidden = ','.join(unique_in_order(
                    [
                        item.strip()
                        for item in str(
                            original_factory_forbidden or ''
                        ).split(',')
                        if item.strip()
                    ]
                    + list(action_team_factory_forbidden)
                ))
            if current_factory_forbidden is not None:
                for key in list(restored_values):
                    if str(key).lower() == 'factoryowners.forbidden':
                        restored_values.pop(key, None)
                restored_values[
                    'FactoryOwners.Forbidden'
                ] = current_factory_forbidden
            final_runtime_identity_rules[source_id] = restored_values
        if final_runtime_identity_rules:
            merge_ini_section_values(lines, final_runtime_identity_rules)
        # Engineer identities can be authored in player/helper TaskForces, so
        # they participate in runtime restoration. Reapply only their native
        # production isolation afterward: the hidden exact-House gate does not
        # prevent scripted creation, but it does prevent a friendly barracks
        # handed over later from masquerading as captured enemy technology.
        final_engineer_gate_rules = {
            source_id: values
            for source_id, values in production_gate_rules.items()
            if source_id in set(ENGINEER_UNIT_IDS)
        }
        if final_engineer_gate_rules:
            merge_ini_section_values(lines, final_engineer_gate_rules)

    runtime_weapon_restore_ids = (
        MISSION_NATIVE_RUNTIME_WEAPON_PRESERVE_IDS.get(code, ())
    )
    if runtime_weapon_restore_ids:
        final_runtime_weapon_rules = {}
        for weapon_id in sorted(runtime_weapon_restore_ids):
            original_values = native_map_sections_preserve.get(
                str(weapon_id).upper(), {}
            )
            current_values = section_value_map_preserve(lines, weapon_id)
            if not original_values and not current_values:
                continue
            restored_values = {
                key: None
                for key in current_values
                if str(key).lower() not in {
                    str(original_key).lower()
                    for original_key in original_values
                }
            }
            restored_values.update(original_values)
            final_runtime_weapon_rules[weapon_id] = restored_values
        if final_runtime_weapon_rules:
            merge_ini_section_values(lines, final_runtime_weapon_rules)
            self.append_log(
                'Restored authored runtime WeaponTypes after player buff '
                'isolation: '
                + ', '.join(sorted(final_runtime_weapon_rules))
                + '.'
            )

    (
        enemy_unit_rules,
        enemy_buffed_unit_ids,
        skipped_enemy_unit_buffs,
        enemy_unit_applications,
    ) = enemy_native_unit_buff_rules(
        lines,
        scaled_enemy_houses,
        enemy_scaling_rewards,
        installed_rule_sections,
        native_map_sections,
    )
    if enemy_unit_rules:
        merge_ini_section_values(lines, enemy_unit_rules)
        self.append_log(
            'Applied native T1/T2/T3 AI unit buffs to: '
            + ', '.join(enemy_buffed_unit_ids)
            + '.'
        )
    if skipped_enemy_unit_buffs:
        self.append_log(
            'Skipped unsafe native AI unit buffs: '
            + '; '.join(skipped_enemy_unit_buffs)
            + '.',
            error=True,
        )
    unit_entries_by_effect = {}
    for entry in enemy_scaling_entries:
        effect_id = str(entry['reward'].get('enemy_effect_id') or '')
        if effect_id:
            unit_entries_by_effect.setdefault(effect_id, []).append(entry)
    for application in enemy_unit_applications:
        effect_entries = unit_entries_by_effect.get(
            application['effect_id'], ()
        )
        if not effect_entries:
            continue
        reward = effect_entries[0]['reward']
        ai_reward_applications.append({
            'mission': code,
            'reward_name': reward.get(
                'name', application['effect_id']
            ),
            'source': ' + '.join(unique_in_order(
                entry['source'] for entry in effect_entries
            )),
            'earned_from': '; '.join(unique_in_order(
                entry['earned_from'] for entry in effect_entries
            )),
            **application,
        })
    native_team_validation_ids = (
        non_player_taskforce_unit_ids - set(ENGINEER_UNIT_IDS)
    )
    if code in MISSION_NATIVE_RUNTIME_PRESERVE_ACTION_TEAMS:
        native_team_validation_ids.difference_update(scripted_story_unit_ids)
    validated_native_team_units = validate_native_taskforce_production_filters(
        lines,
        installed_rule_sections,
        native_map_sections,
        native_team_validation_ids,
        player_runtime_ids=(
            player_runtime_unit_ids - safe_player_clone_unit_ids
        ),
        player_forbidden_houses=player_native_exclusions,
        player_factory_forbidden_houses=player_factory_exclusions,
    )
    if validated_native_team_units:
        self.append_log(
            'Validated authored non-player TaskForce production filters: '
            f'{validated_native_team_units} native type(s).'
        )
    static_power_providers = append_static_startup_buildings(
        lines,
        power_house_names,
        static_startup_power_buildings,
    )
    expected_static_power_providers = (
        len(unique_in_order(power_house_names))
        * len(static_startup_power_buildings)
    )
    if expected_static_power_providers:
        if len(static_power_providers) == expected_static_power_providers:
            self.append_log(
                'Placed exact-House static power provider(s): '
                + ', '.join(
                    f'{building_id} for {house}'
                    for house, building_id, _cell_x, _cell_y
                    in static_power_providers
                )
                + '.'
            )
        else:
            self.append_log(
                'Could not place every exact-House static power provider; '
                f'placed {len(static_power_providers)} of '
                f'{expected_static_power_providers}.',
                error=True,
            )

    # Objective marker TeamTypes still need one concrete owner. Keep this
    # separate from the possibly multi-house superweapon grant list: the
    # latter replaced the old ``house`` local and accidentally left marker
    # generation referencing an undefined name, which made the launcher
    # fall back to the untouched source map (no rewards or access rules).
    hook_house = player_country_from_map(lines)
    superweapon_trigger = append_superweapon_grant_trigger(
        lines,
        power_houses,
        superweapon_actions,
        startup_buildings=startup_power_buildings,
    )
    if superweapon_trigger:
        power_names = [
            reward_display_name(reward)
            for reward in canonical_rewards(launch_power_rewards)
            if reward.get('kind') == 'superweapon'
            and not reward.get('superweapon_grant_buildings')
        ]
        self.append_log(
            'Prepared isolated building-free power rewards for: '
            + ', '.join(power_names)
            + f'. Grant houses: {", ".join(power_houses)}.'
        )
    enemy_static_providers = append_static_startup_buildings(
        lines,
        scaled_enemy_houses,
        enemy_static_power_buildings,
    )
    # TriggerType owners use the HouseType's Country token (for example
    # ``USSR``), not the map section label (``USSR House``). Structures and
    # application receipts still require the exact section label above/below.
    # Feeding section labels to [Triggers] makes Ares report one fatal error
    # per hostile House before the scenario can start.
    enemy_power_grants_by_house = {}
    enemy_power_recipients_by_effect = {}
    for grant in enemy_power_grants:
        reward = grant.get('reward') or {}
        allowed_families = {
            str(family).strip().lower()
            for family in reward.get('enemy_faction_families', ())
            if str(family).strip()
        }
        recipient = next((
            house for house in scaled_enemy_houses
            if country_family(records.get(house, {})) in allowed_families
        ), '')
        if not recipient:
            continue
        enemy_power_grants_by_house.setdefault(recipient, []).append(grant)
        effect_id = str(reward.get('enemy_effect_id') or '')
        if effect_id:
            enemy_power_recipients_by_effect.setdefault(
                effect_id, []
            ).append(recipient)

    enemy_superweapon_trigger = ''
    for house, grants in enemy_power_grants_by_house.items():
        trigger_owner = (
            str(records.get(house, {}).get('country') or '').strip()
            or str(house).removesuffix(' House')
        )
        trigger_id = append_superweapon_grant_trigger(
            lines,
            [trigger_owner],
            [grant['action'] for grant in grants],
            startup_buildings=enemy_startup_power_buildings,
        )
        enemy_superweapon_trigger = enemy_superweapon_trigger or trigger_id
    if enemy_superweapon_trigger:
        grant_summary = [
            f'{grant["name"]} -> {house}'
            for house, grants in enemy_power_grants_by_house.items()
            for grant in grants
        ]
        self.append_log(
            'Prepared faction-matched hostile AI power grants: '
            + ', '.join(grant_summary)
            + '.'
        )
        power_entries_by_effect = {}
        for entry in enemy_scaling_entries:
            effect_id = str(entry['reward'].get('enemy_effect_id') or '')
            if effect_id in prepared_enemy_power_effect_ids:
                power_entries_by_effect.setdefault(effect_id, []).append(entry)
        for effect_id in unique_in_order(prepared_enemy_power_effect_ids):
            effect_entries = power_entries_by_effect.get(effect_id, ())
            if not effect_entries:
                continue
            reward = effect_entries[0]['reward']
            count = min(
                len(effect_entries), int(reward.get('enemy_maximum', 1))
            )
            values = enemy_effect_values(reward, count)
            for house in unique_in_order(
                enemy_power_recipients_by_effect.get(effect_id, ())
            ):
                ai_reward_applications.append({
                    'mission': code,
                    'reward_name': reward.get('name', effect_id),
                    'effect_id': effect_id,
                    'source': ' + '.join(unique_in_order(
                        entry['source'] for entry in effect_entries
                    )),
                    'earned_from': '; '.join(unique_in_order(
                        entry['earned_from'] for entry in effect_entries
                    )),
                    'house': house,
                    'country': str(
                        records.get(house, {}).get('country') or ''
                    ),
                    'category': reward.get(
                        'enemy_category', 'Support Powers'
                    ),
                    'target': str(reward.get('superweapon') or effect_id),
                    'effect': enemy_effect_text(reward, count),
                    **values,
                    'engine_field': 'SuperWeaponTypes',
                    'base_engine_value': 1.0,
                    'final_engine_value': 1.0,
                })
    if enemy_static_power_buildings and not enemy_static_providers:
        self.append_log(
            'Could not place enemy AI power providers.',
            error=True,
        )
    if discovered_enemies:
        self.append_log(
            f'{code} discovered active hostile AI Houses: '
            + ', '.join(discovered_enemies)
            + '.'
        )

    rewritten_native_unlocks = rewrite_techlevel_actions(
        lines,
        mission_unlock_clone_replacements if self.state else {},
        preserved_action_ids=preserved_ai_action_ids,
        keep_source_disabled_ids=(
            MISSION_NATIVE_TECH_UNLOCK_KEEP_SOURCE_DISABLED_IDS.get(code, ())
        ),
    )
    if rewritten_native_unlocks:
        self.append_log(
            f'Retargeted {rewritten_native_unlocks} native tech unlock action(s) '
            'to isolated player clones.'
        )

    unlocked_tech_ids = set(mission_effective_tech_ids)
    # Keep reviewed source IDs as a fail-safe if clone preparation was
    # impossible. Normal launches rewrite Action 106 to the registered clone;
    # delayed clones remain locked until that authored action fires.
    unlocked_tech_ids.update(MISSION_NATIVE_TECH_UNLOCK_IDS.get(code, ()))
    randomized_tech_ids = self.randomized_tech_ids() | suppressed_power_buildings
    unlocked_tech_ids.difference_update(suppressed_power_buildings)
    removed_techlevel_actions = remove_locked_techlevel_actions(
        lines,
        unlocked_tech_ids,
        randomized_tech_ids=randomized_tech_ids,
        preserved_action_ids=preserved_ai_action_ids,
    )
    if removed_techlevel_actions:
        self.append_log(f'Removed {removed_techlevel_actions} native tech unlock action(s) blocked by the randomizer.')
    checks = self.mission_checks(code) if self.state else []
    patch_plan, missing_victory, completed_objectives = pending_check_hook_plan(
        lines,
        checks,
        MISSION_VICTORY_HOOK_ACTION_IDS.get(code, ()),
        MISSION_OBJECTIVE_HOOK_ACTION_REDIRECTS.get(code, {}),
    )
    objective_hook_redirects = MISSION_OBJECTIVE_HOOK_ACTION_REDIRECTS.get(
        code, {}
    )
    if objective_hook_redirects:
        self.append_log(
            'Deferred fragile objective marker action(s): '
            + ', '.join(
                f'{source_action_id} -> {target_action_id}'
                for source_action_id, target_action_id
                in objective_hook_redirects.items()
            )
            + '.'
        )
    if missing_victory:
        self.append_log(f'No automatic victory hook found for {scenario}. Victory may not be recorded.', error=True)

    if (
        not patch_plan
        and not rule_sections
        and not enemy_country_rules
        and not enemy_unit_rules
        and not superweapon_trigger
        and not enemy_superweapon_trigger
    ):
        self.append_log(f'No hookable objective/victory triggers found for {scenario}. Progress may not be recorded.')
        return None

    markers, hook_failures = inject_check_markers(
        lines,
        code,
        patch_plan,
        hook_house,
    )
    for check, action_id in hook_failures:
        self.append_log(
            f'Skipped automatic {check.get("name", check.get("id", "check"))} hook for '
            f'{scenario}: action {action_id} has no safe room for a marker.',
            error=True,
        )

    if patch_plan and not markers:
        self.append_log(f'Hook map generation found triggers for {scenario}, but patching actions failed.', error=True)
        return None

    # Hook insertion can expose or rewrite action groups in unusual
    # campaign action lists. Run the native unlock filter again so a map
    # cannot restore access that is still locked by launcher state.
    removed_after_patching = remove_locked_techlevel_actions(
        lines,
        unlocked_tech_ids,
        randomized_tech_ids=randomized_tech_ids,
        preserved_action_ids=preserved_ai_action_ids,
    )
    if removed_after_patching:
        self.append_log(
            f'Removed {removed_after_patching} additional native tech unlock action(s) after hook patching.'
        )

    registration_rules, repaired_registrations = (
        reconcile_generated_techno_registrations(
            lines,
            installed_rule_sections,
            expected_generated_techno_types,
        )
    )
    if registration_rules:
        merge_ini_section_values(lines, registration_rules)
    if repaired_registrations:
        self.append_log(
            'Repaired generated TechnoType registry entries lost during rule '
            'batch merging: ' + ', '.join(repaired_registrations) + '.'
        )

    if self.state:
        pad_aircraft_validation = validate_player_clone_pad_aircraft(
            lines, clone_handled
        )
        if pad_aircraft_validation['failures']:
            raise ValueError(
                'Generated player aircraft PadAircraft validation failed: '
                + ', '.join(pad_aircraft_validation['failures'])
            )
        clone_selection_validation = validate_player_clone_selection_groups(
            lines, clone_handled
        )
        if clone_selection_validation['failures']:
            raise ValueError(
                'Generated player clone Type Selection validation failed: '
                + '; '.join(clone_selection_validation['failures'])
            )
        if clone_selection_validation['checked']:
            self.append_log(
                'Validated Ares Type Selection grouping for '
                f'{clone_selection_validation["checked"]} player clone(s).'
            )
        buff_validation = validate_generated_unit_buff_changes(
            lines,
            guarded_rewards,
            clone_handled,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            global_production_unit_ids=buildable_clone_ids,
            excluded_unit_ids=MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS.get(
                code, ()
            ),
        )
        if buff_validation['requested_effects']:
            self.append_log(
                'Validated generated unit buffs: '
                f'{buff_validation["applied_effects"]}/'
                f'{buff_validation["requested_effects"]} effects and '
                f'{buff_validation["applied_stacks"]}/'
                f'{buff_validation["requested_stacks"]} effective stacks '
                'changed final player clone/weapon rules.'
            )
        if buff_validation['skipped']:
            skipped_summary = '; '.join(
                f'{entry["unit"]}/{entry["buff_type"]} x'
                f'{entry["stacks"]}: {entry["reason"]}'
                for entry in buff_validation['skipped']
            )
            self.append_log(
                'Skipped requested unit buffs after generated INI validation: '
                + skipped_summary
                + '.',
                error=True,
            )

        starting_rewards_for_report = list(
            self.state.get('starting_rewards', ())
        )
        progression_rewards_for_report = list(
            self.earned_rewards_from_checks(include_starting=False)
        )
        mission_specific_ids_for_report = (
            set(native_required_access_ids)
            | set(MISSION_NATIVE_TECH_UNLOCK_IDS.get(code, ()))
            | set(original_mcv_access_ids)
        )
        starting_faction_tech_ids_for_report = (
            set(self.active_starting_tier_one_expanded_ids())
            | set(self.active_starting_tier_one_defense_expanded_ids())
            | set(ALWAYS_AVAILABLE_TECH_IDS).intersection(
                buildable_clone_ids
            )
        )
        access_report_lines = build_unit_access_report(
            lines,
            installed_rule_sections,
            mission,
            self.state,
            reward_mode=self.active_reward_mode(),
            progression_mode=self.active_progression_mode(),
            campaign_filter=self.state.get('campaign_filter', ''),
            starting_rewards=starting_rewards_for_report,
            progression_rewards=progression_rewards_for_report,
            active_rewards=access_report_active_rewards,
            mission_specific_ids=mission_specific_ids_for_report,
            delayed_mission_unlock_ids=delayed_native_unlock_ids,
            starting_faction_tech_ids=starting_faction_tech_ids_for_report,
            expected_buildable_source_ids=buildable_clone_ids,
            controlled_source_ids=self.randomized_tech_ids(),
            clone_handled=clone_handled,
            similar_tech_enabled=similar_tech_enabled_for_report,
            similar_tech_reason=similar_tech_reason_for_report,
            randomize_unit_access=self.randomize_unit_access_enabled(),
        )
        for report_line in access_report_lines:
            self.append_log(
                report_line,
                error=report_line.startswith('WARNING:'),
            )

    packed_sections = {
        'PreviewPack', 'IsoMapPack5', 'OverlayPack', 'OverlayDataPack',
    }
    current_section = ''
    overlong_lines = []
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped[1:-1].strip()
        byte_length = len(line.encode('utf-8'))
        if (
            current_section not in packed_sections
            and byte_length > MAX_MAP_ACTION_LINE_LENGTH
        ):
            overlong_lines.append(
                f'[{current_section}] line {line_number} ({byte_length} bytes)'
            )
    if overlong_lines:
        raise ValueError(
            'Generated map exceeds the engine INI line limit of '
            f'{MAX_MAP_ACTION_LINE_LENGTH} bytes: '
            + '; '.join(overlong_lines[:8])
        )

    GENERATED_MAP_DIR.mkdir(parents=True, exist_ok=True)
    generated_path = GENERATED_MAP_DIR / scenario.upper()
    generated_text = HOOKED_MAP_MARKER + '\r\n' + '\r\n'.join(lines) + '\r\n'
    # Path.write_text translates every ``\n`` on Windows. Because the map
    # text already uses CRLF, that produced CRCRLF and inserted a blank
    # line after every source line. Write bytes so campaign INI formatting
    # remains byte-for-byte conventional.
    generated_path.write_bytes(generated_text.encode('utf-8'))

    root_map = GAME_ROOT / scenario
    if root_map.exists() and not is_generated_hooked_map(root_map):
        backup_file_once(root_map, 'before-randomizer-hook')
    root_map.write_bytes(generated_text.encode('utf-8'))
    if self.state and hasattr(self, 'record_enemy_reward_applications'):
        self.record_enemy_reward_applications(
            code,
            ai_reward_applications,
        )
    self.append_log(f'Prepared generated map {scenario}: {len(markers)} marker trigger(s).')

    return {
        'mission_code': code,
        'scenario': scenario,
        'markers': markers,
        'seen': set(),
        'completed_objective_checks': completed_objectives,
        'objective_events_seen': 0,
        'offset': DEBUG_LOG.stat().st_size if DEBUG_LOG.exists() else 0,
        'root_map': root_map,
    }
