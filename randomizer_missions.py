"""Mission catalogue parsing and deterministic seed-order construction.

This module deliberately contains no Tk state.  Keeping mission discovery and
ordering pure makes seed compatibility testable without starting the launcher.
"""

import re


FACTION_ORDER = ('Allies', 'Soviets', 'Epsilon', 'Foehn')
FALLBACK_OBJECTIVE_COUNT = 3
STARTING_UNLOCKED_MISSIONS = 3


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


def seed_mission_order(missions, rng, mission_goal, starting_count=STARTING_UNLOCKED_MISSIONS):
    """Return the deterministic staged mission order for one seed RNG."""
    missions = list(missions)
    if not missions:
        return []
    mission_goal = max(1, min(mission_goal, len(missions)))
    campaign_limits = seed_campaign_limits(missions, mission_goal)
    picked_by_faction = {faction: 0 for faction in campaign_limits}

    def bucket(mission):
        score = mission_stage_score(mission)
        return 0 if score <= 6 else 1 if score <= 16 else 2 if score < 24 else 3

    def shuffled(items):
        items = list(items)
        rng.shuffle(items)
        return items

    early_mid = [mission for mission in missions if bucket(mission) <= 1]
    non_finale = [mission for mission in missions if bucket(mission) <= 2]
    if mission_goal <= 5 and len(early_mid) >= mission_goal:
        candidates = early_mid
    elif len(non_finale) >= mission_goal:
        candidates = non_finale
    else:
        candidates = missions

    start_count = min(starting_count, mission_goal)
    starting_pool = shuffled(mission for mission in candidates if bucket(mission) == 0)
    for bucket_index in (1, 2, 3):
        if len(starting_pool) >= start_count:
            break
        starting_pool.extend(shuffled(mission for mission in candidates if bucket(mission) == bucket_index))

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

    for mission in starting_pool:
        if add_mission(mission) and len(ordered) >= start_count:
            break
    if len(ordered) >= mission_goal:
        return [item['code'] for item in ordered]

    for bucket_index in range(4):
        for mission in shuffled(mission for mission in candidates if bucket(mission) == bucket_index):
            if add_mission(mission) and len(ordered) >= mission_goal:
                return [item['code'] for item in ordered]
    for mission in shuffled(missions):
        if add_mission(mission) and len(ordered) >= mission_goal:
            break
    return [item['code'] for item in ordered]
