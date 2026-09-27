"""Regression checks for Megaarena's generated, map-local power chain."""

from pathlib import Path
import unittest

from randomizer.maps._shared import all_section_value_maps
from randomizer.maps.base import cloned_superweapon_plan
from randomizer.maps.ini import merge_ini_section_values
from randomizer.maps.power_buffs import apply_power_buffs_to_unlock_rewards
from randomizer.rewards.catalogue import REWARD_POOL


RULES = Path(__file__).resolve().parents[1] / 'cameo_cache' / 'rulesmo.ini'
BASE_ARMORS = (
    'none', 'flak', 'plate', 'light', 'medium', 'heavy',
    'wood', 'steel', 'concrete', 'special_1', 'special_2',
)


def value(section, key):
    return next(
        (item for name, item in section.items() if name.lower() == key.lower()),
        None,
    )


class MegaarenaRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installed = all_section_value_maps(
            RULES.read_text(errors='replace').splitlines()
        )
        cls.unlock = next(
            reward for reward in REWARD_POOL
            if reward.get('kind') == 'superweapon'
            and reward.get('superweapon') == 'MegaarenaSpecial'
        )
        cls.old_targeting_buff = next(
            reward for reward in REWARD_POOL
            if reward.get('power_buff_type') == 'targeting'
            and reward.get('superweapon') == 'MegaarenaSpecial'
        )

    def generated_rules(self, rewards):
        folded = apply_power_buffs_to_unlock_rewards(rewards, self.installed)
        rules, _, _, _, _, missing = cloned_superweapon_plan(
            [], folded, list(self.installed['SuperWeaponTypes'].values()),
            self.installed, superweapon_required_houses=('MORPLAYER',),
        )
        self.assertEqual(missing, [])
        lines = []
        merge_ini_section_values(lines, rules)
        return all_section_value_maps(lines)

    def test_generated_power_has_no_foehn_tech_gate(self):
        self.assertTrue(self.unlock['superweapon_ignore_foreign_tech_gate'])
        rules = self.generated_rules([self.unlock])
        power = rules['MORMegaarena']
        self.assertEqual(value(power, 'SW.AuxBuildings'), '')
        self.assertIn(value(power, 'SW.RequiredHouses'), (None, ''))
        self.assertIn(value(power, 'SW.ForbiddenHouses'), (None, ''))
        self.assertEqual(value(power, 'Deliver.Types'), 'MORMegaarenaProjector')
        projector = rules['MORMegaarenaProjector']
        self.assertIsNone(value(projector, 'Prerequisite'))
        self.assertEqual(value(projector, 'Secondary'), 'MORMegaarenaCast')
        self.assertEqual(value(rules['MORMegaarenaCast'], 'Projectile'), 'MORMegaarenaP')
        self.assertEqual(value(rules['MORMegaarenaP'], 'AirburstWeapon'), 'MORMegaarenaReal')
        self.assertEqual(value(rules['MORMegaarenaReal'], 'Warhead'), 'MORMegaarenaWH')

    def test_all_normal_unit_armors_receive_effect_without_upgrade(self):
        rules = self.generated_rules([self.unlock])
        warhead = rules['MORMegaarenaWH']
        verses = value(warhead, 'Verses').split(',')
        self.assertEqual(len(verses), len(BASE_ARMORS))
        self.assertEqual(verses[6:9], ['0%'] * 3)
        self.assertEqual(value(warhead, 'DamageAirThreshold'), '-1')
        self.assertEqual(value(warhead, 'AffectsEnemies'), 'no')
        self.assertEqual(value(warhead, 'AffectsAllies'), 'yes')

        armor_types = self.installed['ArmorTypes']
        checked = set()
        for list_name in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes'):
            for unit_id in self.installed[list_name].values():
                unit = self.installed.get(unit_id, {})
                armor = value(unit, 'Armor') or 'none'
                current = armor.lower()
                while current in armor_types:
                    current = armor_types[current].split(';', 1)[0].strip().lower()
                if current == '0%':
                    continue  # Script and immunity helper armors.
                self.assertIn(current, BASE_ARMORS, (unit_id, armor))
                effective = value(warhead, f'Versus.{armor}') or verses[
                    BASE_ARMORS.index(current)
                ]
                self.assertEqual(effective, '100%', (unit_id, armor))
                checked.add(list_name)
        self.assertEqual(checked, {'InfantryTypes', 'VehicleTypes', 'AircraftTypes'})

    def test_existing_targeting_reward_keeps_all_unit_baseline(self):
        without_buff = self.generated_rules([self.unlock])
        with_buff = self.generated_rules([self.unlock, self.old_targeting_buff])
        self.assertEqual(
            without_buff['MORMegaarenaWH'], with_buff['MORMegaarenaWH']
        )


if __name__ == '__main__':
    unittest.main()
