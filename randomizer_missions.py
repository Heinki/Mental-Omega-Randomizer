"""Mission catalogue parsing and deterministic seed-order construction.

This module deliberately contains no Tk state.  Keeping mission discovery and
ordering pure makes seed compatibility testable without starting the launcher.
"""

import re


FACTION_ORDER = ('Allies', 'Soviets', 'Epsilon', 'Foehn')
FALLBACK_OBJECTIVE_COUNT = 3
STARTING_UNLOCKED_MISSIONS = 3
LOW_LEVEL_MISSION_COUNT = 5
LOW_LEVEL_STAGE_MAX = 6

BASE_BUILD = 'base_build'
TRUE_NO_BUILD = 'true_no_build'
NO_BUILD_PRODUCTION = 'no_build_production'

# Community-reviewed gameplay classification for all 97 installed campaign
# maps. Keep every catalogue code explicit: this is player-facing seed data,
# not a title/stage-name guess.
MISSION_BUILD_CLASSIFICATIONS = {
    'AREDDAWN': BASE_BUILD,
    'AEAGLESFLY': BASE_BUILD,
    'AROADTRIP': NO_BUILD_PRODUCTION,
    'AHEAVENHELL': BASE_BUILD,
    'ABADAPPLE': NO_BUILD_PRODUCTION,
    'ABMIND': BASE_BUILD,
    'AHAMMERFALL': TRUE_NO_BUILD,
    'AWRONGSIDE': TRUE_NO_BUILD,
    'AZEROSIGNAL': NO_BUILD_PRODUCTION,
    'AGARDENER': TRUE_NO_BUILD,
    'APANIC': BASE_BUILD,
    'ASUNLIGHT': BASE_BUILD,
    'ASIREN': TRUE_NO_BUILD,
    'APUPPET': BASE_BUILD,
    'ASTONE': NO_BUILD_PRODUCTION,
    'AGHOST': BASE_BUILD,
    'ABOTTLE': TRUE_NO_BUILD,
    'AHYST': BASE_BUILD,
    'ASTORM': BASE_BUILD,
    'APARA': TRUE_NO_BUILD,
    'ARELE': BASE_BUILD,
    'AINSOMNIA': BASE_BUILD,
    'AWITHER': BASE_BUILD,
    'AHAMARTIA': BASE_BUILD,
    'SBLEED': BASE_BUILD,
    'SGGATE': NO_BUILD_PRODUCTION,
    'SHBD': BASE_BUILD,
    'SSIDE': BASE_BUILD,
    'SPEACE': NO_BUILD_PRODUCTION,
    'SRECH': TRUE_NO_BUILD,
    'SIDLE': BASE_BUILD,
    'SDEATH': BASE_BUILD,
    'SROAD': NO_BUILD_PRODUCTION,
    'SOPEN': TRUE_NO_BUILD,
    'SMACHINE': BASE_BUILD,
    'SDRAGON': BASE_BUILD,
    'SRAVEN': BASE_BUILD,
    'SAWAKE': TRUE_NO_BUILD,
    'SEXIST': BASE_BUILD,
    'SFIRE': BASE_BUILD,
    'SJUGGER': BASE_BUILD,
    'SHEART': TRUE_NO_BUILD,
    'SRED': BASE_BUILD,
    'STHREAD': BASE_BUILD,
    'SMELT': NO_BUILD_PRODUCTION,
    'SEARTH': BASE_BUILD,
    'SFATAL': BASE_BUILD,
    'SHAND': BASE_BUILD,
    'EPEACE': TRUE_NO_BUILD,
    'EACCEL': TRUE_NO_BUILD,
    'ESCRAP': NO_BUILD_PRODUCTION,
    'ESHIP': BASE_BUILD,
    'EHUMAN': TRUE_NO_BUILD,
    'ELAND': TRUE_NO_BUILD,
    'ETHINK': BASE_BUILD,
    'ELORD': NO_BUILD_PRODUCTION,
    'EFIELDS': TRUE_NO_BUILD,
    'EFOCUS': TRUE_NO_BUILD,
    'ESING': TRUE_NO_BUILD,
    'EMOON': BASE_BUILD,
    'EDILEMMA': BASE_BUILD,
    'EHUEHUE': TRUE_NO_BUILD,
    'EBREED': BASE_BUILD,
    'EDIVER': BASE_BUILD,
    'EGODSEND': NO_BUILD_PRODUCTION,
    'ELIZARD': NO_BUILD_PRODUCTION,
    'EBLOOD': BASE_BUILD,
    'EHEAD': TRUE_NO_BUILD,
    'ESANDS': BASE_BUILD,
    'ETOTAL': BASE_BUILD,
    'EREALITY': TRUE_NO_BUILD,
    'EMIGDAL': BASE_BUILD,
    'FNOBODY': TRUE_NO_BUILD,
    'FKILL': BASE_BUILD,
    'FEMPIRE': NO_BUILD_PRODUCTION,
    'FBEYOND': BASE_BUILD,
    'FPOINT': TRUE_NO_BUILD,
    'FREMNANT': BASE_BUILD,
    'ADEMON': NO_BUILD_PRODUCTION,
    'AOBST': BASE_BUILD,
    'ACONV': TRUE_NO_BUILD,
    'AFULL': BASE_BUILD,
    'AGRID': BASE_BUILD,
    'ASOMNIA': BASE_BUILD,
    'SARCHE': TRUE_NO_BUILD,
    'SECLIPSE': BASE_BUILD,
    'STROPH': NO_BUILD_PRODUCTION,
    'SNOISE': NO_BUILD_PRODUCTION,
    'SDAWN': BASE_BUILD,
    'SARMS': BASE_BUILD,
    'ETACI': TRUE_NO_BUILD,
    'EASHES': NO_BUILD_PRODUCTION,
    'ERAGE': TRUE_NO_BUILD,
    'ESPLIT': BASE_BUILD,
    'ENIGHT': NO_BUILD_PRODUCTION,
    'ESURV': NO_BUILD_PRODUCTION,
    'FCAPSULE': TRUE_NO_BUILD,
}

TRUE_NO_BUILD_MISSION_CODES = frozenset(
    code for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
    if classification == TRUE_NO_BUILD
)
NO_BUILD_PRODUCTION_MISSION_CODES = frozenset(
    code for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
    if classification == NO_BUILD_PRODUCTION
)
NO_BUILD_MISSION_CODES = frozenset(
    TRUE_NO_BUILD_MISSION_CODES | NO_BUILD_PRODUCTION_MISSION_CODES
)

# Backward-compatible boolean view for older integrations. ``True`` means the
# mission belongs to either non-base-building category.
NO_BUILD_MISSION_FLAGS = {
    code: classification != BASE_BUILD
    for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
}

# User-approved early exceptions are Foehn 01 and 05. Every other Foehn map
# is kept out of a protected opening while another eligible mission exists,
# including no-build operation TIME CAPSULE because its difficulty is high.
LATE_FOEHN_MISSION_CODES = frozenset({
    'FKILL', 'FEMPIRE', 'FBEYOND', 'FREMNANT', 'FCAPSULE',
})


def normalize_faction(side):
    side = (side or '').strip().lower()
    if 'allies' in side or 'allied' in side:
        return 'Allies'
    if 'soviet' in side:
        return 'Soviets'
    if 'epsilon' in side:
        return 'Epsilon'
    if 'foehn' in side:
        return 'Foehn'
    return ''


def filter_missions_by_build_settings(
    missions,
    include_true_no_build=True,
    include_no_build_production=True,
):
    """Apply the two independent no-build category inclusion settings."""
    excluded = set()
    if not include_true_no_build:
        excluded.add(TRUE_NO_BUILD)
    if not include_no_build_production:
        excluded.add(NO_BUILD_PRODUCTION)
    if not excluded:
        return list(missions)
    return [
        mission for mission in missions
        if mission.get('build_classification', BASE_BUILD) not in excluded
    ]


def parse_long_description_objectives(text):
    if not text:
        return []
    objectives = []
    for part in text.split('@'):
        match = re.match(r'\s*Objective\s+(\d+)\s*:\s*(.+?)\s*$', part, flags=re.IGNORECASE)
        if match:
            objectives.append(match.group(2).strip())
    return objectives


def parse_missions(path, fallback_objective_count=FALLBACK_OBJECTIVE_COUNT):
    """Read the ordered campaign catalogue from ``BattleClient.ini``."""
    if not path.exists():
        return []

    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    mission_codes = []
    seen_codes = set()
    sections = {}
    current_section = None
    in_battles = False

    for line in lines:
        no_comment = line.split(';', 1)[0].strip()
        if not no_comment:
            continue
        if no_comment.startswith('[') and no_comment.endswith(']'):
            current_section = no_comment[1:-1].strip()
            in_battles = current_section == 'Battles'
            sections.setdefault(current_section, {})
            continue
        if in_battles and '=' in no_comment:
            _, value = no_comment.split('=', 1)
            code = value.strip()
            if code and code not in seen_codes:
                mission_codes.append(code)
                seen_codes.add(code)
            continue
        if current_section and '=' in no_comment:
            key, value = no_comment.split('=', 1)
            sections.setdefault(current_section, {})[key.strip()] = value.strip()

    missions = []
    for position, code in enumerate(mission_codes, start=1):
        section = sections.get(code, {})
        scenario = section.get('Scenario') or section.get('SCENARIO')
        if not scenario:
            continue
        objectives = parse_long_description_objectives(section.get('LongDescription', ''))
        missions.append({
            'index': position,
            'code': code,
            'scenario': scenario,
            'title': section.get('Description') or section.get('description') or code,
            'side': section.get('SideName') or section.get('Side') or '',
            'objectives': objectives,
            'objective_count': len(objectives) or fallback_objective_count,
            'build_classification': MISSION_BUILD_CLASSIFICATIONS.get(code, BASE_BUILD),
            'no_build': bool(NO_BUILD_MISSION_FLAGS.get(code, False)),
            'true_no_build': code in TRUE_NO_BUILD_MISSION_CODES,
            'no_build_production': code in NO_BUILD_PRODUCTION_MISSION_CODES,
        })
    return missions


def mission_stage_score(mission):
    title = mission.get('title', '') or ''
    code = mission.get('code', '') or ''
    match = re.search(r'\b(?:Allied|Soviet|Epsilon|Foehn)\s+(\d{1,2})\b', title, flags=re.IGNORECASE)
    if match:
        score = int(match.group(1))
    elif re.search(r'\bOp\b', title, flags=re.IGNORECASE):
        score = 9
    else:
        score = int(mission.get('index') or 12)
    if re.search(r'\b(finale|final)\b', title, flags=re.IGNORECASE) or code.upper() == 'SHAND':
        score = max(score, 24)
    return score


def campaign_mission_counts(missions):
    counts = {faction: 0 for faction in FACTION_ORDER}
    for mission in missions:
        faction = normalize_faction(mission.get('side', ''))
        if faction in counts:
            counts[faction] += 1
    return {faction: count for faction, count in counts.items() if count}


def seed_campaign_limits(missions, mission_goal):
    """Cap the short Foehn campaign proportionally in mixed seeds."""
    counts = campaign_mission_counts(missions)
    if len(counts) <= 1 or 'Foehn' not in counts:
        return dict(counts)
    total = sum(counts.values())
    limits = dict(counts)
    limits['Foehn'] = min(
        counts['Foehn'],
        max(1, (mission_goal * counts['Foehn'] + total - 1) // total),
    )
    return limits


def classic_mission_order(missions, mission_goal):
    """Return the requested missions in installed campaign-catalogue order."""
    missions = list(missions)
    if not missions:
        return []
    mission_goal = max(1, min(mission_goal, len(missions)))
    return [mission['code'] for mission in missions[:mission_goal]]


def seed_mission_order(
    missions,
    rng,
    mission_goal,
    low_level_count=LOW_LEVEL_MISSION_COUNT,
    preferred_opening_codes=None,
    excluded_opening_codes=None,
):
    """Return the requested low-level opening, then an unrestricted shuffle."""
    missions = list(missions)
    if not missions:
        return []
    mission_goal = max(1, min(mission_goal, len(missions)))
    campaign_limits = seed_campaign_limits(missions, mission_goal)
    picked_by_faction = {faction: 0 for faction in campaign_limits}

    def bucket(mission):
        score = mission_stage_score(mission)
        return 0 if score <= LOW_LEVEL_STAGE_MAX else 1 if score <= 16 else 2 if score < 24 else 3

    def shuffled(items):
        items = list(items)
        rng.shuffle(items)
        return items

    opening_count = min(max(0, int(low_level_count)), mission_goal)
    preferred_opening_codes = set(preferred_opening_codes or ())
    excluded_opening_codes = set(excluded_opening_codes or ())

    picked_codes = set()
    ordered = []

    def add_mission(mission):
        faction = normalize_faction(mission.get('side', ''))
        if (
            mission['code'] in picked_codes
            or picked_by_faction.get(faction, 0) >= campaign_limits.get(faction, len(missions))
        ):
            return False
        ordered.append(mission)
        picked_codes.add(mission['code'])
        picked_by_faction[faction] = picked_by_faction.get(faction, 0) + 1
        return True

    # Optional no-build preference still respects stage buckets: easier fixed-
    # unit missions win before late/finale no-build missions. Late Foehn maps
    # remain excluded from the protected opening.
    if preferred_opening_codes and opening_count:
        for bucket_index in range(4):
            bucket_missions = (
                mission for mission in missions
                if mission['code'] in preferred_opening_codes
                and mission['code'] not in excluded_opening_codes
                and bucket(mission) == bucket_index
            )
            for mission in shuffled(bucket_missions):
                if add_mission(mission) and len(ordered) >= opening_count:
                    break
            if len(ordered) >= opening_count:
                break

    # Keep only the opening approachable. The installed catalogue has enough
    # missions 1-6 for all campaign filters; later buckets are a defensive
    # fallback for custom or incomplete catalogues.
    for bucket_index in range(4) if len(ordered) < opening_count else ():
        bucket_missions = (
            mission for mission in missions
            if mission['code'] not in excluded_opening_codes
            and bucket(mission) == bucket_index
        )
        for mission in shuffled(bucket_missions):
            if add_mission(mission) and len(ordered) >= opening_count:
                break
        if len(ordered) >= opening_count:
            break

    # A narrow custom/campaign-only pool may contain too few safe opening maps.
    # Fill from excluded maps only when otherwise impossible to reach requested
    # opening size; mixed installed campaigns never need this fallback.
    if len(ordered) < opening_count:
        for bucket_index in range(4):
            bucket_missions = (
                mission for mission in missions
                if mission['code'] in excluded_opening_codes
                and bucket(mission) == bucket_index
            )
            for mission in shuffled(bucket_missions):
                if add_mission(mission) and len(ordered) >= opening_count:
                    break
            if len(ordered) >= opening_count:
                break
    if len(ordered) >= mission_goal:
        return [item['code'] for item in ordered]

    # Everything after the protected opening is equally eligible. Act 2 and
    # finale missions can therefore appear in the first unprotected slot.
    for mission in shuffled(missions):
        if add_mission(mission) and len(ordered) >= mission_goal:
            break
    return [item['code'] for item in ordered]
