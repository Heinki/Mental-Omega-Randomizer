"""Generate the static player-owned TechnoType roster.

Infantry definitions come from the mapper-reviewed InfantryList.txt. Remaining
rewardable units come from the installed Mental Omega 3.3.6 rules registry.
Generated files are committed runtime data; generation is a maintenance step,
never part of mission launch.
"""

from __future__ import annotations

import argparse
import re
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INFANTRY = ROOT / 'InfantryList.txt'
FALLBACK_REVIEWED_INFANTRY = ROOT / 'configs' / 'RandomizerHeroes.ini'
DEFAULT_RULES = ROOT.parent / 'RandomizerLauncherData' / 'cameo_cache' / 'rulesmo.ini'
DEFAULT_OUTPUT_DIR = ROOT / 'configs'
SUPPLEMENTAL_SOURCE_FILES = (
    ROOT.parent / 'MapsMO' / 'Challenge' / 'c_revolution.map',
    ROOT.parent / 'MapsMO' / 'Cooperative' / 'coop_sthunder.map',
    ROOT.parent / 'MapsMO' / 'Cooperative' / 'coop_stoxic.map',
)
TYPE_LISTS = OrderedDict((
    ('infantry', 'InfantryTypes'),
    ('units', 'VehicleTypes'),
    ('aircraft', 'AircraftTypes'),
    ('defenses', 'BuildingTypes'),
    ('special_buildings', 'BuildingTypes'),
))
OUTPUT_GROUPS = OrderedDict((
    ('infantry', ('RandomizerInfantry.ini', 300000)),
    ('heroes', ('RandomizerHeroes.ini', 310000)),
    ('vehicles', ('RandomizerVehicles.ini', 320000)),
    ('ships', ('RandomizerShips.ini', 330000)),
    ('aircraft', ('RandomizerAircraft.ini', 340000)),
    ('buildings', ('RandomizerDefensesAndSpecialBuildings.ini', 350000)),
))
# Append newly reviewed map-only identities instead of renumbering every
# committed registry entry that already follows them in BUFF_TARGETS order.
STABLE_APPEND_ORDER = (
    'MAMM', 'PANTHER',
    'QUICK', 'LIONH', 'CHRP', 'AHVYBOT2', 'AHVYBOT2B',
    'GRUMBLE', 'NAGRUM', 'SYCKLE', 'IDRAG',
    'TRACTOR', 'WORMQ', 'SEIZER', 'SALA', 'SALA_1', 'SALA_2',
    'PHNT', 'SEITAAD', 'ARCH', 'ARCH2', 'RAMW', 'REJU',
    'STHOR', 'DHANDL', 'DHANDR', 'CZEP', 'SHINBOT', 'HEPH',
    'KSNK', 'OTRK', 'MADU', 'MAMU', 'V2', 'ICBM',
    'ARTY', 'RANGER', 'LONGBO', 'GRAV', 'STARDUSTB', 'MECHA', 'YURIX2',
)
STABLE_APPEND_IDS = frozenset(STABLE_APPEND_ORDER)
UNFINISHED_ASSET_IDS = frozenset({
    # Bonus MIX supplies only Heavy Trooper art/cameos. No installed or
    # campaign TechnoType rules exist; do not synthesize gameplay from KNIGHT.
    'CAPU',
})
EXCLUDED_REVIEWED_INFANTRY_IDS = frozenset({
    # Cosmetic Brute variant; no distinct gameplay identity/reward value.
    'BRUTE2',
})
IMAGE_OVERRIDES = {
    # Mapper source calls the Mortar Quad art MORTAR, but installed artmo.ini
    # defines its cameo and sequence under [MOTOR].
    'MOTOR': 'MOTOR',
}
SPECIAL_TEMPLATE_SOURCES = {
    # Campaign/map-only variants receive independent reward identities while
    # retaining the complete installed source definition underneath.
    'GHTNKP': 'GHTNK',
    'PROMEP': 'PROME',
    'ITNK': 'RACC',
    'JACKALP': 'JACKAL',
    'DIVERP': 'DIVER',
    'TARCHIAP': 'TARCHIA',
    'YURIX2': 'YURIX',
    'ROACHP': 'ROACH',
    'NAPSIS': 'YAPSIS',
    'NACLONS': 'NACLON',
    'LUNRE': 'LUNR',
}
TEMPLATE_VALUE_OVERRIDES = {
    'YURIX2': {
        'Name': 'Yuri',
        'UIName': 'Name:YURIHIMSELF',
        'Image': 'YURIX',
        'Cost': '1200',
        'Soylent': '600',
        'Strength': '300',
        'Armor': 'yurix',
        'Sight': '8',
        'Speed': '3',
        'Size': '2',
        'Primary': 'MORYuriPrimeControl',
        'Secondary': 'SuperPsiWave',
        'Deployer': 'yes',
        'DeployFire': 'yes',
        'ImmuneToEMP': 'yes',
        'ImmuneToPsionicWeapons': 'yes',
        'MovementZone': 'AmphibiousDestroyer',
        'SpeedType': 'Amphibious',
        'Locomotor': '{4A582744-9839-11d1-B709-00A024DDAFD1}',
        'PixelSelectionBracketDelta': '-26',
        'Experience.MindControlSelfModifier': '75%',
        'DieSound': 'YuriPrimeDieFinal',
        'OpenTransportWeapon': '1',
        'BuildLimit': '1',
        'BuildTimeMultiplier': '2',
    },
    # Iron Guard is an auto-firing EMPulse cannon. Cloaking the building can
    # prevent its self-targeted field weapon from firing reliably.
    'NAIRDM': {
        'Prerequisite': '',
        'Cloakable.Allowed': 'no',
    },
    'BORIS': {
        'BuildLimit': '1',
    },
    'PERUN': {
        # Campaign source is intentionally impractical to produce. Portable
        # reward must use normal construction timing.
        'BuildTimeMultiplier': '1',
    },
    'CHRP': {
        # PassengerTurret and its sealed capacity drive the Chrono Prison art
        # and prisoner logic. Keep them while blocking manual cargo use.
        'PipScale': 'none',
        'PassengerTurret': 'yes',
        'Passengers': '3',
        'Passengers.BySize': 'no',
        'SizeLimit': '9',
        'NoManualEnter': 'yes',
        'NoManualUnload': 'yes',
        'Survivor.RookiePassengerChance': '0%',
        'Survivor.VeteranPassengerChance': '0%',
        'Survivor.ElitePassengerChance': '0%',
    },
    'RHAD': {
        'BuildLimit': '1',
    },
    'YURIX': {
        'BuildTimeMultiplier': '2',
    },
    'GHTNKP': {
        'Name': 'Gharial Prototype',
        'Image': 'GHTNK2',
        'IFVMode': '3',
        'Primary': 'GharialBetaCannon',
        'Weapon1': 'GharialBetaCannon',
        'ElitePrimary': 'GharialBetaCannon',
        'EliteWeapon1': 'GharialBetaCannon',
        'InitialPayload.Nums': '0',
    },
    'ICBM': {
        'BuildTimeMultiplier': '1',
    },
    'GRAV': {
        'BuildTimeMultiplier': '1',
    },
    'DHANDL': {
        'Name': 'Hand of Ereshkigal Left',
        # Native campaign Hands hide their selection/health bracket off-screen
        # and rely on mission triggers for their scripted lifecycle.  The
        # buildable player copy is a normal damageable unit, so keep its
        # bracket at the normal sprite position.
        'PixelSelectionBracketDelta': '0',
        'GuardRange': '15',
        'WeaponCount': '10',
        'WeaponStages': '5',
        'Stage1': '1',
        'Stage2': '2',
        'Stage3': '3',
        'Stage4': '4',
        'Stage5': '5',
        'EliteStage1': '1',
        'EliteStage2': '2',
        'EliteStage3': '3',
        'EliteStage4': '4',
        'EliteStage5': '5',
        'RateUp': '1',
        'RateDown': '1',
        'IsGattling': 'yes',
        'Gattling.Cycle': 'yes',
        **{
            f'{prefix}Weapon{number}': (
                'DeathBoltAA' if number % 2 == 0 else 'DeathBolt'
            )
            for prefix in ('', 'Elite')
            for number in range(1, 11)
        },
        'BuildTimeMultiplier': '1',
    },
    'DHANDR': {
        'PixelSelectionBracketDelta': '0',
        'GuardRange': '15',
        'WeaponCount': '10',
        'WeaponStages': '5',
        'Stage1': '1',
        'Stage2': '2',
        'Stage3': '3',
        'Stage4': '4',
        'Stage5': '5',
        'EliteStage1': '1',
        'EliteStage2': '2',
        'EliteStage3': '3',
        'EliteStage4': '4',
        'EliteStage5': '5',
        'RateUp': '1',
        'RateDown': '1',
        'IsGattling': 'yes',
        'Gattling.Cycle': 'yes',
        **{
            f'{prefix}Weapon{number}': (
                'DeathBoltAA' if number % 2 == 0 else 'DeathBolt'
            )
            for prefix in ('', 'Elite')
            for number in range(1, 11)
        },
        'BuildTimeMultiplier': '1',
    },
    'CBRIS': {
        'BuildTimeMultiplier': '2',
    },
    'CZEP': {
        'Name': 'Kirov Command Airship',
        'UIName': 'NAME:CZEP',
    },
    'STARDUSTB': {
        # Installed STARDUSTB is the player Paradox identity. STARDUST is its
        # non-selectable AI alias and must never become a second reward.
        'Name': 'The Paradox Engine',
        'BuildTimeMultiplier': '1',
        'IsGattling': 'yes',
        'Turret': 'no',
        'TurretCount': '1',
        'CanPassiveAquire': 'yes',
        'CanRetaliate': 'yes',
        'WeaponCount': '6',
        'WeaponStages': '3',
        'Stage1': '40',
        'Stage2': '80',
        'Stage3': '120',
        'EliteStage1': '40',
        'EliteStage2': '80',
        'EliteStage3': '120',
        'RateUp': '5',
        'RateDown': '10',
        **{
            f'{prefix}Weapon{number}': (
                'ParadoxMedusa' if number % 2 == 0 else 'ParadoxPrism'
            )
            for prefix in ('', 'Elite')
            for number in range(1, 7)
        },
    },
    'SHINBOT': {
        'BuildLimit': '1',
        'BuildTimeMultiplier': '1',
    },
    'HEPH': {
        'WeaponCount': '12',
        'WeaponStages': '6',
        'Stage1': '1',
        'Stage2': '2',
        'Stage3': '3',
        'Stage4': '4',
        'Stage5': '5',
        'Stage6': '6',
        'EliteStage1': '1',
        'EliteStage2': '2',
        'EliteStage3': '3',
        'EliteStage4': '4',
        'EliteStage5': '5',
        'EliteStage6': '6',
        'RateUp': '1',
        'RateDown': '1',
        **{
            f'{prefix}Weapon{number}': (
                ('MegalaserAAE' if prefix else 'MegalaserAA')
                if number % 2 == 0
                else ('MegalaserE' if prefix else 'Megalaser')
            )
            for prefix in ('', 'Elite')
            for number in range(1, 13)
        },
        'BuildTimeMultiplier': '1',
    },
    'CMIN': {
        'Dock': 'NAREFN,GAREFN,CAREFN,YARIREFN,FAREFN,YAMREF,GAOREP,MORPGAOREP',
    },
    'HARV': {
        'Dock': 'NAREFN,GAREFN,CAREFN,YARIREFN,FAREFN,YAMREF,GAOREP,MORPGAOREP',
    },
    'YMIN': {
        'Dock': 'NAREFN,GAREFN,CAREFN,YARIREFN,FAREFN,YAMREF,GAOREP,MORPGAOREP',
    },
    'NMIN': {
        'Dock': 'NAREFN,GAREFN,CAREFN,YARIREFN,FAREFN,YAMREF,GAOREP,MORPGAOREP',
    },
    'PROMEP': {
        'Name': 'Mastodon Prototype',
        'Image': 'PROME2',
        'Speed': '4',
        'IFVMode': '11',
        'Weapon1': 'PrometheusBetaCharge',
        'Weapon2': 'PrometheusBetaCharge',
        'Weapon3': 'PrometheusBetaBlast',
        'Weapon4': 'PrometheusBetaBlast',
        'Weapon5': 'PrometheusBetaCharge2',
        'Weapon6': 'PrometheusBetaCharge2',
        'EliteWeapon1': 'PrometheusBetaCharge',
        'EliteWeapon2': 'PrometheusBetaCharge',
        'EliteWeapon3': 'PrometheusBetaBlast',
        'EliteWeapon4': 'PrometheusBetaBlast',
        'EliteWeapon5': 'PrometheusBetaCharge2',
        'EliteWeapon6': 'PrometheusBetaCharge2',
        'VoiceSelect': 'MastodonBetaSelect',
        'VoiceAttackCommand': 'MastodonBetaAttackCommand',
        'VoiceFeedback': 'none',
        'SelfHealing.Amount': '2',
        'DamageParticleSystems': 'SparkSys,SmallGreySSys',
    },
    'ITNK': {
        'ROT': '6',
        'Image': 'ITNK',
        'Name': 'Infector Tank',
        'UIName': 'NAME:ITNK',
        'Sight': '8',
        'Speed': '6',
        'Strength': '320',
        'MoveSound': 'GharialMoveStart',
        'CrushSound': 'TankCrush',
        'VoiceSelect': 'RaccoonSelect2',
        'InhibitorRange': '0',
        'AttachEffect.Delay': '-1',
        'AttachEffect.Animation': 'DUMMY',
    },
    'JACKALP': {
        'Name': 'Jackal Racer Prototype',
        # JACKALA is a native-map appearance swap whose visible turret still
        # depends on the original JACKAL identity. Standalone reward clones
        # need the complete JACKAL voxel/turret pair.
        'Image': 'JACKAL',
    },
    'DIVERP': {
        'Name': 'Diverbee Prototype',
        'Image': 'ADIVER',
        'Cost': '800',
        'Soylent': '400',
        'Explosion': 'DIVERKILL2',
        'AttachEffect.Animation': 'none',
    },
    'TARCHIAP': {
        'Name': 'Tarchia Prototype',
        'Image': 'ATARCHIA',
        'Speed': '6',
        'IFVMode': '3',
        'Weapon5': 'TarchiaCannonOld',
        'Weapon6': 'TarchiaCannonOld',
        'EliteWeapon5': 'TarchiaCannonOld',
        'EliteWeapon6': 'TarchiaCannonOld',
        'Explodes': 'no',
        'DeathWeapon': 'none',
    },
    'ROACHP': {
        'Name': 'Bison Prototype',
        'Image': 'ROACH2',
        'Speed': '5',
        'Strength': '700',
        'Explodes': 'yes',
        'DeathWeapon': 'MantisDeathWeapon',
        'DamageParticleSystems': 'SparkSys,SmallGreySSys',
    },
    'NAPSIS': {
        'Name': 'Psychic Sensor',
        'UIName': 'NAME:NAPSIS',
        'Image': 'NAPSIS',
        'Cost': '800',
        'Power': '-50',
        'Radar': 'no',
        'Spyable': 'no',
        'SuperWeapon': 'none',
        'SuperWeapon2': 'none',
        'HasRadialIndicator': 'true',
        'PsychicDetectionRadius': '10',
        'ConcentricRadialIndicator': 'true',
    },
    'NACLONS': {
        'Name': 'Soviet Cloning Vats',
        'UIName': 'NAME:NACLON',
        'Image': 'NACLON',
    },
    'LUNRE': {
        'Name': 'Cosmonaut',
        'Image': 'LUNR',
    },
    # Multi-form stolen-tech units keep every runtime conversion and payload
    # on player-owned identities. Native forms remain available to mission AI.
    'AHVYBOT2': {
        'Convert.Deploy': 'MORPAHVYBOT2B',
    },
    'AHVYBOT2B': {
        'Convert.Deploy': 'MORPAHVYBOT2',
    },
    'GRUMBLE': {
        'DeploysInto': 'MORPNAGRUM',
    },
    'NAGRUM': {
        'UndeploysInto': 'MORPGRUMBLE',
    },
    'SALA': {
        'Passengers.Allowed': 'MORPSALA_1,MORPSALA_2',
        'Survivor.RookiePassengerChance': '0%',
        'Survivor.VeteranPassengerChance': '0%',
        'Survivor.ElitePassengerChance': '0%',
        'Passengers': '4',
        'PipScale': 'none',
        'InitialPayload.Types': 'MORPSALA_1,MORPSALA_2',
        'InitialPayload.Nums': '3,1',
        'SizeLimit': '1',
        'OpenTopped': 'yes',
        'NoManualUnload': 'yes',
        'NoManualEnter': 'yes',
    },
    'STHOR': {
        # Super Thor's payload is its complete portable weapon system. Keep
        # passengers inaccessible and account for their full combined Size:
        # 5 GGI + 5 ENFO + 1 HCRUIS = 28.
        'Passengers.Allowed': 'MORPGGI,MORPENFO,MORPHCRUIS',
        'Survivor.RookiePassengerChance': '0%',
        'Survivor.VeteranPassengerChance': '0%',
        'Survivor.ElitePassengerChance': '0%',
        'Passengers': '28',
        'PipScale': 'none',
        'InitialPayload.Types': 'MORPGGI,MORPENFO,MORPHCRUIS',
        'InitialPayload.Nums': '5,5,1',
        'SizeLimit': '18',
        'OpenTopped': 'yes',
        'NoManualUnload': 'yes',
        'NoManualEnter': 'yes',
    },
    'ARCH': {
        'Convert.Deploy': 'MORPARCH2',
    },
    'ARCH2': {
        'Convert.Deploy': 'MORPARCH',
        'ReversedAs': 'MORPARCH',
    },
}
TEMPLATE_VALUE_REMOVALS = {
    'CHRP': frozenset({
        'entertransportsound',
        'leavetransportsound',
    }),
    # Portable Space Commando production is valid in every theater. Installed
    # CBRIS is intentionally lunar-only for its campaign role.
    'CBRIS': frozenset({
        'prerequisite.requiredtheaters',
    }),
    # TARGETMARK belongs to the co-op objective presentation, not the portable
    # player reward. Its otherwise-unused duration is removed with it.
    'STHOR': frozenset({
        'attacheffect.animation',
        'attacheffect.duration',
    }),
    # TARGETMARK is co-op objective presentation, not player-unit identity.
    'YURIX2': frozenset({
        'attacheffect.animation',
        'attacheffect.duration',
    }),
}


def read_sections(path: Path) -> OrderedDict[str, OrderedDict[str, str]]:
    sections: OrderedDict[str, OrderedDict[str, str]] = OrderedDict()
    current = None
    for raw_line in path.read_text(encoding='utf-8-sig', errors='strict').splitlines():
        stripped = raw_line.strip()
        match = re.match(r'^\[([^]]+)\]', stripped)
        if match:
            current = match.group(1).strip()
            sections[current] = OrderedDict()
            continue
        if current is None or not stripped or stripped.startswith(';') or '=' not in raw_line:
            continue
        key, value = raw_line.split('=', 1)
        sections[current][key.strip()] = value.strip()
    return sections


def case_name(sections, requested):
    requested = requested.lower()
    return next((name for name in sections if name.lower() == requested), None)


def infantry_sources(sections):
    registry_name = case_name(sections, 'InfantryTypes')
    if not registry_name:
        raise ValueError('InfantryList.txt has no [InfantryTypes] section.')
    source_to_section = {}
    for clone_id in sections[registry_name].values():
        clone_id = clone_id.split(';', 1)[0].strip()
        if not clone_id.upper().startswith('MOR'):
            continue
        if clone_id.upper() == 'MORE1':
            source_id = 'E1'
        elif clone_id.upper().startswith('MORP'):
            source_id = clone_id[4:].upper()
        else:
            source_id = clone_id[3:].upper()
        section_name = case_name(sections, clone_id)
        if not section_name:
            # Mapper scratch lists may reserve a future registry ID before its
            # definition exists. Required reward targets are checked below.
            continue
        source_to_section[source_id] = section_name
    return source_to_section


def render_section(name, values):
    lines = [f'[{name}]']
    for key, value in values.items():
        if key.lower() == '$inherits':
            continue
        lines.append(f'{key}={value}')
    return lines


def stable_registry_entries(output_path, list_name, source_ids, first_key):
    """Preserve existing numeric type registrations across regeneration."""
    previous = read_sections(output_path) if output_path.is_file() else OrderedDict()
    previous_name = case_name(previous, list_name)
    previous_values = previous.get(previous_name, {}) if previous_name else {}
    current_clone_ids = {f'MORP{source_id}'.upper() for source_id in source_ids}
    existing_keys = {
        value.upper(): str(key)
        for key, value in previous_values.items()
        if value
    }
    reusable_keys = sorted(
        (
            int(key)
            for key, value in previous_values.items()
            if str(key).isdigit() and str(value).upper() not in current_clone_ids
        )
    )
    used_keys = {
        int(key)
        for clone_id, key in existing_keys.items()
        if clone_id in current_clone_ids and key.isdigit()
    }
    next_key = max([first_key - 1, *used_keys, *reusable_keys]) + 1
    entries = []
    for source_id in source_ids:
        clone_id = f'MORP{source_id}'
        key = existing_keys.get(clone_id.upper())
        if key is None:
            if reusable_keys:
                key = str(reusable_keys.pop(0))
            else:
                while next_key in used_keys:
                    next_key += 1
                key = str(next_key)
                next_key += 1
        if key.isdigit():
            used_keys.add(int(key))
        entries.append((key, clone_id))
    return entries, next_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--infantry', type=Path, default=DEFAULT_INFANTRY)
    parser.add_argument('--rules', type=Path, default=DEFAULT_RULES)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        '--group',
        action='append',
        choices=tuple(OUTPUT_GROUPS),
        help='Generate only this output group. May be repeated.',
    )
    args = parser.parse_args()

    # Import after resolving project root so direct script execution works.
    import sys
    sys.path.insert(0, str(ROOT))
    from randomizer.rewards.catalogue import (
        BUFF_TARGETS,
        LIMITED_HERO_UNIT_IDS,
        NAVAL_UNIT_IDS,
        SPECIAL_REWARD_UNIT_IDS,
    )

    selected_groups = set(args.group or OUTPUT_GROUPS)
    needs_reviewed_infantry = bool(selected_groups.intersection({'infantry', 'heroes'}))
    reviewed_infantry_path = args.infantry
    if needs_reviewed_infantry and not reviewed_infantry_path.is_file():
        reviewed_infantry_path = FALLBACK_REVIEWED_INFANTRY
    if needs_reviewed_infantry and not reviewed_infantry_path.is_file():
        raise FileNotFoundError(
            'Reviewed infantry source is required for selected groups: '
            f'{args.infantry} or {FALLBACK_REVIEWED_INFANTRY}'
        )
    infantry_sections = (
        read_sections(reviewed_infantry_path)
        if reviewed_infantry_path.is_file()
        else OrderedDict()
    )
    installed_sections = read_sections(args.rules)
    supplemental_sections = OrderedDict()
    for source_path in SUPPLEMENTAL_SOURCE_FILES:
        if source_path.is_file():
            supplemental_sections.update(read_sections(source_path))
    reviewed_infantry = (
        infantry_sources(infantry_sections) if infantry_sections else {}
    )

    target_ids_by_list = OrderedDict(
        (list_name, []) for list_name in dict.fromkeys(TYPE_LISTS.values())
    )
    target_categories = {}
    for source_id, target in BUFF_TARGETS.items():
        # Most transform-only forms are closed dynamically at launch and are
        # intentionally absent from the committed buildable roster. Preserve
        # only reviewed historical static variants.
        if target.get('runtime_transform') and source_id not in STABLE_APPEND_IDS:
            continue
        category = target.get('category')
        list_name = TYPE_LISTS.get(category)
        if not list_name:
            continue
        target_ids_by_list[list_name].append(source_id.upper())
        target_categories[source_id.upper()] = category

    # Preserve mapper-reviewed extra infantry for later catalogue expansion.
    for source_id in reviewed_infantry:
        if (
            source_id in UNFINISHED_ASSET_IDS
            or source_id in EXCLUDED_REVIEWED_INFANTRY_IDS
        ):
            continue
        if source_id not in target_ids_by_list['InfantryTypes']:
            target_ids_by_list['InfantryTypes'].append(source_id)
            target_categories[source_id] = 'infantry-extra'

    definitions = OrderedDict()
    missing = []
    for list_name, source_ids in target_ids_by_list.items():
        for source_id in source_ids:
            if source_id in definitions:
                continue
            if source_id in reviewed_infantry:
                source_values = infantry_sections[reviewed_infantry[source_id]]
            else:
                template_source = SPECIAL_TEMPLATE_SOURCES.get(source_id, source_id)
                source_sections = installed_sections
                source_name = case_name(source_sections, template_source)
                if not source_name:
                    source_sections = supplemental_sections
                    source_name = case_name(source_sections, template_source)
                if not source_name:
                    missing.append(source_id)
                    continue
                source_values = source_sections[source_name]
            values = OrderedDict(source_values)
            if source_id in SPECIAL_REWARD_UNIT_IDS:
                normal_multiplier = (
                    '2' if target_categories[source_id] == 'infantry' else '1'
                )
                for key, value in list(values.items()):
                    lowered = str(key).lower()
                    if (
                        lowered in {
                            'buildtimemultiplier',
                            'buildtime.multiplefactory',
                        }
                        and str(value).strip() == '121'
                    ):
                        values[key] = (
                            normal_multiplier
                            if lowered == 'buildtimemultiplier'
                            else '1'
                        )
            if source_id in IMAGE_OVERRIDES:
                for key in list(values):
                    if key.lower() == 'image':
                        del values[key]
                values['Image'] = IMAGE_OVERRIDES[source_id]
            elif not any(key.lower() == 'image' and value for key, value in values.items()):
                values['Image'] = source_id
            values.update(TEMPLATE_VALUE_OVERRIDES.get(source_id, {}))
            removed_keys = TEMPLATE_VALUE_REMOVALS.get(source_id, ())
            for key in list(values):
                if str(key).lower() in removed_keys:
                    del values[key]
            definitions[source_id] = values

    if missing:
        raise ValueError('Installed rules missing target section(s): ' + ', '.join(missing))

    grouped_ids = OrderedDict((group, []) for group in OUTPUT_GROUPS)
    for source_id in definitions:
        category = target_categories[source_id]
        if (
            source_id in LIMITED_HERO_UNIT_IDS
            or (
                source_id in SPECIAL_REWARD_UNIT_IDS
                and category == 'infantry'
            )
            or category == 'infantry-extra'
        ):
            group = 'heroes'
        elif category == 'infantry':
            group = 'infantry'
        elif category == 'units' and source_id in NAVAL_UNIT_IDS:
            group = 'ships'
        elif category == 'units':
            group = 'vehicles'
        elif category == 'aircraft':
            group = 'aircraft'
        else:
            group = 'buildings'
        grouped_ids[group].append(source_id)
    for group, source_ids in grouped_ids.items():
        grouped_ids[group] = [
            source_id for source_id in source_ids
            if source_id not in STABLE_APPEND_IDS
        ] + [
            source_id for source_id in STABLE_APPEND_ORDER
            if source_id in source_ids
        ]

        # Keep committed section order byte-stable. Registry keys already stay
        # stable; sorting definitions by those keys prevents one new review
        # from moving hundreds of existing definitions in generated diffs.
        output_path = args.output_dir / OUTPUT_GROUPS[group][0]
        previous = read_sections(output_path) if output_path.is_file() else {}
        registry_order = {}
        list_ranks = {
            list_name: list_rank
            for list_rank, list_name in enumerate(dict.fromkeys(TYPE_LISTS.values()))
        }
        for list_rank, list_name in enumerate(dict.fromkeys(TYPE_LISTS.values())):
            actual = case_name(previous, list_name)
            for raw_key, clone_id in previous.get(actual, {}).items():
                clone_id = str(clone_id).upper()
                if not clone_id.startswith('MORP'):
                    continue
                try:
                    key_rank = int(raw_key)
                except ValueError:
                    key_rank = 1_000_000
                registry_order[clone_id[4:]] = (list_rank, key_rank)
        stable_ranks = {
            source_id: rank for rank, source_id in enumerate(STABLE_APPEND_ORDER)
        }

        def definition_order(source_id):
            list_name = TYPE_LISTS[target_categories[source_id].split('-', 1)[0]]
            list_rank, key_rank = registry_order.get(
                source_id,
                (list_ranks[list_name], 1_000_000),
            )
            if source_id in STABLE_APPEND_IDS:
                return list_rank, 1, stable_ranks[source_id]
            return list_rank, 0, key_rank

        grouped_ids[group] = sorted(
            grouped_ids[group],
            key=definition_order,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for group, source_ids in grouped_ids.items():
        if group not in selected_groups:
            continue
        filename, next_key = OUTPUT_GROUPS[group]
        output_path = args.output_dir / filename
        lines = [
            f'; Mental Omega Randomizer owned {group}',
            '; Generated by tools/generate_randomizer_units.py.',
            '; Runtime changes MORP* sections only. Native IDs remain AI/script types.',
            '',
        ]
        registry_groups = OrderedDict()
        for source_id in source_ids:
            list_name = TYPE_LISTS[target_categories[source_id].split('-', 1)[0]]
            registry_groups.setdefault(list_name, []).append(source_id)
        for list_name, registry_ids in registry_groups.items():
            lines.append(f'[{list_name}]')
            entries, next_key = stable_registry_entries(
                output_path, list_name, registry_ids, next_key
            )
            for registry_key, clone_id in entries:
                lines.append(f'{registry_key}={clone_id}')
            lines.append('')
        for source_id in source_ids:
            lines.extend(render_section(f'MORP{source_id}', definitions[source_id]))
            lines.append('')
        output_path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        print(
            f'Wrote {output_path}: {len(source_ids)} TechnoTypes, '
            f'{len(source_ids)} registry entries.'
        )


if __name__ == '__main__':
    main()
