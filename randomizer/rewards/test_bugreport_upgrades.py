"""Cross-mode contracts for reported unit upgrade gaps."""

import unittest

from randomizer.maps.buff_validation import (
    _unit_fields_are_effective,
    _weapon_field_is_effective,
)
from randomizer.maps.buff_values import (
    apply_unit_buff_value,
    apply_weapon_buff_value,
)
from randomizer.maps.base import resolved_native_designator_clone_rules
from randomizer.rewards.catalogue import BUFF_TARGETS, REWARD_BY_BUFF_KEY
from randomizer.rewards.catalogue import (
    buff_stack_limit, buff_effect_lines, buff_effect_comparison_lines,
)
from randomizer.rewards.roster import randomizer_unit_template_values
from randomizer.shop.catalogue import shop_catalogue
from randomizer.shop.model import ShopProfile
from randomizer.shop.state import normalize_shop_profile


class ReportedUpgradeTests(unittest.TestCase):
    def test_native_power_lists_keep_originals_and_current_clone_forms(self):
        clones = {
            'COON': {'clone_id': 'MORPCOON', 'reference_clone_id': 'MORRCOON'},
            'RACC': {'clone_id': 'MORC01'},
            'FAINHI': {'clone_id': 'MORPFAINHI'},
        }
        installed = {
            'NukeSpecial': {'SW.Inhibitors': 'RACC,COON', 'SW.Designators': 'FAINHI'},
            'Cleared': {'SW.Inhibitors': 'COON'},
        }
        updates = resolved_native_designator_clone_rules(
            installed,
            {'NukeSpecial': {'RechargeTime': '1'}, 'Cleared': {'sw.inhibitors': ''}},
            clones,
        )
        self.assertEqual(
            updates['NukeSpecial']['SW.Inhibitors'],
            'RACC,COON,MORC01,MORPCOON,MORRCOON',
        )
        self.assertEqual(updates['NukeSpecial']['SW.Designators'], 'FAINHI,MORPFAINHI')
        self.assertNotIn('Cleared', updates)
        thread = resolved_native_designator_clone_rules(
            installed, {'NukeSpecial': {'SW.Inhibitors': 'RACC'}}, clones,
        )
        self.assertEqual(thread['NukeSpecial']['SW.Inhibitors'], 'RACC,MORC01')

    def test_opus_numbered_weapons_use_normal_weapon_rewards(self):
        target = BUFF_TARGETS['STNK']
        self.assertEqual(set(target['weapons']), {
            'OPUSGUN', 'OPUSGUNE', 'OPUSGUNX', 'OPUSGUNXE',
            'OPUSGUNY', 'OPUSGUNYE', 'OPUSGUNZ', 'OPUSGUNZE',
        })
        shop_ids = {entry.reward_id for entry in shop_catalogue()}
        for buff_type, field in (('damage', 'Damage'), ('range', 'Range'), ('reload', 'ROF')):
            reward = REWARD_BY_BUFF_KEY[('STNK', buff_type)]
            self.assertIn(reward['name'], shop_ids)
            for stats in target['weapons'].values():
                values = {}
                self.assertTrue(apply_weapon_buff_value(values, stats, buff_type, 1))
                base = stats['rof' if buff_type == 'reload' else buff_type]
                actual = float(values[field])
                self.assertTrue(actual < base if buff_type == 'reload' else actual > base)
        # Their Damage=1/ROF=1 controls must not become ordinary gun upgrades.
        for unit_id in ('COON', 'RACC'):
            self.assertNotIn((unit_id, 'damage'), REWARD_BY_BUFF_KEY)
            self.assertNotIn((unit_id, 'reload'), REWARD_BY_BUFF_KEY)

    def test_opus_passenger_stacks_replace_one_sealed_payload(self):
        reward = REWARD_BY_BUFF_KEY[('STNK', 'initial_passenger')]
        self.assertEqual(buff_stack_limit(reward), 2)
        target = BUFF_TARGETS['STNK']
        values = dict(randomizer_unit_template_values()['STNK'])
        for count, passenger in enumerate(('INIT', 'BRUTE', 'YURI')):
            self.assertTrue(apply_unit_buff_value(values, target, 'initial_passenger', count))
            self.assertEqual(values['InitialPayload.Types'], passenger)
            self.assertEqual(values['InitialPayload.Nums'], '1')
            self.assertEqual(values['Passengers'], '1')
            self.assertIn('one passenger', buff_effect_lines(reward, count=count)[0])
        self.assertEqual(values['NoManualEnter'], 'yes')
        self.assertEqual(values['NoManualUnload'], 'yes')
        for rank in ('Rookie', 'Veteran', 'Elite'):
            self.assertEqual(values[f'Survivor.{rank}PassengerChance'], '0%')
        for count in (0, 1):
            comparison = buff_effect_comparison_lines(reward, count)[0]
            self.assertNotIn('\n', comparison)
            self.assertEqual(comparison.count('one passenger)'), 2)

    def test_shop_and_grid_share_real_plasmerizer_drill(self):
        reward = REWARD_BY_BUFF_KEY[('FAAVAL', 'production')]
        self.assertTrue(any(
            entry.reward_id == reward['name']
            for entry in shop_catalogue()
        ))
        template = randomizer_unit_template_values()['FAAVAL']
        values = {'BuildTimeMultiplier': template['BuildTimeMultiplier']}
        base = dict(values)
        self.assertTrue(apply_unit_buff_value(
            values, BUFF_TARGETS['FAAVAL'], 'production', 1
        ))
        self.assertTrue(_unit_fields_are_effective(
            'production', values, BUFF_TARGETS['FAAVAL'], base
        ))

    def test_splatter_weapons_receive_damage_and_fire_rate(self):
        target = BUFF_TARGETS['PLAG']
        for buff_type in ('damage', 'reload'):
            self.assertIn(('PLAG', buff_type), REWARD_BY_BUFF_KEY)
        for weapon in ('CatapultWeapon', 'CatapultWeaponE'):
            stats = target['weapons'][weapon]
            for buff_type, field in (('damage', 'Damage'), ('reload', 'ROF')):
                values = {}
                self.assertTrue(apply_weapon_buff_value(
                    values, stats, buff_type, 1
                ))
                actual = int(values[field])
                base = stats['damage' if buff_type == 'damage' else 'rof']
                self.assertTrue(actual > base if buff_type == 'damage' else actual < base)

    def test_rejuvenator_healing_replaces_ammo_in_saved_shop_profile(self):
        reward = REWARD_BY_BUFF_KEY[('REJU', 'damage')]
        self.assertEqual(reward['name'], 'Rejuvenator Healing Output I')
        self.assertNotIn(('REJU', 'ammo'), REWARD_BY_BUFF_KEY)
        values = {'Damage': '-5'}
        self.assertTrue(apply_weapon_buff_value(
            values, BUFF_TARGETS['REJU']['weapons']['RejuvenationBullet'],
            'damage', 1,
        ))
        self.assertEqual(values['Damage'], '-6')
        self.assertTrue(_weapon_field_is_effective(
            'damage', 'REJU',
            {'weapon_clone_ids': {'REJUVENATIONBULLET': 'TESTHEAL'}},
            {'TESTHEAL': values},
        ))
        profile = ShopProfile(permanent_buffs=())
        document = profile.to_dict()
        document['permanent_buffs'] = [
            {'reward_id': 'Rejuvenator Ammo Reserves I', 'stacks': 2}
        ]
        restored = normalize_shop_profile(document)
        self.assertEqual(
            [(item.reward_id, item.stacks) for item in restored.permanent_buffs],
            [('Rejuvenator Healing Output I', 2)],
        )

    def test_irkalla_healing_and_aircraft_movement_are_effective(self):
        self.assertIn(('GOTTER', 'self_healing'), REWARD_BY_BUFF_KEY)
        self.assertNotIn(('GOTTER', 'reload'), REWARD_BY_BUFF_KEY)
        healing = {'SelfHealing': 'yes', 'SelfHealing.Rate': '.02'}
        base_healing = dict(healing)
        self.assertTrue(apply_unit_buff_value(
            healing, BUFF_TARGETS['GOTTER'], 'self_healing', 1
        ))
        self.assertTrue(_unit_fields_are_effective(
            'self_healing', healing, BUFF_TARGETS['GOTTER'], base_healing
        ))
        templates = randomizer_unit_template_values()
        for unit_id in ('GOTTER', 'STARDUSTB'):
            target = BUFF_TARGETS[unit_id]
            template = templates[unit_id]
            base = {
                'Speed': template['Speed'],
                'JumpjetSpeed': template['JumpjetSpeed'],
            }
            values = dict(base)
            self.assertTrue(apply_unit_buff_value(values, target, 'speed', 1))
            self.assertEqual(values['Speed'], values['JumpjetSpeed'])
            self.assertTrue(_unit_fields_are_effective(
                'speed', values, target, base
            ))


if __name__ == '__main__':
    unittest.main()
