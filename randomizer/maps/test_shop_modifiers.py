"""Regression coverage for Demolition Charges death-weapon fallback."""

import unittest

from randomizer.maps.shop_modifiers import apply_shop_global_modifiers


class ShopGlobalModifierTests(unittest.TestCase):
    def setUp(self):
        self.installed = {
            'InfantryTypes': {'0': 'CHRONO', '1': 'SCRIPTED'},
            'VehicleTypes': {'0': 'CARRIER'},
            'AircraftTypes': {'0': 'JET'},
            'CHRONO': {'Primary': 'TEMPORAL'},
            'SCRIPTED': {'Primary': 'RIFLE', 'DeathWeapon': 'SCRIPTDEATH'},
            'CARRIER': {'Primary': 'SPAWNER'},
            'JET': {'Primary': 'MISSILE'},
            'TEMPORAL': {'Damage': '18', 'Warhead': 'CHRONOWH'},
            'SPAWNER': {'Damage': '1', 'Spawner': 'yes'},
            'MISSILE': {'Damage': '20'},
            'RIFLE': {'Damage': '10'},
            'CHRONOWH': {'Temporal': 'yes'},
        }

    def test_all_categories_get_explicit_safe_death_weapons(self):
        rules = {}
        apply_shop_global_modifiers(
            rules, (), self.installed, {'shop_demolition_charges': 1},
        )
        for unit, death in (
            ('CHRONO', 'InfantryDeathWeapon'),
            ('CARRIER', 'UnitDeathWeapon'),
            ('JET', 'AircraftDeathWeapon'),
        ):
            self.assertEqual(rules[unit]['DeathWeapon'], death)
            self.assertEqual(rules[unit]['Explodes'], 'yes')
        self.assertNotIn('DeathWeapon', rules['SCRIPTED'])

    def test_map_and_generated_clone_death_weapons_remain_authoritative(self):
        lines = [
            '[CHRONO]', 'DeathWeapon=MAPDEATH',
            '[InfantryTypes]', '20000=SHORTCLONE',
        ]
        rules = {'SHORTCLONE': {'Primary': 'TEMPORAL'},
                 'CARRIER': {'DeathWeapon': 'CLONEDEATH'}}
        apply_shop_global_modifiers(
            rules, lines, self.installed, {'shop_demolition_charges': 1},
        )
        self.assertNotIn('DeathWeapon', rules['CHRONO'])
        self.assertEqual(rules['CARRIER']['DeathWeapon'], 'CLONEDEATH')
        self.assertEqual(rules['SHORTCLONE']['DeathWeapon'], 'InfantryDeathWeapon')

    def test_empty_death_weapon_overrides_receive_safe_fallback(self):
        for empty in ('', 'none', '<none>'):
            with self.subTest(value=empty):
                rules = {'CHRONO': {'deathweapon': empty}}
                apply_shop_global_modifiers(
                    rules, (), self.installed, {'shop_demolition_charges': 1},
                )
                self.assertEqual(rules['CHRONO']['deathweapon'], 'InfantryDeathWeapon')

    def test_all_combat_modifiers_keep_death_weapon_safety(self):
        rules = {}
        apply_shop_global_modifiers(rules, (), self.installed, {
            'shop_demolition_charges': 1,
            'shop_melee_fighters': 1,
            'shop_one_shot_one_kill': 1,
        })
        self.assertEqual(rules['CHRONO']['DeathWeapon'], 'InfantryDeathWeapon')
        self.assertEqual(rules['CHRONO']['Strength'], '1')
        self.assertEqual(rules['TEMPORAL']['Range'], '2.35')
        self.assertEqual(rules['TEMPORAL']['MinimumRange'], '0')

    def test_other_modifiers_do_not_enable_death_weapons(self):
        rules = {}
        apply_shop_global_modifiers(
            rules, (), self.installed, {'shop_one_shot_one_kill': 1},
        )
        self.assertFalse(any('DeathWeapon' in values for values in rules.values()))


if __name__ == '__main__':
    unittest.main()
