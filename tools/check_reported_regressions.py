"""Generate real campaign maps for the Hovracoon, Opus and Noise Severe reports."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.rewards.catalogue import REWARD_BY_NAME, REWARD_BY_BUFF_KEY
from randomizer.rewards.roster import randomizer_unit_template_values
from randomizer.rewards.rules import unlocked_reward_tech_ids
from randomizer.shop.active import active_shop_rewards
from randomizer.shop.model import MissionEconomyClass, MissionOffer, RunStatus, ShopRun
from randomizer.shop.purchases import apply_validated_run_purchase, validate_run_purchase
from randomizer.shop.transitions import reroll_missions


def generate(launcher, mission):
    from randomizer.core.paths import GAME_ROOT, GENERATED_MAP_DIR
    rules = launcher.map_rules_for_launch(
        allowed_unlocked_tech_ids=unlocked_reward_tech_ids(launcher.player_rewards),
    )
    for section, values in launcher.mission_required_launch_rules(mission).items():
        rules.setdefault(section, {}).update(values)
    root_path = GAME_ROOT / mission['scenario']
    previous = root_path.read_bytes() if root_path.is_file() else None
    try:
        hook = launcher.prepare_hooked_map(mission, extra_rules=rules)
        assert hook, mission['code']
        return all_section_value_maps_preserve(
            (GENERATED_MAP_DIR / mission['scenario'].upper()).read_text().splitlines()
        )
    finally:
        if previous is None:
            root_path.unlink(missing_ok=True)
        else:
            root_path.write_bytes(previous)


def purchased_and_rerolled_rewards():
    run = ShopRun(
        run_id='reported-regression', seed='reported-regression',
        status=RunStatus.ACTIVE, stage=1, run_length=2, run_coins=1000,
        reward_mode='Chaos', selected_permanent_units=('Rhino Heavy Tank Access',),
    )
    reward = REWARD_BY_BUFF_KEY[('HTNK', 'cloak')]
    validation = validate_run_purchase(
        reward, price=1, run_coins=run.run_coins, active_tech_ids={'HTNK'},
    )
    assert validation.allowed
    run = apply_validated_run_purchase(run, reward, validation)
    before = active_shop_rewards(run)
    # Rerolls change mission offers, not the projected earned reward state.
    offers = (MissionOffer('SNOISE', MissionEconomyClass.OPERATION),)
    run = reroll_missions(run, offers, maximum_rerolls=1)
    assert active_shop_rewards(run) == before
    return before


def check_noise(missions, launcher_type):
    mission = missions['SNOISE']
    original = all_section_value_maps_preserve(
        (ROOT / 'extracted_maps' / mission['scenario'].upper()).read_text().splitlines()
    )
    taskforces = ('01000054', '01000055', '01000068', '01000090')
    purchased = purchased_and_rerolled_rewards()
    for progression in ('Mission List', 'Shop Mode'):
        for helpers in (False, True):
            for rewards in ((), purchased):
                launcher = launcher_type(progression_mode=progression, enemy_effect_ids=[])
                launcher.config['generation']['buff_allied_helpers'] = helpers
                launcher.player_rewards = list(rewards)
                sections = generate(launcher, mission)
                for taskforce in taskforces:
                    for key, value in original[taskforce].items():
                        if not key.isdigit():
                            continue
                        count, source = value.split(',')[:2]
                        actual_count, clone = sections[taskforce][key].split(',')[:2]
                        assert actual_count == count
                        assert clone != source and clone in sections, (progression, taskforce, source)
                        clone_values = sections[clone]
                        runtime_country = 'FriendlyTank' if taskforce in taskforces[:2] else 'USSR'
                        assert runtime_country in clone_values['RequiredHouses'].split(',')
                        assert not clone_values.get('FactoryOwners.Forbidden')
                        assert not clone_values.get('Prerequisite.Negative')
                        if source == 'HTNK' and rewards:
                            assert clone_values.get('Cloakable', 'no') == 'no'
                # The opening opponent and all authored team scripts stay native.
                assert sections['01000045'] == original['01000045']
                for section, values in original.items():
                    if 'TaskForce' in values:
                        assert sections[section]['Script'] == values['Script']
                # Convoy placements, TaskForces and exact loss-event identities
                # must agree, including the locked RAVA2/RAVA3 variants.
                for source, taskforce in zip(
                    ('RAVA', 'RAVA2', 'RAVA3'),
                    ('01000002', '01000024', '01000025'),
                ):
                    refs = {
                        value.split(',')[1]
                        for section in ('Units',)
                        for value in sections.get(section, {}).values()
                        if value.split(',')[1] in {source, 'MORP' + source}
                    }
                    assert len(refs) == 1, (source, refs)
                    identity = next(iter(refs))
                    assert sections[taskforce]['0'].split(',')[1] == identity
                    assert any(identity in value.split(',') for value in sections['Events'].values())
                print(f'Noise Severe: {progression}, helpers={helpers}, purchased={bool(rewards)}', flush=True)


def check_units(missions, launcher_type):
    template = randomizer_unit_template_values()['STNK']
    for progression in ('Mission List', 'Shop Mode'):
        for count, passenger in enumerate(('INIT', 'BRUTE', 'YURI')):
            launcher = launcher_type(progression_mode=progression, enemy_effect_ids=[])
            launcher.player_rewards = [
                REWARD_BY_NAME['Opus Custom Tank Access'],
                REWARD_BY_NAME['Hovracoon Access'],
                REWARD_BY_NAME['Raccoon Access'],
                *(REWARD_BY_BUFF_KEY[('STNK', kind)] for kind in ('damage', 'range', 'reload')),
                *([REWARD_BY_BUFF_KEY[('STNK', 'initial_passenger')]] * count),
            ]
            sections = generate(launcher, missions['FPOINT'])
            opus = sections['MORPSTNK']
            assert opus['InitialPayload.Types'] == 'MORP' + passenger
            assert opus['InitialPayload.Nums'] == opus['Passengers'] == '1'
            assert opus['NoManualEnter'] == opus['NoManualUnload'] == 'yes'
            assert opus['InitialPayload.Types'] in sections
            for key, source_weapon in template.items():
                if not re.fullmatch(r'(?:Elite)?Weapon\d+', key):
                    continue
                clone_weapon = opus[key]
                assert clone_weapon != source_weapon and clone_weapon in sections
                weapon = sections[clone_weapon]
                assert float(weapon['Damage']) > (55 if 'GunX' in source_weapon else 60 if 'GunY' in source_weapon else 65)
                assert float(weapon['Range']) > 6
                assert float(weapon['ROF']) < (55 if source_weapon in {'OpusGun', 'OpusGunE'} else 50)
            inhibitors = sections['NukeSpecial']['SW.Inhibitors'].split(',')
            for identity in ('COON', 'MORPCOON', 'RACC', 'MORPRACC'):
                assert identity in inhibitors
            assert sections['MORPCOON']['InhibitorRange'] == '6'
            assert sections['MORPCOON']['MovementZone'] == 'Amphibious'
            print(f'Opus/Hovracoon: {progression}, passenger tier={count + 1}', flush=True)
    # Four-silo Thread of Dread's authored list omits native COON too.
    sections = generate(launcher, missions['STHREAD'])
    inhibitors = sections['NukeSpecial']['SW.Inhibitors'].split(',')
    assert 'COON' not in inhibitors and 'MORPCOON' not in inhibitors
    assert 'RACC' in inhibitors and 'MORPRACC' in inhibitors


def main():
    from tools.audit_campaign_maps import _AuditLauncher
    from randomizer.core.paths import BATTLE_CLIENT_INI
    from randomizer.missions.catalogue import parse_missions
    missions = {mission['code']: mission for mission in parse_missions(BATTLE_CLIENT_INI)}
    check_noise(missions, _AuditLauncher)
    check_units(missions, _AuditLauncher)
    print('Reported mission and unit generation regressions passed.')


if __name__ == '__main__':
    main()
