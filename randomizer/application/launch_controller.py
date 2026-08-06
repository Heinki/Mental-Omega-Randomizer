"""Mission file preparation, game process control, and log watching."""

from ._dependencies import (
    ARSENAL_MODE,
    BUFF_TARGETS,
    DEBUG_LOG,
    DIFFICULTIES,
    DISABLED_RULESMO_INI,
    EXTRACTED_MAP_DIR,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    GAME_SPEEDS,
    GRID_COMPLETED,
    GRID_UNLOCKED,
    HOOK_POLL_MS,
    LOCKED_TECH_LEVEL,
    MAX_OPTION_INI_BYTES,
    MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS,
    MISSION_NATIVE_TECH_UNLOCK_IDS,
    MISSION_ORIGINAL_MCV_ACCESS_IDS,
    MISSION_REQUIRED_ACCESS_RULES,
    MISSION_SPECIAL_INFANTRY_FACTORY_EXCLUSIONS,
    NEXT_OBJECTIVE_CHECK_ID,
    NO_BUILD_MISSION_CODES,
    OPTIONS_INI,
    REWARD_POOL,
    RULESMO_INI,
    SCRIPTED_TECH_BUILD_LIMIT,
    SCRIPTED_TECH_LOCK_EXCLUSIONS,
    SPAWN_INI,
    STARTING_UNLOCKED_MISSIONS,
    VICTORY_CLOSE_DELAY_MS,
    YR_OPTIONS_INI,
    always_available_miner_rules,
    always_available_transport_rules,
    claim_runtime_asset_lease,
    chaos_earned_access_rules,
    choice_label_from_ini,
    controlled_tech_ids,
    deploy_generated_unit_art,
    is_generated_hooked_map,
    is_generated_rules_file,
    launch_rules_for_reward,
    log_event,
    logging,
    messagebox,
    mission_basic_unit_rules,
    original_mcv_access_rules,
    mission_player_production_houses,
    mix_reader_assembly_paths,
    patch_large_ini_key,
    powershell_mix_reader_load_script,
    prepare_hooked_mission_map,
    read_text,
    remove_generated_unit_art,
    set_ini_value_lines,
    shutil,
    single_engineer_rules,
    spawn_ini_text,
    starting_tier_one_defense_rules,
    starting_tier_one_rules,
    subprocess,
    summarize_basic_unit_rules,
    tech_ids_for_rewards,
    traceback,
)

class LaunchController:

    def unlocked_mission_codes(self):
        if not self.state:
            return [mission['code'] for mission in self.missions]

        if self.active_progression_mode() == 'Grid Mode':
            states = self.sync_grid_progression()
            return [
                code
                for code in self.state.get('mission_order', [])
                if states.get(code) in {GRID_UNLOCKED, GRID_COMPLETED}
            ]

        order = self.state.get('mission_order', [])
        completed_count = len(self.state.get('completed_missions', []))
        starting_count = self.state.get('starting_unlocked_missions', STARTING_UNLOCKED_MISSIONS)
        open_count = min(len(order), starting_count + completed_count)
        return order[:open_count]

    def get_selected_difficulty_value(self):
        return dict(DIFFICULTIES).get(self.difficulty_var.get(), 1)

    def get_selected_game_speed_value(self):
        return dict(GAME_SPEEDS).get(self.game_speed_var.get(), 3)

    def read_spawn_difficulty(self):
        return choice_label_from_ini(
            SPAWN_INI,
            'DifficultyModeHuman',
            DIFFICULTIES,
            default='Normal',
        )

    def read_spawn_game_speed(self):
        for path in (SPAWN_INI, OPTIONS_INI, YR_OPTIONS_INI):
            label = self.read_game_speed_from_ini(path)
            if label:
                return label
        return '3 - Medium'

    def read_game_speed_from_ini(self, path):
        return choice_label_from_ini(path, 'GameSpeed', GAME_SPEEDS)

    def spawn_reward_options(self):
        return {}

    def mission_required_launch_rules(self, mission):
        scenario = mission.get('scenario')
        if not scenario:
            return {}
        source_path = self.extract_campaign_map(scenario)
        lines = read_text(source_path).splitlines()
        starting_defense_ids = self.active_starting_tier_one_defense_ids()
        starting_unit_ids = self.active_starting_tier_one_unit_ids()
        production_houses = mission_player_production_houses(
            mission.get('code')
        )
        mission_required_rules = MISSION_REQUIRED_ACCESS_RULES.get(
            str(mission.get('code') or '').upper(),
            {},
        )
        mission_code = str(mission.get('code') or '').upper()
        excluded_special_infantry_factories = (
            MISSION_SPECIAL_INFANTRY_FACTORY_EXCLUSIONS.get(
                mission_code, ()
            )
        )

        def merge_required_rules(rules):
            miner_rules = always_available_miner_rules(
                lines,
                additional_build_houses=(),
            )
            for section, values in miner_rules.items():
                rules.setdefault(section, {}).update(values)

            mcv_rules = original_mcv_access_rules(
                lines,
                MISSION_ORIGINAL_MCV_ACCESS_IDS.get(mission_code, ()),
                additional_build_houses=(),
            )
            for section, values in mcv_rules.items():
                rules.setdefault(section, {}).update(values)

            already_available_ids = set(tech_ids_for_rewards(
                self.launch_rewards_for_mission(mission_code)
            ))
            already_available_ids.update(
                self.active_starting_tier_one_expanded_ids()
            )
            already_available_ids.update(
                self.active_starting_tier_one_defense_expanded_ids()
            )
            delayed_native_ids = {
                str(unit_id).upper()
                for unit_id in MISSION_NATIVE_TECH_UNLOCK_IDS.get(
                    mission_code, ()
                )
            } - already_available_ids
            if delayed_native_ids:
                if self.active_reward_mode() in {'Chaos', ARSENAL_MODE}:
                    delayed_rewards = [
                        reward
                        for reward in REWARD_POOL
                        if tech_ids_for_rewards([reward]).intersection(
                            delayed_native_ids
                        )
                    ]
                    delayed_rules = chaos_earned_access_rules(
                        lines,
                        delayed_rewards,
                        additional_build_houses=(),
                        excluded_special_infantry_factories=(
                            excluded_special_infantry_factories
                        ),
                    )
                else:
                    delayed_rules = mission_basic_unit_rules(
                        lines,
                        earned_access_ids=delayed_native_ids,
                        translate_equivalents=False,
                        additional_build_houses=(),
                        additional_production_houses=production_houses,
                        excluded_special_infantry_factories=(
                            excluded_special_infantry_factories
                        ),
                    )
                for unit_id in sorted(delayed_native_ids):
                    values = delayed_rules.get(unit_id)
                    if not values:
                        continue
                    values = dict(values)
                    values['TechLevel'] = LOCKED_TECH_LEVEL
                    rules.setdefault(unit_id, {}).update(values)

            if mission_code in MISSIONS_WITH_ALL_CONYARD_DEFENSE_ACCESS:
                # Juggernaut eventually hands the player an SMCV. Chaos may
                # share earned defenses across all Yards. Standard must keep
                # each mapped faction defense behind physical captured tech.
                earned_defense_rewards = [
                    reward
                    for reward in self.launch_rewards_for_mission(mission_code)
                    if reward.get('kind') not in {'buff', 'superweapon'}
                    and any(
                        BUFF_TARGETS.get(str(tech_id).upper(), {}).get('category')
                        == 'defenses'
                        for tech_id in reward.get('rules', {})
                    )
                ]
                if self.active_reward_mode() in {'Chaos', ARSENAL_MODE}:
                    defense_rules = chaos_earned_access_rules(
                        lines,
                        earned_defense_rewards,
                        additional_build_houses=(),
                        excluded_special_infantry_factories=(
                            excluded_special_infantry_factories
                        ),
                    )
                else:
                    defense_rules = mission_basic_unit_rules(
                        lines,
                        earned_access_ids=tech_ids_for_rewards(
                            earned_defense_rewards
                        ),
                        translate_equivalents=False,
                        additional_build_houses=(),
                        additional_production_houses=production_houses,
                        excluded_special_infantry_factories=(
                            excluded_special_infantry_factories
                        ),
                    )
                for section, values in defense_rules.items():
                    rules.setdefault(section, {}).update(values)
            for section, values in mission_required_rules.items():
                rules.setdefault(section, {}).update(values)
            return rules

        if self.active_reward_mode() in {'Chaos', ARSENAL_MODE}:
            chaos_access_rules = chaos_earned_access_rules(
                lines,
                self.launch_rewards_for_mission(mission_code),
                additional_build_houses=(),
                excluded_special_infantry_factories=(
                    excluded_special_infantry_factories
                ),
            )
            rules = {
                section: dict(values)
                for section, values in chaos_access_rules.items()
            }
            transport_rules = always_available_transport_rules(
                lines,
                chaos_mode=True,
                additional_build_houses=(),
            )
            for section, values in transport_rules.items():
                rules.setdefault(section, {}).update(values)
            engineer_rules = single_engineer_rules(
                lines,
                chaos_mode=True,
                additional_build_houses=(),
                excluded_special_infantry_factories=(
                    excluded_special_infantry_factories
                ),
            )
            for section, values in engineer_rules.items():
                rules.setdefault(section, {}).update(values)
            starter_rules = starting_tier_one_rules(
                lines,
                starting_unit_ids,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
                excluded_unit_ids=self.active_reward_settings().get(
                    'excluded_unit_access_ids', []
                ),
            )
            for section, values in starter_rules.items():
                rules.setdefault(section, {}).update(values)
            starter_defense_rules = starting_tier_one_defense_rules(
                lines,
                starting_defense_ids,
                chaos_mode=True,
                additional_build_houses=(),
                additional_production_houses=production_houses,
                excluded_unit_ids=self.active_reward_settings().get(
                    'excluded_unit_access_ids', []
                ),
            )
            for section, values in starter_defense_rules.items():
                rules.setdefault(section, {}).update(values)
            rules = merge_required_rules(rules)
            # Mission exceptions may add factories or remove limits, but they
            # must not narrow Chaos back to one faction's production. Reapply
            # every Chaos access family after those overrides. Standard never
            # enters this path and retains exact captured-faction gates.
            for chaos_rules in (
                chaos_access_rules,
                transport_rules,
                engineer_rules,
                starter_rules,
                starter_defense_rules,
            ):
                for section, values in chaos_rules.items():
                    rules.setdefault(section, {}).update(values)
            return rules
        # Earned access is identity-exact. An unlocked peer must never expose
        # another member of its role group merely because that faction's
        # factory is present (for example Sniper -> Desolator in SHBD or
        # Abrams -> Scavenger in EDIVER). Standard tier-one starters remain
        # abstract role selections and are resolved separately below.
        translate_equivalents = False
        earned_access_ids = (
            self.active_unlocked_reward_tech_ids()
            if self.randomize_unit_access_enabled()
            else controlled_tech_ids()
        )
        earned_access_ids.update(self.active_starting_tier_one_expanded_ids())
        rules = mission_basic_unit_rules(
            lines,
            earned_access_ids=earned_access_ids,
            translate_equivalents=translate_equivalents,
            additional_build_houses=(),
            additional_production_houses=production_houses,
            excluded_special_infantry_factories=(
                excluded_special_infantry_factories
            ),
        )
        transport_rules = always_available_transport_rules(
            lines,
            additional_build_houses=(),
        )
        for section, values in transport_rules.items():
            rules.setdefault(section, {}).update(values)
        standard_starter_families = self.active_standard_starter_families()
        starter_rules = starting_tier_one_rules(
            lines,
            starting_unit_ids,
            standard_families=standard_starter_families,
            additional_build_houses=(),
            additional_production_houses=production_houses,
            excluded_unit_ids=self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            ),
            allow_player_family_fallback=(
                mission_code not in NO_BUILD_MISSION_CODES
            ),
            include_capturable_production=translate_equivalents,
        )
        for section, values in starter_rules.items():
            rules.setdefault(section, {}).update(values)
        starter_defense_rules = starting_tier_one_defense_rules(
            lines,
            starting_defense_ids,
            standard_families=standard_starter_families,
            additional_build_houses=(),
            additional_production_houses=production_houses,
            excluded_unit_ids=self.active_reward_settings().get(
                'excluded_unit_access_ids', []
            ),
            allow_player_family_fallback=(
                mission_code not in NO_BUILD_MISSION_CODES
            ),
            include_capturable_production=translate_equivalents,
        )
        for section, values in starter_defense_rules.items():
            rules.setdefault(section, {}).update(values)
        rules = merge_required_rules(rules)
        for section, values in starter_defense_rules.items():
            rules.setdefault(section, {}).update(values)
        return rules

    def cleanup_generated_root_maps(self):
        for path in list(GAME_ROOT.glob('*.MAP')) + list(GAME_ROOT.glob('*.map')):
            if is_generated_hooked_map(path):
                result = subprocess.run(
                    [
                        'powershell',
                        '-NoProfile',
                        '-Command',
                        f"Remove-Item -LiteralPath '{str(path).replace(chr(39), chr(39) + chr(39))}' -Force",
                    ],
                    cwd=GAME_ROOT,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and callable(self.__dict__.get('append_log')) and 'log_text' in self.__dict__:
                    detail = (result.stderr or 'Remove-Item failed.').strip()
                    self.append_log(f'Could not remove generated hooked map {path.name}: {detail}', error=True)

    def extract_campaign_map(self, scenario):
        EXTRACTED_MAP_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EXTRACTED_MAP_DIR / scenario.upper()
        if output_path.exists():
            return output_path

        loose_root_map = GAME_ROOT / scenario
        if loose_root_map.exists():
            shutil.copy2(loose_root_map, output_path)
            return output_path

        assembly_paths = mix_reader_assembly_paths()
        if any(not path.exists() for path in assembly_paths):
            missing = ', '.join(path.name for path in assembly_paths if not path.exists())
            raise FileNotFoundError(f'Map Renderer dependency files are missing: {missing}.')

        mix_paths = sorted(GAME_ROOT.glob('expandmo*.mix'), reverse=True)
        if not mix_paths:
            raise FileNotFoundError('No expandmo*.mix archives found.')

        escaped_name = scenario.upper().replace("'", "''")
        escaped_output = str(output_path).replace("'", "''")
        escaped_mixes = [str(path).replace("'", "''") for path in mix_paths]
        mix_array = ','.join(f"'{path}'" for path in escaped_mixes)
        script = f"""
$ErrorActionPreference = 'Stop'
{powershell_mix_reader_load_script()}
$name = '{escaped_name}'
$output = '{escaped_output}'
foreach ($mixPath in @({mix_array})) {{
    $fs = [System.IO.File]::OpenRead($mixPath)
    try {{
        $mix = New-Object CNCMaps.FileFormats.MixFile($fs, [System.IO.Path]::GetFileName($mixPath), $false)
        if ($mix.ContainsFile($name)) {{
            $vf = $mix.OpenFile($name, [CNCMaps.FileFormats.FileFormat]::Ukn, [CNCMaps.FileFormats.VirtualFileSystem.CacheMethod]::NoCache)
            try {{
                $target = [System.IO.File]::Create($output)
                try {{ $vf.CopyTo($target) }} finally {{ $target.Dispose() }}
            }} finally {{
                if ($vf) {{ $vf.Dispose() }}
            }}
            Write-Output $mixPath
            exit 0
        }}
    }} finally {{
        $fs.Dispose()
    }}
}}
throw "Map $name was not found in expandmo*.mix"
"""
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            cwd=GAME_ROOT,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or 'Map extraction failed.').strip()
            log_event(
                'map_extraction_failed',
                level=logging.ERROR,
                scenario=scenario,
                returncode=result.returncode,
                stderr=result.stderr.strip(),
                stdout=result.stdout.strip(),
            )
            raise RuntimeError(detail)
        return output_path

    def randomized_tech_ids(self):
        if not self.randomize_unit_access_enabled():
            return set()
        include_defenses = bool(
            self.active_reward_settings().get('include_defensive_buildings', True)
        )
        include_special_buildings = bool(
            self.active_reward_settings().get('include_special_buildings', True)
        )
        include_special_rewards = bool(
            self.active_reward_settings().get('include_special_rewards', True)
        )
        return {
            section.upper()
            for section in controlled_tech_ids()
            if (
                include_defenses
                or BUFF_TARGETS.get(section.upper(), {}).get('category') != 'defenses'
            )
            and (
                include_special_buildings
                or BUFF_TARGETS.get(section.upper(), {}).get('category')
                != 'special_buildings'
            )
            and (
                include_special_rewards
                or not BUFF_TARGETS.get(section.upper(), {}).get('special_reward')
            )
        }

    def map_rules_for_launch(
        self,
        extra_rules=None,
        allowed_unlocked_tech_ids=None,
    ):
        rule_sections = {}
        randomized_tech_ids = self.randomized_tech_ids()
        allowed_unlocked = (
            None
            if allowed_unlocked_tech_ids is None
            else {
                str(unit_id).upper()
                for unit_id in allowed_unlocked_tech_ids
                if unit_id
            }
        )
        if randomized_tech_ids:
            for section in sorted(randomized_tech_ids):
                section_upper = section.upper()
                values = rule_sections.setdefault(section, {})
                values['BuildLimit'] = SCRIPTED_TECH_BUILD_LIMIT
                if section_upper not in SCRIPTED_TECH_LOCK_EXCLUSIONS:
                    values['TechLevel'] = LOCKED_TECH_LEVEL

            # Prepare ownership and basic production metadata for every access
            # item. BuildLimit keeps unearned tech out of player production
            # without preventing campaign scripts from spawning those units.
            # Earned access removes the limit on the next mission launch.
            for reward in REWARD_POOL:
                if reward.get('kind') == 'buff':
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    if section.upper() not in randomized_tech_ids:
                        continue
                    if (
                        allowed_unlocked is not None
                        and section.upper() not in allowed_unlocked
                    ):
                        continue
                    prepared_values = {
                        key: value
                        for key, value in values.items()
                        if key.lower() not in {'techlevel', 'buildlimit'}
                    }
                    rule_sections.setdefault(section, {}).update(prepared_values)

        if self.state:
            earned_rewards = self.earned_rewards_from_checks()
            self.state['earned_rewards'] = earned_rewards
            for reward in self.active_launch_rewards():
                if reward.get('kind') == 'buff' and reward.get('buff_type'):
                    continue
                for section, values in launch_rules_for_reward(reward).items():
                    if section.upper() not in randomized_tech_ids:
                        continue
                    if (
                        allowed_unlocked is not None
                        and section.upper() not in allowed_unlocked
                    ):
                        continue
                    section_rules = rule_sections.setdefault(section, {})
                    # Remove launcher-injected safety locks before applying an
                    # earned access reward. If the reward carries its own
                    # prerequisite override it is restored by the update.
                    section_rules.pop('BuildLimit', None)
                    section_rules.pop('PrerequisiteOverride', None)
                    section_rules.update(values)

        for section, values in (extra_rules or {}).items():
            section_rules = rule_sections.setdefault(section, {})
            if any(key.lower() == 'techlevel' for key in values):
                section_rules.pop('BuildLimit', None)
            section_rules.update(values)
        return rule_sections

    def prepare_hooked_map(self, mission, extra_rules=None):
        return prepare_hooked_mission_map(self, mission, extra_rules=extra_rules)

    def write_spawn_ini(self, scenario, difficulty_value, game_speed_value):
        try:
            SPAWN_INI.write_text(
                spawn_ini_text(
                    scenario,
                    difficulty_value,
                    game_speed_value,
                    self.spawn_reward_options(),
                ),
                encoding='utf-8',
            )
            self.append_log(
                f'Written spawn.ini: Scenario={scenario}, DifficultyModeHuman={difficulty_value}, '
                f'Difficulty={difficulty_value}, GameSpeed={game_speed_value}'
            )
        except Exception:
            self.append_log('Failed to write spawn.ini:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            raise

    def write_launch_options(self, difficulty_value, game_speed_value):
        try:
            written = []
            skipped = []
            for path in (OPTIONS_INI, YR_OPTIONS_INI):
                # Do not create option files that the installation does not
                # already use. Mental Omega normally provides RA2MO.ini;
                # RA2MD.INI is optional and was previously created needlessly.
                if not path.exists():
                    continue
                if path.exists() and path.stat().st_size > MAX_OPTION_INI_BYTES:
                    patched = self.patch_large_options_ini(
                        path,
                        {
                            'GameSpeed': game_speed_value,
                            'Difficulty': difficulty_value,
                            'CampDifficulty': difficulty_value,
                        },
                    )
                    if patched:
                        written.append(f'{path.name} (in-place)')
                    else:
                        skipped.append(f'{path.name} ({path.stat().st_size} bytes)')
                    continue
                text = read_text(path)
                text = set_ini_value_lines(text, 'Options', 'GameSpeed', game_speed_value)
                text = set_ini_value_lines(text, 'Options', 'Difficulty', difficulty_value)
                text = set_ini_value_lines(text, 'Options', 'CampDifficulty', difficulty_value)
                path.write_text(text, encoding='utf-8')
                written.append(path.name)

            if written:
                self.append_log(
                    f'Written {", ".join(written)}: GameSpeed={game_speed_value}, '
                    f'Difficulty={difficulty_value}, CampDifficulty={difficulty_value}'
                )
            if skipped:
                self.append_log(
                    'Skipped oversized option file(s): '
                    + ', '.join(skipped)
                    + '. GameSpeed and difficulty are still written to spawn.ini and other option files.'
                )
        except Exception:
            self.append_log('Failed to write launch options:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            raise

    def patch_large_options_ini(self, path, values):
        """Patch one-digit option values in oversized/corrupt INIs without rewriting them."""
        try:
            patched = []
            with path.open('r+b') as handle:
                for key, value in values.items():
                    if patch_large_ini_key(handle, key, value):
                        patched.append(key)
            missing = sorted(set(values) - set(patched))
            if missing:
                self.append_log(
                    f'{path.name}: could not in-place patch {", ".join(missing)} in oversized option file.',
                    error=True,
                )
            return len(patched) == len(values)
        except Exception:
            self.append_log(f'Failed to patch oversized option file {path.name}:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            return False

    def disable_generated_rules_for_client(self):
        for path in (RULESMO_INI, DISABLED_RULESMO_INI):
            if path.exists() and is_generated_rules_file(path):
                path.unlink()
        remove_generated_unit_art()

    def build_command(self):
        return f'"{GAME_LAUNCHER_EXE}" "{GAME_EXE.name}" -SPAWN -CD -SPEEDCONTROL -LOG'

    def process_hook_log_text(self, text):
        if not self.active_hook or not text:
            return

        code = self.active_hook['mission_code']
        markers = self.active_hook.get('markers', {})
        seen = self.active_hook.setdefault('seen', set())
        # A normal game startup emits more than one Init_Clear message before
        # the scenario becomes interactive. Only an Init_Clear that occurs
        # after Capture_Mouse marks a genuine in-game restart. Process the log
        # in order so startup messages in the same polling chunk are not
        # mistaken for failed attempts.
        for line in text.splitlines():
            for marker, check_id in markers.items():
                if marker in seen or marker not in line:
                    continue
                seen.add(marker)
                if check_id == NEXT_OBJECTIVE_CHECK_ID:
                    event_index = self.active_hook.setdefault(
                        'objective_events_seen',
                        0,
                    )
                    self.active_hook['objective_events_seen'] = event_index + 1
                    if event_index < self.active_hook.get(
                        'completed_objective_checks',
                        0,
                    ):
                        continue
                    next_check = next(
                        (
                            check for check in self.mission_checks(code)
                            if check.get('id') != 'victory'
                            and not check.get('unlocked')
                        ),
                        None,
                    )
                    if next_check:
                        self.unlock_mission_check(
                            code,
                            next_check['id'],
                            'In-game objective completion',
                        )
                    continue

                unlocked = self.unlock_mission_check(
                    code,
                    check_id,
                    'In-game hook',
                )
                if check_id == 'victory' and unlocked:
                    self.schedule_game_close_after_victory()

            if 'MapClass::Init_Clear entry' in line:
                if self.active_hook.get('scenario_ready'):
                    self.active_hook['scenario_ready'] = False
                    if not self.is_mission_complete(code):
                        self.record_failed_mission_attempt(code, 'In-game mission restart detected')
            elif 'Capture_Mouse()' in line:
                self.active_hook['scenario_ready'] = True

    def schedule_game_close_after_victory(self):
        hook = self.active_hook
        process = self.active_game_process
        if hook is None or process is None or hook.get('victory_close_scheduled'):
            return
        hook['victory_close_scheduled'] = True
        self.append_log(
            f'Victory detected. Closing the spawned game in {VICTORY_CLOSE_DELAY_MS / 1000:g} seconds '
            'to prevent campaign continuation.'
        )
        self.after(
            VICTORY_CLOSE_DELAY_MS,
            lambda: self.close_game_after_victory(process, hook),
        )

    def close_game_after_victory(self, process, hook):
        # Do not close a later mission if the player managed to launch another
        # game during the short victory delay.
        if self.active_game_process is not process or self.active_hook is not hook:
            return
        if process.poll() is not None:
            return

        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/T', '/F'],
            cwd=GAME_ROOT,
            capture_output=True,
            text=True,
            creationflags=creation_flags,
        )
        if result.returncode == 0:
            self.append_log('Closed the spawned game after victory.')
            return

        # taskkill should close Syringe and gamemd as one tree. Keep a direct
        # process fallback for unusual Windows environments where it is absent.
        try:
            process.terminate()
            self.append_log('Closed the game launcher process after victory.')
        except OSError as exc:
            detail = (result.stderr or result.stdout or str(exc)).strip()
            self.append_log(f'Could not close the game after victory: {detail}', error=True)

    def poll_hook_log(self):
        if self.active_hook and DEBUG_LOG.exists():
            try:
                size = DEBUG_LOG.stat().st_size
                offset = self.active_hook.get('offset', 0)
                if size < offset:
                    offset = 0
                    # A truncated/recreated debug log starts a new startup
                    # sequence. Do not carry an earlier Capture_Mouse state
                    # across that boundary or the first Init_Clear in the new
                    # file is misclassified as an in-game restart.
                    self.active_hook['scenario_ready'] = False
                with DEBUG_LOG.open('r', encoding='utf-8', errors='ignore') as handle:
                    handle.seek(offset)
                    text = handle.read()
                    self.active_hook['offset'] = handle.tell()
                self.process_hook_log_text(text)
            except OSError as exc:
                self.append_log(f'Hook log read failed: {exc}', error=True)

        process = self.active_game_process
        if process is not None and process.poll() is None:
            self.after(HOOK_POLL_MS, self.poll_hook_log)
            return

        if self.active_hook:
            scenario = self.active_hook.get('scenario', 'mission')
            seen_count = len(self.active_hook.get('seen', set()))
            marker_count = len(self.active_hook.get('markers', {}))
            self.append_log(f'Hook watcher stopped for {scenario}. Seen {seen_count}/{marker_count} marker(s).')
            log_event(
                'mission_process_finished',
                code=self.active_hook.get('mission_code'),
                scenario=scenario,
                process_returncode=process.poll() if process is not None else None,
                markers_seen=seen_count,
                markers_expected=marker_count,
                completed=self.is_mission_complete(self.active_hook.get('mission_code')),
            )
        attempt = self.active_mission_attempt or {}
        attempt_code = attempt.get('mission_code')
        if attempt_code and not self.is_mission_complete(attempt_code):
            self.record_failed_mission_attempt(attempt_code, 'Mission closed without victory')
        self.active_hook = None
        self.active_game_process = None
        self.active_mission_attempt = None
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()
        if getattr(self, '_close_after_game', False):
            self.destroy()

    def launch_mission_async(self, mission, extra_rules=None, launch_note=''):
        missing = [path for path in (GAME_LAUNCHER_EXE, GAME_EXE) if not path.exists()]
        if missing:
            self.append_log('Missing launch executable(s): ' + ', '.join(str(path) for path in missing), error=True)
            return

        scenario = mission.get('scenario')
        if not scenario:
            self.append_log('Mission scenario is missing.', error=True)
            return

        difficulty_value = self.get_selected_difficulty_value()
        game_speed_value = self.get_selected_game_speed_value()
        self.run_in_background(
            'Starting game, please wait…',
            'Preparing the mission and applying earned rewards.',
            lambda: self.prepare_mission_launch_files(
                mission,
                extra_rules,
                difficulty_value,
                game_speed_value,
            ),
            lambda hook: self.start_mission_process(
                mission,
                hook,
                difficulty_value,
                game_speed_value,
                launch_note,
            ),
            self.handle_mission_prepare_error,
        )

    def handle_mission_prepare_error(self, _exc, detail):
        self.cleanup_generated_root_maps()
        self.disable_generated_rules_for_client()
        self.append_log(detail, error=True)
        messagebox.showerror('Launch Failed', 'Failed to write launch files. See log for details.')

    def prepare_mission_launch_files(
        self,
        mission,
        extra_rules,
        difficulty_value,
        game_speed_value,
    ):
        scenario = mission['scenario']
        try:
            # Loose generated rulesmo.ini files can crash spawned missions or make
            # the MO client reject the install. Keep rewards in launcher state
            # until we have a safe map-specific injection path.
            self.disable_generated_rules_for_client()
            self.cleanup_generated_root_maps()
            claim_runtime_asset_lease()
            launch_rules = {}
            for section, values in (extra_rules or {}).items():
                launch_rules.setdefault(section, {}).update(values)
            mission_required_rules = self.mission_required_launch_rules(mission)
            if mission_required_rules:
                for section, values in mission_required_rules.items():
                    launch_rules.setdefault(section, {}).update(values)
                self.append_log(
                    'Applied mission production access for '
                    + mission['code']
                    + ': '
                    + summarize_basic_unit_rules(mission_required_rules)
                    + '.'
                )
            hook = None
            try:
                hook = self.prepare_hooked_map(mission, extra_rules=launch_rules)
            except Exception:
                self.append_log('Objective hook preparation failed; launching without automatic objective detection.', error=True)
                self.append_log(traceback.format_exc(), error=True)
                self.cleanup_generated_root_maps()
            if hook and hook.get('root_map'):
                try:
                    art_path, art_aliases = deploy_generated_unit_art(
                        hook['root_map']
                    )
                    if art_path:
                        self.append_log(
                            'Prepared temporary unit cameo art for: '
                            + ', '.join(sorted(art_aliases))
                            + '.'
                        )
                except Exception:
                    self.append_log(
                        'Could not prepare temporary unit cameo art; '
                        'existing custom art was left untouched.',
                        error=True,
                    )
                    self.append_log(traceback.format_exc(), error=True)
            self.write_spawn_ini(scenario, difficulty_value, game_speed_value)
            self.write_launch_options(difficulty_value, game_speed_value)
        except Exception:
            self.cleanup_generated_root_maps()
            self.disable_generated_rules_for_client()
            raise
        return hook

    def start_mission_process(
        self,
        mission,
        hook,
        difficulty_value,
        game_speed_value,
        launch_note='',
    ):
        scenario = mission['scenario']
        cmd = self.build_command()
        self.append_log('Attempting game launch via: ' + cmd)

        try:
            process = subprocess.Popen(cmd, cwd=GAME_ROOT)
            self.append_log(f'Launched game process PID={process.pid}.')
            if self.state and mission.get('code') in self.state.get('mission_order', []):
                try:
                    started_missions = self.state.setdefault('started_missions', [])
                    if mission['code'] not in started_missions:
                        started_missions.append(mission['code'])
                        self.save_state()
                        self.redraw_mission_tree()
                        self.refresh_progress_view()
                except Exception:
                    self.append_log('Could not persist the mission in-progress state.', error=True)
                    log_event(
                        'mission_started_state_save_failed',
                        level=logging.ERROR,
                        code=mission.get('code'),
                        traceback=traceback.format_exc(),
                    )
            log_event(
                'mission_process_started',
                pid=process.pid,
                code=mission.get('code'),
                title=mission.get('title'),
                scenario=scenario,
                command=cmd,
                difficulty=difficulty_value,
                game_speed=game_speed_value,
                hook_markers=(hook or {}).get('markers', {}),
                generated_map=(hook or {}).get('generated_map'),
            )
            if launch_note:
                self.append_log(launch_note)
            self.active_game_process = process
            self.active_hook = hook
            if self.active_hook is not None:
                self.active_hook['scenario_ready'] = False
            self.active_mission_attempt = {
                'mission_code': mission.get('code'),
                'scenario': scenario,
            }
            self.after(HOOK_POLL_MS, self.poll_hook_log)
        except Exception:
            self.cleanup_generated_root_maps()
            self.disable_generated_rules_for_client()
            self.append_log('Failed to launch game process:', error=True)
            self.append_log(traceback.format_exc(), error=True)
            messagebox.showerror('Launch Failed', 'Failed to launch the game. See log for details.')
        else:
            self.append_log(
                'Objective/victory hooks are watching debug.log. A detected victory will update the run automatically.'
            )
