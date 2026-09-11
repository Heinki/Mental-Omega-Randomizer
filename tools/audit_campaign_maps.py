"""Generate and validate every installed Mental Omega campaign map.

This maintainer audit enables Yuri Prime, every configured Shop mission boon,
the composed Shop combat/economy modifiers, and maximum Tier 1 AI reward
stacks. It exercises those paths across the full campaign without starting Tk
or the game.
"""

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.application.launch_controller import LaunchController
from randomizer.application.advanced_settings import AdvancedSettingsController
from randomizer.config.player import DEFAULT_CONFIG
from randomizer.core.paths import BATTLE_CLIENT_INI, GENERATED_MAP_DIR
from randomizer.maps._shared import (
    all_section_value_maps_preserve,
    section_value_map_preserve,
)
from randomizer.maps.base import is_generated_hooked_map
from randomizer.maps.ini import parse_action_groups
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import (
    REWARD_POOL,
    canonical_reward,
)
from randomizer.rewards.enemy_scaling import ENEMY_BUFF_DEFINITIONS
from randomizer.rewards.rules import unlocked_reward_tech_ids
from randomizer.rewards.definitions import linked_buff_variant_ids
from randomizer.shop.mission_modifiers import MISSION_MODIFIERS
from randomizer.ui.cameos import installed_rules_registry


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _HookAudit(LaunchController):
    def __init__(self):
        self.active_hook = {
            'mission_code': 'AREDDAWN',
            'markers': {'MOR_AREDDAWN_VIC': 'victory'},
            'seen': set(),
            'scenario_ready': False,
        }
        self.completed = False
        self.failures = []
        self.close_scheduled = False

    def is_mission_complete(self, _code):
        return self.completed

    def unlock_mission_check(self, _code, check_id, _source):
        if check_id != 'victory' or self.completed:
            return False
        self.completed = True
        return True

    def schedule_game_close_after_victory(self):
        self.close_scheduled = True

    def record_failed_mission_attempt(self, code, source):
        self.failures.append((code, source))
        return True


class _AuditLauncher(LaunchController):
    def __init__(
        self,
        reward_mode='Chaos',
        progression_mode='Shop Mode',
        enemy_effect_ids=None,
    ):
        self._reward_mode = reward_mode
        self._progression_mode = progression_mode
        self.config = deepcopy(DEFAULT_CONFIG)
        self.config['generation']['reward_mode'] = reward_mode
        self.state = {}
        self.player_color_var = _Value('Default')
        self.rainbowizer_var = _Value(False)
        self.eva_voice_var = _Value('Mission default')
        self.logs = []
        self.enemy_applications = {}
        reward_by_name = {
            reward.get('name'): reward for reward in REWARD_POOL
            if reward.get('name')
        }
        player_reward_ids = [
            'Epsilon Elite Access',
            'GI Access',
            'GI Firepower I',
            'GI Armor Plating I',
            'Gear Change Power',
            'Industrial Plant Access',
            'Rhino Heavy Tank Access',
            "Stalin's Fist Access",
            "Stalin's Fist Drill I",
            "Stalin's Fist Logistics I",
            "Stalin's Fist Mobility I",
            "Stalin's Fist Armor Plating I",
            "Stalin's Fist Reinforced Frames I",
            "Stalin's Fist Recon Package I",
            "Stalin's Fist Stealth Systems I",
            "Stalin's Fist Sensor Suite I",
            'Stinger Access',
            'Tanya Access',
        ]
        for modifier in MISSION_MODIFIERS:
            player_reward_ids.extend(modifier.player_reward_ids)
        self.player_rewards = [
            canonical_reward(reward_by_name[reward_id])
            for reward_id in player_reward_ids
        ]
        self.enemy_entries = []
        selected_enemy_effect_ids = (
            None
            if enemy_effect_ids is None
            else {str(effect_id) for effect_id in enemy_effect_ids}
        )
        for definition in ENEMY_BUFF_DEFINITIONS:
            if (
                selected_enemy_effect_ids is None
                and not str(definition['id']).startswith('tier1_')
            ) or (
                selected_enemy_effect_ids is not None
                and definition['id'] not in selected_enemy_effect_ids
            ):
                continue
            reward = canonical_reward({'name': definition['name']})
            for _stack in range(int(definition['maximum_stacks'])):
                self.enemy_entries.append({
                    'reward': reward,
                    'source': 'all-map audit',
                    'earned_from': 'maximum configured stack audit',
                })

    def append_log(self, message, error=False):
        self.logs.append((bool(error), str(message)))

    def randomizer_launch_active(self):
        return True

    def randomize_unit_access_enabled(self):
        return True

    def active_launch_campaign_filter(self):
        return 'All Campaigns'

    def active_reward_mode(self):
        return self._reward_mode

    def active_progression_mode(self):
        return self._progression_mode

    def active_reward_settings(self):
        settings = dict(self.config['generation'])
        settings.update({
            'shop_player_damage_percent': 1.25,
            'shop_player_armor_percent': 0.8,
            'shop_production_time_percent': 0.75,
            'shop_combat_production_time_percent': 1.2,
            'shop_player_cost_percent': 1.2,
            'shop_mission_starting_credits_flat': -3000,
        })
        return settings

    def active_launch_seed(self):
        return 'ALL-MAP-AUDIT'

    def active_launch_rewards(self):
        return list(self.player_rewards)

    def launch_rewards_for_mission(self, _code):
        return list(self.player_rewards)

    def mission_effective_unlocked_tech_ids(
        self, _mission, _lines, additional_tech_ids=()
    ):
        return set(unlocked_reward_tech_ids(self.player_rewards)).union(
            str(unit_id).upper() for unit_id in additional_tech_ids
        )

    def active_enemy_scaling_entries(self):
        return list(self.enemy_entries)

    def mission_failure_stack(self, _code):
        return 0

    def failure_assistance_enabled(self):
        return False

    def share_chaos_role_buffs_enabled(self):
        return False

    def mission_checks(self, _code):
        return []

    def cache_mission_assistance_units(self, _code, _unit_ids):
        return None

    def record_enemy_reward_applications(self, code, applications):
        self.enemy_applications[code] = deepcopy(applications)

    def active_starting_rewards_for_report(self):
        return []

    def active_progression_rewards_for_report(self):
        return list(self.player_rewards)

    def active_starting_tier_one_expanded_ids(self):
        return ()

    def active_starting_tier_one_defense_expanded_ids(self):
        return ()

    def active_starting_tier_one_unit_ids(self):
        return ()

    def active_starting_tier_one_defense_ids(self):
        return ()

    def active_standard_starter_families(self):
        return ()

    def active_unlocked_reward_tech_ids(self):
        return unlocked_reward_tech_ids(self.player_rewards)

    def launch_state_document(self):
        return {
            'seed': 'ALL-MAP-AUDIT',
            'campaign_filter': 'All Campaigns',
            'progression_mode': self._progression_mode,
            'earned_rewards': self.player_rewards,
        }


def _assert_mermaid_tanya(path, context):
    mermaid_lines = path.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    tanya = section_value_map_preserve(mermaid_lines, 'TANY')
    forbidden = next(
        (
            str(value).upper()
            for key, value in tanya.items()
            if str(key).lower() == 'factoryowners.forbidden'
        ),
        '',
    )
    if 'MORPLAYER' in forbidden.split(','):
        raise AssertionError(
            f'ASIREN native TANY received the player production gate in {context}'
        )


def _assert_hook_restart_race():
    watcher = _HookAudit()
    watcher.process_hook_log_text(
        'Capture_Mouse()\nMapClass::Init_Clear entry\n'
    )
    if watcher.failures or 'restart_detected_at' not in watcher.active_hook:
        raise AssertionError('AREDDAWN restart was not deferred for its victory marker')
    watcher.process_hook_log_text('Team MOR_AREDDAWN_VIC created\n')
    if (
        watcher.failures
        or not watcher.completed
        or not watcher.close_scheduled
        or 'restart_detected_at' in watcher.active_hook
    ):
        raise AssertionError('AREDDAWN late victory marker lost the teardown race')

    actual_restart = _HookAudit()
    actual_restart.process_hook_log_text(
        'Capture_Mouse()\nMapClass::Init_Clear entry\n'
    )
    actual_restart.active_hook['restart_detected_at'] -= 60
    if not actual_restart.process_pending_restart_failure():
        raise AssertionError('A genuine in-game restart was not recorded')
    if len(actual_restart.failures) != 1:
        raise AssertionError('A genuine restart produced the wrong failure count')


def _assert_targeted_contracts(generated_paths):
    installed_superweapons, _installed_sections = installed_rules_registry(
        synchronous=True
    )
    independent_prototypes = (
        'JACKAL', 'JACKALP',
        'DIVER', 'DIVERP',
        'TARCHIA', 'TARCHIAP',
    )
    for unit_id in independent_prototypes:
        linked_ids = linked_buff_variant_ids(unit_id)
        if linked_ids != frozenset({unit_id}):
            raise AssertionError(
                f'{unit_id} incorrectly shares direct buffs with {sorted(linked_ids)}'
            )
    advanced_ids = {
        entry['id']
        for entry in AdvancedSettingsController.advanced_unit_pool_entries(
            object()
        )
    }
    missing_prototypes = set(independent_prototypes) - advanced_ids
    if missing_prototypes:
        raise AssertionError(
            'Advanced access pool omitted independent units: '
            + ', '.join(sorted(missing_prototypes))
        )

    mermaid = next(
        path for path in generated_paths if path.name.upper() == 'ASIREN.MAP'
    )
    _assert_mermaid_tanya(mermaid, 'Shop Mode/Chaos')

    scrapyard = next(
        path for path in generated_paths if path.name.upper() == 'ESCRAP.MAP'
    )
    scrapyard_lines = scrapyard.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    scrapyard_events = section_value_map_preserve(scrapyard_lines, 'Events')
    stinger_loss = str(scrapyard_events.get('01000028', '')).split(',')
    if len(stinger_loss) < 5 or stinger_loss[4].upper() != 'STING':
        raise AssertionError(
            'ESCRAP Event 01000028 no longer watches native story STING'
        )
    stalins_fist_loss = str(
        scrapyard_events.get('01000032', '')
    ).split(',')
    if (
        len(stalins_fist_loss) < 9
        or stalins_fist_loss[4].upper() != 'MWF'
        or stalins_fist_loss[8].upper() != 'NAFIST'
    ):
        raise AssertionError(
            'ESCRAP Event 01000032 no longer watches native story '
            'MWF/NAFIST'
        )
    scrapyard_units = section_value_map_preserve(scrapyard_lines, 'Units')
    if not any(
        len(tokens) >= 2
        and tokens[0].lower() == 'scorpioncell house'
        and tokens[1].upper() == 'MWF'
        for value in scrapyard_units.values()
        if (tokens := [token.strip() for token in str(value).split(',')])
    ):
        raise AssertionError(
            'ESCRAP starting Stalin\'s Fist no longer uses native MWF'
        )
    stalins_fist_taskforce = section_value_map_preserve(
        scrapyard_lines, '01000321'
    )
    if not any(
        len(tokens) >= 2 and tokens[1].upper() == 'MWF'
        for value in stalins_fist_taskforce.values()
        if (tokens := [token.strip() for token in str(value).split(',')])
    ):
        raise AssertionError(
            'ESCRAP scripted Stalin\'s Fist no longer uses native MWF'
        )
    player_stalins_fist = section_value_map_preserve(
        scrapyard_lines, 'MORPMWF'
    )
    if (
        player_stalins_fist.get('Speed') != '6'
        or str(player_stalins_fist.get('Cloakable')).lower() != 'yes'
        or str(player_stalins_fist.get('Sensors')).lower() != 'yes'
    ):
        raise AssertionError(
            'ESCRAP isolated player Stalin\'s Fist lost its earned buffs'
        )

    shipwrecked = next(
        path for path in generated_paths if path.name.upper() == 'ESHIP.MAP'
    )
    ship_lines = shipwrecked.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    humvee = section_value_map_preserve(ship_lines, 'AHMV')
    if any(
        str(value).upper().startswith('MORE1AHMV')
        for key, value in humvee.items()
        if str(key).lower() in {'primary', 'eliteprimary'}
    ):
        raise AssertionError('ESHIP hostile AHMV received a tier weapon clone')


    for mission_code in ('ESHIP', 'SHBD', 'SEXIST'):
        path = next(
            candidate for candidate in generated_paths
            if candidate.name.upper() == f'{mission_code}.MAP'
        )
        lines = path.read_text(
            encoding='utf-8', errors='ignore'
        ).splitlines()
        industrial_plant_ids = [
            str(type_id)
            for type_id in section_value_map_preserve(
                lines, 'BuildingTypes'
            ).values()
            if str(type_id).upper().startswith('MORPNAINDP')
        ]
        if len(industrial_plant_ids) != 1:
            raise AssertionError(
                f'{mission_code} has no unique registered Industrial Plant clone'
            )
        industrial_plant = section_value_map_preserve(
            lines, industrial_plant_ids[0]
        )
        gear_change = section_value_map_preserve(lines, 'MORGearChange')
        gear_spawner = section_value_map_preserve(lines, 'MORGearSpawner')
        gear_warhead = section_value_map_preserve(lines, 'MORGearWH')
        if any(
            industrial_plant.get(key)
            for key in ('SuperWeapon', 'SuperWeapon2', 'SuperWeapons')
        ):
            raise AssertionError(
                f'{mission_code} Industrial Plant still grants Gear Change'
            )
        if (
            gear_change.get('HunterSeeker.Type') != 'MORGearSpawner'
            or gear_change.get('HunterSeeker.Buildings') != 'MORGearProvider'
            or gear_change.get('SW.AuxBuildings')
        ):
            raise AssertionError(
                f'{mission_code} private Gear Change lacks portable providers'
            )
        required_factions = {'UnitedStates', 'USSR', 'PsiCorps', 'Guild1'}
        if not required_factions.issubset(
            str(gear_spawner.get('Owner') or '').split(',')
        ):
            raise AssertionError(
                f'{mission_code} Gear Change spawner rejects a faction'
            )
        if (
            gear_warhead.get('Versus.fact') != '3%'
            or str(gear_warhead.get('AffectsOwner')).lower() != 'yes'
        ):
            raise AssertionError(
                f'{mission_code} Gear Change no longer disables owned War Factories'
            )
        runtime_superweapons = []
        seen_superweapons = set()
        for power_id in (
            *installed_superweapons,
            *section_value_map_preserve(lines, 'SuperWeaponTypes').values(),
        ):
            normalized = str(power_id).lower()
            if normalized not in seen_superweapons:
                seen_superweapons.add(normalized)
                runtime_superweapons.append(str(power_id))
        gear_index = next(
            (
                index for index, power_id in enumerate(runtime_superweapons)
                if power_id.lower() == 'morgearchange'
            ),
            None,
        )
        gear_granted = any(
            group[0] == '34' and group[2] == str(gear_index)
            for action in section_value_map_preserve(lines, 'Actions').values()
            for _count, groups in (parse_action_groups(action),)
            for group in groups
        )
        if gear_index is None or not gear_granted:
            raise AssertionError(
                f'{mission_code} Gear Change lacks an action-34 grant'
            )
        if mission_code in {'SHBD', 'SEXIST'} and 'MORPNAFIST' not in (
            _mission_prerequisites(
                section_value_map_preserve(lines, 'MORPHTNK')
            )
        ):
            raise AssertionError(
                f'{mission_code} Rhino lacks deployed Stalin\'s Fist factory path'
            )

    for mission_code in ('EACCEL', 'AREDDAWN', 'SHBD'):
        path = next(
            candidate for candidate in generated_paths
            if candidate.name.upper() == f'{mission_code}.MAP'
        )
        lines = path.read_text(
            encoding='utf-8', errors='ignore'
        ).splitlines()
        airborne = section_value_map_preserve(lines, 'MORAmericanParaDrop')
        payload_ids = [
            type_id.strip()
            for type_id in str(airborne.get('ParaDrop.Types') or '').split(',')
            if type_id.strip()
        ]
        guardian_ids = [
            type_id for type_id in payload_ids
            if section_value_map_preserve(lines, type_id).get('Image') == 'GGI2'
        ]
        if len(guardian_ids) != 1:
            raise AssertionError(
                f'{mission_code} Airborne lacks one Guardian GI player clone'
            )
        guardian_id = guardian_ids[0]
        guardian = section_value_map_preserve(lines, guardian_id)
        if (
            str(guardian.get('Selectable') or '').lower() == 'no'
            or str(guardian.get('IsSelectableCombatant') or '').lower() != 'yes'
        ):
            raise AssertionError(
                f'{mission_code} Airborne Guardian GI is uncontrollable'
            )
        if mission_code == 'AREDDAWN' and not any(
            len(tokens) >= 2
            and tokens[0].lower() == 'unitedstates house'
            and tokens[1].upper() == guardian_id.upper()
            for value in section_value_map_preserve(lines, 'Infantry').values()
            if (tokens := [token.strip() for token in str(value).split(',')])
        ):
            raise AssertionError(
                'AREDDAWN starting Guardian GIs do not use the selectable clone'
            )

    yuri_prime_maps = 0
    for path in generated_paths:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        values = section_value_map_preserve(lines, 'MORPYURIPR')
        if not values:
            continue
        yuri_prime_maps += 1
        cloneable = next(
            (
                value for key, value in values.items()
                if str(key).lower() == 'cloneable'
            ),
            '',
        )
        if str(cloneable).lower() != 'no':
            raise AssertionError(f'{path.name} has cloneable MORPYURIPR')
    if not yuri_prime_maps:
        raise AssertionError('No generated map contained MORPYURIPR')

    for path in generated_paths:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        sections = all_section_value_maps_preserve(lines)
        sections_by_lower = {
            str(section).lower(): values
            for section, values in sections.items()
        }
        enemy_weapon_ids = [
            str(value)
            for value in sections_by_lower.get('weapontypes', {}).values()
            if str(value).upper().startswith('MORE')
        ]
        for weapon_id in enemy_weapon_ids:
            values = sections_by_lower.get(weapon_id.lower(), {})
            missing = [
                key for key in ('Projectile', 'Warhead') if key not in values
            ]
            if missing:
                raise AssertionError(
                    f'{path.name} enemy weapon {weapon_id} lacks exact-cased '
                    f'{", ".join(missing)}'
                )


def _assert_mermaid_mode_matrix(missions):
    mermaid = next(mission for mission in missions if mission['code'] == 'ASIREN')
    for progression_mode in ('Mission List', 'Grid Mode', 'Shop Mode'):
        for reward_mode in ('Standard', 'Chaos'):
            launcher = _AuditLauncher(
                reward_mode=reward_mode,
                progression_mode=progression_mode,
            )
            allowed = unlocked_reward_tech_ids(launcher.player_rewards)
            extra_rules = launcher.map_rules_for_launch(
                allowed_unlocked_tech_ids=allowed
            )
            hook = launcher.prepare_hooked_map(mermaid, extra_rules=extra_rules)
            if hook is None:
                raise AssertionError(
                    f'No ASIREN map for {progression_mode}/{reward_mode}'
                )
            generated_path = GENERATED_MAP_DIR / mermaid['scenario'].upper()
            _assert_mermaid_tanya(
                generated_path,
                f'{progression_mode}/{reward_mode}',
            )
            root_map = Path(hook['root_map'])
            if root_map.is_file() and is_generated_hooked_map(root_map):
                root_map.unlink()


def _assert_reported_mission_mode_matrix(missions):
    """Check the Remnant unlock and Parasomnia safety with full AI rewards."""
    for progression_mode in ('Mission List', 'Grid Mode', 'Shop Mode'):
        for reward_mode in ('Standard', 'Chaos'):
            launcher = _AuditLauncher(
                reward_mode=reward_mode,
                progression_mode=progression_mode,
                enemy_effect_ids=[item['id'] for item in ENEMY_BUFF_DEFINITIONS],
            )
            for code in ('FREMNANT', 'ASOMNIA'):
                mission = next(item for item in missions if item['code'] == code)
                context = f'{code}/{progression_mode}/{reward_mode}'
                source = all_section_value_maps_preserve(
                    launcher.extract_campaign_map(mission['scenario'])
                    .read_text(encoding='utf-8-sig').splitlines()
                )
                rules = launcher.map_rules_for_launch(
                    allowed_unlocked_tech_ids=unlocked_reward_tech_ids(
                        launcher.player_rewards
                    )
                )
                for section, values in launcher.mission_required_launch_rules(
                    mission
                ).items():
                    rules.setdefault(section, {}).update(values)
                hook = launcher.prepare_hooked_map(mission, extra_rules=rules)
                if hook is None:
                    raise AssertionError(f'No generated map for {context}')
                path = GENERATED_MAP_DIR / mission['scenario'].upper()
                sections = all_section_value_maps_preserve(
                    path.read_text(encoding='utf-8-sig').splitlines()
                )
                if code == 'ASOMNIA':
                    if launcher.enemy_applications.get(code) != []:
                        raise AssertionError(f'AI scaling broke opening safety: {context}')
                    if not any(
                        f'Skipped all configured AI scaling rewards for {code}:' in msg
                        for _error, msg in launcher.logs
                    ):
                        raise AssertionError(f'Missing opening-safety log: {context}')
                else:
                    action_id = '01000302'
                    if sections['Actions'][action_id] != source['Actions'][action_id]:
                        raise AssertionError(f'MCV announcement/unlock changed: {context}')
                    _, actions = parse_action_groups(sections['Actions'][action_id])
                    unlocks = {group[2]: int(group[7]) for group in actions if group[0] == '106'}
                    player_level = int(sections['Guild3 House']['TechLevel'])
                    registered = set(sections.get('VehicleTypes', {}).values())
                    for unit_id in ('AMCV', 'SMCV'):
                        values = sections[unit_id]
                        if not int(values['TechLevel']) > player_level >= unlocks[unit_id]:
                            raise AssertionError(f'{unit_id} lost delayed unlock: {context}')
                        for field in ('ForbiddenHouses', 'FactoryOwners.Forbidden'):
                            denied = set(str(values.get(field, '')).lower().split(','))
                            if denied.intersection({'guild3', 'morplayer'}):
                                raise AssertionError(f'{unit_id} player production forbidden: {context}')
                        # Standard can prepare a locked reference counterpart
                        # through the Construction Yard's linked buff family.
                        # Only the native MCV may become buildable at unlock.
                        clone_id = 'MORP' + unit_id
                        if clone_id in registered:
                            clone_level = int(sections[clone_id]['TechLevel'])
                            if 0 <= clone_level <= player_level:
                                raise AssertionError(f'{unit_id} duplicate MCV production: {context}')
                            for value in sections.get('Actions', {}).values():
                                _, groups = parse_action_groups(value)
                                if any(group[0] == '106' and group[2] == clone_id
                                       for group in groups):
                                    raise AssertionError(f'{unit_id} clone unlocked by script: {context}')
                        for field in ('Owner', 'RequiredHouses'):
                            if 'Guild3' not in values[field].split(','):
                                raise AssertionError(f'{unit_id} missing player access: {context}')
                        if any('MOR' in str(value) for key, value in values.items()
                               if key.startswith('Prerequisite')):
                            raise AssertionError(f'{unit_id} retains generated prerequisite gate: {context}')
                root_map = Path(hook['root_map'])
                if root_map.is_file() and is_generated_hooked_map(root_map):
                    root_map.unlink()


def _mission_prerequisites(values):
    prerequisites = [str(values.get('Prerequisite') or '').upper()]
    try:
        list_count = int(str(values.get('Prerequisite.Lists') or '0'))
    except ValueError:
        list_count = 0
    prerequisites.extend(
        str(values.get(f'Prerequisite.List{index}') or '').upper()
        for index in range(1, list_count + 1)
    )
    return {value for value in prerequisites if value}


def _assert_golden_gate_transport_factories(missions):
    mission = next(mission for mission in missions if mission['code'] == 'SGGATE')
    for reward_mode in ('Standard', 'Chaos'):
        launcher = _AuditLauncher(
            reward_mode=reward_mode,
            progression_mode='Shop Mode',
        )
        allowed = unlocked_reward_tech_ids(launcher.player_rewards)
        extra_rules = launcher.map_rules_for_launch(
            allowed_unlocked_tech_ids=allowed
        )
        for section, values in launcher.mission_required_launch_rules(
            mission
        ).items():
            extra_rules.setdefault(section, {}).update(values)
        hook = launcher.prepare_hooked_map(mission, extra_rules=extra_rules)
        if hook is None:
            raise AssertionError(f'No SGGATE map for Shop Mode/{reward_mode}')
        generated_path = GENERATED_MAP_DIR / mission['scenario'].upper()
        transport = section_value_map_preserve(
            generated_path.read_text(
                encoding='utf-8', errors='ignore'
            ).splitlines(),
            'MORPSAPC',
        )
        missing = {'GAWEAP', 'NAYARD'} - _mission_prerequisites(transport)
        if missing:
            raise AssertionError(
                f'SGGATE Shop Mode/{reward_mode} Zubr lacks factory path(s): '
                + ', '.join(sorted(missing))
            )
        root_map = Path(hook['root_map'])
        if root_map.is_file() and is_generated_hooked_map(root_map):
            root_map.unlink()


def _assert_mode_switch_buff_clones(missions):
    mission = next(mission for mission in missions if mission['code'] == 'SHBD')
    linked_modes = {
        'ETNK': 'ETNK2',
        'AERO': 'AERO2',
        'AHVYBOT2': 'AHVYBOT2B',
        'SUB': 'SUB2',
        'DEVO': 'DEVOD',
        'BURA': 'BURA2',
        'BASS': 'BASS2',
        'CHRTNK': 'CHRTNK2',
        'DRON': 'DRON2',
        'SIREN': 'SIREN2',
        'TRIKE': 'TRIKE2',
        'SHADOW': 'SHADOWF',
        'ROADR': 'ROADR2',
        'ARCH': 'ARCH2',
    }
    reward_by_name = {
        reward.get('name'): reward
        for reward in REWARD_POOL
        if reward.get('name')
    }
    from randomizer.rewards.catalogue import BUFF_TARGETS
    reward_names = []
    for source_id in linked_modes:
        label = BUFF_TARGETS[source_id]['label']
        reward_names.extend((
            f'{label} Access',
            f'{label} Reinforced Frames I',
        ))
    launcher = _AuditLauncher()
    launcher.player_rewards = [
        canonical_reward(reward_by_name[name]) for name in reward_names
    ]
    allowed = unlocked_reward_tech_ids(launcher.player_rewards)
    extra_rules = launcher.map_rules_for_launch(
        allowed_unlocked_tech_ids=allowed
    )
    hook = launcher.prepare_hooked_map(mission, extra_rules=extra_rules)
    if hook is None:
        raise AssertionError('No SHBD map for mode-switch buff audit')
    generated_path = GENERATED_MAP_DIR / mission['scenario'].upper()
    lines = generated_path.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    registered = {
        str(type_id).upper()
        for type_id in section_value_map_preserve(
            lines, 'VehicleTypes'
        ).values()
    }
    for source_id, mode_id in linked_modes.items():
        source_clone = f'MORP{source_id}'
        mode_clone = f'MORP{mode_id}'
        if {source_clone.upper(), mode_clone.upper()} - registered:
            raise AssertionError(
                f'SHBD mode-switch clone registration missing for '
                f'{source_id}/{mode_id}'
            )
        source_values = section_value_map_preserve(lines, source_clone)
        mode_values = section_value_map_preserve(lines, mode_clone)
        if (
            source_values.get('Convert.Deploy') != mode_clone
            or mode_values.get('Convert.Deploy') != source_clone
        ):
            raise AssertionError(
                f'SHBD mode switch escapes buffed clones for '
                f'{source_id}/{mode_id}'
            )
    root_map = Path(hook['root_map'])
    if root_map.is_file() and is_generated_hooked_map(root_map):
        root_map.unlink()




def _assert_taciturn_tier_three_weapon_clone(missions):
    mission = next(mission for mission in missions if mission['code'] == 'ETACI')
    launcher = _AuditLauncher(
        reward_mode='Standard',
        progression_mode='Shop Mode',
        enemy_effect_ids={'tier3_damage'},
    )
    allowed = unlocked_reward_tech_ids(launcher.player_rewards)
    extra_rules = launcher.map_rules_for_launch(
        allowed_unlocked_tech_ids=allowed
    )
    for section, values in launcher.mission_required_launch_rules(
        mission
    ).items():
        extra_rules.setdefault(section, {}).update(values)
    hook = launcher.prepare_hooked_map(mission, extra_rules=extra_rules)
    if hook is None:
        raise AssertionError('No ETACI map for Tier 3 enemy weapon audit')
    generated_path = GENERATED_MAP_DIR / mission['scenario'].upper()
    lines = generated_path.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    weapon_ids = [
        str(value)
        for value in section_value_map_preserve(lines, 'WeaponTypes').values()
        if str(value).upper() == 'MORE3TTNKTANKBOLT'
    ]
    if len(weapon_ids) != 1:
        raise AssertionError(
            'ETACI Tier 3 damage audit did not create one TankBolt clone'
        )
    weapon = section_value_map_preserve(lines, weapon_ids[0])
    if (
        weapon.get('Projectile') != 'NotbounceEMP'
        or weapon.get('Warhead') != 'ElectricTank2'
    ):
        raise AssertionError(
            f'ETACI enemy weapon {weapon_ids[0]} lacks complete authored rules'
        )
    root_map = Path(hook['root_map'])
    if root_map.is_file() and is_generated_hooked_map(root_map):
        root_map.unlink()


def _assert_reality_engineering_team_clone(missions):
    mission = next(
        mission for mission in missions if mission['code'] == 'EREALITY'
    )
    launcher = _AuditLauncher(
        reward_mode='Standard',
        progression_mode='Shop Mode',
    )
    launcher.player_rewards = [
        canonical_reward(reward)
        for reward in REWARD_POOL
        if reward.get('name') == 'Engineering Team Power'
    ]
    if len(launcher.player_rewards) != 1:
        raise AssertionError('Engineering Team reward is not unique')
    allowed = unlocked_reward_tech_ids(launcher.player_rewards)
    extra_rules = launcher.map_rules_for_launch(
        allowed_unlocked_tech_ids=allowed
    )
    for section, values in launcher.mission_required_launch_rules(
        mission
    ).items():
        extra_rules.setdefault(section, {}).update(values)
    hook = launcher.prepare_hooked_map(mission, extra_rules=extra_rules)
    if hook is None:
        raise AssertionError('No EREALITY map for Engineering Team audit')
    generated_path = GENERATED_MAP_DIR / mission['scenario'].upper()
    lines = generated_path.read_text(
        encoding='utf-8', errors='ignore'
    ).splitlines()
    sections = all_section_value_maps_preserve(lines)
    powers = [
        values for values in sections.values()
        if values.get('Name') == 'Engineering Team'
        and values.get('ParaDrop.Types')
    ]
    if len(powers) != 1:
        raise AssertionError(
            f'EREALITY generated {len(powers)} Engineering Team powers'
        )
    payload_id = str(powers[0]['ParaDrop.Types']).upper()
    if payload_id == 'SENGINEER':
        raise AssertionError('EREALITY Engineering Team uses invisible SENGINEER')
    infantry_ids = {
        str(value).upper()
        for value in section_value_map_preserve(
            lines, 'InfantryTypes'
        ).values()
    }
    payload = section_value_map_preserve(lines, payload_id)
    if payload_id not in infantry_ids or not payload:
        raise AssertionError(
            f'EREALITY Engineering Team clone {payload_id} is unregistered'
        )
    if (
        str(payload.get('Image', '')).upper() != 'ENGINEER'
        or str(payload.get('Selectable', 'yes')).lower() == 'no'
        or str(payload.get('Insignificant', 'no')).lower() == 'yes'
    ):
        raise AssertionError(
            f'EREALITY Engineering Team clone {payload_id} is not selectable'
        )
    native = section_value_map_preserve(lines, 'SENGINEER')
    if (
        str(native.get('Image', '')).lower() != 'dummy'
        or str(native.get('Selectable', '')).lower() != 'no'
    ):
        raise AssertionError('EREALITY native scripted SENGINEER was rewritten')
    root_map = Path(hook['root_map'])
    if root_map.is_file() and is_generated_hooked_map(root_map):
        root_map.unlink()


def main():
    _assert_hook_restart_race()
    missions = parse_missions(BATTLE_CLIENT_INI)
    if len(missions) != 97:
        raise AssertionError(f'Expected 97 campaign maps, found {len(missions)}')

    launcher = _AuditLauncher()
    allowed = unlocked_reward_tech_ids(launcher.player_rewards)
    extra_rules = launcher.map_rules_for_launch(
        allowed_unlocked_tech_ids=allowed
    )
    generated = []
    try:
        for index, mission in enumerate(missions, 1):
            launch_rules = deepcopy(extra_rules)
            for section, values in launcher.mission_required_launch_rules(
                mission
            ).items():
                launch_rules.setdefault(section, {}).update(values)
            hook = launcher.prepare_hooked_map(
                mission, extra_rules=launch_rules
            )
            if hook is None:
                raise AssertionError(f'No generated map for {mission["code"]}')
            generated_path = GENERATED_MAP_DIR / mission['scenario'].upper()
            if not generated_path.is_file():
                raise AssertionError(f'Missing generated map {generated_path}')
            generated.append(generated_path)
            root_map = Path(hook['root_map'])
            if root_map.is_file() and is_generated_hooked_map(root_map):
                root_map.unlink()
            print(f'[{index:02d}/97] {mission["code"]}', flush=True)
        _assert_targeted_contracts(generated)
        if launcher.enemy_applications.get('AWITHER') != []:
            raise AssertionError(
                'AWITHER received AI scaling despite its opening-safety policy'
            )
        if not any(
            'Skipped all configured AI scaling rewards for AWITHER:' in message
            for _error, message in launcher.logs
        ):
            raise AssertionError(
                'AWITHER AI-scaling safety exception was not reported'
            )
        _assert_mermaid_mode_matrix(missions)
        _assert_reported_mission_mode_matrix(missions)
        _assert_golden_gate_transport_factories(missions)
        _assert_mode_switch_buff_clones(missions)
        _assert_taciturn_tier_three_weapon_clone(missions)
        _assert_reality_engineering_team_clone(missions)
        if not any(
            'Applied composed Shop run clone modifiers:' in message
            for _error, message in launcher.logs
        ):
            raise AssertionError('Shop clone modifiers were never applied')
    finally:
        for mission in missions:
            root_map = BATTLE_CLIENT_INI.parents[1] / mission['scenario']
            if root_map.is_file() and is_generated_hooked_map(root_map):
                root_map.unlink()
    print(
        'All 97 campaign maps passed Shop modifier/boon/Yuri/AI audit; '
        'Mermaid, Remnant, Parasomnia, Golden Gate, Taciturn, and Reality focused checks passed.'
    )


if __name__ == '__main__':
    main()
