import unittest

from randomizer_app import LauncherApp
from randomizer_map import (
    append_superweapon_grant_trigger,
    find_section_bounds,
    insert_actions_before_codes,
    parse_action_groups,
    section_value_map_preserve,
    superweapon_actions_for_rewards,
)
from randomizer_rewards import (
    REWARD_BY_NAME,
    SUPERWEAPON_UNLOCK_REWARDS,
    buff_effect_lines,
    canonical_reward,
)


class VictoryActionInsertionTests(unittest.TestCase):
    def test_inserts_marker_and_reward_before_terminal_win(self):
        lines = [
            '[Actions]',
            'WIN=2,21,6,EVA_ObjectiveComplete,0,0,0,0,A,1,0,0,0,0,0,0,A',
            '',
            '[Basic]',
        ]
        marker = ['4', '1', 'RND00001', '0', '0', '0', '0', 'A']
        reward = ['106', '9', 'CLEG', '0', '0', '0', '0', '1']

        inserted = insert_actions_before_codes(lines, 'WIN', [marker, reward], ('1', '67', '69'))

        self.assertTrue(inserted)
        start, end = find_section_bounds(lines, 'Actions')
        _, value = lines[start + 1].split('=', 1)
        count, groups = parse_action_groups(value)
        self.assertEqual(count, 4)
        self.assertEqual(groups, [
            ['21', '6', 'EVA_ObjectiveComplete', '0', '0', '0', '0', 'A'],
            marker,
            reward,
            ['1', '0', '0', '0', '0', '0', '0', 'A'],
        ])

    def test_does_not_modify_action_list_without_terminal_code(self):
        lines = [
            '[Actions]',
            'OBJECTIVE=1,21,6,EVA_ObjectiveComplete,0,0,0,0,A',
        ]
        original = list(lines)
        marker = ['4', '1', 'RND00001', '0', '0', '0', '0', 'A']

        inserted = insert_actions_before_codes(lines, 'OBJECTIVE', [marker], ('1', '67', '69'))

        self.assertFalse(inserted)
        self.assertEqual(lines, original)


class SuperweaponGrantTests(unittest.TestCase):
    def test_builds_repeating_grant_actions_and_deduplicates_types(self):
        lightning = SUPERWEAPON_UNLOCK_REWARDS[0]

        actions = superweapon_actions_for_rewards([lightning, lightning])

        self.assertEqual(actions, [['34', '0', '2', '0', '0', '0', '0', 'A']])

    def test_adds_player_owned_map_start_trigger(self):
        lines = ['[Basic]', 'Name=Test Mission']
        actions = [['34', '0', '2', '0', '0', '0', '0', 'A']]

        trigger_id = append_superweapon_grant_trigger(lines, 'UnitedStates', actions)

        self.assertTrue(trigger_id)
        self.assertEqual(section_value_map_preserve(lines, 'Events')[trigger_id], '1,13,0,1')
        self.assertEqual(
            section_value_map_preserve(lines, 'Actions')[trigger_id],
            '1,34,0,2,0,0,0,0,A',
        )
        self.assertTrue(
            section_value_map_preserve(lines, 'Triggers')[trigger_id].startswith(
                'UnitedStates,<none>,MOR Earned Superweapons,'
            )
        )


class MissionSortingTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(LauncherApp)
        self.app.missions = [
            {'code': 'A', 'title': 'Alpha', 'side': 'Allies'},
            {'code': 'B', 'title': 'Beta', 'side': 'Soviets'},
        ]
        self.app.state = {
            'mission_order': ['B', 'A'],
            'starting_unlocked_missions': 2,
            'completed_missions': ['A'],
            'mission_checks': {
                'A': [{'id': 'victory', 'unlocked': True, 'rewards': []}],
                'B': [{'id': 'victory', 'unlocked': False, 'rewards': []}],
            },
        }
        self.app.mission_sort_column = None
        self.app.mission_sort_reverse = False

    def test_default_order_keeps_open_missions_above_completed(self):
        self.assertEqual([mission['code'] for _, mission in self.app.visible_missions()], ['B', 'A'])

    def test_selected_column_sorts_in_both_directions(self):
        self.app.mission_sort_column = 'title'
        self.assertEqual([mission['code'] for _, mission in self.app.visible_missions()], ['A', 'B'])
        self.app.mission_sort_reverse = True
        self.assertEqual([mission['code'] for _, mission in self.app.visible_missions()], ['B', 'A'])


class RewardDescriptionTests(unittest.TestCase):
    def test_old_battle_fortress_name_migrates_to_barracuda(self):
        reward = canonical_reward({'name': 'Battle Fortress Access'})

        self.assertEqual(reward['name'], 'Barracuda Access')
        self.assertIn('GAAIRC', reward['rules']['FORTRESS']['PrerequisiteOverride'])

    def test_abrams_ammo_and_sensor_effects_explain_gameplay(self):
        ammo = next(
            reward
            for reward in REWARD_BY_NAME.values()
            if reward.get('unit') == 'ABRM' and reward.get('buff_type') == 'ammo'
        )
        sensors = next(
            reward
            for reward in REWARD_BY_NAME.values()
            if reward.get('unit') == 'ABRM' and reward.get('buff_type') == 'sensors'
        )

        self.assertIn('Main-cannon ammo 1 -> 2', buff_effect_lines(ammo)[0])
        self.assertIn('Sensors enabled (8-cell range', buff_effect_lines(sensors)[0])


if __name__ == '__main__':
    unittest.main()
