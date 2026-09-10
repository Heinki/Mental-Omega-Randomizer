"""Regression checks for inline buff values in Shop rows and unit tooltips."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace, MethodType
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from randomizer.application.shop_polish_controller import ShopPolishController
from randomizer.application.unlock_data import UnlockDataController
from randomizer.rewards.catalogue import BUFF_TARGETS, REWARD_POOL
from randomizer.rewards.display import (
    buff_effect_lines, unit_buff_counts, inherited_unit_buff_rewards,
    house_wide_buff_scope, buff_stack_limit, canonical_rewards,
)
from randomizer.config.tuning import stacked_weapon_damage
from randomizer.shop.catalogue import canonical_reward_for_id, shop_catalogue
from randomizer.shop.model import ShopRewardType


class InlineEffectChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = shop_catalogue()
        cls.damage = next(
            entry for entry in cls.entries
            if entry.reward_type is ShopRewardType.UNIT_BUFF
            and canonical_reward_for_id(entry.reward_id).get('buff_type') == 'damage'
            and (entry.stack_limit or 1) >= 3
            and any(stats.get('damage', 0) > 0 for stats in BUFF_TARGETS[entry.target_id].get('weapons', {}).values())
        )
        cls.reward = canonical_reward_for_id(cls.damage.reward_id)

    def test_shop_effect_column_contains_values(self):
        text = ShopPolishController._shop_catalogue_display_name(self.damage, '', 0)
        stats = next(s for s in BUFF_TARGETS[self.damage.target_id]['weapons'].values() if s.get('damage', 0) > 0)
        base = stats['damage']
        self.assertIn(f'{stacked_weapon_damage(base, 1)} [{base:g}]', text)
        self.assertNotIn('% higher', text)
        self.assertNotIn('\n', text)

    def test_unit_dashboard_current_effects_contain_values(self):
        entry = dict(
            id=self.damage.target_id, label='Test unit', kind='unit', status='unlocked',
            privacy=False,
            sources={'earned': [('Mission victory', self.reward)] * 3, 'available_unlocks': []},
        )
        text = UnlockDataController.unlock_dashboard_tooltip(SimpleNamespace(), entry)
        expected = buff_effect_lines(self.reward, count=3, include_label=False, multiline=True)[0]
        self.assertIn('Current effects:\n• ' + expected, text)
        self.assertIn('[', expected)
        self.assertNotIn('Stats with attached buffs:', text)
        self.assertNotIn('After next purchase:', text)

    def test_next_stack_and_maximum(self):
        preview = ShopPolishController._shop_catalogue_display_name(self.damage, 'Stacks 2', 2)
        self.assertIn(buff_effect_lines(self.reward, count=3, include_label=False, include_stack=False)[0], preview)
        maximum = self.damage.stack_limit
        self.assertEqual(
            buff_effect_lines(self.reward, count=maximum),
            buff_effect_lines(self.reward, count=maximum + 20),
        )
        maxed = ShopPolishController._shop_catalogue_display_name(self.damage, 'MAX', maximum)
        self.assertIn('(MAX)', maxed)
        self.assertNotIn('Next stack:', maxed)

    def test_sources_combine_before_display(self):
        counts = unit_buff_counts([self.reward] * 3, self.damage.target_id)
        self.assertEqual(counts['damage'], 3)
        self.assertEqual(unit_buff_counts([self.reward], 'UNKNOWN_UNIT'), {})

    def test_numeric_effects_are_inline_across_catalogue(self):
        numeric = {'damage', 'range', 'cost', 'health', 'armor', 'sight', 'ammo', 'storage', 'income', 'passenger_capacity', 'build_limit', 'building_limit'}
        for entry in self.entries:
            if entry.reward_type is not ShopRewardType.UNIT_BUFF:
                continue
            reward = canonical_reward_for_id(entry.reward_id)
            lines = buff_effect_lines(reward, count=entry.stack_limit or 1, include_label=False)
            with self.subTest(reward=entry.reward_id):
                self.assertTrue(lines)
                self.assertEqual(len(lines), 1)
                self.assertNotIn('base:', lines[0])
                self.assertNotIn('frames', lines[0])
                self.assertNotIn('Stacked', lines[0])
                if reward.get('buff_type') in numeric and 'no applicable weapon' not in lines[0]:
                    self.assertIn('[', lines[0])

    def test_combined_health_and_armor_context(self):
        reward = next(canonical_reward_for_id(e.reward_id) for e in self.entries if canonical_reward_for_id(e.reward_id).get('buff_type') == 'health')
        own = buff_effect_lines(reward, include_stack=False)
        combined = buff_effect_lines(reward, include_stack=False, buff_counts={'armor': 2})
        self.assertNotEqual(own, combined)
        self.assertIn('[', combined[0])

    def test_fire_rate_uses_inverse_reload_ratio(self):
        reward = {'kind': 'buff', 'unit': self.damage.target_id, 'buff_type': 'reload'}
        with patch.dict(BUFF_TARGETS, {self.damage.target_id: {
            'weapons': {'Gun': {'rof': 80}},
        }}), patch('randomizer.rewards.display.stacked_weapon_rof', return_value=40):
            line = buff_effect_lines(reward, include_label=False, include_stack=False)[0]
        self.assertEqual(line, 'Fire rate 100% faster')

    def test_weapon_details_use_separate_tooltip_lines(self):
        reward = {'kind': 'buff', 'unit': self.damage.target_id, 'buff_type': 'damage'}
        with patch.dict(BUFF_TARGETS, {self.damage.target_id: {
            'weapons': {'Cannon': {'damage': 40}, 'Missile': {'damage': 75}},
        }}):
            compact = buff_effect_lines(reward, include_label=False)[0]
            tooltip = buff_effect_lines(reward, include_label=False, multiline=True)[0]
        self.assertNotIn('\n', compact)
        self.assertIn('\n    Cannon:', tooltip)
        self.assertIn('\n    Missile:', tooltip)
        self.assertEqual(tooltip.count('stacks'), 1)

    def test_dashboard_merges_health_and_armor(self):
        health_entry = next(e for e in self.entries if canonical_reward_for_id(e.reward_id).get('buff_type') == 'health')
        armor_entry = next(e for e in self.entries if e.target_id == health_entry.target_id and canonical_reward_for_id(e.reward_id).get('buff_type') == 'armor')
        health, armor = map(canonical_reward_for_id, (health_entry.reward_id, armor_entry.reward_id))
        entry = dict(
            id=health_entry.target_id, label='Test unit', kind='unit', status='unlocked',
            privacy=False,
            sources={'earned': [('Health reward', health), ('Armor reward', armor)], 'available_unlocks': []},
        )
        text = UnlockDataController.unlock_dashboard_tooltip(SimpleNamespace(), entry)
        self.assertEqual(text.count(' HP'), 1)
        self.assertIn('Health + armor', text)
        self.assertIn('Health 1/', text)
        self.assertIn('Armor 1/', text)
        self.assertLess(text.index('Current effects:'), text.index('Earned from:'))

    def dashboard(self, rewards):
        controller = SimpleNamespace(
            state={'test': True}, active_progression_mode=lambda: 'Linear',
            active_reward_mode=lambda: 'Standard',
            active_starting_tier_one_access_ids=lambda: set(),
            canonical_earned_rewards=lambda: rewards,
            randomize_unit_access_enabled=lambda: True,
            reward_house_wide_buff_scope=lambda r: house_wide_buff_scope(r, unit_specific_mode=True),
            starting_reward_source_items=lambda: [],
            unit_faction_sort_key=lambda unit: unit,
            share_chaos_role_buffs_enabled=lambda: False,
            foehn_standard_bundles_enabled=lambda: False,
        )
        controller.unlock_dashboard_reward_keys = MethodType(
            UnlockDataController.unlock_dashboard_reward_keys, controller,
        )
        sources = {}
        for reward in rewards:
            for key in controller.unlock_dashboard_reward_keys(reward):
                source = sources.setdefault(key, dict(
                    assigned=[], earned=[], earned_unlocks=[], available=[],
                    available_unlocks=[], available_codes=[],
                ))
                item = ('Earned reward', reward)
                source['assigned'].append(item)
                source['earned'].append(item)
                if reward.get('kind') != 'buff':
                    source['earned_unlocks'].append(item)
        controller.unlock_dashboard_sources = lambda: sources
        return controller, UnlockDataController.unlock_dashboard_entries(controller)

    def test_access_only_cards_show_applicable_army_buffs(self):
        globals_ = [r for r in REWARD_POOL if r.get('global_buff')]
        access = [canonical_reward_for_id(e.reward_id) for e in self.entries if e.reward_type is ShopRewardType.UNIT_ACCESS]
        controller, entries = self.dashboard([*access, *globals_])
        projected = 0
        for entry in entries:
            if entry.get('kind') != 'unit' or entry['status'] != 'unlocked':
                continue
            inherited = inherited_unit_buff_rewards(globals_, entry['id'])
            self.assertEqual(entry.get('inherited_buffs', []), inherited)
            if inherited:
                text = UnlockDataController.unlock_dashboard_tooltip(controller, entry)
                self.assertIn('Current effects:', text)
                self.assertIn('Includes army-wide upgrades.', text)
                for reward in inherited:
                    expected = buff_effect_lines(reward, include_label=False, multiline=True)[0]
                    self.assertIn(expected, text)
                projected += 1
        if any(r.get('unit') in BUFF_TARGETS for r in globals_):
            self.assertGreater(projected, 0)
        else:
            self.assertEqual(projected, 0)

    def test_army_buffs_do_not_grant_access(self):
        globals_ = [r for r in REWARD_POOL if r.get('global_buff')]
        _controller, entries = self.dashboard(globals_)
        locked = [entry for entry in entries if entry.get('kind') == 'unit' and entry['status'] != 'unlocked']
        self.assertTrue(locked)
        self.assertTrue(all(not entry.get('inherited_buffs') for entry in locked))

    def test_direct_and_army_stacks_combine_without_mutating_rewards(self):
        import copy
        globals_ = [r for r in REWARD_POOL if r.get('global_buff')]
        original = copy.deepcopy(globals_)
        for target in BUFF_TARGETS:
            inherited = inherited_unit_buff_rewards(globals_, target)
            for unit_reward in inherited:
                kind = unit_reward['buff_type']
                combined = unit_buff_counts([*globals_, unit_reward], target)
                expected = min(2, buff_stack_limit(unit_reward))
                self.assertEqual(combined[kind], expected)
        self.assertEqual(globals_, original)

    def test_every_speed_reward_matches_engine_cap(self):
        from randomizer.maps.buff_values import apply_unit_buff_value
        speed_rewards = [r for r in REWARD_POOL if r.get('buff_type') == 'speed' and not r.get('global_buff')]
        self.assertTrue(speed_rewards)
        for reward in speed_rewards:
            with self.subTest(unit=reward['unit']):
                target = BUFF_TARGETS[reward['unit']]
                maximum = buff_stack_limit(reward)
                values = {}
                apply_unit_buff_value(values, target, 'speed', maximum)
                line = buff_effect_lines(reward, count=maximum, include_label=False)[0]
                self.assertIn(f"Speed {values['Speed']} [{int(target['speed'])}]", line)
                counts = unit_buff_counts([reward] * maximum, reward['unit'])
                self.assertEqual(counts['speed'], maximum)

    def test_old_stat_panels_are_removed(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ('randomizer/application/shop_polish_controller.py', 'randomizer/application/shop_controller.py', 'randomizer/ui/shop.py'):
            text = (root/rel).read_text()
            self.assertNotIn('_shop_unit_stats_text', text)
            self.assertNotIn('shop_permanent_buff_tooltip', text)


if __name__ == '__main__':
    unittest.main()
