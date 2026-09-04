"""Shared policy for building player-owned ``MORP*`` TechnoType templates.

``tools/generate_randomizer_units.py`` bakes the committed
``configs/Randomizer*.ini`` roster from an installed rules registry. The
launcher replays the same policy at map-generation time against the live
installed registry, so a submodded ``rulesmo.ini`` reaches player clones
without regenerating committed data. Both callers must apply identical
policy; keeping it here is what makes that true.
"""

from collections import OrderedDict


NORMAL_BUILD_TIME_SENTINEL = '121'
BUILD_TIME_MULTIPLIER_KEYS = ('buildtimemultiplier', 'buildtime.multiplefactory')


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
    'MAMUP': 'MAMU',
    'YAHCRE': 'YAHCR',
}
TEMPLATE_VALUE_OVERRIDES = {
    'RAVA': {
        # Installed RAVA is delayed as a campaign/power payload. Player
        # production uses normal vehicle timing and normal veterancy behavior.
        'BuildTimeMultiplier': '1',
        'Trainable': 'yes',
    },
    'YURIX2': {
        # Purgatory Challenge deploys the installed YURIX identity directly.
        # Keep the stable randomizer reward ID, but do not layer the unrelated
        # Death's Hand YURIX2 mission tuning over that source definition.
        'Image': 'YURIX',
        'BuildLimit': '1',
        'BuildTimeMultiplier': '2',
    },
    'MAMUP': {
        # Soviet Arms Race uses MAMU for the Apocalypse Prototype. Give the
        # campaign identity its own reward ID, without its scripted operator
        # and passenger gate.
        'Name': 'Apocalypse Prototype',
        'UIName': 'NAME:COPA',
        'Image': 'COPA',
        'Armor': 'ex_apoc',
        'Strength': '3600',
        'Speed': '5',
        'Passengers': '0',
    },
    'YAHCRE': {
        # Earthrise retools YAHCR into a mobile beam platform. Preserve the
        # installed Gehenna separately and expose this authored variant under
        # a stable reward identity.
        'Name': 'Gehenna Platform (Earthrise)',
        'UIName': 'NOSTR:Gehenna Platform (Earthrise)',
        'Image': 'YAHCRWO',
        'Primary': 'MiniAntaresBeam',
        'ElitePrimary': 'MiniAntaresBeamE',
        'Spawns': 'none',
        'SpawnsNumber': '0',
        'Speed': '5',
        'ROT': '3',
        'Turret': 'yes',
        'TurretROT': '4',
        'GuardRange': '12',
        'NoSpawnAlt': 'no',
        'PipScale': 'none',
        'LandTargeting': '0',
        'ImmuneToPsionics': 'yes',
        'VoiceMove': 'ChaosDroneMove',
        'VoiceAttack': 'ChaosDroneAttackCommand',
        'VoiceSelect': 'ChaosDroneSelect',
        'MaxDebris': '8',
        'MinDebris': '4',
        'Weight': '3',
    },
    # Give each boss Brute a distinct ArtType so its manually colored cameo
    # does not overwrite the shared [BRUT] art section used by every variant.
    'BRUTM': {
        'Image': 'BRUTM',
    },
    'BRUTS': {
        'Image': 'BRUTS',
    },
    'BRUTV': {
        'Image': 'BRUTV',
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
    'YURIPR': {
        # A free Cloning Vats copy can satisfy the hero BuildLimit while the
        # paid copy remains queued forever. Keep this limited hero unclonable.
        'Cloneable': 'no',
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
    'MAMUP': frozenset({
        'operator',
        'initialpayload.types',
        'initialpayload.nums',
    }),
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


def case_insensitive_section(sections, wanted):
    """Return the actual section name matching ``wanted``, ignoring case."""
    wanted = str(wanted or '').lower()
    if not wanted:
        return None
    return next(
        (name for name in sections if str(name).lower() == wanted),
        None,
    )


def template_source_id(source_id):
    """Return the installed section a reward identity is templated from."""
    source_id = str(source_id or '').upper()
    return SPECIAL_TEMPLATE_SOURCES.get(source_id, source_id)


def build_template_values(
    source_id,
    source_values,
    *,
    category,
    special_reward,
    description,
):
    """Return one ``MORP*`` template body from an installed source section.

    ``source_values`` is the complete installed/reviewed section for
    :func:`template_source_id`. The result is the reviewed player identity:
    campaign build delays normalized, art bound to the reward identity,
    reviewed value overrides applied, the shared clone tooltip installed, and
    campaign-only keys removed.
    """
    source_id = str(source_id or '').upper()
    values = OrderedDict(source_values)
    if special_reward:
        normal_multiplier = '2' if category == 'infantry' else '1'
        for key, value in list(values.items()):
            lowered = str(key).lower()
            if (
                lowered in BUILD_TIME_MULTIPLIER_KEYS
                and str(value).strip() == NORMAL_BUILD_TIME_SENTINEL
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
    elif not any(
        key.lower() == 'image' and value for key, value in values.items()
    ):
        values['Image'] = source_id
    values.update(TEMPLATE_VALUE_OVERRIDES.get(source_id, {}))
    description_key = next(
        (key for key in values if str(key).lower() == 'uidescription'),
        'UIDescription',
    )
    values[description_key] = description
    removed_keys = TEMPLATE_VALUE_REMOVALS.get(source_id, ())
    for key in list(values):
        if str(key).lower() in removed_keys:
            del values[key]
    return values
