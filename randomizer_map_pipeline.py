"""Generated mission-map pipeline separated from Tk orchestration."""

from randomizer_cameos import installed_rules_registry
from randomizer_custom_assets import deploy_superweapon_sidebar_assets
from randomizer_ini import (
    all_section_value_maps,
    merge_ini_section_values,
    read_text,
    section_value_map_preserve,
)
from randomizer_map import (
    HOOKED_MAP_MARKER,
    action_has_code,
    action_has_objective_complete,
    action_line_ids,
    append_action_to_action_id,
    append_hook_team,
    append_parallel_global_hook,
    append_superweapon_grant_trigger,
    backup_file_once,
    clone_player_country_for_house_buffs,
    cloned_superweapon_plan,
    helper_ai_autobuild_plan,
    helper_ai_autobuild_rules,
    hook_marker_name,
    insert_actions_before_codes,
    is_generated_hooked_map,
    map_house_records,
    mission_assistance_buff_rules,
    mission_assistance_direct_rewards,
    mission_assistance_unit_ids,
    native_variant_unit_buff_rules,
    player_controlled_houses,
    player_country_buff_rules,
    player_country_from_map,
    player_house_from_map,
    player_unit_clone_rules,
    remove_locked_techlevel_actions,
    resolve_configured_helper_houses,
    stacked_house_buff_values,
    trigger_action_ids_by_name,
    unique_in_order,
    unit_weapon_buff_rules,
)
from randomizer_mission_houses import mission_house_config, mission_player_power_houses
from randomizer_mission_overrides import (
    MISSION_NATIVE_DIRECT_BUFF_EXCLUSIONS,
    MISSION_NATIVE_TECHNO_CLONE_EXCLUSIONS,
    MISSION_NATIVE_TECH_UNLOCK_IDS,
    MISSION_NATIVE_TRIGGER_REFERENCE_IDS,
    MISSION_NATIVE_VARIANT_BUFF_RULES,
    MISSION_REQUIRED_ACCESS_RULES,
    MISSION_REWARD_EXCLUDED_PLAYER_HOUSES,
    MISSION_SUPERWEAPON_TECHNO_CLONE_OVERRIDES,
    MISSION_TEAM_HOUSE_OVERRIDES,
    MISSION_TECHNO_BASE_RULES,
)
from randomizer_mission_safety import safe_build_countries
from randomizer_missions import normalize_faction
from randomizer_paths import DEBUG_LOG, GAME_ROOT, GENERATED_MAP_DIR
from randomizer_rewards import (
    BUFF_TARGETS,
    ENGINEER_UNIT_IDS,
    canonical_rewards,
    reward_display_name,
)


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
    excluded_player_houses = MISSION_REWARD_EXCLUDED_PLAYER_HOUSES.get(
        code, ()
    )

    source_path = self.extract_campaign_map(scenario)
    lines = read_text(source_path).splitlines()
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
    for section, values in mission_base_rules.items():
        rule_sections.setdefault(section, {}).update(values)
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
    launch_power_rewards = list(earned_rewards)
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
    installed_superweapon_types, installed_rule_sections = installed_rules_registry()
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
            values = rule_sections.get(section)
            if not values:
                continue
            values['Owner'] = safe_owners
            values['RequiredHouses'] = safe_owners
            values['ForbiddenHouses'] = denied_owners
    # Generic randomized ownership must not erase mission-authored recovery
    # access such as Power Hunger's native Burillo.
    for section, values in MISSION_REQUIRED_ACCESS_RULES.get(code, {}).items():
        rule_sections.setdefault(section, {}).update(values)
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
            # global type/weapon ownership guard even when a shared
            # country makes category multipliers unsafe.
            assistance_direct_rewards = mission_assistance_direct_rewards(
                assistance_unit_ids,
                assistance_stacks,
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
            excluded_player_houses=excluded_player_houses,
        )
        if clone_rule_sections:
            merge_ini_section_values(lines, clone_rule_sections)
            self.append_log(
                'Prepared isolated standalone player unit/defense clones for: '
                + ', '.join(cloned_unit_names)
                + '. Compatible helper references use the same buffed clones; native IDs remain buildable fallbacks.'
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
        native_variant_buff_config = MISSION_NATIVE_VARIANT_BUFF_RULES.get(code)
        if native_variant_buff_config:
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
    randomized_tech_ids = self.randomized_tech_ids()
    removed_techlevel_actions = remove_locked_techlevel_actions(
        lines,
        unlocked_tech_ids,
        randomized_tech_ids=randomized_tech_ids,
    )
    if removed_techlevel_actions:
        self.append_log(f'Removed {removed_techlevel_actions} native tech unlock action(s) blocked by the randomizer.')
    objective_action_ids = action_line_ids(
        lines,
        lambda groups: action_has_objective_complete(groups) and not action_has_code(groups, 1) and not action_has_code(groups, 67),
    )
    # Prefer a real Winner action over Announce Win. Some missions contain
    # both, and choosing whichever appears first can fire the marker during
    # an earlier victory announcement instead of the terminal win action.
    victory_action_ids = unique_in_order(
        action_line_ids(lines, lambda groups: action_has_code(groups, 1))
        + action_line_ids(lines, lambda groups: action_has_code(groups, 67))
        + trigger_action_ids_by_name(lines, ['[win]', '/win', 'mission victory', 'mission successful'])
    )
    checks = self.mission_checks(code) if self.state else []

    patch_plan = []
    objective_checks = [check for check in checks if check.get('id') != 'victory']
    for check, action_id in zip(objective_checks, objective_action_ids):
        if not check.get('unlocked'):
            patch_plan.append((check, action_id))

    victory_check = next((check for check in checks if check.get('id') == 'victory'), None)
    if victory_check and not victory_check.get('unlocked') and victory_action_ids:
        patch_plan.append((victory_check, victory_action_ids[0]))
    elif victory_check and not victory_check.get('unlocked'):
        self.append_log(f'No automatic victory hook found for {scenario}. Victory may not be recorded.', error=True)

    if not patch_plan and not rule_sections and not superweapon_trigger:
        self.append_log(f'No hookable objective/victory triggers found for {scenario}. Progress may not be recorded.')
        return None

    markers = {}
    for index, (check, action_id) in enumerate(patch_plan, start=1):
        marker = hook_marker_name(code, check.get('id', f'check_{index}'))
        team_id = f'RND{index:05d}'
        taskforce_id = f'RNT{index:05d}'
        script_id = f'RNS{index:05d}'
        marker_action = ['4', '1', team_id, '0', '0', '0', '0', 'A']
        if check.get('id') == 'victory':
            patched = insert_actions_before_codes(
                lines,
                action_id,
                [marker_action],
                before_codes=('1', '67', '69'),
            )
            # A name-based fallback may identify a victory action list
            # without one of the standard terminal codes. Preserve the
            # previous append behavior for those unusual maps.
            if not patched:
                patched = append_action_to_action_id(lines, action_id, marker_action)
        else:
            patched = append_action_to_action_id(lines, action_id, marker_action)
            if not patched:
                patched = append_parallel_global_hook(
                    lines,
                    action_id,
                    marker_action,
                    marker,
                )
        if patched:
            append_hook_team(
                lines,
                team_id,
                taskforce_id,
                script_id,
                marker,
                hook_house,
            )
            markers[marker] = check.get('id')
        else:
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
