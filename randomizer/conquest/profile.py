"""Native installation contract for this Conquest port."""

from pathlib import Path
from randomizer.core.paths import CAMEO_CACHE_DIR
from randomizer.ui.cameos import extract_mix_files_sync
from randomizer.maps.ini import all_section_value_maps_preserve


def read_ini(path):
    data = Path(path).read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('latin-1')
    return {name: {key: value.split(';', 1)[0].strip() for key, value in values.items()}
            for name, values in all_section_value_maps_preserve(text.splitlines()).items()}


def installed_rules():
    """Read the installed, unmodified archive cache rather than a previous run."""
    if not extract_mix_files_sync([(RULES_FILE, CAMEO_CACHE_DIR / RULES_FILE),
                                   (ART_FILE, CAMEO_CACHE_DIR / ART_FILE),
                                   (AI_FILE, CAMEO_CACHE_DIR / AI_FILE)]):
        raise ValueError('Installed rules, art or AI data are unavailable. Repair the game installation.')
    rows = read_ini(CAMEO_CACHE_DIR / RULES_FILE)
    # Reloaded contains dormant countries. Keep the same native country
    # policy used by Fortress, leaving eight independent multiplayer seats.
    countries = [c for c in rows['Countries'].values() if c not in INACTIVE_COUNTRIES]
    rows['Countries'] = {str(i): c for i, c in enumerate(countries)}
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        rows[category] = {k: v for k, v in rows[category].items() if v in rows}
    return rows

GAME = 'mo'
TITLE = 'Mental Omega'
RULES_FILE, ART_FILE, AI_FILE = ('rulesmo.ini', 'artmo.ini', 'aimo.ini')
INACTIVE_COUNTRIES = ()
INSTALLATION_FILES = ('gamemd.exe', 'Syringe.exe', 'Ares.dll', 'cncnet5.dll', 'cncnet5mo.dll', 'Resources/GameOptions.ini', 'INI/MentalOmegaMaps.ini')
NATIVE_COUNTRIES = {'United States': 'UnitedStates',
 'Euro Alliance': 'Europeans',
 'Pacific Front': 'Pacific',
 'Russia': 'USSR',
 'Confederation': 'Latin',
 'China': 'Chinese',
 'PsiCorps': 'PsiCorps',
 'Scorpion Cell': 'ScorpionCell',
 'Epsilon HQ': 'Headquaters',
 'Haihead': 'Guild1',
 'Coronia': 'Guild2',
 'Last Bastion': 'Guild3'}
FAMILIES = {'United States': 'Allies',
 'Euro Alliance': 'Allies',
 'Pacific Front': 'Allies',
 'Russia': 'Soviets',
 'Confederation': 'Soviets',
 'China': 'Soviets',
 'PsiCorps': 'Epsilon',
 'Scorpion Cell': 'Epsilon',
 'Epsilon HQ': 'Epsilon',
 'Haihead': 'Foehn',
 'Coronia': 'Foehn',
 'Last Bastion': 'Foehn'}
ROSTERS = {'United States': ('E1', 'FV', 'ETNK', 'GAPOWR', 'GAPILE', 'GAREFN', 'CMIN', 'GAPILL'),
 'Euro Alliance': ('E1', 'FV', 'MTNK', 'GAPOWR', 'GAPILE', 'GAREFN', 'CMIN', 'GAPILL'),
 'Pacific Front': ('E1', 'FV', 'KTNK', 'GAPOWR', 'GAPILE', 'GAREFN', 'CMIN', 'GAPILL'),
 'Russia': ('E2', 'SCAR', 'HTNK', 'NAPOWR', 'NAHAND', 'NAREFN', 'HARV', 'NALASR'),
 'Confederation': ('E2', 'HTK', 'JTNK', 'NAPOWR', 'NAHAND', 'NAREFN', 'HARV', 'NALASR'),
 'China': ('E2', 'HTK', 'CTNK', 'NAPOWR', 'NAHAND', 'NAREFN', 'HARV', 'NALASR'),
 'PsiCorps': ('INIT', 'STING', 'LTNK', 'YAPOWR', 'YABRCK', 'YARIREFN', 'YMIN', 'YAGGUN'),
 'Scorpion Cell': ('INIT', 'STING', 'QTNK', 'YAPOWR', 'YABRCK', 'YARIREFN', 'YMIN', 'YAGGUN'),
 'Epsilon HQ': ('INIT', 'STING', 'STNK', 'YAPOWR', 'YABRCK', 'YARIREFN', 'YMIN', 'YAGGUN'),
 'Haihead': ('KNIGHT', 'JACKAL', 'CYCL', 'FATRAP', 'FABARR', 'FAREFN', 'NMIN', 'FASONI'),
 'Coronia': ('KNIGHT', 'JACKAL', 'DRACO', 'FATRAP', 'FABARR', 'FAREFN', 'NMIN', 'FASONI'),
 'Last Bastion': ('KNIGHT', 'JACKAL', 'ROACH', 'FATRAP', 'FABARR', 'FAREFN', 'NMIN', 'FASONI')}
FACTORIES = {'United States': 'GAWEAP',
 'Euro Alliance': 'GAWEAP',
 'Pacific Front': 'GAWEAP',
 'Russia': 'NAWEAP',
 'Confederation': 'NAWEAP',
 'China': 'NAWEAP',
 'PsiCorps': 'YAWEAP',
 'Scorpion Cell': 'YAWEAP',
 'Epsilon HQ': 'YAWEAP',
 'Haihead': 'FAWEAP',
 'Coronia': 'FAWEAP',
 'Last Bastion': 'FAWEAP'}
AIRCRAFT_BUILDINGS = {'United States': 'GAAIRC',
 'Euro Alliance': 'GAAIRC',
 'Pacific Front': 'GAAIRC',
 'Russia': 'NAAIR',
 'Confederation': 'NAAIR',
 'China': 'NAAIR',
 'PsiCorps': 'YAAIRF',
 'Scorpion Cell': 'YAAIRF',
 'Epsilon HQ': 'YAAIRF',
 'Haihead': 'FAWEAP',
 'Coronia': 'FAWEAP',
 'Last Bastion': 'FAWEAP'}
ESCORT_ROSTERS = {'United States': {'infantry': ('E1', 'GGI', 'GHOST', 'TANY'),
                   'vehicles': ('ETNK', 'FV', 'MGTK', 'SREF')},
 'Euro Alliance': {'infantry': ('E1', 'GGI', 'GHOST', 'TANY'),
                   'vehicles': ('MTNK', 'FV', 'MGTK', 'SREF')},
 'Pacific Front': {'infantry': ('E1', 'GGI', 'GHOST', 'TANY'),
                   'vehicles': ('KTNK', 'FV', 'MGTK', 'SREF')},
 'Russia': {'infantry': ('E2', 'FLAKT', 'FLAMER', 'DESO'),
            'vehicles': ('HTNK', 'DRON', 'V3', 'APOC')},
 'Confederation': {'infantry': ('E2', 'FLAKT', 'FLAMER', 'DESO'),
                   'vehicles': ('JTNK', 'DRON', 'V3', 'APOC')},
 'China': {'infantry': ('E2', 'FLAKT', 'FLAMER', 'SHOCK'),
           'vehicles': ('CTNK', 'DRON', 'V3', 'APOC')},
 'PsiCorps': {'infantry': ('INIT', 'HARP', 'BRUTE', 'VIRUS'),
              'vehicles': ('LTNK', 'YTNK', 'STING', 'MIND')},
 'Scorpion Cell': {'infantry': ('INIT', 'HARP', 'BRUTE', 'VIRUS'),
                   'vehicles': ('QTNK', 'YTNK', 'STING', 'MIND')},
 'Epsilon HQ': {'infantry': ('INIT', 'HARP', 'BRUTE', 'VIRUS'),
                'vehicles': ('STNK', 'YTNK', 'STING', 'MIND')},
 'Haihead': {'infantry': ('KNIGHT', 'COVE', 'HUNTR', 'CLAIR'),
             'vehicles': ('CYCL', 'JACKAL', 'CONF', 'PROME')},
 'Coronia': {'infantry': ('KNIGHT', 'COVE', 'HUNTR', 'CLAIR'),
             'vehicles': ('DRACO', 'JACKAL', 'CONF', 'PROME')},
 'Last Bastion': {'infantry': ('KNIGHT', 'COVE', 'HUNTR', 'CLAIR'),
                  'vehicles': ('ROACH', 'JACKAL', 'CONF', 'PROME')}}
