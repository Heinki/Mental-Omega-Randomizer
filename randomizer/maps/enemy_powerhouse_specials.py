"""Private hero/superunit companions and bounded hostile factory production."""

from hashlib import sha256

from randomizer.rewards.catalogue import BUFF_TARGETS
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.rewards.enemy_scaling import enemy_effect_values

from .base import MAX_MAP_ACTION_LINE_LENGTH, RANDOMIZER_TYPE_LIST_KEY_START
from .houses import canonical_house_name, country_family, production_owner_countries
from .ini import parse_action_groups
from .ownership import unsafe_country_houses
from .production import PLAYER_ORIGINAL_PRODUCTION_GATE_ID


HERO_UNITS_BY_FAMILY = {
    'allies': ('TANY', 'SIEG', 'ARMR'),
    'soviets': ('VOLKOV', 'YUNRU', 'MORALES', 'BORIS'),
    'epsilon': ('LIBRA', 'UNDER', 'ASSN', 'CBRIS'),
    'foehn': ('EUREKA', 'SIBFIN', 'SICALI', 'URAGAN'),
}
# Each tuple is one boss encounter. Both Hands share a companion team but
# receive separate, damageable portable identities and their correct art.
SUPERUNITS_BY_FAMILY = {
    'allies': (('STARDUSTB',), ('SHINBOT',)),
    'soviets': (('CNTR',), ('PERUN',)),
    'epsilon': (('DHANDL', 'DHANDR'), ('HEPH',), ('GOTTER',)),
    'foehn': (('RAMW',), ('ARCH2',)),
}
_SPECIAL_UNIT_FAMILIES = {
    unit: family for family, pool in HERO_UNITS_BY_FAMILY.items() for unit in pool
}
_SPECIAL_UNIT_FAMILIES.update({
    unit: family for family, pool in SUPERUNITS_BY_FAMILY.items()
    for bundle in pool for unit in bundle
})
_CREATE_ACTIONS = frozenset({'4', '7', '80', '107'})
_YES = frozenset({'yes', 'true', '1'})


def powerhouse_level(stage=1, difficulty=1):
    """Unlock heroes at stage 4, bosses at 8; Mental advances one tier."""
    stage = max(1, int(stage))
    return min(2, (2 if stage >= 8 else 1 if stage >= 4 else 0)
               + (1 if int(difficulty) >= 2 else 0))


def _fold(values):
    return {str(key).lower(): value for key, value in values.items()}


def _rank(identity, values):
    return sorted(values, key=lambda value: sha256(
        f'{identity}|{value}'.encode('utf-8')
    ).digest())


def special_powerhouse_rules(
    lines, sections, records, hostile_houses, wave_applications, installed,
    reward, heavy_pools, *, stage=1, difficulty=1, excluded_unit_ids=(),
    production_enabled=True, player_countries=(), seed='',
):
    """Plan private actors; preserve every authored TechnoType and AI team."""
    level = powerhouse_level(stage, difficulty)
    _, _, templates = randomizer_unit_roster()
    by_lower = {str(name).lower(): values for name, values in sections.items()}
    installed_lower = {str(name).lower(): values for name, values in installed.items()}
    protected = {str(unit).upper() for unit in excluded_unit_ids}
    player_countries = sorted(set(player_countries))
    hostile = {str(house).lower() for house in hostile_houses}
    occupied = set(by_lower) | set(installed_lower)
    registries = {}
    rules, applications, skipped = {}, [], []
    identity = repr(by_lower.get('basic', {}))
    if seed:
        identity += f'|{seed}'

    def effective(type_id):
        return {**_fold(installed_lower.get(str(type_id).lower(), {})),
                **_fold(by_lower.get(str(type_id).lower(), {}))}

    def unique(prefix, scope):
        stem = prefix + sha256(scope.encode('utf-8')).hexdigest()[:10].upper()
        candidate, suffix = stem, 2
        while candidate.lower() in occupied:
            candidate = f'{stem}{suffix}'
            suffix += 1
        occupied.add(candidate.lower())
        return candidate

    def register(section, type_id):
        values = registries.setdefault(section, dict(by_lower.get(section.lower(), {})))
        key = str(max(RANDOMIZER_TYPE_LIST_KEY_START,
                      max((int(key) for key in values if str(key).isdigit()), default=-1) + 1))
        values[key] = type_id
        rules.setdefault(section, {})[key] = type_id

    def portable(source):
        basis = 'DHANDL' if source == 'DHANDR' else source
        values = dict(templates.get(basis, {}))
        if source == 'DHANDR':
            values.update({'Image': 'DHANDR', 'Name': 'Hand of Ereshkigal Right'})
        return values

    def available(source):
        values = _fold(portable(source))
        return bool(source not in protected and values and any(
            values.get(key) and str(values[key]).lower() not in {'none', '<none>'}
            for key in ('primary', 'secondary', 'weapon1')
        ) and not any(str(values.get(key, '')).upper().startswith('MORP') for key in (
            'initialpayload.types', 'passengers.allowed', 'spawns', 'deploysinto', 'undeploysinto',
        )))

    def member_kind(source):
        values = _fold(portable(source))
        if str(values.get('naval', '')).lower() in _YES:
            return 'naval'
        return 'air' if str(values.get('movementzone', '')).lower() == 'fly' else 'land'

    def special_picks(family, scope, hero_count):
        heroes = _rank(f'{scope}|heroes', [
            unit for unit in HERO_UNITS_BY_FAMILY.get(family, ()) if available(unit)
        ])[:hero_count]
        bosses = _rank(f'{scope}|bosses', [
            bundle for bundle in SUPERUNITS_BY_FAMILY.get(family, ())
            if all(available(unit) for unit in bundle)
        ])[:1]
        # Campaign enemy factions do not reliably provide Foehn armies.
        # Treat Foehn as occasional auxiliaries for each existing faction,
        # while retaining the native hero lead and the existing team budget.
        if family in {'allies', 'soviets', 'epsilon'}:
            for kind, pool in (
                ('heroes', [(unit,) for unit in HERO_UNITS_BY_FAMILY['foehn']]),
                ('bosses', SUPERUNITS_BY_FAMILY['foehn']),
            ):
                roll = int.from_bytes(sha256(f'{scope}|foehn-{kind}'.encode('utf-8')).digest()[:4], 'big')
                if roll % 3:
                    continue
                candidates = _rank(f'{scope}|foehn-{kind}|units', [
                    bundle for bundle in pool if all(available(unit) for unit in bundle)
                ])
                if candidates:
                    if kind == 'heroes':
                        heroes = [*heroes[:max(0, hero_count - 1)], candidates[0][0]]
                    else:
                        bosses = candidates[:1]
        return heroes, bosses

    def clone(source, house, mode, factory=''):
        values = portable(source)
        if not available(source):
            return ''
        country = records[house]['country']
        type_id = unique('MOREU', f'{house}|{source}|{mode}')
        # These complete portable rules provide Paradox/Hands weapons and
        # normal durability, without inheriting cinematic map overrides.
        values = {key: value for key, value in values.items() if value is not None
                  and not str(key).lower().startswith(('prerequisite', 'requiresstolen', 'convert.'))
                  and str(key).lower() not in {
                      '$inherits', 'basesection', 'requiredhouses', 'forbiddenhouses',
                      'factoryowners', 'initialpayload.types', 'initialpayload.nums',
                      'passengers.allowed', 'deploysinto', 'undeploysinto', 'reversedas', 'groupas',
                  }}
        values.update({
            'Name': f'Enemy Powerhouse: {values.get("Name", source)}',
            'Owner': ','.join(production_owner_countries(lines, [country])),
            'TechLevel': '1' if mode == 'production' else '-1',
            'BuildLimit': '1' if mode == 'production' else '0',
            'Prerequisite': factory if mode == 'production' else 'none',
            'RequiredHouses': country if mode == 'production' else 'none',
            'ForbiddenHouses': (','.join(player_countries) or 'none')
            if mode == 'production' else 'none',
            'BuildTimeMultiplier': '1', 'BuildTime.MultipleFactory': '1',
            'CanPassiveAquire': 'yes', 'CanRetaliate': 'yes',
            'PreventAttackMove': 'no', 'IsSelectableCombatant': 'yes',
            'Selectable': 'yes', 'Insignificant': 'no', 'Immune': 'no',
            'CanBeReversed': 'no', 'Cloneable': 'no',
            'AllowedToStartInMultiplayer': 'no', 'Passengers': '0',
            'OpenTopped': 'no', 'PipScale': 'none',
        })
        if mode == 'production':
            values['Prerequisite.Negative'] = PLAYER_ORIGINAL_PRODUCTION_GATE_ID
        category = BUFF_TARGETS.get('DHANDL' if source == 'DHANDR' else source, {}).get('category')
        register('InfantryTypes' if category == 'infantry' else 'VehicleTypes', type_id)
        rules[type_id] = values
        return type_id

    script_id = ''

    def team(source_team_id, house, sources, mode, factory=''):
        nonlocal script_id
        actor_ids = [clone(source, house, mode, factory) for source in sources]
        if not all(actor_ids):
            return '', []
        if not script_id:
            script_id = unique('MORESC', 'powerhouse-hunt')
            register('ScriptTypes', script_id)
            # Authored MO "Attack Anything" scripts use mission 15 (Hunt).
            rules[script_id] = {'Name': 'Enemy Powerhouses Hunt', '0': '11,15'}
        force_id = unique('MORESF', f'{house}|{sources}|{mode}|{source_team_id}')
        team_id = unique('MOREST', f'{house}|{sources}|{mode}|{source_team_id}')
        register('TaskForces', force_id)
        register('TeamTypes', team_id)
        rules[force_id] = {'Name': 'Enemy Powerhouses', 'Group': '-1',
                           **{str(index): f'1,{actor}' for index, actor in enumerate(actor_ids)}}
        values = _fold(by_lower.get(source_team_id.lower(), {}))
        values.update({
            'name': 'Enemy Powerhouses', 'taskforce': force_id, 'script': script_id,
            'house': values.get('house') or house, 'max': '1', 'full': 'yes',
            'reinforce': 'no' if mode == 'production' else 'yes',
            'autocreate': 'yes' if mode == 'production' else 'no',
            'prebuild': 'no', 'recruiter': 'no', 'looserecruit': 'no',
            'areteammembersrecruitable': 'no', 'droppod': 'no',
            'isontransonly': 'no', 'transportwaypoint': '-1',
            'veteranlevel': '3' if level == 2 else '2',
            'priority': '1' if mode == 'production' else '5',
        })
        rules[team_id] = values
        return team_id, actor_ids

    actions = dict(by_lower.get('actions', {}))
    triggers = by_lower.get('triggers', {})
    ai_triggers = by_lower.get('aitriggertypes', {})
    enabled = _fold(by_lower.get('aitriggertypesenable', {}))

    def source_triggers(source_id):
        return [(key, str(raw).split(',')) for key, raw in ai_triggers.items()
                if str(enabled.get(str(key).lower(), 'yes')).lower() not in {'no', 'false', '0'}
                and len(str(raw).split(',')) >= 18
                and str(raw).split(',')[15 + int(difficulty)].strip().lower() in _YES
                and str(raw).split(',')[1].strip().lower() == source_id.lower()]

    def companion_actions(source_id, new_team):
        updated = {}
        for action_id, raw in actions.items():
            trigger_fields = str(triggers.get(action_id, '')).split(',')
            if len(trigger_fields) >= 7 and trigger_fields[4 + int(difficulty)].strip().lower() not in _YES:
                continue
            count, groups = parse_action_groups(str(raw))
            if count != len(groups):
                continue
            extras = []
            for group in groups:
                if group[0] in _CREATE_ACTIONS and source_id.lower() in {
                    token.lower() for token in group[1:]
                }:
                    extras.append([new_team if token.lower() == source_id.lower() else token
                                   for token in group])
            if extras:
                value = ','.join([str(count + len(extras)),
                                  *(token for group in [*groups, *extras] for token in group)])
                if len(f'{action_id}={value}'.encode('utf-8')) > MAX_MAP_ACTION_LINE_LENGTH:
                    return None
                updated[action_id] = value
        return updated

    def attach_companion(source_id, new_team):
        updated = companion_actions(source_id, new_team)
        if updated is None:
            return False
        if updated:
            actions.update(updated)
            rules.setdefault('Actions', {}).update(updated)
            return True
        return False

    def receipt(house, team_id, sources, actors, mode, source_team=''):
        labels = ', '.join(
            'Hand of Ereshkigal Right' if source == 'DHANDR'
            else BUFF_TARGETS.get(source, {}).get('label', source)
            for source in sources
        )
        applications.append({
            **enemy_effect_values(reward, 1),
            'effect_id': reward['enemy_effect_id'], 'category': 'Enemy reinforcements',
            'house': house, 'country': records[house]['country'], 'target': team_id,
            'effect': f'Enemy Powerhouses {mode}: {labels}',
            'engine_field': 'AI production team' if mode == 'production' else 'Companion reinforcement team',
            'application_kind': mode, 'source_team_id': source_team,
            'source_unit_ids': list(sources), 'added_unit_ids': actors,
            'added_unit_count': len(actors), 'current_stacks': 1, 'maximum_stacks': 1,
            'powerhouse_level': level,
            'enemy_family': country_family(records[house]),
            'unit_families': [
                _SPECIAL_UNIT_FAMILIES.get(source, country_family(records[house]))
                for source in sources
            ],
        })

    # At most two hero companion definitions and one boss companion definition
    # per hostile house. Authored repeating waves may request them again.
    # Wave-only actors must use explicit reinforcement creation, never an
    # AITrigger factory queue that cannot build their TechLevel=-1 identity.
    for house in hostile_houses:
        family = country_family(records.get(house, {}))
        waves = [entry for entry in wave_applications if entry['house'] == house]
        heroes, bosses = special_picks(family, f'{identity}|{house}', 2)
        encounters = ([(hero,) for hero in heroes] if level >= 1 else [])
        if level >= 2 and bosses:
            encounters.append(bosses[0])
        for sources in encounters:
            matching = [entry for entry in waves if (
                entry.get('wave_kind') == 'land'
                or all(member_kind(source) == 'air' for source in sources)
            ) and (not entry.get('amphibious_only') or all(
                member_kind(source) == 'air'
                or str(_fold(portable(source)).get('movementzone', '')).lower().startswith('amphibious')
                for source in sources
            ))]
            matching = _rank(f'{house}|{sources}', [entry['source_team_id'] for entry in matching])
            for source_id in matching:
                candidate_links = companion_actions(source_id, 'MOREST' + '0' * 24)
                if candidate_links == {}:
                    continue
                # Reserve a conservative ID length before adding any actors
                # or registry entries. Full authored action lines stay intact.
                if candidate_links is None:
                    skipped.append(f'{source_id}: companion action line has no safe space')
                    continue
                new_team, actors = team(source_id, house, sources, 'companion')
                if new_team and attach_companion(source_id, new_team):
                    receipt(house, new_team, sources, actors, 'companion', source_id)
                    break
                raise ValueError(f'Enemy Powerhouses companion has no creation link: {source_id}')

    if not production_enabled:
        return rules, applications, skipped
    factories = {}

    def factory(owner, building):
        house = canonical_house_name(records, owner)
        if house.lower() not in hostile:
            return
        values = effective(building)
        kind = str(values.get('factory', '')).lower()
        category = {'infantrytype': 'infantry', 'unittype': 'units'}.get(kind)
        if category and str(values.get('naval', '')).lower() not in _YES:
            factories.setdefault(house, {}).setdefault(category, []).append(building)

    for raw in by_lower.get('structures', {}).values():
        fields = str(raw).split(',')
        if len(fields) >= 2:
            factory(fields[0].strip(), fields[1].strip())
    for house in hostile_houses:
        for key, raw in by_lower.get(house.lower(), {}).items():
            if str(key).isdigit():
                factory(house, str(raw).split(',')[0].strip())

    for house, classes in factories.items():
        record = records[house]
        country, family = record['country'], country_family(record)
        if country in player_countries or unsafe_country_houses(
            lines, country, hostile_houses, records=records,
        ):
            skipped.append(f'{house}: production country shared with non-hostile actors')
            continue
        heroes, bosses = special_picks(family, f'{identity}|{house}|production', 1)
        selected = list(heavy_pools.get(family, ())[:1])
        if level >= 1:
            selected += heroes[:1]
        if level >= 2 and bosses:
            selected += list(bosses[0])
        for source in selected:
            basis = 'DHANDL' if source == 'DHANDR' else source
            category = BUFF_TARGETS.get(basis, {}).get('category')
            if category not in classes or not available(source):
                continue
            source_team = ''
            trigger = None
            for team_id in by_lower.get('teamtypes', {}).values():
                values = _fold(by_lower.get(str(team_id).lower(), {}))
                if canonical_house_name(records, values.get('house')) != house:
                    continue
                if str(values.get('reinforce', '')).lower() in _YES:
                    continue
                if str(values.get('droppod', '')).lower() in _YES:
                    continue
                if str(values.get('isontransonly', '')).lower() in _YES:
                    continue
                if str(values.get('transportwaypoint', '-1')).strip() not in {'', '-1'}:
                    continue
                triggers = source_triggers(str(team_id))
                if str(values.get('autocreate', '')).lower() not in _YES and not triggers:
                    continue
                source_team, trigger = str(team_id), (triggers[0] if triggers else None)
                break
            if not source_team:
                skipped.append(f'{house}: no active factory production team template')
                continue
            new_team, actors = team(source_team, house, (source,), 'production', classes[category][0])
            if not new_team:
                continue
            if trigger:
                trigger_id, tokens = trigger
                tokens = list(tokens)
                tokens[0], tokens[1], tokens[2], tokens[14] = 'Enemy Powerhouses Production', new_team, country, '<none>'
                tokens[7:10] = ['5.000000', '1.000000', '10.000000']
                new_trigger = unique('MOREPR', f'{trigger_id}|{new_team}')
                rules.setdefault('AITriggerTypes', {})[new_trigger] = ','.join(tokens)
                rules.setdefault('AITriggerTypesEnable', {})[new_trigger] = 'yes'
            receipt(house, new_team, (source,), actors, 'production', source_team)
    return rules, applications, skipped
