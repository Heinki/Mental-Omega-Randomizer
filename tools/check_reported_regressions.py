"""Audit real campaign-map generation for reported gameplay regressions."""

from itertools import product
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.maps._shared import LOCKED_TECH_LEVEL, UNLOCKED_TECH_LEVEL
from randomizer.rewards.catalogue import REWARD_BY_NAME, REWARD_BY_BUFF_KEY
from randomizer.rewards.roster import randomizer_unit_template_values
from randomizer.rewards.rules import unlocked_reward_tech_ids
from randomizer.config.tuning import stacking_amount
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
                REWARD_BY_NAME['Super Thor Gunship Access'],
                *(REWARD_BY_BUFF_KEY[('STNK', kind)] for kind in ('damage', 'range', 'reload')),
                *([REWARD_BY_BUFF_KEY[('STNK', 'initial_passenger')]] * count),
            ]
            sections = generate(launcher, missions['FPOINT'])
            thor = sections['MORPSTHOR']
            assert thor['OpenTopped'] == 'yes'
            assert thor['InitialPayload.Nums'] == '5,5,1'
            payloads = thor['InitialPayload.Types'].split(',')
            assert thor['Passengers.Allowed'].split(',') == payloads
            for payload in payloads:
                assert payload in sections
                assert sections[payload]['Primary']
                # A saved tier-one starter may also have normal build access.
                assert sections[payload]['TechLevel'] in {
                    LOCKED_TECH_LEVEL, UNLOCKED_TECH_LEVEL,
                }
                assert sections[payload].get('BuildLimit') != '0'
                if sections[payload]['TechLevel'] == LOCKED_TECH_LEVEL:
                    assert not sections[payload].get('BuildLimit')
                assert not sections[payload].get('Prerequisite.Negative')
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


def check_bottleneck(missions, launcher_type):
    class DemolitionLauncher(launcher_type):
        def active_reward_settings(self):
            settings = super().active_reward_settings()
            settings.update({
                'shop_demolition_charges': 1,
                'shop_melee_fighters': 1,
                'shop_one_shot_one_kill': 1,
            })
            return settings

    launcher = DemolitionLauncher(enemy_effect_ids=[])
    sections = generate(launcher, missions['ABOTTLE'])
    for unit in ('CLEG', 'AICLEG'):
        assert sections[unit]['Explodes'] == 'yes'
        assert sections[unit]['DeathWeapon'] == 'InfantryDeathWeapon'
        assert sections[unit]['Strength'] == '1'
    # Preserve the authored opening EMP discharge, not a generic explosion.
    assert sections['NCHF']['DeathWeapon'] == 'TemporalShield'
    assert sections['NeutronRifle']['Range'] == '2.35'
    print('Bottleneck: Chaos Shop, all global combat modifiers, safe death weapons', flush=True)


def check_shrike_and_nanocharge(missions, launcher_type):
    for progression in ('Grid Mode', 'Shop Mode'):
        for source, count, veteran in (
            ('FAGUAR', 1, False), ('NASAM', 1, False), ('FAGUAR', 40, True),
        ):
            launcher = launcher_type(progression_mode=progression, enemy_effect_ids=[])
            if source != 'FAGUAR':
                launcher.share_chaos_role_buffs_enabled = lambda: True
            launcher.player_rewards = [
                REWARD_BY_NAME['Foehn Shrike Nest Access'],
                *([REWARD_BY_BUFF_KEY[(source, 'range')]] * count),
                *([REWARD_BY_BUFF_KEY[('FAGUAR', 'veteran')]] if veteran else []),
            ]
            sections = generate(launcher, missions['APUPPET'])
            nests = [
                values for values in sections.values()
                if values.get('GroupAs') == 'FAGUAR'
            ]
            assert len(nests) == 1, (progression, source, count)
            nest = nests[0]
            gain = stacking_amount('range', count)
            for field, native_weapon, baseline in (
                ('Primary', 'NestFake', 12), ('Secondary', 'NestLauncher', 14),
            ):
                weapon_id = nest[field]
                assert weapon_id != native_weapon
                assert float(sections[weapon_id]['Range']) == baseline + gain
                assert native_weapon not in sections
            spawn_id = nest['Spawns']
            assert spawn_id != 'SHRIKE'
            assert spawn_id in sections['AircraftTypes'].values()
            assert float(sections[spawn_id]['GuardRange']) == 30 + gain
            assert sections[spawn_id]['Spawned'] == 'yes'
            assert sections[spawn_id]['Image'] == 'SHRIKE'
            assert sections[spawn_id]['Primary'] == 'FlyingDroneRocket'
            assert 'SHRIKE' not in sections
            print(f'Puppet: {progression}, Shrike range source={source}, stacks={count}, veteran={veteran}', flush=True)

        for upgraded in (False, True):
            launcher = launcher_type(progression_mode=progression, enemy_effect_ids=[])
            launcher.player_rewards = [
                REWARD_BY_NAME['Nanocharge Power'],
                REWARD_BY_NAME['Mastodon Access'],
                REWARD_BY_NAME['Leviathan Helicarrier Access'],
            ]
            if upgraded:
                launcher.player_rewards.extend(
                    reward for reward in REWARD_BY_NAME.values()
                    if reward.get('superweapon') == 'NanochargeSpecial'
                    and reward.get('power_buff_type') == 'targeting'
                )
            sections = generate(launcher, missions['AINSOMNIA'])
            nano = sections['MORNanocharge']
            assert nano['Type'] == 'GenericWarhead'
            assert nano['SW.Damage'] == '0'
            assert nano['SW.AffectsHouse'] == 'owner'
            assert not any(key.startswith('HunterSeeker.') for key in nano)
            warhead_id = nano['SW.Warhead']
            assert warhead_id in sections['Warheads'].values()
            warhead = sections[warhead_id]
            assert warhead['AllowZeroDamage'] == 'yes'
            assert warhead['EffectsRequireDamage'] == 'no'
            assert warhead['AffectsOwner'] == 'yes'
            assert warhead['AffectsAllies'] == warhead['AffectsEnemies'] == 'no'
            assert warhead['AttachEffect.Animation'] == 'MASTHEAL'
            assert warhead['AttachEffect.Duration'] == '360'
            assert warhead['Versus.prome'] == warhead['Versus.s_spin_levi'] == '3%'
            provider_id = 'MORNanoProvider'
            assert sections[provider_id]['SuperWeapon'] == 'MORNanocharge'
            assert provider_id in sections['BuildingTypes'].values()
            assert any(
                value.split(',')[:2] == ['UnitedStates House', provider_id]
                for value in sections['Structures'].values()
            )
            if upgraded:
                assert not nano['SW.Designators']
                assert warhead['Verses'].split(',')[3:6] == ['3%'] * 3
            else:
                designators = nano['SW.Designators'].split(',')
                for source in ('LEVI', 'PROME'):
                    clone_id = 'MORP' + source
                    assert source in designators and clone_id in designators
                    assert sections[clone_id]['DesignatorRange'] == '384'
            # Insomnia uses its native NCHF for scripted temporal shielding.
            assert sections['NCHF']['DeathWeapon'] == 'TemporalShield'
            assert 'MORNanoSpawner' not in sections
            print(f'Insomnia: {progression}, direct owner Nanocharge, all-vehicle upgrade={upgraded}', flush=True)


def check_tempest(missions, launcher_type):
    """Audit real campaign maps and the early Tempest rules/art deployment."""
    from randomizer.core.paths import CAMEO_CACHE_DIR, GENERATED_MAP_DIR
    from randomizer.maps.assets import deploy_generated_unit_art

    modes = (
        ('Chaos', 'Shop Mode'),
        ('Chaos', 'Grid Mode'),
        ('Randomizer Arsenal', 'Grid Mode'),
    )
    buffs = (
        (1, 0, '23', '9'),
        (0, 1, '20', '9.5'),
        (5, 0, '40', '9'),
        (5, 20, '40', '19'),
    )
    for code, (reward_mode, progression), buff in product(
        ('EACCEL', 'FKILL', 'AROADTRIP'), modes, buffs,
    ):
        damage_count, area_count, expected_damage, expected_spread = buff
        mission = missions[code]
        launcher = launcher_type(
            reward_mode=reward_mode, progression_mode=progression,
            enemy_effect_ids=[],
        )
        launcher.player_rewards = [
            REWARD_BY_NAME['Great Tempest Power'],
            *([REWARD_BY_NAME['Great Tempest Power Amplified Payload I']] * damage_count),
            *([REWARD_BY_NAME['Great Tempest Power Expanded Area I']] * area_count),
        ]
        sections = generate(launcher, mission)
        with TemporaryDirectory(prefix='mo-tempest-map-audit-') as folder:
            target = Path(folder) / 'artmo.ini'
            _, aliases = deploy_generated_unit_art(
                GENERATED_MAP_DIR / mission['scenario'].upper(),
                target_path=target,
                art_cache_path=CAMEO_CACHE_DIR / 'artmo.ini',
                rules_cache_path=CAMEO_CACHE_DIR / 'rulesmo.ini',
            )
            preload = all_section_value_maps_preserve(
                (target.parent / 'rulesmo.ini').read_text().splitlines()
            )
            registered = set(preload['Warheads'].values())
            for animation in sections['MORTempestAnimations']:
                art = aliases[animation]
                assert art['Damage'] == expected_damage
                warhead = art['Warhead']
                if area_count:
                    assert warhead in registered
                    # Engine INI keys and emitted type names must keep
                    # their spelling, including custom armor overrides.
                    assert preload[warhead] == sections[warhead]
                    assert preload[warhead]['CellSpread'] == expected_spread
                    assert preload[warhead]['Verses'].startswith('50%,50%,40%')
                else:
                    assert warhead in {'GreatTempestAnimWH', 'GreatTempestAnim2WH'}
                    assert preload[warhead]['CellSpread'] == '9'
            assert aliases['MORFVORTEX']['Next'] == 'MORFVORTEX2'
        print(f'{code}: {reward_mode} {progression} Tempest, damage={damage_count}, '
              f'area={area_count}, early warhead casing preserved', flush=True)


def check_crane_and_hunter_seeker(missions, launcher_type):
    """Audit support building identities and instant Hunter Seeker delivery."""
    from randomizer.ui.cameos import installed_rules_registry
    from randomizer.maps.powers import _scripted_waypoint_cells

    _power_ids, installed = installed_rules_registry(synchronous=True)
    for code in ('APUPPET', 'EDIVER', 'EREALITY', 'AHAMARTIA', 'SHAND'):
        original = all_section_value_maps_preserve(
            (ROOT / 'extracted_maps' / missions[code]['scenario'].upper())
            .read_text().splitlines()
        )
        for mode in ('Standard', 'Chaos'):
            for veteran in (False, True):
                launcher = launcher_type(
                    reward_mode=mode, progression_mode='Mission List',
                    enemy_effect_ids=[],
                )
                names = [
                    'Hunter-Seeker Power', 'Soviet Repair Crane Access',
                    'Soviet Iron Guard Access', 'Rhino Heavy Tank Access',
                ]
                if veteran:
                    names.append('Soviet Repair Crane Drill I')
                launcher.player_rewards = [REWARD_BY_NAME[name] for name in names]
                sections = generate(launcher, missions[code])
                for source, power in (
                    ('NADRON', 'CraneSpecial'), ('NAIRDM', 'IronGuardSpecial'),
                ):
                    clones = [
                        type_id for type_id in sections['BuildingTypes'].values()
                        if sections.get(type_id, {}).get('GroupAs') == source
                    ]
                    assert clones, (code, mode, source)
                    cannons = sections[power]['EMPulse.Cannons'].split(',')
                    assert source in cannons and set(clones).issubset(cannons)
                    for clone in clones:
                        assert sections[clone]['SuperWeapon'] == power
                        assert sections[clone]['Primary']
                hunter = sections['MORHunterSeeker']
                assert hunter['Type'] == 'HunterSeeker'
                assert hunter['SW.AutoFire'] == 'no'
                assert hunter['RechargeTime'] == installed['HunterSeekerSpecial']['RechargeTime']
                drone_id = hunter['HunterSeeker.Type']
                assert drone_id != 'SUNB' and drone_id in sections['VehicleTypes'].values()
                drone = sections[drone_id]
                for key in (
                    'HunterSeeker', 'Locomotor', 'MovementZone', 'FlightLevel',
                ):
                    assert drone[key] == installed['SUNB'][key], (code, key)
                addon_id = drone['InitialPayload.Types']
                assert addon_id != 'SUNB_1' and drone['Passengers.Allowed'] == addon_id
                assert addon_id in sections['VehicleTypes'].values()
                for weapon_id, source in (
                    (drone['Primary'], 'SeekerFake'),
                    (drone['DeathWeapon'], 'SunburstBomb'),
                    (sections[addon_id]['Primary'], 'SunburstLaser'),
                ):
                    weapon = sections[weapon_id]
                    assert weapon_id != source and weapon_id in sections['WeaponTypes'].values()
                    assert weapon['Damage'] == installed[source]['Damage']
                    warhead_id = weapon['Warhead']
                    projectile_id = weapon['Projectile']
                    assert warhead_id in sections['Warheads'].values()
                    assert projectile_id in sections['Projectiles'].values()
                    assert sections[warhead_id] == installed[installed[source]['Warhead']]
                    assert sections[projectile_id] == installed[installed[source]['Projectile']]
                assert drone['Image'] == 'SUNB'
                assert not drone.get('RequiredHouses') and not drone.get('PoweredBy')
                for source in ('SUNB', 'SUNB_1', 'SeekerWH', 'SunburstBombWH', 'SunburstLaserWH'):
                    assert sections.get(source, {}) == original.get(source, {}), (code, source)
                assert sections.get('HunterSeekerSpecial', {}) == original.get('HunterSeekerSpecial', {})
                provider_id = hunter['HunterSeeker.Buildings']
                placements = [
                    value.split(',') for value in sections['Structures'].values()
                    if value.split(',')[1] == provider_id
                ]
                assert len(placements) == 1
                assert placements[0][0] == original['Basic']['Player']
                assert sections[provider_id]['SuperWeapon'] == 'MORHunterSeeker'
                cell = tuple(map(int, placements[0][3:5]))
                waypoint_cells = _scripted_waypoint_cells(
                    (ROOT / 'extracted_maps' / missions[code]['scenario'].upper())
                    .read_text().splitlines()
                )
                assert all(max(abs(cell[0] - x), abs(cell[1] - y)) > 3
                           for x, y in waypoint_cells)
                # Both missions start through player-owned reinforcement actions.
                # Do not fall back to Puppet Master's remote Guild1 landmark.
                if code == 'APUPPET':
                    assert max(abs(cell[0] - 190), abs(cell[1] - 114)) <= 12, cell
                print(f'{code}: {mode}, crane veteran={veteran}, cannon identities bound, '
                      f'instant Hunter Seeker provider={cell}', flush=True)


def check_hover_infantry_restrictions(missions, launcher_type):
    """Audit production roulette against real campaign infantry/air/naval clones."""
    access_names = (
        'Epsilon Elite Access', 'Libra Access', 'Dunerider Access',
        'Rocketeer Access', 'Gyrocopter Access', 'Harrier Access',
        'Horizon Destroyer Access', 'Hovracoon Access', 'Rhino Heavy Tank Access',
    )
    production_categories = {
        'YURIPR': 'infantry', 'LIBRA': 'infantry', 'DUNE': 'infantry',
        'JUMPJET': 'infantry', 'GYRO': 'infantry', 'ORCA': 'aircraft',
        'DEST': 'naval', 'COON': 'naval', 'HTNK': 'vehicles',
    }
    for code in ('APUPPET', 'EDIVER'):
        for blocked in ((), ('aircraft',), ('naval',), ('aircraft', 'naval'),
                        ('vehicles',), ('infantry',)):
            launcher = launcher_type(progression_mode='Shop Mode', enemy_effect_ids=[])
            launcher.config['generation']['shop_production_restrictions'] = blocked
            launcher.player_rewards = [REWARD_BY_NAME[name] for name in access_names]
            sections = generate(launcher, missions[code])
            for source, category in production_categories.items():
                clones = [
                    type_id
                    for registry in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
                    for type_id in sections[registry].values()
                    if sections.get(type_id, {}).get('GroupAs') == source
                ]
                assert clones, (code, source)
                for clone in clones:
                    denied = sections[clone]['TechLevel'] == '-1'
                    assert denied == (category in blocked), (code, blocked, source, clone)
            print(f'{code}: Shop production restrictions={blocked}, hover/flying infantry '
                  'retain infantry category; aircraft/naval/vehicle bans preserved', flush=True)


def check_brothers_in_arms(missions, launcher_type):
    """Audit reward deployment against SARMS's native vehicle-cloning factory."""
    mission = missions['SARMS']
    original = all_section_value_maps_preserve(
        (ROOT / 'extracted_maps' / mission['scenario'].upper()).read_text().splitlines()
    )
    for progression, mode, buffed in product(
        ('Mission List', 'Shop Mode'), ('Standard', 'Chaos'), (False, True),
    ):
        launcher = launcher_type(
            progression_mode=progression, reward_mode=mode, enemy_effect_ids=[],
        )
        launcher.player_rewards = [REWARD_BY_NAME["Stalin's Fist Access"]]
        if buffed:
            launcher.player_rewards.extend([
                REWARD_BY_NAME["Stalin's Fist Reinforced Frames I"],
                REWARD_BY_NAME["Stalin's Fist Stealth Systems I"],
            ])
        sections = generate(launcher, mission)
        mobile = sections['MORPMWF']
        deployed_id = mobile['DeploysInto']
        assert deployed_id != 'NAFIST' and deployed_id in sections
        deployed = sections[deployed_id]
        assert deployed['Factory'] == 'UnitType'
        assert deployed.get('CloningFacility', 'no').lower() == 'no'
        assert deployed.get('Cloning', 'no').lower() == 'no'
        assert deployed['UndeploysInto'] == 'MORPMWF'
        for identity in ('NAFIST', 'NAFISTB'):
            for key in ('Factory', 'CloningFacility', 'UndeploysInto'):
                assert sections[identity].get(key) == original[identity].get(key)
        print(f'Brothers in Arms: {progression}, {mode}, buffed={buffed}; '
              'reward factory and native cloner preserved', flush=True)


def check_captured_factory_access(missions, launcher_type):
    """Audit the reported maps with locked and purchased portable units."""
    from randomizer.maps.production import PLAYER_ORIGINAL_PRODUCTION_GATE_ID
    from randomizer.ui.cameos import installed_rules_registry

    _powers, installed = installed_rules_registry(synchronous=True)
    armor_types = {str(key).lower() for key in installed['ArmorTypes']}
    for code, progression, mode, purchased in product(
        ('AZEROSIGNAL', 'FBEYOND'), ('Grid Mode', 'Mission List', 'Shop Mode'),
        ('Standard', 'Chaos'), (False, True),
    ):
        launcher = launcher_type(
            progression_mode=progression, reward_mode=mode, enemy_effect_ids=[],
        )
        launcher.player_rewards = [
            REWARD_BY_NAME[name] for name in (
                'Cavalier Medium Tank Access', 'Archon AMC Access',
                'Psychic Boss Brute Access', 'Gene Boss Brute Access',
                'Virus Boss Brute Access',
            )
        ] if purchased else []
        sections = generate(launcher, missions[code])
        gate = sections[PLAYER_ORIGINAL_PRODUCTION_GATE_ID]
        assert gate['DontScore'] == 'no', (code, progression, mode)
        player = sections['Basic']['Player']
        assert any(
            value.split(',')[:2] == [player, PLAYER_ORIGINAL_PRODUCTION_GATE_ID]
            for value in sections['Structures'].values()
        ), (code, progression, mode, 'missing player gate')
        for source in ('AMC', 'MTNK'):
            assert PLAYER_ORIGINAL_PRODUCTION_GATE_ID in (
                sections[source].get('Prerequisite.Negative', '').split(',')
            ), (code, progression, mode, purchased, source)
        if purchased:
            for source in ('BRUTM', 'BRUTS', 'BRUTV'):
                clone = sections['MORP' + source]
                assert clone['Armor'] == 'brute' and 'brute' in armor_types
        # Locked opening units stay native and retain runtime house access.
        # Purchased clones can still take part in the usual placement rewrite.
        original = all_section_value_maps_preserve(
            (ROOT / 'extracted_maps' / missions[code]['scenario'].upper())
            .read_text().splitlines()
        )
        if code == 'AZEROSIGNAL' and not purchased:
            for key, value in original['Units'].items():
                if value.split(',')[1] in {'AMC', 'MTNK'}:
                    assert sections['Units'][key] == value
            for source in ('AMC', 'MTNK'):
                authored = {**installed[source], **original.get(source, {})}
                authored_forbidden = authored.get('ForbiddenHouses')
                assert sections[source].get(
                    'ForbiddenHouses', authored_forbidden,
                ) == authored_forbidden
        print(f'{code}: {mode} {progression}, purchased={purchased}; '
              'captured-factory gate and portable Brute armor valid', flush=True)


def check_ghost_hunt_powerhouses(missions, launcher_type):
    """Audit the base-building mission's vulnerable fixed-unit opening."""
    from randomizer.core.paths import GENERATED_MAP_DIR
    from tools.audit_campaign_maps import _assert_powerhouse_waves

    mission = missions['AGHOST']
    for progression in ('Grid Mode', 'Shop Mode'):
        launcher = launcher_type(
            progression_mode=progression, enemy_effect_ids={'powerhouse'},
        )
        launcher.player_rewards = []
        generate(launcher, mission)
        applications = launcher.enemy_applications[mission['code']]
        waves = [entry for entry in applications
                 if entry.get('application_kind') == 'wave']
        assert waves, (progression, 'no hostile waves audited')
        assert all('MIND' not in entry.get('added_unit_ids', ())
                   for entry in applications), progression
        _assert_powerhouse_waves(
            launcher.extract_campaign_map(mission['scenario']),
            GENERATED_MAP_DIR / mission['scenario'].upper(), mission, applications,
        )
        print(f'Ghost Hunt: {progression}; no added Masterminds, authored waves preserved', flush=True)


def check_bleed_red_access(missions, launcher_type):
    """Audit locked launch overlays and native Boris creation on the real map."""
    from randomizer.ui.cameos import installed_rules_registry

    mission = missions['SBLEED']
    original = all_section_value_maps_preserve(
        (ROOT / 'extracted_maps' / mission['scenario'].upper()).read_text().splitlines()
    )
    _powers, installed = installed_rules_registry(synchronous=True)
    for progression, mode, purchased in product(
        ('Grid Mode', 'Mission List', 'Shop Mode'),
        ('Standard', 'Chaos'), (False, True),
    ):
        launcher = launcher_type(
            progression_mode=progression, reward_mode=mode, enemy_effect_ids=[],
        )
        launcher.player_rewards = [REWARD_BY_NAME['Morales Access']] if purchased else []
        sections = generate(launcher, mission)
        for source in ('E2', 'SHK', 'HTNK', 'MORALES'):
            clone = sections.get('MORP' + source, {})
            if purchased and source == 'MORALES':
                assert clone.get('TechLevel') == UNLOCKED_TECH_LEVEL
            else:
                assert clone.get('TechLevel', LOCKED_TECH_LEVEL) == LOCKED_TECH_LEVEL, (
                    progression, mode, purchased, source,
                )
        # The native Boris actor must remain spawnable and controllable.
        # Only its human factory production is filtered, including when the
        # earned build-only clone is present alongside native story teams.
        boris = sections['MORALES']
        assert {'USSR', 'Boris', 'MORPLAYER'}.issubset(
            set(boris.get('FactoryOwners.Forbidden', '').split(','))
        )
        assert not boris.get('Prerequisite.Negative')
        assert boris.get('ForbiddenHouses') == original['MORALES'].get(
            'ForbiddenHouses', installed['MORALES'].get('ForbiddenHouses'),
        )
        for team_id in ('01000468', '01000509'):
            taskforce = original[team_id]['TaskForce']
            assert sections[team_id]['TaskForce'] == taskforce
            assert sections[taskforce] == original[taskforce]
        assert not any(
            'WARNING: Unauthorized production access' in log
            or 'WARNING: Duplicate production entry' in log
            for _error, log in launcher.logs
        ), (progression, mode, purchased)
        print(f'Bleed Red: {mode} {progression}, purchased={purchased}; '
              'locked access and native Boris preserved', flush=True)


def main():
    from tools.audit_campaign_maps import _AuditLauncher
    from randomizer.core.paths import BATTLE_CLIENT_INI
    from randomizer.missions.catalogue import parse_missions
    missions = {mission['code']: mission for mission in parse_missions(BATTLE_CLIENT_INI)}
    check_noise(missions, _AuditLauncher)
    check_units(missions, _AuditLauncher)
    check_bottleneck(missions, _AuditLauncher)
    check_shrike_and_nanocharge(missions, _AuditLauncher)
    check_tempest(missions, _AuditLauncher)
    check_crane_and_hunter_seeker(missions, _AuditLauncher)
    check_hover_infantry_restrictions(missions, _AuditLauncher)
    check_brothers_in_arms(missions, _AuditLauncher)
    check_captured_factory_access(missions, _AuditLauncher)
    check_ghost_hunt_powerhouses(missions, _AuditLauncher)
    check_bleed_red_access(missions, _AuditLauncher)
    print('Reported mission and unit generation regressions passed.')


if __name__ == '__main__':
    main()
