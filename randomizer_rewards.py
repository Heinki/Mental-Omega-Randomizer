"""Reward catalogue and display helpers for the Mental Omega randomizer."""

from randomizer_weapon_stats import (
    ROSTER_DAMAGE_WEAPON_REFS,
    ROSTER_WEAPON_REFS,
    WEAPON_BASE_STATS,
)

# This module is intentionally data-heavy. Keeping it separate from the Tk
# launcher makes future Archipelago item/location work much easier.

ALLIED_BUILD_HOUSES = 'UnitedStates,Europeans,Pacific,Europeans2,MORPLAYER'
SOVIET_BUILD_HOUSES = 'USSR,Latin,Chinese,MORPLAYER'
EPSILON_BUILD_HOUSES = 'PsiCorps,Headquaters,ScorpionCell,MORPLAYER'
FOEHN_BUILD_HOUSES = 'Guild1,Guild2,Guild3,MORPLAYER'
ALL_BUILD_HOUSES = (
    ALLIED_BUILD_HOUSES + ',' + SOVIET_BUILD_HOUSES + ','
    + EPSILON_BUILD_HOUSES + ',' + FOEHN_BUILD_HOUSES
)
DEFAULT_REWARDS_PER_CHECK = 1
MAX_REWARDS_PER_CHECK = 30

# Complete playable 3.3.6 faction rosters.  These use the real rulesmo.ini
# section IDs, which frequently differ from the public-facing unit names.
# Keep economy, construction, support and hero units here too: a buffs-only
# seed must be able to improve every player-owned faction unit, not merely the
# small subset that also has an access reward.
FACTION_UNIT_ROSTERS = {
    'Allies': {
        'infantry': {
            'E1': 'GI', 'GGI': 'Guardian GI', 'ADOG': 'Allied Attack Dog',
            'ENGINEER': 'Allied Engineer', 'AMEDIC': 'Field Medic',
            'ENFO': 'Siege Cadre', 'JUMPJET': 'Rocketeer', 'GHOST': 'Navy SEAL',
            'SPY': 'Spy', 'RIOT': 'Riot Trooper', 'SNIPE': 'Sniper',
            'SUPR': 'Suppressor', 'CLEG': 'Chrono Legionnaire', 'TANY': 'Tanya',
            'SIEG': 'Siegfried', 'ARMR': 'Norio',
        },
        'units': {
            'CMIN': 'Chrono Miner', 'FV': 'Stryker IFV',
            'ETNK': 'Bulldog Light Tank', 'AMC': 'Archon AMC',
            'MTNK': 'Cavalier Medium Tank', 'TENGU': 'Tsurugi Powersuit',
            'KTNK': 'Kappa Hover Tank', 'ROBO': 'Robot Tank',
            'AHMV': 'Airborne Humvee', 'AMCV': 'Allied MCV',
            'SHAD': 'Stallion Transport', 'COMA': 'Warhawk',
            'MGTK': 'Mirage Tank', 'HOWI': 'Zephyr Artillery',
            'BASS': 'Athena Cannon', 'ABRM': 'Abrams Tank',
            'AERO': 'Aeroblaze', 'SREF': 'Prism Tank',
            'CHRTNK': 'Charon Tank', 'THOR': 'Thor Gunship',
            'VCARR': 'Hailstorm', 'BLZZ': 'Blizzard Tank',
            'BFRT': 'Battle Tortoise', 'CRYO': 'Cryocopter',
            'LCRF': 'Voyager Transport', 'DEST': 'Horizon Destroyer',
            'AEGIS': 'Aegis Cruiser', 'DLPH': 'Dolphin',
            'HCRUIS': 'Trident Battleship', 'CARRIER': 'Enterprise Aircraft Carrier',
            'SIREN': 'Siren Frigate',
        },
        'aircraft': {
            'STORM': 'Stormchild', 'ORCA': 'Harrier', 'BEAG': 'Black Eagle',
            'FORTRESS': 'Barracuda', 'HBIRD': 'Hummingbird',
        },
    },
    'Soviets': {
        'infantry': {
            'E2': 'Soviet Conscript', 'FLAKT': 'Flak Trooper',
            'DOG': 'Soviet Attack Dog', 'SENGINEER': 'Soviet Engineer',
            'FLAMER': 'Pyro', 'SHK': 'Tesla Trooper', 'SHOCK': 'Shock Trooper',
            'MOTOR': 'Mortar Quad', 'GYRO': 'Gyrocopter', 'DESO': 'Desolator',
            'DESOR': 'Eradicator', 'SBTR': 'Saboteur', 'ARSO': 'Arsonist',
            'CHITZ': 'Chitzkoi', 'VOLKOV': 'Volkov', 'MORALES': 'Morales',
            'YUNRU': 'Yunru',
        },
        'units': {
            'HARV': 'War Miner', 'HTK': 'Halftrack', 'SCAR': 'Tigr APC',
            'HTNK': 'Rhino Heavy Tank', 'JTNK': 'Jaguar Battle Tank',
            'CTNK': 'Qilin Assault Tank', 'DRON': 'Terror Drone',
            'SMCV': 'Soviet MCV', 'BOREK': 'Borillo', 'ARMA': 'Armadillo',
            'DTRUCK': 'Demolition Truck', 'BGGY': 'Bomb Buggy',
            'RAVA': 'Drakuv Prison Vehicle', 'TTNK': 'Tesla Cruiser',
            'V3': 'Scud Launcher', 'WOLF': 'Wolfhound', 'MWF': "Stalin's Fist",
            'APOC': 'Catastrophe Tank', 'BURA': 'Buratino', 'SCHP': 'Vulture',
            'FDRON': 'Fury Drone', 'EMPR': 'Nuwa Cannon', 'EDRN': 'Dragonfly',
            'SENT': 'Sentinel', 'CNTR': 'Centurion Siege Crawler',
            'ZEP': 'Kirov Airship', 'SAPC': 'Zubr Transport',
            'SUB': 'Typhoon Attack Sub', 'SWLF': 'Seawolf Gunboat',
            'REAP': 'Reaper Corvette', 'DBOAT': 'Mosquito Demoboat',
            'DRED': 'Kuznetsov Dreadnought', 'AKULA': 'Akula Missile Sub',
        },
        'aircraft': {'FOX': 'Foxtrot', 'DUST': 'Dustdevil'},
    },
    'Epsilon': {
        'infantry': {
            'INIT': 'Initiate', 'HARP': 'Archer', 'YDOG': 'Epsilon Spook',
            'YENGINEER': 'Epsilon Engineer', 'BRUTE': 'Brute', 'KAOS': 'Bloatick',
            'YURI': 'Epsilon Adept', 'YURIPR': 'Epsilon Elite',
            'INTRUDER': 'Infiltrator', 'HIJACKER': 'Hijacker',
            'REPU': 'Repulsor', 'SCRG': 'Scourge', 'STALKER': 'Stalker',
            'VIRUS': 'Virus', 'LIBRA': 'Libra', 'UNDER': 'Malver', 'ASSN': 'Rahn',
        },
        'units': {
            'YMIN': 'Ghost Miner', 'YTNK': 'Gatling Tank',
            'LTNK': 'Lasher Light Tank', 'QTNK': 'Mantis Scrap Tank',
            'STNK': 'Opus Custom Tank', 'STING': 'Stinger', 'PCV': 'Epsilon MCV',
            'DRIL': 'Driller APC', 'DISK': 'Invader', 'MARA': 'Marauder',
            'TRIKE': 'Speeder Trike', 'SHADOW': 'Shadow Tank',
            'MIND': 'Mastermind', 'TELE': 'Magnetron', 'YAHCR': 'Gehenna Platform',
            'SCAV': 'Tyrant', 'PLAG': 'Plague Splatter', 'COYO': 'Oxidizer',
            'DEVO': 'Colossus', 'QUAD': 'Hazequad', 'RUINER': 'Ruiner',
            'BASIL': 'Basilisk', 'GOTTER': 'Aerial Fortress Irkalla',
            'YHVR': 'Mandjet Transport', 'SLED': 'Piranha Minisub',
            'SQD': 'Giant Squid', 'NAUT': 'Nautilus Magnetic Sub',
            'BSUB': 'Resheph Ballistic Sub',
        },
        'aircraft': {'BLIGHT': 'Dybbuk-Attacker', 'VENOM': 'Dybbuk-Evolver'},
    },
    'Foehn': {
        'infantry': {
            'KNIGHT': 'Knightframe', 'COVE': 'Lancer',
            'FENGINEER': 'Foehn Engineer', 'HUNTR': 'Huntress',
            'SYNC': 'Syncronin', 'CLAIR': 'Clairvoyant', 'WASP': 'Neonwasp',
            'ZORB': 'Zorbtrotter', 'BANE': 'Giantsbane', 'SIBFIN': 'Fin',
            'SICALI': 'Alize', 'EUREKA': 'Eureka', 'URAGAN': 'Uragan',
        },
        'units': {
            'NMIN': 'Minermite', 'TERA': 'Teratorn', 'CYCL': 'Cyclops Walker',
            'DRACO': 'Draco Light Tank', 'ROACH': 'Bison Combat Tank',
            'JACKAL': 'Jackal Racer', 'FMCV': 'Foehn MCV', 'MSA': 'SODAR Array',
            'RACC': 'Raccoon', 'COON': 'Hovracoon', 'BUZZ': 'Buzzard',
            'COND': 'Condor', 'CONF': 'Irritator', 'ROADR': 'Roadrunner',
            'SWPR': 'Sweeper', 'MEGA': 'Megalodon', 'SHRAY': 'Shadray Torch Tank',
            'DIVER': 'Diverbee', 'MAD': 'M.A.D.M.A.N.', 'VIPER': 'Pteranodon',
            'TARCHIA': 'Tarchia Cannon', 'HURR': 'Alanqa Skystation',
            'ORCIN': 'Orcinus Waveshaper', 'PROME': 'Mastodon',
            'GHTNK': 'Gharial', 'BOID': 'Boidmachine', 'QUETZ': 'Quetzal',
            'SEAT': 'Watercat Transport', 'SWORD': 'Swordfish',
            'SHARK': 'Angelshark', 'MANTA': 'Whipray',
            'LEVI': 'Leviathan Helicarrier',
        },
        'aircraft': {'HARB': 'Harbinger'},
    },
}

# Snapshot of the installed 3.3.6 rules values used by map-local stat buffs.
# Tuple order: Cost, Speed, Strength, Sight, GuardRange, Ammo.  GuardRange
# falls back to Sight when the base rules inherit/omit it.
UNIT_BASE_STATS = {
    'E1': (120, 6, 135, 7, 7, None), 'GGI': (250, 6, 170, 6, 6, None),
    'ADOG': (100, 9, 75, 8, 7, None), 'ENGINEER': (300, 6, 90, 6, 9, None),
    'AMEDIC': (300, 7, 120, 8, 6, None), 'ENFO': (450, 7, 155, 6, 6, None),
    'JUMPJET': (450, 34, 135, 8, 8, None), 'GHOST': (600, 7, 170, 7, 7, None),
    'SPY': (800, 6, 140, 8, 8, None), 'RIOT': (950, 6, 265, 7, 7, None),
    'SNIPE': (650, 5, 145, 8, 8, None), 'SUPR': (950, 7, 340, 8, 8, None),
    'CLEG': (1250, 5, 210, 5, 5, None), 'TANY': (1500, 9, 200, 9, 9, None),
    'SIEG': (1500, 5, 430, 10, 10, 1), 'ARMR': (1500, 45, 290, 10, 10, None),
    'CMIN': (1400, 4, 1100, 4, 4, None), 'FV': (600, 8, 275, 6, 6, None),
    'ETNK': (700, 7, 395, 6, 6, 4), 'AMC': (650, 7, 330, 6, 6, None),
    'MTNK': (750, 6, 450, 6, 6, None), 'TENGU': (550, 7, 300, 7, 7, None),
    'KTNK': (750, 10, 420, 6, 6, None), 'ROBO': (550, 10, 330, 7, 7, None),
    'AHMV': (500, 9, 260, 6, 6, None), 'AMCV': (3000, 4, 2000, 7, 7, None),
    'SHAD': (1000, 40, 330, 8, 8, None), 'COMA': (1200, 34, 330, 7, 7, 8),
    'STORM': (1150, 30, 220, 8, 30, 1), 'MGTK': (1000, 6, 440, 6, 6, None),
    'ORCA': (1200, 25, 230, 8, 30, 1), 'HOWI': (950, 5, 360, 7, 14, None),
    'BEAG': (1300, 26, 260, 8, 30, 1), 'BASS': (1600, 4, 370, 6, 6, 1),
    'ABRM': (1500, 6, 500, 6, 6, 1), 'AERO': (1450, 6, 355, 6, 6, None),
    'SREF': (1450, 6, 330, 6, 6, None), 'CHRTNK': (1700, 4, 710, 6, 6, 1),
    'THOR': (2000, 14, 820, 9, 9, 1), 'VCARR': (1700, 4, 650, 6, 6, None),
    'BLZZ': (1300, 6, 530, 6, 6, None), 'BFRT': (1900, 4, 1250, 6, 6, None),
    'FORTRESS': (2000, 18, 340, 5, 30, 2), 'CRYO': (1400, 28, 460, 7, 7, None),
    'HBIRD': (1400, 36, 300, 6, 30, 2), 'LCRF': (1000, 7, 1000, 4, 4, None),
    'DEST': (1200, 6, 600, 6, 6, None), 'AEGIS': (1650, 4, 720, 6, 6, None),
    'DLPH': (600, 12, 200, 8, 4, None), 'HCRUIS': (2800, 3, 1350, 6, 15, 4),
    'CARRIER': (2500, 4, 1000, 6, 10, None), 'SIREN': (1500, 8, 360, 6, 6, None),
    'E2': (60, 7, 125, 7, 7, None), 'FLAKT': (150, 6, 145, 6, 6, None),
    'DOG': (100, 9, 75, 8, 7, None), 'SENGINEER': (300, 6, 90, 6, 9, None),
    'FLAMER': (350, 7, 225, 6, 6, None), 'SHK': (450, 6, 270, 7, 7, None),
    'SHOCK': (500, 6, 320, 7, 7, None), 'MOTOR': (600, 8, 220, 7, 7, None),
    'GYRO': (600, 26, 275, 9, 9, None), 'DESO': (950, 5, 210, 5, 5, 1),
    'DESOR': (1100, 5, 260, 5, 5, 1), 'SBTR': (1000, 6, 140, 8, 8, None),
    'ARSO': (1000, 6, 140, 8, 8, 1), 'CHITZ': (1000, 10, 500, 10, 10, None),
    'VOLKOV': (1500, 6, 600, 9, 9, None), 'MORALES': (1500, 7, 240, 9, 9, 1),
    'YUNRU': (1500, 6, 200, 9, 9, None), 'HARV': (1400, 4, 1200, 4, 4, None),
    'HTK': (550, 7, 330, 6, 6, None), 'SCAR': (600, 6, 385, 6, 6, None),
    'HTNK': (850, 5, 480, 6, 6, 3), 'JTNK': (750, 6, 435, 6, 6, None),
    'CTNK': (900, 4, 510, 6, 6, None), 'DRON': (500, 10, 140, 4, 6, None),
    'SMCV': (3000, 4, 2000, 6, 6, None), 'BOREK': (1000, 6, 700, 6, 6, None),
    'ARMA': (1200, 5, 790, 6, 6, None), 'DTRUCK': (1300, 6, 350, 6, 6, None),
    'BGGY': (1300, 8, 225, 6, 6, None), 'RAVA': (1800, 7, 1050, 6, 6, 3),
    'FOX': (1350, 24, 230, 8, 30, 2), 'DUST': (1400, 26, 400, 6, 30, 4),
    'TTNK': (1500, 6, 540, 6, 6, 2), 'V3': (1600, 4, 360, 6, 9, None),
    'WOLF': (1800, 20, 450, 8, 8, 4), 'MWF': (2500, 5, 2000, 6, 6, None),
    'APOC': (1600, 4, 620, 6, 6, None), 'BURA': (1350, 5, 360, 6, 6, 8),
    'SCHP': (1450, 34, 380, 8, 8, 1), 'FDRON': (500, 10, 180, 7, 6, None),
    'EMPR': (2000, 4, 1180, 6, 6, None), 'EDRN': (750, 45, 230, 8, 8, None),
    'SENT': (1500, 5, 540, 6, 6, 6), 'CNTR': (3000, 3, 2250, 6, 6, None),
    'ZEP': (2400, 9, 2000, 8, 8, 5), 'SAPC': (1000, 7, 1050, 4, 4, None),
    'SUB': (1100, 5, 720, 6, 6, None), 'SWLF': (900, 7, 450, 6, 6, None),
    'REAP': (1300, 8, 360, 6, 6, None), 'DBOAT': (1350, 8, 540, 6, 6, 1),
    'DRED': (2800, 4, 1200, 8, 10, None), 'AKULA': (2800, 3, 1300, 5, 5, None),
    'INIT': (150, 6, 150, 7, 7, None), 'HARP': (200, 6, 150, 6, 6, None),
    'YDOG': (100, 9, 75, 8, 7, None), 'YENGINEER': (300, 6, 90, 6, 9, None),
    'BRUTE': (500, 7, 365, 5, 5, None), 'KAOS': (350, 10, 100, 7, 7, None),
    'YURI': (1000, 5, 110, 8, 8, None), 'YURIPR': (1200, 6, 130, 8, 8, None),
    'INTRUDER': (1200, 6, 140, 8, 8, None), 'HIJACKER': (450, 7, 120, 8, 8, None),
    'REPU': (1250, 6, 120, 7, 7, 1), 'SCRG': (1050, 8, 190, 5, 5, 5),
    'STALKER': (1400, 5, 345, 6, 6, None), 'VIRUS': (1500, 4, 180, 8, 8, 1),
    'LIBRA': (1500, 10, 300, 9, 9, 3), 'UNDER': (1500, 6, 230, 10, 10, None),
    'ASSN': (1500, 7, 410, 9, 9, None), 'YMIN': (1400, 4, 1050, 4, 4, None),
    'YTNK': (600, 7, 300, 6, 6, None), 'LTNK': (700, 6, 420, 6, 6, 4),
    'QTNK': (600, 7, 310, 6, 6, None), 'STNK': (650, 6, 395, 6, 6, None),
    'STING': (550, 8, 330, 7, 7, None), 'PCV': (3000, 4, 2000, 7, 7, None),
    'DRIL': (1000, 4, 240, 4, 8, None), 'DISK': (1000, 32, 440, 6, 6, None),
    'MARA': (1000, 8, 240, 6, 6, None), 'TRIKE': (750, 11, 150, 7, 7, None),
    'SHADOW': (1000, 7, 350, 7, 7, None), 'BLIGHT': (1150, 22, 260, 8, 30, 6),
    'MIND': (1800, 4, 505, 6, 6, None), 'TELE': (1500, 5, 440, 7, 7, None),
    'YAHCR': (1500, 4, 540, 6, 18, None), 'SCAV': (1400, 7, 410, 6, 6, 18),
    'PLAG': (750, 6, 270, 6, 6, None), 'COYO': (1000, 7, 300, 7, 7, None),
    'DEVO': (1550, 5, 670, 7, 7, 8), 'QUAD': (900, 10, 260, 5, 5, None),
    'RUINER': (1100, 30, 600, 5, 5, None), 'BASIL': (1750, 25, 360, 8, 8, None),
    'GOTTER': (3000, 6, 1750, 10, 10, None), 'VENOM': (1700, 18, 440, 6, 30, 2),
    'YHVR': (800, 8, 950, 6, 6, None), 'SLED': (800, 9, 255, 4, 4, None),
    'SQD': (1000, 8, 440, 8, 5, None), 'NAUT': (2000, 5, 1000, 6, 6, None),
    'BSUB': (2800, 4, 950, 4, 4, None), 'KNIGHT': (450, 6, 270, 7, 7, None),
    'COVE': (500, 7, 300, 9, 9, None), 'FENGINEER': (300, 6, 90, 6, 9, None),
    'HUNTR': (800, 7, 240, 7, 7, None), 'SYNC': (950, 8, 220, 9, 9, None),
    'CLAIR': (400, 6, 200, 8, 8, None), 'WASP': (1050, 30, 250, 6, 6, 16),
    'ZORB': (1350, 7, 240, 7, 7, None), 'BANE': (1300, 5, 750, 8, 8, None),
    'SIBFIN': (1500, 7, 260, 10, 10, 15), 'SICALI': (1500, 7, 260, 10, 10, 1),
    'EUREKA': (1500, 6, 520, 9, 9, 1), 'URAGAN': (1500, 9, 1050, 10, 10, None),
    'NMIN': (900, 6, 510, 4, 4, None), 'TERA': (700, 9, 260, 7, 7, None),
    'CYCL': (800, 6, 450, 6, 7, None), 'DRACO': (750, 5, 420, 6, 6, None),
    'ROACH': (900, 4, 530, 6, 6, None), 'JACKAL': (750, 12, 360, 8, 8, None),
    'FMCV': (3000, 4, 2000, 7, 7, None), 'MSA': (950, 7, 750, 6, 6, None),
    'RACC': (850, 10, 240, 10, 10, None), 'COON': (900, 10, 280, 10, 10, None),
    'BUZZ': (1300, 26, 440, 7, 7, 4), 'COND': (1400, 24, 480, 7, 7, 1),
    'CONF': (1200, 5, 270, 7, 7, 6), 'ROADR': (1250, 8, 415, 4, 8, None),
    'SWPR': (1050, 7, 275, 7, 7, None), 'MEGA': (1700, 9, 920, 6, 5, 1),
    'SHRAY': (1600, 4, 315, 6, 6, None), 'DIVER': (900, 36, 220, 5, 5, None),
    'MAD': (3000, 3, 2400, 6, 6, 1), 'VIPER': (2000, 24, 900, 8, 8, None),
    'TARCHIA': (1650, 4, 650, 6, 6, 3), 'HURR': (2050, 15, 550, 9, 9, 1),
    'ORCIN': (1750, 5, 1150, 7, 7, None), 'HARB': (3000, 20, 2000, 0, 30, 8),
    'PROME': (2400, 3, 1450, 6, 6, 1), 'GHTNK': (2050, 5, 750, 6, 6, None),
    'BOID': (3000, 4, 2000, 6, 6, None), 'QUETZ': (2250, 18, 510, 10, 10, None),
    'SEAT': (1000, 6, 900, 6, 6, None), 'SWORD': (1000, 6, 470, 7, 7, None),
    'SHARK': (1400, 8, 460, 6, 6, 2), 'MANTA': (1300, 7, 650, 7, 7, None),
    'LEVI': (3200, 3, 1300, 8, 8, None),
}

def build_roster_weapon_stats():
    """Expand the generated rules registry into the normal reward format."""
    roster = {}
    field_names = ('damage', 'rof', 'range')
    for unit_id, weapon_ids in ROSTER_WEAPON_REFS.items():
        weapons = {}
        for weapon_id in weapon_ids:
            values = WEAPON_BASE_STATS.get(weapon_id)
            if not values:
                continue
            stats = {}
            for field, value in zip(field_names, values):
                if value is None or value <= 0:
                    continue
                # Damage=1 is commonly a launcher/scanner control value. The
                # real damaging payload is registered separately below.
                if field == 'damage' and value <= 1:
                    continue
                # ROF=1 is already the engine minimum and cannot be reduced
                # to make the weapon fire faster.
                if field == 'rof' and value <= 1:
                    continue
                stats[field] = value
            if stats:
                weapons[weapon_id] = stats
        for weapon_id in ROSTER_DAMAGE_WEAPON_REFS.get(unit_id, ()):
            values = WEAPON_BASE_STATS.get(weapon_id)
            damage = values[0] if values else None
            if damage is not None and damage > 1:
                weapons.setdefault(weapon_id, {})['damage'] = damage
        if weapons:
            roster[unit_id] = weapons
    return roster


# Complete playable 3.3.6 weapon baselines extracted from RULESMO.INI.
ROSTER_WEAPON_STATS = build_roster_weapon_stats()

# Installed 3.3.6 capability snapshot. Do not offer a one-time enable reward
# when the TechnoType already has that capability. Explicit ``no`` values are
# intentionally absent because those units can still gain the capability.
EXISTING_SELF_HEALING_IDS = frozenset('''
AMEDIC TTNK AKULA DRED SQD MIND QUETZ RIOT SUPR TANY SIEG ARMR CMIN AMCV COMA
ABRM CHRTNK THOR VCARR BFRT CRYO DLPH HCRUIS CARRIER STORM ORCA BEAG FORTRESS
HBIRD DESO DESOR CHITZ VOLKOV MORALES YUNRU HARV SMCV RAVA WOLF MWF APOC SCHP
EMPR EDRN CNTR ZEP FOX DUST BRUTE YURI YURIPR SCRG STALKER LIBRA UNDER ASSN
YMIN PCV DISK SCAV DEVO RUINER BASIL GOTTER NAUT BSUB BLIGHT VENOM WASP BANE
SIBFIN SICALI EUREKA URAGAN NMIN FMCV BUZZ COND MEGA MAD VIPER HURR PROME
GHTNK BOID LEVI FAFILD FACONF
'''.split())
EXISTING_CLOAK_IDS = frozenset('''
AKULA SUB SQD DLPH STORM ORCA BEAG FORTRESS HBIRD FOX DUST UNDER YMIN SHADOW
QUAD SLED NAUT BSUB BLIGHT VENOM SHARK GACPIL GACRYO NATRAP YAVNMM FAFILD
FACONF FAMMIN
'''.split())
EXISTING_SENSOR_IDS = frozenset('''
SHK AKULA DRED SUB SQD GHOST TANY SIEG ROBO DEST DLPH SHOCK VOLKOV MORALES
YUNRU BOREK ARMA LIBRA UNDER ASSN STING SHADOW SLED NAUT BSUB HUNTR SIBFIN
SICALI EUREKA MSA SWORD SHARK NASCOM FAFILD FACONF
'''.split())
EXISTING_CAPABILITY_IDS = {
    'self_healing': EXISTING_SELF_HEALING_IDS,
    'cloak': EXISTING_CLOAK_IDS,
    'sensors': EXISTING_SENSOR_IDS,
}

# These types mount disguise, capture/defuse, scanner, or explicit
# ``NotAWeapon`` helpers. Their WeaponType fields are engine controls rather
# than attacks, so weapon-stat rewards are misleading or ineffective.
NONCOMBAT_WEAPON_TARGET_IDS = frozenset({
    'ENGINEER', 'SENGINEER', 'YENGINEER', 'FENGINEER',
    'SPY', 'SBTR', 'INTRUDER', 'HIJACKER',
    'MWF', 'MSA', 'SWPR', 'ORCIN',
})

# Economy, base-operation, and mission-transport essentials are deliberately
# never access items. They remain available regardless of randomizer progress.
AMPHIBIOUS_TRANSPORT_UNIT_IDS = frozenset({'LCRF', 'SAPC', 'YHVR', 'SEAT'})
ALWAYS_AVAILABLE_UNIT_IDS = {
    'AMCV', 'SMCV', 'PCV', 'FMCV',
    'CMIN', 'HARV', 'YMIN', 'NMIN',
    'ENGINEER', 'SENGINEER', 'YENGINEER', 'FENGINEER',
    *AMPHIBIOUS_TRANSPORT_UNIT_IDS,
}
ALWAYS_AVAILABLE_BUILDING_IDS = {
    'GACNST', 'NACNST', 'YACNST', 'FACNST',
    'GAPOWR', 'NAPOWR', 'YAPOWR', 'FATRAP',
    'GAREFN', 'NAREFN', 'YAREFN', 'FAREFN',
}
ALWAYS_AVAILABLE_TECH_IDS = ALWAYS_AVAILABLE_UNIT_IDS | ALWAYS_AVAILABLE_BUILDING_IDS

# Explicit cross-faction gameplay roles used only for single-campaign buff
# sharing. Unique units remain independent; they are never forced into a weak
# equivalence merely because their broad sidebar category matches.
UNIT_ROLE_EQUIVALENCE_GROUPS = (
    # Infantry roles.
    frozenset({'E1', 'E2', 'INIT', 'KNIGHT'}),
    frozenset({'GGI', 'FLAKT', 'HARP', 'COVE'}),
    frozenset({'ADOG', 'DOG', 'YDOG'}),
    frozenset({'ENGINEER', 'SENGINEER', 'YENGINEER', 'FENGINEER'}),
    frozenset({'JUMPJET', 'GYRO', 'KAOS', 'WASP'}),
    frozenset({'RIOT', 'SHK', 'BRUTE', 'BANE'}),
    frozenset({'GHOST', 'VOLKOV', 'ASSN', 'EUREKA'}),
    frozenset({'SPY', 'SBTR', 'INTRUDER', 'SYNC'}),
    frozenset({'SNIPE', 'MORALES', 'VIRUS', 'HUNTR'}),
    frozenset({'AMEDIC', 'MOTOR', 'REPU', 'CLAIR'}),
    frozenset({'SUPR', 'DESO', 'SCRG', 'ZORB'}),
    frozenset({'TANY', 'YUNRU', 'LIBRA', 'SICALI'}),
    # Economy, vehicle, armor, artillery, support, and transport roles.
    frozenset({'CMIN', 'HARV', 'YMIN', 'NMIN'}),
    frozenset({'AMCV', 'SMCV', 'PCV', 'FMCV'}),
    frozenset({'AHMV', 'HTK', 'YTNK', 'JACKAL'}),
    frozenset({'FV', 'SCAR', 'DRIL', 'RACC'}),
    frozenset({'ETNK', 'HTNK', 'LTNK', 'DRACO'}),
    frozenset({'MTNK', 'JTNK', 'QTNK', 'CYCL'}),
    frozenset({'MGTK', 'CTNK', 'STNK', 'ROACH'}),
    frozenset({'HOWI', 'V3', 'YAHCR', 'TARCHIA'}),
    frozenset({'ABRM', 'APOC', 'DEVO', 'GHTNK'}),
    frozenset({'BFRT', 'CNTR', 'GOTTER', 'BOID'}),
    frozenset({'AMC', 'BURA', 'PLAG', 'SHRAY'}),
    frozenset({'SREF', 'EMPR', 'TELE', 'MSA'}),
    frozenset({'ROBO', 'DRON', 'MARA', 'TERA'}),
    frozenset({'SHAD', 'BOREK', 'LCRF', 'SAPC', 'YHVR', 'SEAT'}),
    # Aircraft and airborne combat roles.
    frozenset({'STORM', 'FOX', 'BLIGHT', 'QUETZ'}),
    frozenset({'ORCA', 'DUST', 'VENOM', 'HARB'}),
    frozenset({'THOR', 'SCHP', 'DISK', 'DIVER'}),
    frozenset({'FORTRESS', 'ZEP', 'BASIL', 'HURR'}),
    # Naval roles.
    frozenset({'DEST', 'SWLF', 'SLED', 'SWORD'}),
    frozenset({'SIREN', 'SUB', 'NAUT', 'SHARK'}),
    frozenset({'DLPH', 'DBOAT', 'SQD', 'MANTA'}),
    frozenset({'HCRUIS', 'DRED', 'BSUB', 'LEVI'}),
    frozenset({'AEGIS', 'REAP', 'ORCIN'}),
    # Comparable defensive roles.
    frozenset({'GAPILL', 'NALASR', 'NATBNK', 'FASONI'}),
    frozenset({'NASAM', 'NAFLAK', 'YAGGUN', 'FAGUAR'}),
    frozenset({'ATESLA', 'TESLA', 'YARAIL', 'FARAIL'}),
    frozenset({'GTGCAN', 'NAHAMM', 'YAHADE', 'FACOMP'}),
    frozenset({'GACRYO', 'NATRAP', 'YAVNMM', 'FAMMIN'}),
    frozenset({'GAGAP', 'NASCOM', 'YAMPSI', 'FAINHI'}),
)


def unit_role_equivalents(unit_id):
    unit_id = str(unit_id or '').upper()
    equivalents = {unit_id} if unit_id else set()
    for group in UNIT_ROLE_EQUIVALENCE_GROUPS:
        if unit_id in group:
            equivalents.update(group)
    return frozenset(equivalents)

FACTION_DEFENSE_ROSTERS = {
    'Allies': {
        'GAPILL': 'Allied Pillbox',
        'NASAM': 'Allied Patriot Missiles',
        'GAGUN': 'Allied Gun Turret',
        'GACPIL': 'Camo Pillbox',
        'ATESLA': 'Allied Prism Tower',
        'GTGCAN': 'Allied Grand Cannon',
        'GASTAS': 'Ultra Dome',
        'GAHYPE': 'Hyperion',
        'GACRYO': 'Cryomines',
        'GAGAP': 'Allied Gap Generator',
        'GAPOST': 'Allied Warpnode',
    },
    'Soviets': {
        'NALASR': 'Soviet Sentry Gun',
        'NAFLAK': 'Soviet Flak Cannon',
        'NABNKR': 'Soviet Battle Bunker',
        'TESLA': 'Soviet Tesla Coil',
        'NASCOM': 'Soviet Sensor Tower',
        'NAHAMM': 'Soviet Hammer Defense',
        'NAMORT': 'Smoke Turret',
        'NADRON': 'Soviet Repair Crane',
        'NAEMPS': 'EMP Control Station',
        'NATRAP': 'EMP Mines',
        'NAIRDM': 'Soviet Iron Guard',
    },
    'Epsilon': {
        'YAGGUN': 'Epsilon Gatling Cannon',
        'NATBNK': 'Epsilon Tank Bunker',
        'YARAIL': 'Epsilon Inferno Tower',
        'YAMPSI': 'Epsilon Mind Reader',
        'YARIFT': 'Epsilon Chimera Core',
        'YAHADE': 'Epsilon Antares Battery',
        'YAPSYT': 'PsiCorps Psychic Tower',
        'YAVNMM': 'Epsilon Genomines',
        'YAMREF': 'Epsilon War Rig',
    },
    'Foehn': {
        'FASONI': 'Foehn Sonic Emitter',
        'FAGUAR': 'Foehn Shrike Nest',
        'FAFILD': 'Foehn Stun Grid',
        'FACONF': 'Foehn Turmoil Grid',
        'FARAIL': 'Foehn Railgun Tower',
        'FACOAT': 'Foehn Nanocoat Regulator',
        'FACOMP': 'Foehn Neutralizer',
        'FAINHI': 'Foehn Signal Inhibitor',
        'FAAVAL': 'Plasmerizer',
        'FABTRC': 'Foehn Blast Trench',
        'FAMMIN': 'M.A.D. Mine',
        'FAHARB': 'Harbinger Tower',
    },
}

# Tuple order: Cost, Strength, Sight, GuardRange.
DEFENSE_BASE_STATS = {
    'GAPILL': (400, 500, 7, 7), 'NASAM': (800, 900, 10, 12),
    'GAGUN': (600, 700, 7, 7.5), 'GACPIL': (500, 375, 6, 6),
    'ATESLA': (1200, 850, 8, 9), 'GTGCAN': (1800, 1650, 10, 14),
    'GASTAS': (1000, 1800, 4, 9), 'GAHYPE': (2000, 2000, 10, 15),
    'GACRYO': (75, 150, 4, 4), 'GAGAP': (1500, 700, 5, 5),
    'GAPOST': (1000, 850, 7, 9),
    'NALASR': (400, 500, 7, 7), 'NAFLAK': (700, 800, 10, 12),
    'NABNKR': (500, 900, 6, 6), 'TESLA': (1200, 850, 8, 8),
    'NASCOM': (800, 650, 15, 10), 'NAHAMM': (1800, 1650, 10, 14),
    'NAMORT': (900, 750, 7, 12), 'NADRON': (800, 800, 4, 4),
    'NAEMPS': (1000, 1000, 6, 6), 'NATRAP': (75, 150, 2, 6),
    'NAIRDM': (1800, 700, 6, 6),
    'YAGGUN': (700, 800, 10, 12), 'NATBNK': (300, 975, 6, 6),
    'YARAIL': (1200, 850, 8, 9), 'YAMPSI': (800, 600, 9, 9),
    'YARIFT': (1400, 600, 5, 9), 'YAHADE': (1800, 1650, 10, 15),
    'YAPSYT': (1500, 1050, 10, 8), 'YAVNMM': (75, 150, 4, 4),
    'YAMREF': (2000, 1350, 5, 10),
    'FASONI': (500, 650, 7, 6.5), 'FAGUAR': (700, 850, 8, 14),
    'FAFILD': (40, 120, 2, 2), 'FACONF': (40, 140, 2, 2),
    'FARAIL': (1200, 850, 8, 8), 'FACOAT': (1000, 800, 7, 7),
    'FACOMP': (1800, 1650, 10, 14), 'FAINHI': (2500, 650, 5, 9.5),
    'FAAVAL': (3000, 6000, 10, 21), 'FABTRC': (150, 700, 2, 8),
    'FAMMIN': (300, 400, 4, 4), 'FAHARB': (2000, 1000, 6, 6),
}

DEFENSE_WEAPON_STATS = {
    'GAPILL': {'Vulcan2': {'damage': 80, 'rof': 30, 'range': 6}},
    'NASAM': {'RedEye2': {'damage': 45, 'rof': 40, 'range': 12}},
    'GAGUN': {'TurretGun': {'damage': 80, 'rof': 50, 'range': 7.5}},
    'GACPIL': {'CamoVulcan2': {'damage': 120, 'rof': 40, 'range': 6}},
    'ATESLA': {
        'PrismShot': {'damage': 110, 'rof': 50, 'range': 8},
        'PrismShotSupport': {'damage': 110, 'rof': 50, 'range': 9},
    },
    'GTGCAN': {'GrandCannonWeapon': {'damage': 145, 'rof': 140, 'range': 14}},
    'GAHYPE': {'HyperionBlast': {'damage': 30, 'rof': 2, 'range': 15}},
    'GACRYO': {'CryomineBomb': {'damage': 30, 'rof': 10, 'range': 2}},
    'NALASR': {'Vulcan': {'damage': 25, 'rof': 12, 'range': 6}},
    'NAFLAK': {'FlakWeapon': {'damage': 24, 'rof': 20, 'range': 12}},
    'TESLA': {
        'CoilBolt': {'damage': 200, 'rof': 110, 'range': 8},
        'OPCoilBolt': {'damage': 300, 'rof': 55, 'range': 8},
    },
    'NAHAMM': {'HammerWeapon': {'damage': 140, 'rof': 140, 'range': 14}},
    'NATRAP': {'MineBomb': {'damage': 150, 'rof': 10, 'range': 2}},
    'YAGGUN': {
        'AGGattling': {'damage': 32, 'rof': 15, 'range': 6},
        'AAGattCann': {'damage': 25, 'rof': 14, 'range': 12},
        'AGGattling2': {'damage': 32, 'rof': 12, 'range': 6},
        'AAGattCann2': {'damage': 25, 'rof': 12, 'range': 12},
    },
    'YARAIL': {
        'InfernoRailgun': {'damage': 170, 'rof': 80, 'range': 8},
        'InfernoRailgunBlue': {'damage': 250, 'rof': 80, 'range': 9},
    },
    'YAHADE': {
        'AntaresBeam': {'damage': 140, 'rof': 140, 'range': 14},
        'AntaresBeamBlue': {'damage': 210, 'rof': 140, 'range': 15},
    },
    'YAVNMM': {'GenomineBomb': {'damage': 200, 'rof': 10, 'range': 2}},
    'FASONI': {'EmitterZap': {'damage': 50, 'rof': 70, 'range': 6.5}},
    'FARAIL': {'RailgunTowerBlast': {'damage': 125, 'rof': 120, 'range': 8}},
    'FACOMP': {'NeutralizerCutter': {'damage': 12, 'rof': 1, 'range': 14}},
}

# RULESMO.INI explicitly marks these defenses Trainable=yes and gives them
# veteran/elite behavior.  Support structures and mine-style defenses without
# that flag must not receive a dead "Veteran start" reward.
TRAINABLE_DEFENSE_IDS = {
    'GAPILL', 'NASAM', 'GAGUN', 'GACPIL', 'ATESLA', 'GTGCAN', 'GAHYPE',
    'NALASR', 'NAFLAK', 'TESLA', 'NAHAMM',
    'YAGGUN', 'YARAIL', 'YAHADE', 'YAPSYT',
    'FASONI', 'FAGUAR', 'FARAIL', 'FACOMP', 'FAAVAL',
}


def build_unlock(section, tech_level, prerequisite=None, houses=ALLIED_BUILD_HOUSES):
    values = {
        'TechLevel': str(tech_level),
        'Owner': houses,
        'RequiredHouses': houses,
        'ForbiddenHouses': 'none',
    }
    if prerequisite:
        values['PrerequisiteOverride'] = prerequisite
    return {section: values}

UNIT_UNLOCK_REWARDS = [
    {
        'name': 'GI Access',
        'description': 'Allows basic Allied GIs where the map tech tree permits them.',
        'rules': build_unlock('E1', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Guardian GI Access',
        'description': 'Allows Guardian GIs where the map tech tree permits them.',
        'rules': build_unlock('GGI', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Attack Dog Access',
        'description': 'Allows Allied Attack Dogs where the map tech tree permits them.',
        'rules': build_unlock('ADOG', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Field Medic Access',
        'description': 'Allows Allied Field Medics where the map tech tree permits them.',
        'rules': build_unlock('AMEDIC', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Rocketeer Access',
        'description': 'Allows Rocketeers where the map tech tree permits them.',
        'rules': build_unlock('JUMPJET', 1, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Humvee Access',
        'description': 'Allows Humvees where the map tech tree permits them.',
        'rules': build_unlock('AHMV', 2, 'GAWEAP'),
        'factions': ['Allies'],
    },
    {
        'name': 'IFV Access',
        'description': 'Allows IFVs where the map tech tree permits them.',
        'rules': build_unlock('FV', 2, 'GAWEAP'),
        'factions': ['Allies'],
    },
    {
        'name': 'Chrono Legionnaire Access',
        'description': (
            'Allows Chrono Legionnaire training from any Allied Barracks, '
            'including in low-tech missions.'
        ),
        'rules': build_unlock('CLEG', 3, 'GAPILE'),
        'factions': ['Allies'],
    },
    {
        'name': 'Barracuda Access',
        'description': 'Allows Barracuda production from an Allied airfield.',
        'rules': build_unlock('FORTRESS', 4, 'GAAIRC'),
        'factions': ['Allies'],
    },
    {
        'name': 'Conscript Access',
        'description': 'Allows Conscripts where the map tech tree permits them.',
        'rules': build_unlock('E2', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Flak Trooper Access',
        'description': 'Allows Flak Troopers where the map tech tree permits them.',
        'rules': build_unlock('FLAKT', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Soviet Attack Dog Access',
        'description': 'Allows Soviet Attack Dogs where the map tech tree permits them.',
        'rules': build_unlock('DOG', 1, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Tesla Trooper Access',
        'description': 'Allows Tesla Troopers where the map tech tree permits them.',
        'rules': build_unlock('SHK', 2, 'NAHAND', SOVIET_BUILD_HOUSES),
        'factions': ['Soviets'],
    },
    {
        'name': 'Heavy Tank Access',
        'description': 'Allows Soviet Heavy Tanks where the map tech tree permits them.',
        'rules': {'HTNK': {'TechLevel': '2'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Flak Track Access',
        'description': 'Allows Flak Tracks where the map tech tree permits them.',
        'rules': {'HTK': {'TechLevel': '2'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Tesla Tank Access',
        'description': 'Allows Tesla Tanks where the map tech tree permits them.',
        'rules': {'TTNK': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Akula Access',
        'description': 'Allows Akulas where the map tech tree permits them.',
        'rules': {'AKULA': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Dreadnought Access',
        'description': 'Allows Dreadnoughts where the map tech tree permits them.',
        'rules': {'DRED': {'TechLevel': '4'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Initiate Access',
        'description': 'Allows Initiates where the map tech tree permits them.',
        'rules': {'INIT': {'TechLevel': '1'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Lasher Tank Access',
        'description': 'Allows Lasher Tanks where the map tech tree permits them.',
        'rules': {'LTNK': {'TechLevel': '2'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Gatling Tank Access',
        'description': 'Allows Gatling Tanks where the map tech tree permits them.',
        'rules': {'YTNK': {'TechLevel': '2'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Virus Access',
        'description': 'Allows Viruses where the map tech tree permits them.',
        'rules': {'VIRUS': {'TechLevel': '3'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Mastermind Access',
        'description': 'Allows Masterminds where the map tech tree permits them.',
        'rules': {'MIND': {'TechLevel': '4'}},
        'factions': ['Epsilon'],
    },
    {
        'name': 'Knightframe Access',
        'description': 'Allows Knightframes where the map tech tree permits them.',
        'rules': {'KNIGHT': {'TechLevel': '1'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Jackal Racer Access',
        'description': 'Allows Jackal Racers where the map tech tree permits them.',
        'rules': {'JACKAL': {'TechLevel': '2'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Cyclops Walker Access',
        'description': 'Allows Cyclops Walkers where the map tech tree permits them.',
        'rules': {'CYCL': {'TechLevel': '2'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Draco Tank Access',
        'description': 'Allows Draco Tanks where the map tech tree permits them.',
        'rules': {'DRACO': {'TechLevel': '3'}},
        'factions': ['Foehn'],
    },
    {
        'name': 'Quetzal Access',
        'description': 'Allows Quetzals where the map tech tree permits them.',
        'rules': {'QUETZ': {'TechLevel': '4'}},
        'factions': ['Foehn'],
    },
]

EXTRA_UNIT_UNLOCK_REWARDS = [
    {
        'name': 'Destroyer Access',
        'description': 'Allows Allied Destroyers where the map tech tree permits them.',
        'rules': build_unlock('DEST', 3, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Dolphin Access',
        'description': 'Allows Dolphins where the map tech tree permits them.',
        'rules': build_unlock('DLPH', 3, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Aegis Cruiser Access',
        'description': 'Allows Aegis Cruisers where the map tech tree permits them.',
        'rules': build_unlock('AEGIS', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Aircraft Carrier Access',
        'description': 'Allows Aircraft Carriers where the map tech tree permits them.',
        'rules': build_unlock('CARRIER', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Battlecruiser Access',
        'description': 'Allows Allied battlecruisers where the map tech tree permits them.',
        'rules': build_unlock('HCRUIS', 4, 'GAYARD'),
        'factions': ['Allies'],
    },
    {
        'name': 'Typhoon Sub Access',
        'description': 'Allows Soviet submarines where the map tech tree permits them.',
        'rules': {'SUB': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
    {
        'name': 'Squid Access',
        'description': 'Allows Giant Squids where the map tech tree permits them.',
        'rules': {'SQD': {'TechLevel': '3'}},
        # Mental Omega 3.3.6 assigns SQD to the Epsilon naval roster.  This
        # used to say Soviets even though normalize_roster_unlock_rules()
        # correctly rewrote its ownership/prerequisite to Epsilon, allowing
        # an Epsilon cameo into Soviet seeds.
        'factions': ['Epsilon'],
    },
    {
        'name': 'Sea Scorpion Access',
        'description': 'Allows Sea Scorpions where the map tech tree permits them.',
        'rules': {'DBOAT': {'TechLevel': '3'}},
        'factions': ['Soviets'],
    },
]

FACTION_ACCESS_RULES = {
    'Allies': {
        'houses': ALLIED_BUILD_HOUSES, 'infantry': 'GAPILE',
        'units': 'GAWEAP', 'aircraft': 'GAAIRC', 'naval': 'GAYARD',
        'defenses': 'GACNST',
    },
    'Soviets': {
        'houses': SOVIET_BUILD_HOUSES, 'infantry': 'NAHAND',
        'units': 'NAWEAP', 'aircraft': 'NAAIR', 'naval': 'NAYARD',
        'defenses': 'NACNST',
    },
    'Epsilon': {
        'houses': EPSILON_BUILD_HOUSES, 'infantry': 'YABRCK',
        'units': 'YAWEAP', 'aircraft': 'YAAIRF', 'naval': 'YAYARD',
        'defenses': 'YACNST',
    },
    'Foehn': {
        'houses': FOEHN_BUILD_HOUSES, 'infantry': 'FABARR',
        'units': 'FAWEAP', 'aircraft': 'FAWEAP', 'naval': 'FAYARD',
        'defenses': 'FACNST',
    },
}

NAVAL_UNIT_IDS = {
    'LCRF', 'DEST', 'AEGIS', 'DLPH', 'HCRUIS', 'CARRIER', 'SIREN',
    'SAPC', 'SUB', 'SWLF', 'REAP', 'DBOAT', 'DRED', 'AKULA',
    'YHVR', 'SLED', 'SQD', 'NAUT', 'BSUB',
    'SEAT', 'SWORD', 'SHARK', 'MANTA', 'LEVI',
}


def access_target_lookup():
    lookup = {}
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        for category, units in categories.items():
            for unit_id, label in units.items():
                lookup[unit_id] = (faction, category, label)
    return lookup


def reward_tech_ids(rewards):
    return {
        section.upper()
        for reward in rewards
        for section, values in reward.get('rules', {}).items()
        if any(key.lower() == 'techlevel' for key in values)
    }


def build_missing_roster_unlock_rewards(existing_rewards):
    existing_ids = reward_tech_ids(existing_rewards)
    rewards = []
    for unit_id, (faction, category, label) in access_target_lookup().items():
        if unit_id in ALWAYS_AVAILABLE_UNIT_IDS or unit_id in existing_ids:
            continue
        access = FACTION_ACCESS_RULES[faction]
        prerequisite = access['naval'] if unit_id in NAVAL_UNIT_IDS else access[category]
        rewards.append({
            'name': f'{label} Access',
            'description': f'Allows {label} production from the earliest matching faction facility.',
            'rules': build_unlock(unit_id, 1, prerequisite, access['houses']),
            'factions': [faction],
        })
    return rewards


def build_defense_unlock_rewards():
    rewards = []
    for faction, defenses in FACTION_DEFENSE_ROSTERS.items():
        access = FACTION_ACCESS_RULES[faction]
        for defense_id, label in defenses.items():
            rewards.append({
                'name': f'{label} Access',
                'description': f'Allows {label} construction from the faction Construction Yard.',
                'access_category': 'defense',
                'rules': build_unlock(defense_id, 1, access['defenses'], access['houses']),
                'factions': [faction],
            })
    return rewards


def normalize_roster_unlock_rules(rewards):
    lookup = access_target_lookup()
    for reward in rewards:
        for section, values in reward.get('rules', {}).items():
            unit_id = section.upper()
            target = lookup.get(unit_id)
            if not target or unit_id in ALWAYS_AVAILABLE_UNIT_IDS:
                continue
            faction, category, _ = target
            access = FACTION_ACCESS_RULES[faction]
            prerequisite = access['naval'] if unit_id in NAVAL_UNIT_IDS else access[category]
            values.update({
                'Owner': access['houses'],
                'RequiredHouses': access['houses'],
                'ForbiddenHouses': 'none',
                'PrerequisiteOverride': prerequisite,
            })


ROSTER_UNIT_UNLOCK_REWARDS = build_missing_roster_unlock_rewards(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS
)
DEFENSE_UNLOCK_REWARDS = build_defense_unlock_rewards()
normalize_roster_unlock_rules(
    UNIT_UNLOCK_REWARDS + EXTRA_UNIT_UNLOCK_REWARDS + ROSTER_UNIT_UNLOCK_REWARDS
)

BUFF_TARGETS = {
    'MOR_BUILDINGS': {
        'label': 'Faction Production',
        'plural': 'Faction production queues',
        'category': 'global',
        'factions': ['Allies', 'Soviets', 'Epsilon', 'Foehn'],
        'allowed_buff_types': ['production'],
        'buff_descriptions': {
            'production': (
                'Infantry, vehicles, aircraft, buildings, and defenses have '
                '15% shorter production times for the player faction and enabled allied helpers.'
            ),
        },
        'global_buff': True,
        'global_production': True,
    },
    'E1': {
        'label': 'GI',
        'plural': 'GIs',
        'category': 'infantry',
        'factions': ['Allies'],
        'cost': 100,
        'speed': 6,
        'strength': 125,
        'sight': 5,
        'guard_range': 5,
        'weapons': {
            'M60': {'damage': 15, 'rof': 20, 'range': 4},
            'M60E': {'damage': 20, 'rof': 20, 'range': 5},
            'Para': {'damage': 18, 'rof': 20, 'range': 5},
            'ParaE': {'damage': 24, 'rof': 20, 'range': 6},
        },
    },
    'GGI': {'label': 'Guardian GI', 'plural': 'Guardian GIs', 'category': 'infantry', 'factions': ['Allies'], 'cost': 150, 'speed': 6, 'strength': 150, 'sight': 6, 'guard_range': 6},
    'AMEDIC': {'label': 'Field Medic', 'plural': 'Field Medics', 'category': 'infantry', 'factions': ['Allies'], 'cost': 500, 'speed': 6, 'strength': 125, 'sight': 5, 'guard_range': 5},
    'JUMPJET': {'label': 'Rocketeer', 'plural': 'Rocketeers', 'category': 'infantry', 'factions': ['Allies'], 'cost': 650, 'speed': 8, 'strength': 150, 'sight': 7, 'guard_range': 7},
    'E2': {
        'label': 'Conscript', 'plural': 'Conscripts', 'category': 'infantry',
        'factions': ['Soviets'], 'cost': 100, 'speed': 7, 'strength': 125,
        'sight': 7, 'guard_range': 7,
        'weapons': {
            'M1Carbine': {'damage': 16, 'rof': 20, 'range': 5},
            'M1CarbineE': {'damage': 16, 'rof': 20, 'range': 5},
        },
    },
    'FLAKT': {'label': 'Flak Trooper', 'plural': 'Flak Troopers', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 300, 'speed': 5, 'strength': 125, 'sight': 6, 'guard_range': 6},
    'DOG': {'label': 'Soviet Attack Dog', 'plural': 'Soviet Attack Dogs', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 200, 'speed': 8, 'strength': 100, 'sight': 5, 'guard_range': 5},
    'SHK': {'label': 'Tesla Trooper', 'plural': 'Tesla Troopers', 'category': 'infantry', 'factions': ['Soviets'], 'cost': 500, 'speed': 4, 'strength': 200, 'sight': 6, 'guard_range': 6},
    'AHMV': {
        'label': 'Humvee',
        'plural': 'Humvees',
        'category': 'units',
        'factions': ['Allies'],
        'cost': 500,
        'speed': 9,
        'strength': 300,
        'sight': 6,
        'guard_range': 6,
        'weapons': {
            'HumveeGun': {'damage': 60, 'rof': 35, 'range': 6},
            'HumveeGunE': {'damage': 75, 'rof': 30, 'range': 7},
        },
    },
    'FV': {'label': 'IFV', 'plural': 'IFVs', 'category': 'units', 'factions': ['Allies'], 'cost': 800, 'speed': 10, 'strength': 300, 'sight': 8, 'guard_range': 8},
    'HTNK': {'label': 'Heavy Tank', 'plural': 'Heavy Tanks', 'category': 'units', 'factions': ['Soviets'], 'cost': 900, 'speed': 7, 'strength': 500, 'sight': 6, 'guard_range': 6},
    'HTK': {'label': 'Flak Track', 'plural': 'Flak Tracks', 'category': 'units', 'factions': ['Soviets'], 'cost': 500, 'speed': 8, 'strength': 250, 'sight': 5, 'guard_range': 5},
    'TTNK': {'label': 'Tesla Tank', 'plural': 'Tesla Tanks', 'category': 'units', 'factions': ['Soviets'], 'cost': 1200, 'speed': 6, 'strength': 400, 'sight': 7, 'guard_range': 7},
    'AKULA': {'label': 'Akula', 'plural': 'Akulas', 'category': 'units', 'factions': ['Soviets'], 'cost': 1200, 'speed': 5, 'strength': 600, 'sight': 8, 'guard_range': 8},
    'DRED': {'label': 'Dreadnought', 'plural': 'Dreadnoughts', 'category': 'units', 'factions': ['Soviets'], 'cost': 2000, 'speed': 4, 'strength': 800, 'sight': 8, 'guard_range': 8},
    'SUB': {'label': 'Typhoon Sub', 'plural': 'Typhoon Subs', 'category': 'units', 'factions': ['Soviets'], 'cost': 1000, 'speed': 4, 'strength': 600, 'sight': 8, 'guard_range': 8},
    'SQD': {'label': 'Giant Squid', 'plural': 'Giant Squids', 'category': 'units', 'factions': ['Soviets'], 'cost': 1000, 'speed': 8, 'strength': 300, 'sight': 5, 'guard_range': 5},
    'DBOAT': {'label': 'Sea Scorpion', 'plural': 'Sea Scorpions', 'category': 'units', 'factions': ['Soviets'], 'cost': 600, 'speed': 8, 'strength': 400, 'sight': 7, 'guard_range': 7},
    'SAPC': {'label': 'Soviet Transport', 'plural': 'Soviet Transports', 'category': 'units', 'factions': ['Soviets'], 'cost': 900, 'speed': 6, 'strength': 300, 'sight': 6, 'guard_range': 6},
    'INIT': {
        'label': 'Initiate', 'plural': 'Initiates', 'category': 'infantry',
        'factions': ['Epsilon'], 'cost': 150, 'speed': 6, 'strength': 150,
        'sight': 7, 'guard_range': 7,
        'weapons': {
            'PsychicJab': {'damage': 27, 'rof': 18, 'range': 5.5},
            'PsychicJabE': {'damage': 27, 'rof': 18, 'range': 5.5},
        },
    },
    'LTNK': {'label': 'Lasher Tank', 'plural': 'Lasher Tanks', 'category': 'units', 'factions': ['Epsilon'], 'cost': 700, 'speed': 8, 'strength': 350, 'sight': 6, 'guard_range': 6},
    'YTNK': {'label': 'Gatling Tank', 'plural': 'Gatling Tanks', 'category': 'units', 'factions': ['Epsilon'], 'cost': 600, 'speed': 8, 'strength': 300, 'sight': 6, 'guard_range': 6},
    'VIRUS': {'label': 'Virus', 'plural': 'Viruses', 'category': 'infantry', 'factions': ['Epsilon'], 'cost': 700, 'speed': 5, 'strength': 100, 'sight': 8, 'guard_range': 8},
    'MIND': {'label': 'Mastermind', 'plural': 'Masterminds', 'category': 'units', 'factions': ['Epsilon'], 'cost': 1500, 'speed': 5, 'strength': 300, 'sight': 8, 'guard_range': 8},
    'KNIGHT': {
        'label': 'Knightframe', 'plural': 'Knightframes', 'category': 'infantry',
        'factions': ['Foehn'], 'cost': 500, 'speed': 6, 'strength': 270,
        'sight': 7, 'guard_range': 7,
        'weapons': {
            'KnightGun': {'damage': 50, 'rof': 55, 'range': 6},
            'KnightGunAA': {'damage': 50, 'rof': 55, 'range': 7},
            'KnightGunE': {'damage': 50, 'rof': 55, 'range': 6},
            'KnightGunAAE': {'damage': 50, 'rof': 55, 'range': 7},
        },
    },
    'JACKAL': {'label': 'Jackal Racer', 'plural': 'Jackal Racers', 'category': 'units', 'factions': ['Foehn'], 'cost': 600, 'speed': 10, 'strength': 250, 'sight': 7, 'guard_range': 7},
    'CYCL': {'label': 'Cyclops Walker', 'plural': 'Cyclops Walkers', 'category': 'units', 'factions': ['Foehn'], 'cost': 900, 'speed': 7, 'strength': 450, 'sight': 7, 'guard_range': 7},
    'DRACO': {'label': 'Draco Tank', 'plural': 'Draco Tanks', 'category': 'units', 'factions': ['Foehn'], 'cost': 1200, 'speed': 7, 'strength': 450, 'sight': 7, 'guard_range': 7},
    'QUETZ': {'label': 'Quetzal', 'plural': 'Quetzals', 'category': 'aircraft', 'factions': ['Foehn'], 'cost': 1400, 'speed': 12, 'strength': 300, 'sight': 8, 'guard_range': 8},
}


def default_plural(label):
    special = {
        'Infantry': 'Infantry',
        'Navy SEAL': 'Navy SEALs',
        'Stryker IFV': 'Stryker IFVs',
        'Archon AMC': 'Archon AMCs',
        'Allied MCV': 'Allied MCVs',
        'Soviet MCV': 'Soviet MCVs',
        'Epsilon MCV': 'Epsilon MCVs',
        'Foehn MCV': 'Foehn MCVs',
        'Stalin\'s Fist': 'Stalin\'s Fists',
    }
    return special.get(label, f'{label}s')


def add_complete_faction_buff_targets():
    for faction, categories in FACTION_UNIT_ROSTERS.items():
        for category, units in categories.items():
            for unit_id, label in units.items():
                cost, speed, strength, sight, guard_range, ammo = UNIT_BASE_STATS[unit_id]
                target = BUFF_TARGETS.setdefault(unit_id, {})
                # Preserve any hand-authored weapon tables while replacing the
                # old placeholder labels/stats with the installed 3.3.6 data.
                target.update({
                    'label': label,
                    'plural': default_plural(label),
                    'category': category,
                    'factions': [faction],
                    'cost': cost,
                    'speed': speed,
                    'strength': strength,
                    'sight': sight,
                    'guard_range': guard_range,
                })
                if ammo is not None:
                    target['ammo'] = ammo
                else:
                    target.pop('ammo', None)
                if unit_id in ROSTER_WEAPON_STATS:
                    target['weapons'] = ROSTER_WEAPON_STATS[unit_id]

    defense_buff_types = [
        'production', 'cost', 'armor', 'health', 'sight',
        'damage', 'reload', 'rof', 'range',
        'self_healing', 'cloak', 'sensors', 'veteran',
    ]
    for faction, defenses in FACTION_DEFENSE_ROSTERS.items():
        for defense_id, label in defenses.items():
            cost, strength, sight, guard_range = DEFENSE_BASE_STATS[defense_id]
            target = {
                'label': label,
                'plural': default_plural(label),
                'category': 'defenses',
                'factions': [faction],
                'cost': cost,
                'strength': strength,
                'sight': sight,
                'guard_range': guard_range,
                'allowed_buff_types': defense_buff_types,
                'trainable': defense_id in TRAINABLE_DEFENSE_IDS,
            }
            if not target['trainable']:
                target['allowed_buff_types'] = [
                    buff_type for buff_type in defense_buff_types if buff_type != 'veteran'
                ]
            if defense_id in DEFENSE_WEAPON_STATS:
                target['weapons'] = DEFENSE_WEAPON_STATS[defense_id]
            BUFF_TARGETS[defense_id] = target


add_complete_faction_buff_targets()

# Westwood-spawn missiles do not expose their real impact damage as a normal
# WeaponType. These General-section fields are the actual payload damage for
# the corresponding playable launchers.
SPECIAL_DAMAGE_FIELDS = {
    'V3': {
        'V3RocketDamage': 250,
        'V3RocketEliteDamage': 400,
    },
    'DRED': {
        'DMislDamage': 300,
        'DMislEliteDamage': 400,
    },
    'AKULA': {
        'CMislDamage': 300,
        'CMislEliteDamage': 400,
    },
}
for special_unit_id, damage_fields in SPECIAL_DAMAGE_FIELDS.items():
    BUFF_TARGETS[special_unit_id]['special_damage_fields'] = damage_fields

UNIT_LABELS = {
    'ADOG': 'Attack Dog',
    'AEGIS': 'Aegis Cruiser',
    'AHMV': 'Humvee',
    'AMEDIC': 'Field Medic',
    'CARRIER': 'Aircraft Carrier',
    'CLEG': 'Cryo Legionnaire',
    'DEST': 'Destroyer',
    'DLPH': 'Dolphin',
    'E1': 'GI',
    'E2': 'Conscript',
    'DOG': 'Soviet Attack Dog',
    'ENGINEER': 'Engineer',
    'FORTRESS': 'Barracuda',
    'FV': 'IFV',
    'GGI': 'Guardian GI',
    'HCRUIS': 'Trident Battleship',
    'JUMPJET': 'Rocketeer',
    'LCRF': 'Voyager Transport',
    'AKULA': 'Akula',
    'DBOAT': 'Sea Scorpion',
    'DRED': 'Dreadnought',
    'FLAKT': 'Flak Trooper',
    'HTK': 'Flak Track',
    'HTNK': 'Heavy Tank',
    'SAPC': 'Zubr Transport',
    'SHK': 'Tesla Trooper',
    'SQD': 'Giant Squid',
    'SUB': 'Typhoon Sub',
    'TTNK': 'Tesla Tank',
    'INIT': 'Initiate',
    'LTNK': 'Lasher Tank',
    'MIND': 'Mastermind',
    'VIRUS': 'Virus',
    'YTNK': 'Gatling Tank',
    'CYCL': 'Cyclops Walker',
    'DRACO': 'Draco Tank',
    'JACKAL': 'Jackal Racer',
    'KNIGHT': 'Knightframe',
    'QUETZ': 'Quetzal',
}

for faction_categories in FACTION_UNIT_ROSTERS.values():
    for roster_units in faction_categories.values():
        UNIT_LABELS.update(roster_units)
for faction_defenses in FACTION_DEFENSE_ROSTERS.values():
    UNIT_LABELS.update(faction_defenses)


def unit_display_label(unit_id):
    target = BUFF_TARGETS.get(unit_id)
    if target:
        return target.get('label', unit_id)
    return UNIT_LABELS.get((unit_id or '').upper(), unit_id)


ACCESS_REWARD_ALIASES = {}


def normalize_access_reward_display_names():
    """Use the installed playable name for every single-unit access item."""
    access_rewards = (
        UNIT_UNLOCK_REWARDS
        + EXTRA_UNIT_UNLOCK_REWARDS
        + ROSTER_UNIT_UNLOCK_REWARDS
        + DEFENSE_UNLOCK_REWARDS
    )
    for reward in access_rewards:
        unlocked_ids = [
            section
            for section, values in reward.get('rules', {}).items()
            if any(key.lower() == 'techlevel' for key in values)
        ]
        if len(unlocked_ids) != 1:
            continue
        unit_id = unlocked_ids[0].upper()
        target = BUFF_TARGETS.get(unit_id)
        if not target:
            continue
        old_name = reward.get('name', '')
        new_name = f'{target["label"]} Access'
        if old_name and old_name != new_name:
            ACCESS_REWARD_ALIASES[old_name] = new_name
        reward['name'] = new_name
        reward['description'] = (
            f'Allows {target["plural"]} where the map tech tree permits them.'
        )


normalize_access_reward_display_names()


BUFF_TYPES = [
    {
        'id': 'production',
        'name': 'Drill',
        'setting_label': 'Production / construction time',
        'description': '{plural} have 15% shorter build/train times in future launched missions.',
    },
    {
        'id': 'cost',
        'name': 'Logistics',
        'setting_label': 'Cost reduction',
        'description': '{plural} cost 20% less in future launched missions.',
    },
    {
        'id': 'speed',
        'name': 'Mobility',
        'setting_label': 'Movement speed',
        'description': '{plural} move faster in future launched missions.',
    },
    {
        'id': 'armor',
        'name': 'Armor Plating',
        'setting_label': 'Armor',
        'description': '{plural} take less incoming damage in future launched missions.',
    },
    {
        'id': 'health',
        'name': 'Reinforced Frames',
        'setting_label': 'Health',
        'description': '{plural} gain more health in future launched missions.',
        'requires_stat': 'strength',
    },
    {
        'id': 'sight',
        'name': 'Recon Package',
        'setting_label': 'Vision',
        'description': '{plural} gain more vision in future launched missions.',
        'requires_stat': 'sight',
    },
    {
        'id': 'damage',
        'name': 'Firepower',
        'setting_label': 'Damage',
        'description': '{plural} deal more weapon damage in future launched missions.',
        'requires_weapons': True,
        'requires_weapon_stat': 'damage',
        'requires_clone': True,
    },
    {
        'id': 'reload',
        'name': 'Weapon Tuning',
        'setting_label': 'Unit fire rate',
        'description': '{plural} fire their weapons faster in future launched missions.',
        'requires_weapons': True,
        'requires_weapon_stat': 'rof',
        'requires_weapon_min': 1,
        'requires_clone': True,
    },
    {
        'id': 'rof',
        'name': 'Rapid Fire',
        'setting_label': 'Army-wide fire rate',
        'description': 'All player weapons fire faster in future launched missions.',
        'requires_weapons': True,
        'requires_weapon_stat': 'rof',
    },
    {
        'id': 'range',
        'name': 'Optics',
        'setting_label': 'Attack range',
        'description': '{plural} gain more weapon range in future launched missions.',
        'requires_weapons': True,
        'requires_weapon_stat': 'range',
        'requires_clone': True,
    },
    {
        'id': 'ammo',
        'name': 'Ammo Reserves',
        'setting_label': 'Ammo',
        'description': '{plural} gain +1 ammo capacity per stack, allowing more ammo-consuming attacks before reloading or rearming in future launched missions.',
        'requires_stat': 'ammo',
        'requires_clone': True,
    },
    {
        'id': 'self_healing',
        'name': 'Repair Systems',
        'setting_label': 'Self-healing',
        'description': '{plural} gain self-healing in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'cloak',
        'name': 'Stealth Systems',
        'setting_label': 'Cloaking',
        'description': '{plural} gain cloaking in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'sensors',
        'name': 'Sensor Suite',
        'setting_label': 'Sensors',
        'description': '{plural} gain sensors in future launched missions.',
        'requires_clone': True,
    },
    {
        'id': 'veteran',
        'name': 'Veteran Training',
        'setting_label': 'Veteran start',
        'description': '{plural} start as veterans for the player house in future launched missions.',
    },
]


def build_buff_rewards():
    rewards = []
    for unit_id, target in BUFF_TARGETS.items():
        for buff_type in BUFF_TYPES:
            buff_type_id = buff_type['id']
            allowed_types = target.get('allowed_buff_types')
            if allowed_types and buff_type_id not in allowed_types:
                continue
            if unit_id in EXISTING_CAPABILITY_IDS.get(buff_type_id, ()):
                continue
            if (
                unit_id in NONCOMBAT_WEAPON_TARGET_IDS
                and buff_type_id in {'damage', 'reload', 'rof', 'range'}
            ):
                continue
            if buff_type.get('requires_stat') and buff_type.get('requires_stat') not in target:
                continue
            if buff_type.get('requires_weapons') and not target.get('weapons'):
                continue
            required_weapon_stat = buff_type.get('requires_weapon_stat')
            if required_weapon_stat:
                required_weapon_min = buff_type.get('requires_weapon_min', 0)
                has_weapon_stat = any(
                    stats.get(required_weapon_stat, 0) > required_weapon_min
                    for stats in target.get('weapons', {}).values()
                )
                has_special_damage = (
                    required_weapon_stat == 'damage'
                    and bool(target.get('special_damage_fields'))
                )
                if not has_weapon_stat and not has_special_damage:
                    continue
            rewards.append({
                'name': f'{target["label"]} {buff_type["name"]} I',
                'description': target.get('buff_descriptions', {}).get(
                    buff_type['id'],
                    buff_type['description'].format(plural=target['plural']),
                ),
                'rules': {},
                'factions': target['factions'],
                'kind': 'buff',
                'unit': unit_id,
                'buff_type': buff_type['id'],
                'global_buff': bool(target.get('global_buff')),
            })
    return rewards


UNIT_BUFF_REWARDS = build_buff_rewards()


# Keep the normal Allied storm independent from mission-local [General]
# settings. SFIRE reduces shared lightning values for its scripted Ion Storm.
LIGHTNING_STORM_MAP_RULES = {
    'UIName': 'NAME:Storm',
    'Name': 'Lightning Storm',
    'IsPowered': 'false',
    'RechargeTime': '10',
    'Type': 'LightningStorm',
    'Action': 'LightningStorm',
    'SidebarPCX': 'bolticon.pcx',
    'ShowTimer': 'yes',
    'DisableableFromShell': 'no',
    'AIDefendAgainst': 'yes',
    'Range': '9',
    'LineMultiplier': '3',
    'SW.CreateRadarEvent': 'yes',
    'Message.FirerColor': 'yes',
    'Message.Launch': 'NAME:STORMACTIVE',
    'Message.Abort': 'NAME:GREATTEMPESTNO',
    'Message.Detected': 'NAME:STORMDETECT',
    'EVA.Ready': 'EVA_BattlePowerReady',
    'SW.AutoFire': 'no',
    'SW.ManualFire': 'yes',
    'SW.ShowCameo': 'yes',
    'SW.UseAITargeting': 'no',
    'SW.InitialReady': 'no',
    'SW.AITargeting': 'LightningStorm',
    'SW.RequiredHouses': '',
    'SW.ForbiddenHouses': '',
    'SW.AuxBuildings': '',
    'SW.NegBuildings': '',
    'SW.Damage': '250',
    'SW.Warhead': 'IonWH',
    'SW.Range': '10',
    'SW.Deferment': '250',
    'SW.ActivationSound': 'WeatherIntro',
    'Lightning.Duration': '210',
    'Lightning.RadarOutage': '450',
    'Lightning.RadarOutageAffects': 'enemies',
    'Lightning.HitDelay': '90',
    'Lightning.ScatterDelay': '5',
    'Lightning.ScatterCount': '1',
    'Lightning.Separation': '3',
    'Lightning.PrintText': 'yes',
    'Lightning.Clouds': 'WCCLOUD1,WCCLOUD2,WCCLOUD3',
    'Lightning.Bolts': 'WCLBOLT1,WCLBOLT2,WCLBOLT3',
    'Lightning.BoltExplosion': 'EXPLOLB',
    'Lightning.Sounds': 'WeatherStrike',
    'Light.Enabled': 'yes',
    'Light.Blue': '75',
    'Light.Red': '45',
    'Light.Green': '45',
    'Light.Ambient': '100',
    'SW.Inhibitors': 'CACEAS,FAINHI,FAINHIB,RACC,COON,FAJAMM',
    'Cursor': 'Storm',
    'NoCursor': 'NoCanDo',
}

CHRONOSHIFT_MAP_RULES = {
    'UIName': 'NAME:Chrono',
    'Name': 'Chronoshift Pre',
    'IsPowered': 'false',
    'RechargeTime': '6.5',
    'Type': 'ChronoSphere',
    'Action': 'ChronoSphere',
    'SidebarPCX': 'chroicon.pcx',
    'ShowTimer': 'yes',
    'DisableableFromShell': 'no',
    'Range': '1',
    'SW.Range': '3,3',
    'LineMultiplier': '0',
    'SW.FireIntoShroud': 'no',
    'Chronosphere.ReconsiderBuildings': 'no',
    'Message.FirerColor': 'yes',
    'Message.Launch': 'NAME:CHRONOACTIVE',
    'Message.Detected': 'NAME:CHRONODETECT',
    'SW.CreateRadarEvent': 'yes',
    'EVA.Ready': 'EVA_BattlePowerReady',
    'EVA.Activated': 'none',
    'EVA.Detected': 'EVA_ChronoSphereDetected',
    'SW.AffectsHouse': 'team',
    'SW.AffectsTarget': 'units',
    'SW.PostDependent': 'ChronoWarpSpecial',
    'SW.AutoFire': 'no',
    'SW.ManualFire': 'yes',
    'SW.ShowCameo': 'yes',
    'SW.UseAITargeting': 'no',
    'SW.InitialReady': 'no',
    'SW.AITargeting': 'None',
    'SW.RequiredHouses': '',
    'SW.ForbiddenHouses': '',
    'SW.AuxBuildings': '',
    'SW.NegBuildings': '',
    'SW.Inhibitors': 'CACEAS,FAINHI,FAINHIB,RACC,COON,FAJAMM',
    'Cursor': 'Shift',
    'NoCursor': 'NoCanDo',
}

CHRONOWARP_MAP_RULES = {
    'UIName': 'NAME:Chrono2',
    'Name': 'Chronoshift Post',
    'IsPowered': 'false',
    'RechargeTime': '1',
    'Type': 'ChronoWarp',
    'Action': 'ChronoWarp',
    'Range': '1',
    'LineMultiplier': '1',
    'SW.AffectsHouse': 'team',
    'SW.AffectsTarget': 'units',
    'SW.CreateRadarEvent': 'yes',
    'SW.RequiredHouses': '',
    'SW.ForbiddenHouses': '',
    'SW.AuxBuildings': '',
    'SW.NegBuildings': '',
    'SW.Inhibitors': 'CACEAS,FAINHI,FAINHIB,RACC,COON,FAJAMM',
    'FlashSidebarTabFrames': '0',
    'Cursor': 'Shift',
    'NoCursor': 'NoCanDo',
}


SUPERWEAPON_UNLOCK_REWARDS = [
    {
        'name': 'Lightning Storm Power',
        'description': 'Grants a building-free, repeating Lightning Storm in future launched missions.',
        'rules': {},
        'factions': ['Allies'],
        'kind': 'superweapon',
        'power_category': 'offensive',
        'superweapon': 'LightningStormSpecial',
        'superweapon_index': 2,
        'superweapon_rules': dict(LIGHTNING_STORM_MAP_RULES),
    },
    {
        'name': 'Nuclear Missile Power',
        'description': 'Grants a building-free, repeating Tactical Nuke in future launched missions.',
        'rules': {},
        'factions': ['Soviets'],
        'kind': 'superweapon',
        'power_category': 'offensive',
        'superweapon': 'NukeSpecial',
        'superweapon_index': 0,
        'superweapon_rules': {'IsPowered': 'false'},
    },
    {
        'name': 'Psychic Dominator Power',
        'description': 'Grants a building-free, repeating Psychic Dominator in future launched missions.',
        'rules': {},
        'factions': ['Epsilon'],
        'kind': 'superweapon',
        'power_category': 'offensive',
        'superweapon': 'PsychicDominatorSpecial',
        'superweapon_index': 7,
        'superweapon_rules': {'IsPowered': 'false'},
    },
    {
        'name': 'Great Tempest Power',
        'description': 'Grants a building-free, repeating Great Tempest in future launched missions.',
        'rules': {},
        'factions': ['Foehn'],
        'kind': 'superweapon',
        'power_category': 'offensive',
        'superweapon': 'GreatTempestSpecial',
        'superweapon_index': 48,
        'superweapon_rules': {'IsPowered': 'false'},
    },
]

SECONDARY_SUPERWEAPON_UNLOCK_REWARDS = [
    {
        'name': 'Chronoshift Power',
        'description': 'Grants a building-free, repeating Chronoshift in future launched missions.',
        'rules': {},
        'factions': ['Allies'],
        'kind': 'superweapon',
        'power_category': 'secondary',
        'superweapon': 'ChronoSphereSpecial',
        'superweapon_index': 3,
        'superweapon_rules': dict(CHRONOSHIFT_MAP_RULES),
        'superweapon_rule_sections': {
            'ChronoWarpSpecial': dict(CHRONOWARP_MAP_RULES),
        },
    },
    {
        'name': 'Invulnerability Power',
        'description': 'Grants a building-free, repeating Iron Curtain Invulnerability power in future launched missions.',
        'rules': {},
        'factions': ['Soviets'],
        'kind': 'superweapon',
        'power_category': 'secondary',
        'superweapon': 'IronCurtainSpecial',
        'superweapon_index': 1,
        'superweapon_rules': {'IsPowered': 'false'},
    },
    {
        'name': 'Rage Power',
        'description': 'Grants a building-free, repeating Rage Inductor power in future launched missions.',
        'rules': {},
        'factions': ['Epsilon'],
        'kind': 'superweapon',
        'power_category': 'secondary',
        'superweapon': 'RageInductorSpecial',
        'superweapon_index': 28,
        'superweapon_rules': {'IsPowered': 'false'},
    },
    {
        'name': 'Blasticade Power',
        'description': 'Grants a building-free, repeating Blasticade activation; Foehn Blast Trenches are still required for its barrier.',
        'rules': {},
        'factions': ['Foehn'],
        'kind': 'superweapon',
        'power_category': 'secondary',
        'superweapon': 'BlasticadeSpecial',
        'superweapon_index': 47,
        'superweapon_rules': {'IsPowered': 'false'},
    },
]


AID_POWER_MAP_CONFIGS = [
    # Allies
    {
        'superweapon': 'AmericanParaDropSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'BloodhoundsSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'ZephyrBeaconSpecial',
        'values': {
            'IsPowered': 'false',
            'RechargeTime': '5.5',
            'Money.Amount': '-500',
            'SW.Deferment': '0',
            'Deliver.Types': 'ZTARGET',
            'Deliver.Owner': 'neutral',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.ShowCameo': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.InitialReady': 'no',
            'SW.AITargeting': 'None',
            'SW.FireIntoShroud': 'no',
            'SW.RequiresTarget': 'land',
            'SW.RequiredHouses': '',
            'SW.ForbiddenHouses': '',
            'SW.AuxBuildings': '',
            'SW.NegBuildings': '',
            'AuxBuilding': '',
            'SW.Inhibitors': 'CACEAS,FAINHI,FAINHIB,RACC,COON,FAJAMM',
        },
    },
    {
        # Already source-independent in the installed rules.
        'superweapon': 'LightningRodSpecial',
        'values': {},
    },
    {
        'superweapon': 'WarpMinersSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.AuxBuildings': '',
        },
    },
    {
        'superweapon': 'KingsnakesSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.FireIntoShroud': 'yes',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.AITargeting': 'None',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
            'SW.RequiredHouses': '',
            'SW.AuxBuildings': '',
            'SW.Designators': '',
        },
        'techno_clones': {
            'F_KSNAK': {
                'list': 'VehicleTypes',
                'clone': 'MORF_KSNAK',
                'values': {'PoweredBy': ''},
            },
        },
    },
    {
        'superweapon': 'PaladinAidSpecial',
        'values': {
            'Range': '1.5',
            'SW.Sound': 'ChronosphereMove',
            'EVA.Ready': 'EVA_ReinforcementsReady',
            'IsPowered': 'false',
            'SW.UseAITargeting': 'no',
            'SW.Animation': 'CHRONOTG',
            'SW.Deferment': '20',
            'Deliver.Owner': 'invoker',
            'Deliver.Types': 'PANTHER,PANTHER',
            'LineMultiplier': '0',
            'SW.AITargeting': 'None',
            'SW.FireIntoShroud': 'no',
            'SW.RequiresTarget': 'land',
            'Cursor': 'Shift',
            'SW.RequiredHouses': '',
            'SW.AuxBuildings': '',
        },
    },
    # Soviets
    {
        'superweapon': 'RepairDroneSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.NegBuildings': '',
        },
    },
    {
        'superweapon': 'TankDropSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'InstantShelterSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'MotorAmbushSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'NavalMineSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.FireIntoShroud': 'yes',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.AITargeting': 'None',
            'SW.Designators': '',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
        },
    },
    {
        'superweapon': 'TerrorDropSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'FlameTowerSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'DrakuvSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.FireIntoShroud': 'yes',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.AITargeting': 'None',
            'SW.AuxBuildings': '',
            'SW.Designators': '',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
        },
    },
    {
        'superweapon': 'RepairDronesSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.AuxBuildings': '',
        },
    },
    {
        'superweapon': 'DisruptorSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.AuxBuildings': '',
        },
    },
    # Epsilon
    {
        'superweapon': 'RisenMonolithSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'RavenSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'VisionSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'MagnetShiftSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'LibraCloneSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'TickTrapSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'QuickFortSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'RuinerSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.FireIntoShroud': 'yes',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.AITargeting': 'None',
            'SW.AuxBuildings': '',
            'SW.Designators': '',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
        },
    },
    {
        'superweapon': 'HijackersSpecial',
        'values': {'IsPowered': 'false'},
    },
    # Foehn
    {
        'superweapon': 'SpinbladeSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'MegaarenaSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'KnightfallSpecial',
        'values': {
            'EVA.Ready': 'EVA_BattlePowerReady',
            'IsPowered': 'false',
            'RechargeTime': '0.5',
            'SW.Deferment': '0',
            'Deliver.Owner': 'invoker',
            'LineMultiplier': '2',
            'SW.AITargeting': 'None',
            'SW.RangeMaximum': '-1',
        },
    },
    {
        'superweapon': 'SweeperDropSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'SignalJammerSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'DecoyTeamSpecial',
        'values': {'IsPowered': 'false'},
    },
    {
        'superweapon': 'DecoySquadronSpecial',
        'values': {
            'IsPowered': 'false',
            'SW.AuxBuildings': '',
        },
    },
    {
        'superweapon': 'MADMineSpecial',
        'values': {
            'SW.FireIntoShroud': 'yes',
            'SW.AutoFire': 'no',
            'SW.ManualFire': 'yes',
            'SW.UseAITargeting': 'no',
            'SW.AITargeting': 'None',
            'SW.Designators': '',
            'SW.Inhibitors': '',
            'SW.AnyInhibitor': 'no',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
        },
    },
    {
        'superweapon': 'MORV3TestSpecial',
        # Proven custom-power template. Keep definition for future use, but do
        # not place it in generated reward pools while this switch is true.
        'disabled': True,
        'custom': True,
        'clone': 'MORV3TestSpecial',
        'cameo_superweapon': 'AmericanParaDropSpecial',
        'values': {
            'UIName': 'NAME:APara',
            'Name': 'V3 Test Drop',
            'IsPowered': 'false',
            'RechargeTime': '0.5',
            'Money.Amount': '0',
            'Type': 'UnitDelivery',
            'Action': 'Custom',
            'SidebarPCX': 'aparicon.pcx',
            'ShowTimer': 'no',
            'DisableableFromShell': 'no',
            'Range': '3',
            'LineMultiplier': '0',
            'Cursor': 'Paradrop',
            'NoCursor': 'NoCanDo',
            'EVA.Ready': 'EVA_ParatroopersReady',
            'Deliver.Types': ','.join(['V3'] * 20),
            'Deliver.Owner': 'invoker',
            'SW.Deferment': '20',
            'SW.FireIntoShroud': 'yes',
            'SW.RequiresTarget': 'land',
            'SW.AITargeting': 'None',
            'SW.CreateRadarEvent': 'no',
            'SW.Inhibitors': '',
            'SW.RangeMaximum': '-1',
            'SW.RangeMinimum': '-1',
            'FlashSidebarTabFrames': '0',
        },
    },
]
AID_POWER_MAP_CONFIG_BY_SUPERWEAPON = {
    config['superweapon']: config
    for config in AID_POWER_MAP_CONFIGS
}


def build_aid_power_rewards():
    # These are the installed, player-facing delivery/reinforcement powers.
    # Internal automatic spawn helpers and neutral tech-building powers are
    # deliberately excluded even though the engine also classifies them as
    # superweapons.
    definitions = [
        # Allies
        ('Airborne Power', 'Drops 6 G.I.s and 4 Guardian G.I.s at the selected area.', 'Allies', 'AmericanParaDropSpecial', 6),
        ('Bloodhounds Power', 'Drops 3 Airborne Humvees and 2 Stryker I.F.V.s at the selected area.', 'Allies', 'BloodhoundsSpecial', 26),
        ('Zephyrobot Power', 'Deploys a targeting beacon for Zephyr Artillery units you already own.', 'Allies', 'ZephyrBeaconSpecial', 34),
        ('Lightning Rod Power', 'Deploys a temporary Lightning Rod at the selected area.', 'Allies', 'LightningRodSpecial', 51),
        ('Ultra Miner Power', 'Deploys an Ultra Miner at the selected area.', 'Allies', 'WarpMinersSpecial', 61),
        ('Kingsnakes Power', 'Deploys a temporary Kingsnake defense portal at the selected area.', 'Allies', 'KingsnakesSpecial', 126),
        ('Paladin Aid Power', 'Deploys 2 Paladin Tank Hunters for the player.', 'Allies', 'PaladinAidSpecial', 128),
        # Soviets
        ('Repair Drone Power', 'Drops 1 Repair Drone at the selected area.', 'Soviets', 'RepairDroneSpecial', 13),
        ('Tank Drop Power', 'Drops the Russian Hydra Cannon and Tank Killer contingent at the selected area.', 'Soviets', 'TankDropSpecial', 16),
        ('Instant Shelter Power', 'Deploys a Battle Bunker with 2 Conscripts at the selected area.', 'Soviets', 'InstantShelterSpecial', 29),
        ('Motor Ambush Power', 'Deploys 3 Mortar Quads at the selected area.', 'Soviets', 'MotorAmbushSpecial', 32),
        ('Naval Mine Power', 'Deploys a Naval Mine at the selected water area.', 'Soviets', 'NavalMineSpecial', 60),
        ('V3 Test Drop Power', 'Drops 20 V3 Launchers using an isolated test power.', 'Soviets', 'MORV3TestSpecial', -1),
        ('Terror Drop Power', 'Drops 2 Terror Drones at the selected area.', 'Soviets', 'TerrorDropSpecial', 62),
        ('Flame Tower Power', 'Deploys a temporary Flame Tower at the selected area.', 'Soviets', 'FlameTowerSpecial', 68),
        ('Drakuv Prison Vehicle Power', 'Deploys a Drakuv Prison Vehicle for the player.', 'Soviets', 'DrakuvSpecial', 70),
        ('Repair Drones Power', 'Drops the upgraded Repair Drone contingent at the selected area.', 'Soviets', 'RepairDronesSpecial', 124),
        ('Disruptor Power', 'Deploys a Disruptor support unit for the player.', 'Soviets', 'DisruptorSpecial', 125),
        # Epsilon
        ('Risen Monolith Power', 'Deploys a temporary Risen Monolith at the selected area.', 'Epsilon', 'RisenMonolithSpecial', 15),
        ('Scout Raven Power', 'Deploys a Scout Raven at the selected area.', 'Epsilon', 'RavenSpecial', 18),
        ('Vision Power', 'Deploys an Epsilon Vision scout at the selected area.', 'Epsilon', 'VisionSpecial', 21),
        ('Magnetic Beam Power', 'Deploys the Magnetic Beam support object at the selected area.', 'Epsilon', 'MagnetShiftSpecial', 30),
        ('Libra Clones Power', 'Drops 3 Libra Clones at the selected area.', 'Epsilon', 'LibraCloneSpecial', 33),
        ('Bloatick Trap Power', 'Deploys a Bloatick Trap at the selected area.', 'Epsilon', 'TickTrapSpecial', 36),
        ('Quick Fort Power', 'Deploys a temporarily strengthened Tank Bunker at the selected area.', 'Epsilon', 'QuickFortSpecial', 86),
        ('Ruiner Power', 'Deploys a Ruiner support unit for the player.', 'Epsilon', 'RuinerSpecial', 93),
        ('Hijackers Power', 'Drops 3 Hijackers at the selected area.', 'Epsilon', 'HijackersSpecial', 108),
        # Foehn
        ('Spinblade Power', 'Deploys a Spinblade support structure at the selected area.', 'Foehn', 'SpinbladeSpecial', 39),
        ('Megaarena Power', 'Deploys a temporary Megaarena Projector at the selected area.', 'Foehn', 'MegaarenaSpecial', 52),
        ('Knightfall Power', 'Deploys a Knightfall reinforcement beacon at the selected area.', 'Foehn', 'KnightfallSpecial', 72),
        ('Sweeper Drop Power', 'Drops 2 Sweepers at the selected area.', 'Foehn', 'SweeperDropSpecial', 76),
        ('Signal Jammer Power', 'Deploys a temporary Signal Jammer at the selected area.', 'Foehn', 'SignalJammerSpecial', 77),
        ('Decoy Team Power', 'Deploys a holographic infantry decoy team at the selected area.', 'Foehn', 'DecoyTeamSpecial', 118),
        ('Decoy Squadron Power', 'Deploys a holographic aircraft decoy squadron at the selected area.', 'Foehn', 'DecoySquadronSpecial', 119),
        ('M.A.D. Mine Power', 'Deploys a M.A.D. Mine at the selected area.', 'Foehn', 'MADMineSpecial', 133),
    ]
    rewards = []
    for name, description, faction, superweapon, index in definitions:
        modified_config = AID_POWER_MAP_CONFIG_BY_SUPERWEAPON.get(superweapon)
        if modified_config and modified_config.get('disabled'):
            continue
        reward = {
            'name': name,
            'description': description + ' Restored at the start of future missions without its normal source building.',
            'rules': {},
            'factions': [faction],
            'kind': 'superweapon',
            'power_category': 'aid',
            'superweapon': superweapon,
            'superweapon_index': index,
        }
        if modified_config and modified_config['values']:
            reward['superweapon_rules'] = dict(modified_config['values'])
        if modified_config and modified_config.get('sections'):
            reward['superweapon_rule_sections'] = {
                section: dict(values)
                for section, values in modified_config['sections'].items()
            }
        if modified_config and modified_config.get('techno_clones'):
            reward['superweapon_techno_clones'] = {
                section: {
                    key: dict(value) if key == 'values' else value
                    for key, value in clone.items()
                }
                for section, clone in modified_config['techno_clones'].items()
            }
        if modified_config and modified_config.get('custom'):
            reward['superweapon_custom'] = True
        if modified_config and modified_config.get('clone'):
            reward['superweapon_clone'] = modified_config['clone']
        if modified_config and modified_config.get('cameo_superweapon'):
            reward['cameo_superweapon'] = modified_config['cameo_superweapon']
        rewards.append(reward)
    return rewards


AID_POWER_UNLOCK_REWARDS = build_aid_power_rewards()

REWARD_POOL = (
    UNIT_UNLOCK_REWARDS
    + EXTRA_UNIT_UNLOCK_REWARDS
    + ROSTER_UNIT_UNLOCK_REWARDS
    + DEFENSE_UNLOCK_REWARDS
    + SUPERWEAPON_UNLOCK_REWARDS
    + SECONDARY_SUPERWEAPON_UNLOCK_REWARDS
    + AID_POWER_UNLOCK_REWARDS
    + UNIT_BUFF_REWARDS
)
REWARD_BY_NAME = {reward.get('name'): reward for reward in REWARD_POOL if reward.get('name')}
REWARD_BY_BUFF_KEY = {
    (reward.get('unit'), reward.get('buff_type')): reward
    for reward in UNIT_BUFF_REWARDS
}
RETIRED_REWARD_BY_NAME = {
    # Elite Reserves is implemented by delivering an invisible production-state
    # marker from a Soviet lab. Granting the power itself with action 34 and no
    # source building crashes during the map-start trigger. Keep old generated
    # seeds loadable, but never inject or assign this unsafe reward again.
    'Elite Reserves Power': {
        'name': 'Elite Reserves Power (retired: unsafe building-free grant)',
        'description': 'Disabled because its internal production marker requires the original Soviet lab source.',
        'rules': {},
        'factions': ['Soviets'],
        'kind': 'retired',
        'retired_reward': True,
    },
    # The custom implementation works, but this test-only reward is currently
    # disabled. Canonicalize old generated seeds so they do not inject it.
    'V3 Test Drop Power': {
        'name': 'V3 Test Drop Power (retired: test disabled)',
        'description': 'Custom 20-V3 delivery test is preserved for future use but currently disabled.',
        'rules': {},
        'factions': ['Soviets'],
        'kind': 'retired',
        'retired_reward': True,
    },
}
REWARD_ALIASES = {
    **ACCESS_REWARD_ALIASES,
    'Medic Drill I': 'Field Medic Drill I',
    'Humvee Assembly I': 'Humvee Drill I',
    'IFV Assembly I': 'IFV Drill I',
    'Cryo Legionnaires': 'Chrono Legionnaire Access',
    'Chrono Legionnaires': 'Chrono Legionnaire Access',
    'Battle Fortress Access': 'Barracuda Access',
    'Mind Control Access': 'Mastermind Access',
    'Base Construction Drill I': 'Faction Production Drill I',
    'Mind Control Unit Targeting Package I': 'Mastermind Recon Package I',
}
for target in BUFF_TARGETS.values():
    # Existing seeds may contain the removed GuardRange reward. Convert it to
    # the same unit's useful vision reward instead of applying behavior that
    # can pull units out of position or leaving the old location reward empty.
    old_name = f'{target["label"]} Targeting Package I'
    replacement_name = f'{target["label"]} Recon Package I'
    if replacement_name in REWARD_BY_NAME:
        REWARD_ALIASES[old_name] = replacement_name
for defense_id, target in BUFF_TARGETS.items():
    if target.get('category') == 'defenses' and not target.get('trainable'):
        REWARD_ALIASES[
            f'{target["label"]} Veteran Training I'
        ] = f'{target["label"]} Armor Plating I'

for buff_type in BUFF_TYPES:
    REWARD_ALIASES[f'Mind Control Unit {buff_type["name"]} I'] = f'Mastermind {buff_type["name"]} I'


def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}

    reward_name = reward.get('name')
    if not reward_name:
        return reward
    reward_name = REWARD_ALIASES.get(reward_name, reward_name)

    if reward_name in RETIRED_REWARD_BY_NAME:
        return RETIRED_REWARD_BY_NAME[reward_name]
    current_reward = REWARD_BY_NAME.get(reward_name)
    if current_reward:
        return current_reward
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        active_reward = REWARD_BY_BUFF_KEY.get(
            (reward.get('unit'), reward.get('buff_type'))
        )
        if active_reward:
            return active_reward
        return {
            'name': f'{reward_name} (retired: redundant or inapplicable)',
            'description': (
                'Disabled because the installed unit already has this capability '
                'or has no compatible combat weapon.'
            ),
            'rules': {},
            'factions': list(reward.get('factions') or []),
            'kind': 'retired',
            'retired_reward': True,
        }
    return reward


def canonical_rewards(rewards):
    if isinstance(rewards, list):
        return [canonical_reward(reward) for reward in rewards if isinstance(reward, dict)]
    if isinstance(rewards, dict):
        return [canonical_reward(rewards)]
    return []


def check_rewards(check):
    rewards = canonical_rewards(check.get('rewards'))
    if rewards:
        return rewards
    return canonical_rewards(check.get('reward'))


def reward_names(rewards):
    names = [reward_display_name(reward) for reward in rewards]
    return ', '.join(names) if names else 'No reward'


def clamp_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def valid_choice(value, choices, default):
    return value if value in choices else default


HOUSE_CATEGORY_SUFFIXES = {
    'infantry': 'Infantry',
    'units': 'Units',
    'aircraft': 'Aircraft',
    'buildings': 'Buildings',
    'defenses': 'Defenses',
}

HOUSE_SCOPED_BUFF_TYPES = {'production', 'cost', 'speed', 'armor', 'rof', 'veteran'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload'}
UNIT_STAT_BUFF_TYPES = {'health', 'sight', 'ammo', 'self_healing', 'cloak', 'sensors'}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = MAP_GUARDED_BUFF_TYPES
MAX_VETERANCY_STACKS = 1


def reward_display_name(reward):
    reward = canonical_reward(reward)
    name = reward.get('name', 'Unknown reward')
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        effect_lines = buff_effect_lines(reward, include_stack=False)
        if effect_lines:
            return effect_lines[0]
    if reward.get('kind') == 'buff' and name.endswith(' I'):
        return name[:-2]
    return name


def house_category_suffix(target):
    return HOUSE_CATEGORY_SUFFIXES.get(target.get('category', 'units'), 'Units')


def buff_stack_limit(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return None
    if reward.get('buff_type') == 'veteran':
        return MAX_VETERANCY_STACKS
    if reward.get('buff_type') in {'self_healing', 'cloak', 'sensors'}:
        return 1
    return None


def effective_buff_count(reward, count):
    limit = buff_stack_limit(reward)
    if limit is None:
        return count
    return min(count, limit)


def stack_label(count):
    return f'Stacked {count} time' + ('s' if count != 1 else '')


def buff_effect_lines(reward, count=1, include_label=True, include_stack=True):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)

    def stacked(text):
        if not include_stack:
            return text
        return f'{text} ({stack_label(count)})'

    if buff_type == 'production':
        multiplier = max(0.35, 0.85 ** count)
        shorter = int(round((1.0 - multiplier) * 100))
        effect = (
            'Construction time'
            if target.get('category') in {'buildings', 'defenses'}
            else 'Production time'
        )
        return [stacked(f'{prefix}{effect} {shorter}% shorter')]
    if buff_type == 'cost':
        multiplier = max(0.30, 0.80 ** count)
        cheaper = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Cost {cheaper}% cheaper')]
    if buff_type == 'speed':
        multiplier = min(1.75, 1.10 ** count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        multiplier = max(0.50, 0.90 ** count)
        tougher = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Armor {tougher}% stronger')]
    if buff_type == 'health':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Health {stronger}% higher')]
    if buff_type == 'sight':
        increase = min(4, count)
        return [stacked(f'{prefix}Vision +{increase}')]
    if buff_type == 'rof':
        multiplier = max(0.40, 0.90 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        return [stacked(f'Army-wide fire rate {faster}% faster')]
    if buff_type == 'veteran':
        return [stacked(f'{prefix}Veteran start')]
    if buff_type == 'damage':
        multiplier = min(2.0, 1.15 ** count)
        stronger = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Damage {stronger}% higher')]
    if buff_type == 'reload':
        multiplier = max(0.45, 0.90 ** count)
        faster = int(round((1.0 - multiplier) * 100))
        return [stacked(f'{prefix}Fire rate {faster}% faster')]
    if buff_type == 'range':
        increase = min(3.0, 0.5 * count)
        if increase.is_integer():
            increase_text = str(int(increase))
        else:
            increase_text = f'{increase:.1f}'
        return [stacked(f'{prefix}Range +{increase_text}')]
    if buff_type == 'ammo':
        increase = min(5, count)
        base_ammo = int(target.get('ammo', 0))
        total_ammo = base_ammo + increase
        if reward.get('unit') == 'ABRM':
            return [stacked(f'{prefix}Main-cannon ammo {base_ammo} -> {total_ammo}')]
        return [stacked(f'{prefix}Ammo {base_ammo} -> {total_ammo}')]
    if buff_type == 'self_healing':
        return [stacked(f'{prefix}Self-healing enabled')]
    if buff_type == 'cloak':
        return [stacked(f'{prefix}Cloaking enabled')]
    if buff_type == 'sensors':
        sensor_range = int(round(target.get('sight', 5) + 2))
        sensor_text = f'{prefix}Sensors enabled ({sensor_range}-cell range)'
        if include_stack:
            sensor_text = (
                f'{prefix}Sensors enabled ({sensor_range}-cell range; '
                f'{stack_label(count)})'
            )
        return [sensor_text]
    return []


def reward_rule_summary(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        return buff_effect_lines(reward)
    if reward.get('kind') == 'superweapon':
        return ['Building-free repeating power; restored at the start of future missions.']

    summaries = []
    rules = reward.get('rules', {})
    for section, values in rules.items():
        changes = []
        for key, value in values.items():
            key_lower = key.lower()
            if key_lower == 'techlevel':
                changes.append('unlocked')
            elif key_lower == 'buildtimemultiplier':
                try:
                    multiplier = float(value)
                    delta = int(round((1.0 - multiplier) * 100))
                except (TypeError, ValueError):
                    delta = 0
                if delta > 0:
                    changes.append(f'builds/trains {delta}% faster')
                elif delta < 0:
                    changes.append(f'builds/trains {abs(delta)}% slower')
                else:
                    changes.append(f'BuildTimeMultiplier={value}')
            elif key_lower in {'owner', 'requiredhouses', 'forbiddenhouses', 'prerequisiteoverride'}:
                continue
            else:
                changes.append(f'{key}={value}')

        if changes:
            summaries.append(f'{unit_display_label(section)}: {", ".join(changes)}')

    return summaries
