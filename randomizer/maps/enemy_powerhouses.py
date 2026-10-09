"""Expand hostile reinforcement waves without changing shared TaskForces.

Adapted from DTA's Powerhouse planning: land waves rotate faction heavies,
air/naval waves reuse their existing terrain-compatible members. MO keeps
transport, objective, unique-unit and no-build mission protections.
"""

from hashlib import sha256
from copy import deepcopy

from randomizer.rewards.definitions import (
    ENGINEER_UNIT_IDS,
    LIMITED_HERO_UNIT_IDS,
    MCV_UNIT_IDS,
    NONCOMBAT_WEAPON_TARGET_IDS,
)
from randomizer.rewards.enemy_scaling import enemy_effect_text, enemy_effect_values

from .houses import canonical_house_name, country_family, map_house_records
from .ini import all_section_value_maps_preserve, parse_action_groups
from .enemy_powerhouse_specials import special_powerhouse_rules


# Installed combat types with no cargo or unique-unit cap. Specials remain
# native enemy types; no player unlock or foreign production access is added.
POWERHOUSE_UNITS_BY_FAMILY = {
    'allies': ('AHVYBOT', 'BLZZ', 'SREF'),
    'soviets': ('MAMM', 'EMPR', 'TTNK'),
    'epsilon': ('DEVO', 'MIND', 'TELE'),
    'foehn': ('ARCH', 'PROME', 'TARCHIA'),
}
_REINFORCEMENT_ACTIONS = frozenset({'7', '80', '107'})
_TRUE_VALUES = frozenset({'yes', 'true', '1'})
_PROTECTED_UNIT_IDS = (
    ENGINEER_UNIT_IDS | LIMITED_HERO_UNIT_IDS | MCV_UNIT_IDS
    | NONCOMBAT_WEAPON_TARGET_IDS
)


def _fold(values):
    return {str(key).casefold(): value for key, value in values.items()}


def _unit_values(unit_id, mission, installed, seen=()):
    """Resolve native rules and map-local inheritance, rejecting cycles."""
    unit_id = str(unit_id).casefold()
    if unit_id in seen:
        return {}
    native = _fold(installed.get(unit_id, {}))
    override = _fold(mission.get(unit_id, {}))
    values = {**native, **override}
    parent = override.get('$inherits') or override.get('basesection')
    if not native:
        parent = parent or values.get('$inherits') or values.get('basesection')
    if parent:
        values = {
            **_unit_values(parent, mission, installed, (*seen, unit_id)),
            **values,
        }
    return values


def _member_kind(unit_id, mission, installed, protected):
    """Return safe combat terrain, or an empty string for protected members."""
    values = _unit_values(unit_id, mission, installed)
    try:
        passengers = int(values.get('passengers', 0))
        build_limit = int(values.get('buildlimit', 0))
    except (ValueError, TypeError):
        return ''
    if (
        str(unit_id).upper() in protected
        or str(unit_id).upper().endswith('MCV')
        or not values
        or passengers != 0
        or build_limit != 0
        or any(str(values.get(key, '')).casefold() in _TRUE_VALUES for key in (
            'harvester', 'weeder', 'engineer', 'isvehicletransport', 'carryall',
            'isdeployment', 'deploytocombat',
        ))
        or str(values.get('category', '')).casefold() == 'transport'
        or not any(values.get(key) for key in (
            'primary', 'secondary', 'weapon1',
        ))
    ):
        return ''
    movement = str(values.get('movementzone', '')).casefold()
    speed = str(values.get('speedtype', '')).casefold()
    if (
        str(values.get('naval', '')).casefold() in _TRUE_VALUES
        or speed == 'float' or movement == 'water'
    ):
        return 'naval'
    if movement == 'fly' or str(values.get('category', '')).casefold() == 'airpower':
        return 'air'
    # Underground waves use a different entry path; keep their native shape.
    if movement in {'subterannean', 'subterranean'}:
        return ''
    if movement or speed or values.get('category'):
        return 'land'
    return ''


def _clone_id(team_id, occupied):
    stem = 'MORETF' + sha256(team_id.encode('utf-8')).hexdigest()[:8].upper()
    candidate = stem
    suffix = 2
    while candidate.casefold() in occupied:
        candidate = f'{stem}{suffix}'
        suffix += 1
    occupied.add(candidate.casefold())
    return candidate


def enemy_powerhouse_rules(
    lines, enemy_houses, rewards, installed_sections,
    *, excluded_teams=(), excluded_unit_ids=(), house_records=None,
    stage=1, difficulty=1, production_enabled=True, player_countries=(),
    protected_mission=False, seed='',
):
    """Return map-local TaskForce/TeamType rules and exact application receipts."""
    reward = next((
        reward for reward in rewards
        if reward.get('enemy_reward') and reward.get('enemy_effect') == 'powerhouse'
    ), None)
    if reward is None or not enemy_houses or protected_mission:
        return {}, [], []
    sections = all_section_value_maps_preserve(lines)
    by_lower = {str(name).casefold(): values for name, values in sections.items()}
    installed = {
        str(name).casefold(): values for name, values in installed_sections.items()
    }
    records = map_house_records(lines) if house_records is None else house_records
    hostile = {str(house).casefold() for house in enemy_houses}
    excluded = {str(team).casefold() for team in excluded_teams}
    protected = _PROTECTED_UNIT_IDS | {
        str(unit_id).upper() for unit_id in excluded_unit_ids
    }
    teams = tuple(dict.fromkeys(by_lower.get('teamtypes', {}).values()))
    known = {str(team).casefold() for team in teams}
    reinforcement_teams = set()
    for action in by_lower.get('actions', {}).values():
        _count, groups = parse_action_groups(str(action))
        for group in groups:
            if group[0] in _REINFORCEMENT_ACTIONS:
                reinforcement_teams.update(
                    str(token).casefold() for token in group[1:]
                    if str(token).casefold() in known
                )
    identity = repr((by_lower.get('basic', {}), teams))
    if seed:
        identity += f'|{seed}'
    cursors = {
        family: int.from_bytes(sha256(
            f'{family}|{identity}'.encode('utf-8')
        ).digest()[:4], 'big') % len(pool)
        for family, pool in POWERHOUSE_UNITS_BY_FAMILY.items()
    }
    occupied = set(by_lower) | set(installed)
    registry = dict(by_lower.get('taskforces', {}))
    rules, applications, skipped = {}, [], []
    for team_id in teams:
        team_id = str(team_id)
        values = _fold(by_lower.get(team_id.casefold(), {}))
        house = canonical_house_name(records, values.get('house'))
        if house.casefold() not in hostile:
            continue
        if (
            team_id.casefold() in excluded
            or (team_id.casefold() not in reinforcement_teams
                and str(values.get('reinforce', '')).casefold() not in _TRUE_VALUES)
        ):
            continue
        if any(str(values.get(key, '')).casefold() in _TRUE_VALUES for key in (
            'droppod', 'isontransonly',
        )) or str(values.get('transportwaypoint', '')).strip() not in {'', '-1'}:
            skipped.append(f'{team_id}: transport/drop-pod team')
            continue
        taskforce = by_lower.get(str(values.get('taskforce', '')).casefold(), {})
        members = []
        malformed = False
        for key in sorted((key for key in taskforce if str(key).isdigit()), key=int):
            fields = [field.strip() for field in str(taskforce[key]).split(',')]
            try:
                if len(fields) != 2 or int(fields[0]) <= 0:
                    malformed = True
                    break
            except ValueError:
                malformed = True
                break
            members.append((key, int(fields[0]), fields[1], _member_kind(
                fields[1], by_lower, installed, protected,
            )))
        kinds = {kind for _key, _count, _unit, kind in members}
        if malformed or not members or '' in kinds or len(kinds) != 1:
            skipped.append(f'{team_id}: protected, unknown or mixed-terrain members')
            continue
        kind = next(iter(kinds))
        clone = dict(taskforce)
        additions = []
        if kind == 'land':
            family = country_family(records.get(house, {}))
            pool = POWERHOUSE_UNITS_BY_FAMILY.get(family, ())
            pool = tuple(unit for unit in pool if (
                _member_kind(unit, by_lower, installed, protected) == 'land'
            ))
            # An entirely amphibious wave may enter over water or follow a
            # water-only route. Only add heavies with the same capability.
            if all(str(_unit_values(
                unit, by_lower, installed
            ).get('movementzone', '')).casefold().startswith('amphibious')
                   for _key, _count, unit, _kind in members):
                pool = tuple(unit for unit in pool if str(_unit_values(
                    unit, by_lower, installed
                ).get('movementzone', '')).casefold().startswith('amphibious'))
            if len(pool) < 2:
                skipped.append(f'{team_id}: no compatible faction heavy-unit pool')
                continue
            start = cursors[family] % len(pool)
            chosen = [pool[(start + offset) % len(pool)] for offset in range(2)]
            next_key = max(int(key) for key, *_rest in members) + 1
            new_types = [unit for unit in chosen if not any(
                member[2].casefold() == unit.casefold() for member in members
            )]
            # Keep the conservative six-entry TaskForce budget. Do not make a
            # partial wave upgrade when two added types would exceed it.
            if next_key + len(new_types) > 6:
                skipped.append(f'{team_id}: full TaskForce member list')
                continue
            for unit_id in chosen:
                existing = next((member for member in members
                                 if member[2].casefold() == unit_id.casefold()), None)
                if existing:
                    clone[existing[0]] = f'{existing[1] + 1},{existing[2]}'
                else:
                    clone[str(next_key)] = f'1,{unit_id}'
                    next_key += 1
                additions.append(unit_id)
            cursors[family] += 1
        else:
            key, count, unit_id, _kind = members[0]
            clone[key] = f'{count + 1},{unit_id}'
            additions.append(unit_id)
        clone_id = _clone_id(team_id, occupied)
        list_key = str(max((int(key) for key in registry if str(key).isdigit()), default=-1) + 1)
        registry[list_key] = clone_id
        rules.setdefault('TaskForces', {})[list_key] = clone_id
        rules[clone_id] = clone
        rules[team_id] = {'TaskForce': clone_id}
        try:
            veteran_level = int(values.get('veteranlevel', 1))
        except (TypeError, ValueError):
            veteran_level = 1
        if veteran_level < 2:
            rules[team_id]['VeteranLevel'] = '2'
        applications.append({
            **enemy_effect_values(reward, 1),
            'effect_id': reward['enemy_effect_id'],
            'effect': enemy_effect_text(reward, 1),
            'category': reward.get('enemy_category', 'Enemy reinforcements'),
            'house': house,
            'country': records.get(house, {}).get('country', ''),
            'target': f'{team_id} / ' + ', '.join(additions),
            'engine_field': 'TaskForce members / TeamType.VeteranLevel',
            'added_unit_ids': additions,
            'added_unit_count': len(additions),
            'application_kind': 'wave', 'source_team_id': team_id,
            'wave_kind': kind,
            'amphibious_only': all(str(_unit_values(
                unit, by_lower, installed
            ).get('movementzone', '')).casefold().startswith('amphibious')
                for _key, _count, unit, _kind in members),
        })
    working_sections = deepcopy(sections)
    for section, values in rules.items():
        working_sections.setdefault(section, {}).update(values)
    special_rules, special_applications, special_skips = special_powerhouse_rules(
        lines, working_sections, records, enemy_houses, applications,
        installed_sections, reward, POWERHOUSE_UNITS_BY_FAMILY,
        stage=stage, difficulty=difficulty, excluded_unit_ids=excluded_unit_ids,
        production_enabled=production_enabled, player_countries=player_countries,
        seed=seed,
    )
    for section, values in special_rules.items():
        rules.setdefault(section, {}).update(values)
    applications.extend(special_applications)
    skipped.extend(special_skips)
    return rules, applications, skipped
