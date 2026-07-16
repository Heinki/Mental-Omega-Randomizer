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

    # Keep only the opening approachable. The installed catalogue has enough
    # missions 1-6 for all campaign filters; later buckets are a defensive
    # fallback for custom or incomplete catalogues.
    for bucket_index in range(4) if opening_count else ():
        bucket_missions = (
            mission for mission in missions if bucket(mission) == bucket_index
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
