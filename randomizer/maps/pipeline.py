"""Generated mission-map pipeline separated from Tk orchestration."""

from randomizer.core.collections import unique_in_order
from randomizer.ui.cameos import installed_rules_registry
from randomizer.maps.assets import deploy_superweapon_sidebar_assets
from randomizer.maps.ini import (
    all_section_value_maps,
    merge_ini_section_values,
    read_text,
    section_value_map_preserve,
)
from randomizer.maps.ownership import script_referenced_taskforce_unit_ids
from randomizer.maps.power_buffs import apply_power_buffs_to_unlock_rewards
from randomizer.maps.rules import (
    HOOKED_MAP_MARKER,
    LOCKED_TECH_LEVEL,
    append_superweapon_grant_trigger,
    backup_file_once,
    clone_player_country_for_house_buffs,
    cloned_superweapon_plan,
    helper_ai_autobuild_plan,
    helper_ai_autobuild_rules,
    is_generated_hooked_map,
    mission_assistance_buff_rules,
    mission_assistance_direct_rewards,
    mission_assistance_unit_ids,
    native_variant_unit_buff_rules,
    native_variant_veterancy_rules,
    player_country_buff_rules,
    player_unit_clone_rules,
    resolved_academy_clone_rules,
    resolved_map_section_rules,
    remove_locked_techlevel_actions,
    stacked_house_buff_values,
    suppressed_superweapon_building_ids,
    unit_weapon_buff_rules,
)
from randomizer.rewards.rules import expand_equivalent_role_buffs
from randomizer.maps.progress_hooks import (
    inject_check_markers,
    pending_check_hook_plan,
)
from randomizer.maps.houses import (
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
from randomizer.missions.houses import mission_house_config, mission_player_power_houses
from randomizer.missions.overrides import (
    MISSION_CLONE_ONLY_COUNTRY_BUFF_TYPES,
    MISSION_DISABLED_TRIGGERS,
    MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS,
    MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS,
    MISSION_NATIVE_TECH_UNLOCK_IDS,
    MISSION_NATIVE_TRIGGER_REFERENCE_IDS,
    MISSION_NATIVE_VARIANT_BUFF_RULES,
    MISSION_REQUIRED_ACCESS_RULES,
    MISSION_REWARD_EXCLUDED_PLAYER_HOUSES,
    MISSION_MAP_SECTION_RULES,
    MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES,
    MISSION_TEAM_HOUSE_OVERRIDES,
    MISSION_TECHNO_BASE_RULES,
)
from randomizer.missions.safety import safe_build_countries
from randomizer.missions.catalogue import normalize_faction
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT, GENERATED_MAP_DIR
from randomizer.rewards.catalogue import (
    BUFF_TARGETS,
    ENGINEER_UNIT_IDS,
    canonical_rewards,
    reward_display_name,
)
from randomizer.ui.config import (
    EVA_APPEARANCE_PROFILES,
    EVA_VOICE_TAGS,
    RAINBOWIZER_COLORS,
)
from randomizer.rewards.roster import randomizer_unit_roster


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
            and self.active_reward_mode() != 'Chaos (Experimental)'
        )
        or self.share_chaos_role_buffs_enabled()
    )
    chaos_unit_specific_buffs = self.active_reward_mode() == 'Chaos (Experimental)'
    buff_allied_helpers = bool(self.active_reward_settings().get('buff_allied_helpers', False))

    scenario = mission.get('scenario')
    code = mission.get('code')
    if not scenario or not code:
        return None
    native_techno_exclusions = MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS.get(
        code, ()
    )
    native_required_access_ids = {
        str(section).upper()
        for section in MISSION_REQUIRED_ACCESS_RULES.get(code, {})
    }
    native_build_only_clone_ids = (
        set(native_techno_exclusions) - native_required_access_ids
    )
    excluded_player_houses = MISSION_REWARD_EXCLUDED_PLAYER_HOUSES.get(
        code, ()
    )
    clone_only_country_buff_types = (
        MISSION_CLONE_ONLY_COUNTRY_BUFF_TYPES.get(code, ())
    )
    if clone_only_country_buff_types:
        self.append_log(
            f'Kept {", ".join(sorted(clone_only_country_buff_types))} '
            f'country buffs clone-only for {code}; native scripted '
            'reinforcements retain mission-authored stats.'
        )

    source_path = self.extract_campaign_map(scenario)
    lines = read_text(source_path).splitlines()
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
    scripted_story_unit_ids = script_referenced_taskforce_unit_ids(
        lines,
        native_map_sections,
    )
    installed_superweapon_types, installed_rule_sections = installed_rules_registry()
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
    enemy_names = {house.lower() for house in configured_enemies}
    native_helpers = [
        house for house in native_helpers if house.lower() not in enemy_names
    ]
    # Native helper timing, scripts, and triggers stay intact. Compatible
    # TaskForce slots use buffed clones, while native unit IDs remain
    # buildable for dynamic AI requests outside those TaskForces.
    reward_helpers = tuple(native_helpers) if buff_allied_helpers else ()
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
        self.append_log(
            f'{code} configured allied helper allowlist: '
            + (', '.join(reward_helpers) if reward_helpers else 'none')
            + '. Helper teams use buffed clones; native IDs remain buildable queue fallbacks.'
        )
    earned_rewards = self.active_launch_rewards() if self.state else []
    standard_single_campaign = bool(
        self.state
        and self.state.get('campaign_filter')
        in {'Allies', 'Soviets', 'Epsilon', 'Foehn'}
        and self.active_reward_mode() != 'Chaos (Experimental)'
    )
    if standard_single_campaign:
        # Translate a buff only to role peers the current mission can actually
        # produce. This prevents every faction peer (and Foehn) leaking into
        # Standard while still buffing a captured foreign factory's unit.
        earned_rewards = expand_equivalent_role_buffs(
            earned_rewards,
            enabled=True,
            allowed_unit_ids=mission_effective_tech_ids,
        )
        share_basic_equivalent_buffs = False
    launch_power_rewards = apply_power_buffs_to_unlock_rewards(
        earned_rewards,
        installed_rule_sections,
    )
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
    mission_power_techno_clone_overrides = (
        MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES.get(
            code, {}
        )
    )
    (
        cloned_power_rules,
        superweapon_actions,
        _cloned_power_names,
        startup_power_buildings,
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
    )
    for section, values in cloned_power_rules.items():
        rule_sections.setdefault(section, {}).update(values)
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
    preserved_native_access_ids = (
        set(native_techno_exclusions) | scripted_story_unit_ids
    )
    for source_id in sorted(isolated_native_ids - preserved_native_access_ids):
        forbidden = []
        for source_values in (
            installed_rule_sections.get(
                installed_names.get(source_id.lower()), {}
            ),
            native_map_sections.get(native_names.get(source_id.lower()), {}),
        ):
            for key, value in source_values.items():
                if str(key).lower() != 'forbiddenhouses':
                    continue
                forbidden.extend(
                    item.strip()
                    for item in str(value).split(',')
                    if item.strip().lower() not in {'', 'none', '<none>'}
                )
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

    generation_config = self.config.get('generation', {})
    experimental_house_buffs = bool(generation_config.get('experimental_house_buffs', False))
    safe_player_country_buffs = bool(generation_config.get('safe_player_country_buffs', True))
    require_unlocked_access_for_buffs = self.randomize_unit_access_enabled()
    buff_access_tech_ids = set(fallback_tech_ids) | set(mission_buff_unit_ids)
    if self.state and experimental_house_buffs:
        player_house, house_buffs = clone_player_country_for_house_buffs(
            lines,
            earned_rewards,
            require_unlocked_access=require_unlocked_access_for_buffs,
            additional_unlocked_tech_ids=buff_access_tech_ids,
            share_basic_equivalent_buffs=share_basic_equivalent_buffs,
            unit_specific_mode=chaos_unit_specific_buffs,
            excluded_buff_types=clone_only_country_buff_types,
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
            excluded_buff_types=clone_only_country_buff_types,
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
        buildable_clone_ids = set(fallback_tech_ids)
        buildable_clone_ids.update(mission_effective_tech_ids)
        if not require_unlocked_access_for_buffs:
            buildable_clone_ids.update(
                unit_id
                for unit_id, target in BUFF_TARGETS.items()
                if target.get('category') in {
                    'infantry', 'units', 'aircraft', 'defenses',
                }
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
            build_owner_ids=safe_build_countries(lines, records, ()),
            helper_autobuild_support=helper_autobuild.get('support'),
            forced_buildable_clone_ids=(
                fallback_tech_ids.intersection(ENGINEER_UNIT_IDS)
            ),
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
            excluded_unit_ids=native_techno_exclusions,
            build_only_excluded_unit_ids=native_build_only_clone_ids,
            excluded_player_houses=excluded_player_houses,
            owned_clone_ids=owned_clone_ids,
            owned_clone_templates=owned_clone_templates,
            owned_clone_rule_overlays=owned_clone_rule_overlays,
            force_direct_house_scoped_fallback_types=(
                clone_only_country_buff_types
            ),
        )
        if clone_rule_sections:
            merge_ini_section_values(lines, clone_rule_sections)
            self.append_log(
                'Prepared isolated standalone player unit/defense clones for: '
                + ', '.join(cloned_unit_names)
                + '. Compatible helper references use the same buffed clones; native IDs remain buildable fallbacks.'
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
        for native_variant_buff_config in MISSION_NATIVE_VARIANT_BUFF_RULES.get(code, ()):
            source_unit_id = native_variant_buff_config['source_unit']
            native_variant_ids = native_variant_buff_config['native_units']
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
            weapon_rule_sections,
            weapon_buffed_units,
            weapon_skipped_units,
        ) = unit_weapon_buff_rules(
            lines,
            guarded_rewards,
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

    unlocked_tech_ids = set(mission_effective_tech_ids)
    # Preserve reviewed native Action 106 unlocks. Their initial
    # TechLevel remains locked; mission_required_launch_rules removes only
    # BuildLimit so the native action can reveal them at the right time.
    unlocked_tech_ids.update(MISSION_NATIVE_TECH_UNLOCK_IDS.get(code, ()))
    randomized_tech_ids = self.randomized_tech_ids() | suppressed_power_buildings
    unlocked_tech_ids.difference_update(suppressed_power_buildings)
    removed_techlevel_actions = remove_locked_techlevel_actions(
        lines,
        unlocked_tech_ids,
        randomized_tech_ids=randomized_tech_ids,
    )
    if removed_techlevel_actions:
        self.append_log(f'Removed {removed_techlevel_actions} native tech unlock action(s) blocked by the randomizer.')
    checks = self.mission_checks(code) if self.state else []
    patch_plan, missing_victory = pending_check_hook_plan(lines, checks)
    if missing_victory:
        self.append_log(f'No automatic victory hook found for {scenario}. Victory may not be recorded.', error=True)

    if not patch_plan and not rule_sections and not superweapon_trigger:
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
    )
    if removed_after_patching:
        self.append_log(
            f'Removed {removed_after_patching} additional native tech unlock action(s) after hook patching.'
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
    self.append_log(f'Prepared generated map {scenario}: {len(markers)} marker trigger(s).')

    return {
        'mission_code': code,
        'scenario': scenario,
        'markers': markers,
        'seen': set(),
        'offset': DEBUG_LOG.stat().st_size if DEBUG_LOG.exists() else 0,
        'root_map': root_map,
    }
