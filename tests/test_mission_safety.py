import unittest

from randomizer_mission_safety import (
    mission_basic_unit_rules,
    starting_tier_one_rules,
    tier_one_unit_ids,
)


ENEMY_SOVIET_BARRACKS_MAP = """\
[Basic]
Player=UnitedStates House
[Houses]
0=UnitedStates House
1=USSR House
[UnitedStates House]
Country=UnitedStates
PlayerControl=yes
[USSR House]
Country=USSR
[UnitedStates]
ParentCountry=UnitedStates
[USSR]
ParentCountry=USSR
[Structures]
0=USSR House,NAHAND,256,1,1,0,None,1,0,0,0,0,0,0,0,0,0
""".splitlines()


class MissionBasicUnitRulesTests(unittest.TestCase):
    def test_all_campaigns_exposes_exact_unlock_after_enemy_factory_capture(self):
        rules = mission_basic_unit_rules(
            ENEMY_SOVIET_BARRACKS_MAP,
            earned_access_ids={'E2'},
            translate_equivalents=False,
        )

        self.assertIn('E2', rules)
        self.assertEqual(rules['E2']['PrerequisiteOverride'], 'NAHAND')

    def test_all_campaigns_does_not_translate_unlock_after_capture(self):
        rules = mission_basic_unit_rules(
            ENEMY_SOVIET_BARRACKS_MAP,
            earned_access_ids={'E1'},
            translate_equivalents=False,
        )

        self.assertNotIn('E2', rules)

    def test_single_campaign_translates_unlock_after_enemy_factory_capture(self):
        rules = mission_basic_unit_rules(
            ENEMY_SOVIET_BARRACKS_MAP,
            earned_access_ids={'E1'},
            translate_equivalents=True,
        )

        self.assertIn('E2', rules)
        self.assertEqual(rules['E2']['PrerequisiteOverride'], 'NAHAND')


def player_conyard_map(country, conyards):
    structures = '\n'.join(
        f'{index}={country} House,{conyard},256,1,1'
        for index, conyard in enumerate(conyards)
    )
    return f"""\
[Basic]
Player={country} House
[Houses]
0={country} House
[{country} House]
Country={country}
PlayerControl=yes
[{country}]
ParentCountry={country}
[Structures]
{structures}
""".splitlines()


class StartingTierOneRulesTests(unittest.TestCase):
    def test_standard_all_campaigns_resolves_each_campaign_family(self):
        cases = (
            ('UnitedStates', ('GACNST',), {'E1', 'GGI', 'ETNK', 'FV', 'STORM'}),
            ('USSR', ('NACNST',), {'E2', 'FLAKT', 'HTNK', 'SCAR', 'FOX'}),
            ('PsiCorps', ('YACNST',), {'INIT', 'HARP', 'LTNK', 'YTNK', 'BLIGHT'}),
        )
        markers = tier_one_unit_ids(('allies', 'soviets', 'epsilon'))

        for country, conyards, expected_units in cases:
            with self.subTest(country=country):
                rules = starting_tier_one_rules(
                    player_conyard_map(country, conyards),
                    markers,
                    standard_families=('allies', 'soviets', 'epsilon'),
                )
                self.assertTrue(expected_units.issubset(rules))

    def test_standard_foehn_uses_allied_and_soviet_starters(self):
        families = ('allies', 'soviets')
        rules = starting_tier_one_rules(
            player_conyard_map('Guild1', ('GACNST', 'NACNST')),
            tier_one_unit_ids(families),
            standard_families=families,
        )

        self.assertTrue(
            {
                'E1', 'GGI', 'ETNK', 'FV', 'STORM',
                'E2', 'FLAKT', 'HTNK', 'SCAR', 'FOX',
            }.issubset(rules)
        )
        self.assertFalse({'INIT', 'HARP', 'LTNK', 'YTNK', 'BLIGHT'} & set(rules))


if __name__ == '__main__':
    unittest.main()
