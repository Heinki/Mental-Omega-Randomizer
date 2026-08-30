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
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import (
    REWARD_POOL,
    canonical_reward,
)
from randomizer.rewards.enemy_scaling import ENEMY_BUFF_DEFINITIONS
from randomizer.rewards.rules import unlocked_reward_tech_ids
from randomizer.rewards.definitions import linked_buff_variant_ids
from randomizer.shop.mission_modifiers import MISSION_MODIFIERS


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
    def __init__(self, reward_mode='Chaos', progression_mode='Shop Mode'):
        self._reward_mode = reward_mode
        self._progression_mode = progression_mode
        self.config = deepcopy(DEFAULT_CONFIG)
        self.config['generation']['reward_mode'] = reward_mode
        self.state = {}
        self.player_color_var = _Value('Default')
        self.rainbowizer_var = _Value(False)
        self.eva_voice_var = _Value('Mission default')
        self.logs = []
        reward_by_name = {
            reward.get('name'): reward for reward in REWARD_POOL
            if reward.get('name')
        }
        player_reward_ids = [
            'Epsilon Elite Access',
            'GI Access',
            'GI Firepower I',
            'GI Armor Plating I',
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
        for definition in ENEMY_BUFF_DEFINITIONS:
            if not str(definition['id']).startswith('tier1_'):
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

    def record_enemy_reward_applications(self, _code, _applications):
        return None

    def active_starting_rewards_for_report(self):
        return []

    def active_progression_rewards_for_report(self):
        return list(self.player_rewards)

    def active_starting_tier_one_expanded_ids(self):
        return ()

    def active_starting_tier_one_defense_expanded_ids(self):
        return ()

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
            hook = launcher.prepare_hooked_map(mission, extra_rules=extra_rules)
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
        _assert_mermaid_mode_matrix(missions)
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
        'Mermaid passed all progression/reward modes.'
    )


if __name__ == '__main__':
    main()
