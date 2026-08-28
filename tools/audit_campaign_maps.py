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
from randomizer.config.player import DEFAULT_CONFIG
from randomizer.core.paths import BATTLE_CLIENT_INI, GENERATED_MAP_DIR
from randomizer.maps._shared import section_value_map_preserve
from randomizer.maps.base import is_generated_hooked_map
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import (
    REWARD_POOL,
    canonical_reward,
)
from randomizer.rewards.enemy_scaling import ENEMY_BUFF_DEFINITIONS
from randomizer.rewards.rules import unlocked_reward_tech_ids
from randomizer.shop.mission_modifiers import MISSION_MODIFIERS


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _AuditLauncher(LaunchController):
    def __init__(self):
        self.config = deepcopy(DEFAULT_CONFIG)
        self.config['generation']['reward_mode'] = 'Chaos'
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
        return 'Chaos'

    def active_progression_mode(self):
        return 'Shop Mode'

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
            'progression_mode': 'Mission List',
            'earned_rewards': self.player_rewards,
        }


def _assert_targeted_contracts(generated_paths):
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


def main():
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
        'All 97 campaign maps passed Shop modifier/boon/Yuri/AI audit.'
    )


if __name__ == '__main__':
    main()
