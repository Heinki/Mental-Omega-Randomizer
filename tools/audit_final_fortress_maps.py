"""Audit configurations of the single Fortress map without launching a game.

Produces reviewable map variants, spawn files and a manifest for every native country
and difficulty. Baseline, helper-only and maximum-perk/Challenge loadouts cover
the separate country and AI routing paths. This does not edit player profiles,
source maps or game-root runtime files, and is not a gameplay simulation.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
from randomizer.core.paths import GAME_ROOT
from randomizer.final_fortress.challenges import load_ai_rules, maximum
from randomizer.final_fortress.config import DIFFICULTY_IDS, load_config
from randomizer.final_fortress.engine import build_map, spawn_data
from randomizer.final_fortress.perks import ranks
from randomizer.final_fortress.player_perks import coalition
from randomizer.final_fortress.planning import build_run_plan
from randomizer.maps.ini import all_section_value_maps_preserve, parse_action_groups
from randomizer.ui.cameos import ART_CACHE_PATH, extract_mix_files_sync, installed_rules_registry


def read_sections(data):
    return all_section_value_maps_preserve(data.decode('latin-1').splitlines())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def footprint(row, art):
    image = row.get('Image', '')
    entry = art.get(image.casefold(), {})
    foundation = row.get('Foundation', entry.get('Foundation', '1x1'))
    match = re.fullmatch(r'(\d+)[xX](\d+)', foundation)
    if match:
        return {(x, y) for x in range(int(match[1])) for y in range(int(match[2]))}
    require(foundation.lower() == 'custom', f'Unknown foundation {foundation} for {image}')
    cells = {tuple(map(int, value.split(','))) for key, value in entry.items()
             if re.fullmatch(r'Foundation\.\d+', key)}
    require(cells, f'Empty custom foundation for {image}')
    return cells


def audit_map(data, spawn, preloads, plan, rules, source, art, ai, terrain=None):
    rows = read_sections(data)
    effective = deepcopy(rules)
    for section, values in ai.items():
        effective.setdefault(section, {}).update(values)
    for section, values in rows.items():
        effective.setdefault(section, {}).update(values)
    ids = {section.casefold(): section for section in effective}

    # Packed map sections must stay byte-for-byte equivalent as INI values.
    for section in ('IsoMapPack5', 'OverlayPack', 'OverlayDataPack', 'Terrain'):
        require(rows.get(section) == source.get(section), f'Source terrain changed: {section}')
    countries = list(effective['Countries'].values())
    indices = sorted(int(key) for key in effective['Countries'])
    require(indices == list(range(len(indices))), 'Country indices are not contiguous')
    actors = ['FFENEMY1', 'FFENEMY2', 'FFENEMY3']
    if 'FFPLAYER' in countries:
        actors += ['FFPLAYER', *[f'FFALLY{i + 1}' for i in range(len(plan['allied_countries']))]]
    require(all(actor in preloads['rules'] for actor in actors), 'Missing preloaded country')

    registries = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes', 'SuperWeaponTypes')
    for registry in registries:
        require(all(value.casefold() in ids for value in effective[registry].values()),
                f'Unresolved {registry} definition')
    technos = {unit for registry in registries[:4] for unit in effective[registry].values()}
    for force in rows.get('TaskForces', {}).values():
        for key, value in effective[force].items():
            if key.isdigit():
                count, unit = value.split(',')
                require(int(count) > 0 and unit in technos, f'Bad task force {force}: {value}')
    for team in rows.get('TeamTypes', {}).values():
        row = effective[team]
        for field in ('TaskForce', 'Script'):
            require(row[field].casefold() in ids, f'Unresolved {team}.{field}')
        if row.get('Name', '').startswith(('Camp ', 'Final Fortress wave ', 'Final Fortress AI controller')):
            require(row['House'] in actors[:3], f'Unresolved private enemy team owner: {team}')
        if row.get('Name', '').startswith(('Camp ', 'Final Fortress wave ', 'Fortress helper starting army ',
                                           'Fortress friendly arrival ')):
            require(row.get('OnlyTargetHouseEnemy') == 'no',
                    f'Trigger-created team restricts acquisition to a single primary enemy: {team}')
    for key, value in rows.get('Actions', {}).items():
        require(len((key + '=' + value).encode('latin-1')) <= 511, f'Action line too long: {key}')
        count, actions = parse_action_groups(value)
        require(count == len(actions), f'Malformed action list: {key}')
        require(len(value.split(',')) == 1 + 8*count, f'Embedded comma or malformed native action fields: {key}')
        for action in actions:
            if action[0] in ('4', '5', '7'):
                require(action[2] in rows['TeamTypes'].values(), f'Unknown action team: {action[2]}')
    for value in rows.get('AITriggerTypes', {}).values():
        fields = value.split(',')
        if fields[2] not in actors:
            continue
        for index in (1, 14):
            require(fields[index].lower() in ('<none>', 'none', '0', '') or fields[index] in rows['TeamTypes'].values(),
                    f'Unresolved private AI team: {fields[index]}')
    require(len(rows.get('VariableNames', {})) <= 100, 'Native local-variable capacity exceeded')
    countdown = [key for key, value in rows['Triggers'].items()
                 if value.split(',')[2] == 'Final Fortress countdown']
    require(len(countdown) == 1, 'Missing or duplicated survival countdown')
    _, timer_actions = parse_action_groups(rows['Actions'][countdown[0]])
    require([action[0] for action in timer_actions] == ['27', '23', '103'],
            'Timer Set/Start must precede Timer Text: setting the duration clears its caption')
    require(timer_actions[0][2] == str(plan['survival_seconds']), 'Wrong survival countdown duration')
    require(timer_actions[2][1:3] == ['4', 'NOSTR:Until Victory'], 'Missing survival timer caption')
    require(rows['Events'][countdown[0]] == '1,13,0,0', 'Survival countdown starts late')
    audit_arsenal(rows, effective, plan, rules, preloads, terrain)
    audit_utilities_and_challenges(rows, effective, plan, rules, preloads)
    audit_survival_fixes(rows, effective, plan, rules, preloads, terrain)
    audit_arrival_fixes(rows, effective, plan, rules, preloads, terrain)
    audit_wave_pools(rows, effective, plan, rules, preloads, spawn, terrain)
    audit_wave_clock(rows, effective, plan, preloads)

    # Every purchased support unlock must be registered and granted to each
    # friendly house, including ranks beyond the proxy's two building slots.
    powers = plan['effects']['support_powers']
    from randomizer.final_fortress.powers import power_rewards
    blueprints = ({entry['superweapon']: entry for entry in power_rewards(plan, rules)}
                  if plan.get('plan_version', 1) >= 9 else {})
    if plan['effects'].get('power_upgrade_stacks') and not powers:
        clock = rows.get('FFWaveClock', {}).get('Power')
        require({k:v for k,v in rows.get('SuperWeaponTypes', {}).items() if v != clock}
                == source.get('SuperWeaponTypes', {}),
                'Power upgrades granted an unpurchased power')
    registered_powers = list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
    for actor, country, _ in coalition(plan):
        if actor in effective:
            for suffix in ('Infantry', 'Units', 'Aircraft', 'Buildings', 'Defenses'):
                field = f'BuildTime{suffix}Mult'
                expected = float(rules[country].get(field, '1')) * (
                    1 - plan['effects'].get('production_percent', 0) / 100)
                require(abs(float(effective[actor].get(field, '1')) - expected) < 1e-10,
                        f'Incorrect production bonus for {actor}.{field}')
        if not powers:
            continue
        grants = [key for key, value in rows['Triggers'].items()
                  if value.split(',')[:3] == [actor, '<none>', 'Fortress perk powers ' + actor]]
        require(len(grants) == 1, f'Missing support power grant for {actor}')
        _, actions = parse_action_groups(rows['Actions'][grants[0]])
        require(len(actions) == len(powers), f'Wrong support power count for {actor}')
        for original, action in zip(powers, actions):
            blueprint = blueprints.get(original, {})
            native = {**rules[original], **blueprint.get('superweapon_rules', {})}
            require(action[0] == '34', f'Non-repeatable support power grant for {actor}')
            power = effective[registered_powers[int(action[2])]]
            require(power['Name'] == 'Fortress ' + rules[original].get('Name', original),
                    f'Wrong cloned support unlock for {actor}: {original}')
            for field in ('Type', 'UIName', 'RechargeTime', 'Money.Amount', 'SidebarPCX'):
                require(power.get(field) == native.get(field), f'Changed native {original}.{field}')
            relocated = {'SW.RequiredHouses', 'SW.ForbiddenHouses', 'SW.AllowPlayer', 'SW.AllowAI',
                         'SW.PostDependent', 'ParaDrop.Types', 'Deliver.Types', 'DropPod.Types',
                         'WeaponType', 'Nuke.Payload', 'SW.Warhead', 'SpyPlane.Type',
                         'Dominator.FirstAnim'}
            for field, expected in blueprint.get('superweapon_rules', {}).items():
                if field not in relocated:
                    require(power.get(field) == (str(expected) if expected is not None else None),
                            f'Power upgrade not materialized: {original}.{field}')
            for field in ('WeaponType', 'Nuke.Payload', 'SW.Warhead', 'SpyPlane.Type', 'SW.PostDependent'):
                value = str(power.get(field, '')).strip()
                if value.lower() not in ('', 'none', '<none>'):
                    require(value.casefold() in ids, f'Unresolved power dependency: {original}.{field}')
            for field in ('SW.AuxBuildings', 'SW.NegBuildings', 'SW.ForbiddenHouses', 'SW.Designators'):
                require(str(power.get(field, '')).lower() in ('', 'none', '<none>'),
                        f'Unavailable standalone power: {original}.{field}')
            if plan.get('plan_version', 1) >= 9:
                require(power.get('SW.RequiredHouses') == actor, f'Power escapes friendly house: {original}')
                require(power.get('SW.AllowAI') == ('no' if actor == 'FFPLAYER' else 'yes'),
                        f'Wrong helper power access for {actor}')
                require(any(effective[value.split(',')[1]].get('SuperWeapon')
                            == registered_powers[int(action[2])]
                            for value in rows['Structures'].values()),
                        f'Power has no owned launch provider: {original}')
            for field in ('Deliver.Types', 'ParaDrop.Types'):
                require(all(kind.strip() in technos for kind in power.get(field, '').split(',') if kind.strip()),
                        f'Unresolved support payload for {country}: {original}')

    for animation in rows.get('MORNanofiberAnimations', {}):
        entry = effective[animation]
        mutation_types = effective['General']['AnimToInfantry'].split(',')
        target = mutation_types[int(entry['MakeInfantry'])]
        require(target in effective['InfantryTypes'].values(), 'Unregistered private Nanofiber target')
        require(effective[target].get('TechLevel') == '-1', 'Private Nanofiber form became buildable')

    # Installed art supplies foundations. Include source structures and reserve
    # every active MCV's deployment rectangle when checking added buildings.
    occupied = {}
    native_structures = source.get('Structures', {})
    for key, value in rows.get('Structures', {}).items():
        fields = value.split(',')
        original = fields[1]
        row = dict(effective[original])
        row.setdefault('Image', original)
        x, y = map(int, fields[3:5])
        cells = {(x + dx, y + dy) for dx, dy in footprint(row, art)}
        added = key not in native_structures
        if added and terrain is not None:
            require(terrain.bounds.contains(cells, heights=terrain.heights),
                    f'Foundation outside playable LocalSize at {(x, y)}: {original}')
        if added and terrain is not None and row.get('IsPassable', 'no').lower() != 'yes':
            require(terrain.clear(cells), f'Unsafe building terrain at {(x, y)}: {original}')
        for cell in cells:
            require(not added or cell not in occupied, f'Building overlap at {cell}: {original}')
            occupied[cell] = original
    points = rows['Waypoints']
    starts = [plan['map']['player_waypoint'], *plan['map']['enemy_waypoints'], *plan['allied_waypoints']]
    for waypoint in starts:
        cell = int(points[str(waypoint)])
        x, y = cell % 1000, cell // 1000
        for dx in range(-2, 2):
            for dy in range(-1, 2):
                require((x + dx, y + dy) not in occupied, f'MCV deployment overlap: waypoint {waypoint}')
    for category in ('Infantry', 'Units'):
        for key, value in rows.get(category, {}).items():
            if key in source.get(category, {}):
                continue
            fields = value.split(',')
            x, y = map(int, fields[3:5])
            pad = rows.get('FFReinforcementPads', {}).get('Type')
            require((x, y) not in occupied or occupied[(x, y)] == pad,
                    f'Starting unit overlaps a building at {(x, y)}')
            require(fields[0] == 'Neutral', 'Private starting objects must use native ownership transfers')
            if terrain is not None:
                require(terrain.clear({(x, y)}), f'Unit outside playable clear terrain at {(x, y)}')

    for actor, _, waypoint in coalition(plan):
        layout = plan['map'].get('perk_layouts', {}).get(str(waypoint))
        if not layout:
            continue
        staging = layout['units']
        army = [value.split(',') for category in ('Infantry', 'Units')
                for key, value in rows.get(category, {}).items() if key not in source.get(category, {})
                and staging['x'] <= int(value.split(',')[3]) < staging['x'] + 5
                and staging['y'] <= int(value.split(',')[4]) < staging['y'] + 3]
        require(len(army) == sum(unit['count'] for unit in plan['effects']['starting_units']),
                f'Wrong starting army count for {actor}')
        require(all(int(unit[9] if unit[1] in effective['InfantryTypes'].values() else unit[8])
                    == plan['effects']['veterancy'] * (100 if plan.get('plan_version', 1) >= 13 else 1) for unit in army),
                f'Wrong starting army veterancy for {actor}')

    spawn_rows = read_sections(spawn)
    friendly_slots = [0, *range(4, 4 + len(plan['allied_countries']))]
    for slot in friendly_slots:
        allies = set(map(int, spawn_rows[f'Multi{slot + 1}_Alliances'].values()))
        require(allies == set(friendly_slots) - {slot},
                'Coalition alliances do not protect helpers/player during unrestricted hostile targeting')
    require(int(spawn_rows['Settings']['AIPlayers']) == 3 + len(plan['allied_countries']), 'Wrong AI count')
    require(spawn_rows['Settings']['MapSHA1'] == hashlib.sha1(data).hexdigest(), 'Wrong scenario digest')
    for value in [spawn_rows['Settings']['Side'], *spawn_rows['HouseCountries'].values()]:
        require(int(value) in indices, f'Unresolved spawner country {value}')
    if plan.get('plan_version', 1) >= 7:
        buildings = [*plan['effects']['starting_buildings'], *plan['effects']['defense_types'],
                     *plan['effects'].get('starting_power_buildings', [])]
    if plan['effects'].get('starting_power_buildings'):
        require(sum(int(rules[kind].get('Power', '0')) for kind in buildings) >= 0,
                'Granted buildings start with insufficient power')
    if plan.get('plan_version', 1) >= 7:
        required_transfers = (1 + sum(unit['count'] for unit in plan['effects']['starting_units'])
                              + sum(unit['count'] for unit in plan['effects']['starting_harvesters'])
                              + len(buildings) + len(plan['effects']['starting_defenses'])
                              + (len(powers) if plan.get('plan_version', 1) >= 9 else int(bool(powers))))
        if rows.get('FFWaveClock'):
            required_transfers += 1
        require(plan['initial_transfer_kills'] == required_transfers, 'Starting power transfers counted as combat kills')
    return {registry: len(set(effective[registry].values())) for registry in registries}


def audit_arsenal(rows, effective, plan, rules, preloads, terrain):
    """Review generated production gates, arrival identities and capacity events."""
    from randomizer.final_fortress.arsenal import FACTORIES, reviewed_rules
    from randomizer.final_fortress.engine import _waypoint

    access = plan['effects'].get('special_access', [])
    mapping = rows.get('FFSpecialAccess', {})
    require(set(mapping) == set(access), 'Special access does not match purchased rank')
    reviewed, _ = reviewed_rules(rules, access)
    friends = {actor for actor, _, _ in coalition(plan)}
    for original, alias in mapping.items():
        row = effective[alias]
        require(alias in preloads['rules'], f'Special unit missing early preload: {original}')
        require(row['TechLevel'] == '1', f'Special access is unbuildable: {original}')
        require(set(row['Owner'].split(',')) == friends
                and set(row['RequiredHouses'].split(',')) == friends,
                f'Special access leaked to native/enemy countries: {original}')
        require(row['Prerequisite'] == FACTORIES[rules[plan['player_country']]['Side']],
                f'Special access retained a mission prerequisite: {original}')
        require(not any(key.startswith(('Prerequisite.', 'FactoryOwners')) for key in row),
                f'Special access retained a hidden production gate: {original}')
        native_limit = reviewed[original].get('BuildLimit')
        from randomizer.final_fortress.utilities import supported_pairs
        expected_limit = str(int(native_limit) + plan['effects'].get('unique_limit_stacks', 0)) if (
            native_limit and int(native_limit) > 0 and (original, 'build_limit') in supported_pairs()) else native_limit
        require(row.get('BuildLimit') == expected_limit,
                f'Special unit lost its unique limit: {original}')
        require(not any('MORP' in value for value in row.values()), f'Unresolved roster alias: {original}')
        for field, value in row.items():
            if re.fullmatch(r'(?:Elite)?(?:Primary|Secondary|Weapon\d+)', field):
                require(value.lower() in ('none', '') or value in effective,
                        f'Unresolved special unit weapon: {original}.{field}')
        for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass'):
            value = row.get(field, '')
            require(value.lower() in ('none', '') or value in effective,
                    f'Unresolved special conversion: {original}.{field}')
    schedule = plan.get('reinforcement_schedule', [])
    if not schedule:
        return
    effect = plan['effects']['reinforcements']
    if plan.get('plan_version', 1) >= 17:
        audit_friendly_pools(rows, effective, plan, finished_name='Final Fortress finished')
        return
    triggers = {value.split(',')[2]: key for key, value in rows['Triggers'].items()}
    flags = {value.rsplit(',', 1)[0]: int(key) for key, value in rows['VariableNames'].items()}
    all_types = set()
    counts = []
    for index, arrival in enumerate(schedule, 1):
        prefix = f'Friendly arrival {index}'
        spawn = triggers[prefix + ' spawn']
        _, actions = parse_action_groups(rows['Actions'][spawn])
        teams = [effective[action[2]] for action in actions if action[0] == '7']
        require(len(teams) == len(coalition(plan)), 'Reinforcement arrival lost a friendly house')
        count = 0
        identities = set()
        for group, team in zip(arrival['groups'], teams):
            require(team['House'] == group['owner'], 'Wrong reinforcement owner')
            require(team['VeteranLevel'] == str(effect.get('veterancy', 0) + 1),
                    'Wrong Rookie/Veteran/Elite reinforcement rank')
            helper = plan.get('plan_version', 1) >= 14 and group['owner'] != 'FFPLAYER'
            require(effective[team['Script']]['0'] == ('0,1' if helper else '11,5'),
                    'Friendly arrival has the wrong human/helper orders')
            require(team['AreTeamMembersRecruitable'] == ('no' if helper else 'yes'),
                    'Friendly arrival can be stranded by native AI recruitment')
            slot = next(i for i, (actor, _, _) in enumerate(coalition(plan)) if actor == group['owner'])
            require(team['Waypoint'] == _waypoint(10 + slot), 'Arrival uses occupied MCV waypoint')
            position = plan['map']['perk_layouts'][str(group['waypoint'])]['units']
            require(int(rows['Waypoints'][str(10 + slot)]) == position['y'] * 1000 + position['x'],
                    'Wrong reinforcement staging coordinates')
            if terrain is not None:
                require(terrain.clear({(position['x'], position['y'])}), 'Unsafe reinforcement staging terrain')
            force = effective[team['TaskForce']]
            units = [value.split(',') for key, value in force.items() if key.isdigit()]
            require([int(unit[0]) for unit in units] == [unit['count'] for unit in group['units']],
                    'Wrong reinforcement roster counts')
            for amount, alias in units:
                identities.add(alias)
                require(effective[alias]['TechLevel'] == '-1' and effective[alias]['BuildLimit'] == '0',
                        'A reinforcement identity became producible')
                count += int(amount)
        require(not identities & all_types, 'Different arrivals share cap-tracking identities')
        all_types.update(identities)
        complete = rows['Events'][triggers[prefix + ' complete']]
        require(all(alias in complete.split(',') for alias in identities), 'Untracked reinforcement identity')
        interval = rows['Events'][triggers[prefix + ' interval']]
        delay = effect['first_seconds'] if index == 1 else effect['interval_seconds']
        require(interval == f'1,13,0,{delay}', 'Wrong friendly reinforcement interval')
        require(rows['Triggers'][triggers[prefix + ' interval']].split(',')[3] == str(int(index > 1)),
                'Friendly timer starts before preceding arrival')
        if index < len(schedule):
            require(any(action[0] == '53' and action[2] == triggers[f'Friendly arrival {index + 1} interval']
                        for action in actions), 'Next friendly timer is not chained to actual admission')
        capacities = [key for key, value in rows['Triggers'].items() if value.split(',')[2] == prefix + ' capacity']
        require(capacities, 'Friendly arrival has no capacity gate')
        for key in capacities:
            tokens = rows['Events'][key].split(',')[1:]
            events = [tuple(map(int, tokens[i:i + 3])) for i in range(0, len(tokens), 3)]
            require((36, 0, flags[prefix + ' ready']) in events
                    and (37, 0, flags[prefix + ' spawned']) in events
                    and (37, 0, flags['Final Fortress finished']) in events,
                    'Friendly admission lacks time, uniqueness or finish gate')
            released = sum(prior_count for prior, prior_count in enumerate(counts, 1)
                           if (36, 0, flags[f'Friendly arrival {prior} cleared']) in events)
            require(sum(counts) - released + count <= effect['max_active_units'],
                    'Friendly capacity gate can exceed the living-unit cap')
        counts.append(count)


def audit_utilities_and_challenges(rows, effective, plan, rules, preloads):
    """Inspect actual private utility types, enemy powers and Powerhouse teams."""
    from randomizer.final_fortress.enemy_powers import rewards_for
    from randomizer.final_fortress.utilities import supported_pairs
    from randomizer.config.tuning import stacked_self_heal_amount, stacking_amount

    effects = plan['effects']
    pairs = supported_pairs()
    buildings = set(rules['BuildingTypes'].values())
    changed = dict(healing_stacks=0, recon_stacks=0, unique_limit_stacks=0, income_stacks=0)
    for original, alias in rows.get('FFPlayerTypes', {}).items():
        row, base = effective[alias], rules[original]
        require(alias in preloads['rules'], f'Private utility type not preloaded: {original}')
        mobile_or_defense = original not in buildings or base.get('IsBaseDefense', 'no').lower() == 'yes'
        if effects.get('healing_stacks') and mobile_or_defense and any(
                (original, kind) in pairs for kind in ('self_healing', 'self_healing_rate')):
            require(row.get('SelfHealing') == 'yes' and row.get('SelfHealing.Max') == '100%',
                    f'Automatic healing not active for rookie {original}')
            require(int(row['SelfHealing.Amount']) >= stacked_self_heal_amount(
                row['Strength'], effects['healing_stacks']), f'Healing amount ignores actual HP: {original}')
            require(float(row['SelfHealing.Rate']) > 0, f'Nonpositive healing interval: {original}')
            changed['healing_stacks'] += 1
        if effects.get('recon_stacks') and mobile_or_defense:
            if (original, 'sight') in pairs:
                require(float(row['Sight']) >= float(base.get('Sight', '0')) + effects['recon_stacks'],
                        f'Recon sight missing: {original}')
                changed['recon_stacks'] += 1
            if (original, 'sensors') in pairs:
                require(row.get('Sensors') == 'yes' and float(row['SensorsSight']) >= float(row['Sight']) + 2,
                        f'Recon cloak sensors missing: {original}')
        if effects.get('unique_limit_stacks') and (original, 'build_limit') in pairs and int(row.get('BuildLimit', '0')) > 0:
            require(int(row['BuildLimit']) == int(base['BuildLimit']) + effects['unique_limit_stacks'],
                    f'Wrong unique-unit capacity: {original}')
            changed['unique_limit_stacks'] += 1
        if effects.get('income_stacks') and (original, 'income') in pairs:
            expected = float(base['ProduceCashAmount']) + stacking_amount('income', effects['income_stacks'])
            require(float(row['ProduceCashAmount']) == expected, f'Wrong special-building income: {original}')
            require(row.get('ProduceCashDelay') == base.get('ProduceCashDelay'), 'Income perk changed payout interval')
            require(row.get('Prerequisite') == base.get('Prerequisite'), 'Income perk granted free building access')
            changed['income_stacks'] += 1
    for field, count in changed.items():
        require(not effects.get(field) or count > 0, f'Enabled utility perk affected no private types: {field}')
    # Gate/list additions are allowed on native identities; perk stats and
    # challenge power behavior must remain confined to private definitions.
    for original in (
            set(rules['InfantryTypes'].values()) | set(rules['VehicleTypes'].values())
            | set(rules['AircraftTypes'].values()) | buildings):
        for field in ('Strength', 'Sight', 'Sensors', 'SensorsSight', 'SelfHealing', 'SelfHealing.Amount',
                      'SelfHealing.Rate', 'BuildLimit', 'ProduceCashAmount', 'ProduceCashDelay'):
            require(effective[original].get(field) == rules[original].get(field),
                    f'Perk leaked onto native type: {original}.{field}')

    registered = list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
    expected_powers = {}
    for index, country in enumerate(plan['enemy_countries']):
        if plan.get('plan_version', 1) < 12:
            break
        actor = f'FFENEMY{index + 1}'
        rewards = rewards_for(plan, country)
        expected_powers[actor] = {entry['superweapon']: entry for entry in rewards}
        grants = [key for key, value in rows['Triggers'].items()
                  if value.split(',')[:3] == [actor, '<none>', 'Fortress enemy powers ' + actor]]
        require(len(grants) == int(bool(rewards)), f'Wrong enemy power grant count: {actor}')
        if not grants:
            continue
        _, actions = parse_action_groups(rows['Actions'][grants[0]])
        require(len(actions) == len(rewards), 'Enemy power grant action count differs from unlocks')
        for action in actions:
            require(action[0] == '34', 'Enemy power did not use repeatable native grant')
            alias = registered[int(action[2])]
            owner, original = rows['FFEnemyPowers'][alias].split(',')
            require(owner == actor and original in expected_powers[actor], 'Enemy faction received another power')
            power = effective[alias]
            require(alias in preloads['rules'], 'Enemy power not preloaded')
            require(power['SW.RequiredHouses'] == actor and power['SW.AllowPlayer'] == 'no'
                    and power['SW.AllowAI'] == 'yes', 'Enemy power leaked to human/helper')
            require(power['SW.InitialReady'] == 'no' and power['SW.UseAITargeting'] == 'yes',
                    'Enemy power lacks initial charge or automatic targeting')
            reward = expected_powers[actor][original]
            expected = reward['superweapon_rules']
            base_recharge = expected.get('RechargeTime', rules[original]['RechargeTime'])
            require(float(power['RechargeTime']) == float(base_recharge) * reward['superweapon_recharge_multiplier'],
                    'Enemy power recharge differs from frozen challenge settings')
            require(power['SW.Shots'] == expected['SW.Shots'], 'Wrong enemy power launch budget')
            for field in ('Deliver.Types', 'ParaDrop.Types', 'DropPod.Types'):
                for kind in power.get(field, '').split(','):
                    require(not kind or kind in effective, f'Unresolved enemy payload: {kind}')
            require(any(effective[value.split(',')[1]].get('SuperWeapon') == alias
                        for value in rows['Structures'].values()), 'Enemy power has no real launch provider')
    require(len(rows.get('FFEnemyPowers', {})) == sum(map(len, expected_powers.values())),
            'Unexpected hostile power without a selected Challenge')
    for original in rules['SuperWeaponTypes'].values():
        require(effective[original] == rules[original], f'Native power changed by enemy Challenge: {original}')
    powerhouse = any(entry.get('enemy_effect_id') == 'powerhouse' for entry in plan.get('challenges', []))
    if not powerhouse:
        return
    for index, wave in enumerate(plan['wave_schedule'], 1):
        count = 0
        for group in wave['groups']:
            name = f'Final Fortress wave {index} {group["house"]}'
            if plan.get('plan_version', 1) >= 16:
                first_slot = next(key for key, value in rows['FFWavePools'].items()
                                  if value.split(',')[0] == f'FFENEMY{plan["map"]["enemy_waypoints"].index(group["waypoint"]) + 1}')
                teams = [effective[key] for key in rows['TeamTypes'].values()
                         if effective[key].get('Name', '').startswith(name + ' batch ')
                         and effective[key]['Name'].endswith(' slot ' + first_slot)]
            else:
                teams = [effective[key] for key in rows['TeamTypes'].values() if effective[key].get('Name') == name]
            require(teams and all(t['VeteranLevel'] == '2' for t in teams), 'Powerhouse team is not veteran')
            actual = [value.split(',') for team in teams for key, value in effective[team['TaskForce']].items()
                      if key.isdigit()]
            require(sum(int(value[0]) for value in actual) == sum(unit['count'] for unit in group['units']),
                    'Powerhouse actual counts differ from frozen wave budget')
            images = {effective[value[1]].get('Image') for value in actual}
            require(all(rules[kind].get('Image', kind) in images for kind in group['powerhouse_types']),
                    'Powerhouse wave lacks its selected heavy identities')
            count += sum(int(value[0]) for value in actual)
        require(count <= min(plan['max_wave_units'], plan['wave_pressure']['max_active_units']),
                'Powerhouse exceeded the shared scripted-wave cap')


def audit_survival_fixes(rows, effective, plan, rules, preloads, terrain):
    if plan.get('plan_version', 1) < 13:
        return
    from randomizer.final_fortress.enemy_bases import IMMUTABLE
    from randomizer.final_fortress.player_perks import _eligible
    enemies = {f'FFENEMY{i + 1}' for i in range(3)}
    for original, alias in rows.get('FFEnemyBuildings', {}).items():
        require(alias in preloads['rules'], f'Enemy building missing early preload: {original}')
        require(all(effective[alias].get(key) == value for key, value in IMMUTABLE.items()),
                f'Enemy building can be destroyed/captured: {original}')
        if plan.get('plan_version', 1) >= 16:
            require(effective[alias].get('LegalTarget') == 'no', 'Immortal building can absorb helper attacks')
        require(set(effective[alias]['RequiredHouses'].split(',')) <= enemies,
                f'Protected enemy building leaked to player: {original}')
        require(effective[original].get('Immune') == rules[original].get('Immune'),
                f'Enemy immunity leaked onto native building: {original}')
        for field, value in rules['AI'].items():
            if original in value.split(','):
                require(alias in effective['AI'][field].split(','),
                        f'AI cannot request protected {original} through {field}')
    for original, alias in rows.get('FFEnemyBaseUnits', {}).items():
        yard = rules.get(rules[original].get('DeploysInto'), {})
        if yard.get('ConstructionYard', 'no').lower() != 'yes':
            require(effective[alias].get('Immune') == rules[original].get('Immune'),
                    f'Ordinary enemy docking/deploying unit became immortal: {original}')
    for actor, country in zip(sorted(enemies), plan['enemy_countries']):
        require(effective[actor].get('StartInMultiplayer.WithConst') == 'yes',
                'Enemy does not start with a protected construction yard')
        starting_yard = next(kind for kind in effective['AI']['BuildConst'].split(',')
                             if _eligible(effective[kind], actor))
        require(starting_yard in rows['FFEnemyBuildings'].values() and effective[starting_yard]['Immune'] == 'yes',
                'Enemy construction-yard start can select a destructible native yard')
        native = next(kind for kind in rules['VehicleTypes'].values() if _eligible(rules[kind], country)
                      and rules.get(rules[kind].get('DeploysInto'), {}).get('ConstructionYard', 'no').lower() == 'yes')
        alias = rows['FFEnemyBaseUnits'][native]
        require(effective[alias]['Immune'] == 'yes' and actor in effective[alias]['RequiredHouses'].split(','),
                'Enemy MCV is destructible or belongs to the wrong country')
        yard = effective[alias]['DeploysInto']
        require(effective[yard]['Immune'] == 'yes' and yard in rows['FFEnemyBuildings'].values(),
                'Enemy MCV deploys into a destructible yard')
        for power in effective[actor].get('AI.PowerPlants', '').split(','):
            if power:
                require(power in rows['FFEnemyBuildings'].values(), 'Enemy AI requests a native unprotected power plant')
    fortifications = set(rows.get('FFEnemyFortifications', {}).values())
    placed = [value for value in rows['Structures'].values() if value.split(',')[1] in fortifications]
    expected = sum(len(values) for values in plan['map']['enemy_defenses']['layouts'].values())
    require(len(placed) == expected, 'Missing enemy starting fortifications')
    for alias in fortifications:
        require(effective[alias]['Immune'] == 'yes' and effective[alias]['Powered'] == 'no'
                and effective[alias]['Power'] == '0' and effective[alias]['TechLevel'] == '-1',
                'Fixed enemy fortification is destructible, powered down or buildable')
        if plan.get('plan_version', 1) >= 16:
            require(effective[alias].get('LegalTarget') == 'no', 'Immortal defense can absorb helper attacks')
    actors = [('FFPLAYER', plan['player_country']),
              *[(f'FFALLY{i + 1}', country) for i, country in enumerate(plan['allied_countries'])],
              *zip(sorted(enemies), plan['enemy_countries'])]
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes'):
        for original in rules[category].values():
            row = effective[original]
            required = set(row.get('RequiredHouses', '').split(','))
            require(required, f'Native unit has no concrete country gate: {original}')
            for actor, country in actors:
                if not _eligible(rules[original], country):
                    require(actor not in required, f'Foreign unit leaked into {actor} production: {original}')
    for actor, country in actors:
        if country == 'Europeans':
            require(actor not in effective['VIRUS']['RequiredHouses'].split(','), 'Euro Alliance can still produce Virus')
    if terrain is not None:
        locations = []
        for camp in plan['map']['camps']:
            from randomizer.final_fortress.camps import guard_positions
            p = camp['position']
            count = sum(unit['count'] for unit in camp['guards'])
            cells = {(p['x'], p['y']), *((v['x'], v['y']) for v in guard_positions(camp))}
            require(terrain.clear(cells), f'Camp guards/crate are inaccessible or outside bounds: {camp["id"]}')
            locations.append(terrain.bounds.project(p['x'], p['y'], terrain.heights[(p['x'], p['y'])]))
            garrison = next(effective[key] for key in rows['TeamTypes'].values()
                            if effective[key].get('Name') == 'Camp ' + camp['id'] + ' garrison')
            force = effective[garrison['TaskForce']]
            kinds = {value.split(',')[1] for key, value in force.items() if key.isdigit()}
            guards = [value.split(',') for category in ('Infantry', 'Units')
                      for value in rows.get(category, {}).values() if value.split(',')[1] in kinds]
            require(len(guards) == count and all(guard[6] == 'Sleep' for guard in guards),
                    'Camp garrison is missing or can wander before ownership/recruitment')
            require({(int(g[3]),int(g[4])) for g in guards}
                    == {(v['x'],v['y']) for v in guard_positions(camp)}, 'Camp ignores reviewed guard positions')
            require(garrison['AreTeamMembersRecruitable'] == 'no', 'Normal enemy AI can recruit the camp garrison')
            claim = next(key for key, value in rows['Triggers'].items()
                         if value.split(',')[2] == 'Camp ' + camp['id'] + ' claim')
            require(f'1,0,{4475 + plan["map"]["player_waypoint"]}' in rows['Events'][claim],
                    'Camp reward is not restricted to the human start house')
            tag = rows['CellTags'][str(p['y'] * 1000 + p['x'])]
            require(rows['Tags'][tag].split(',')[2] == claim, 'Camp crate cell is not connected to reward claim')
            if plan.get('plan_version',1) >= 18:
                balance=plan['camp_balance']
                require(count == min(balance['guards_by_difficulty'][plan['difficulty']]*plan['wave_multiplier'],
                                     balance['max_guards_per_camp'],balance['max_total_guards']//len(plan['map']['camps'])),
                        'Camp population ignores difficulty, multiplier or shared limits')
                if plan.get('plan_version', 1) >= 19:
                    require(camp['guard_country'] in SIDE_COUNTRIES, 'Camp uses an unknown faction roster')
                else:
                    require(camp['guard_country'] == plan['enemy_countries'][camp['enemy_index']], 'Camp uses foreign faction guards')
                require(camp['special_unit'] is None or any(u['type']==camp['special_unit'] for u in camp['guards']),
                        'Camp lost its selected special unit')
                cleared = next(key for key,value in rows['Triggers'].items()
                               if value.split(',')[2] == 'Camp '+camp['id']+' cleared')
                clear_actions=parse_action_groups(rows['Actions'][cleared])[1]
                clear_markers=[effective[a[2]]['Name'] for a in clear_actions if a[0]=='4']
                require(len(clear_markers)==1 and clear_markers[0].startswith('MFF_'), 'Camp clear has no durable Gem receipt')
                require(plan['gem_rewards']['camp_clear:'+camp['id']]==camp['gems']
                        and plan['gem_rewards']['camp:'+camp['id']]==0, 'Camp Gems still require crate collection')
                require(any(a[0]=='108' for a in clear_actions), 'Cleared camp has no random reward crate')
        if plan.get('plan_version', 1) >= 19:
            families = [SIDE_FAMILIES[SIDE_COUNTRIES.index(camp['guard_country'])] for camp in plan['map']['camps']]
            require(len(set(families[:4])) == 4 and max(families.count(family) for family in set(families)) <= 2,
                    'Camp roster selection omits or overrepresents a faction')
        require(len(locations) == 6 and max(x for x, y in locations) - min(x for x, y in locations)
                > .65 * terrain.bounds.width_local
                and max(y for x, y in locations) - min(y for x, y in locations) > .6 * terrain.bounds.height_local,
                'Camps do not span the playable map')


def audit_arrival_fixes(rows, effective, plan, rules, preloads, terrain):
    """Inspect production shortcuts, reserved ground and explicit helper orders."""
    if plan.get('plan_version', 1) < 14:
        return
    if plan.get('plan_version', 1) >= 15:
        from math import hypot
        for actor, _, waypoint in coalition(plan):
            cell = int(rows['Waypoints'][str(waypoint)])
            center = (cell % 1000, cell // 1000)
            layout = plan['map']['perk_layouts'][str(waypoint)]
            require(all(hypot(p['x'] - center[0], p['y'] - center[1]) >= 20
                        for p in layout['defenses']), f'Defense still occupies the central base: {actor}')
            if actor == 'FFPLAYER':
                require(all(p['x'] >= center[0] + 16 and center[1] - 10 <= p['y'] <= center[1] + 34
                            for p in layout['defenses']), 'Human defenses left the marked outer approach arc')
    for registry in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        for kind in effective[registry].values():
            row = effective[kind]
            for index in range(1, int(row.get('Prerequisite.Lists', '0')) + 1):
                native = rules.get(kind, {})
                if not native.get(f'Prerequisite.List{index}'):
                    require(row.get(f'Prerequisite.List{index}'),
                            f'Empty generated alternative unlocks production without prerequisites: {kind}')
            if kind in rules:
                require(row.get('Prerequisite.List0') == rules[kind].get('Prerequisite.List0'),
                        f'Building equivalent erased native prerequisites: {kind}')
            if int(row.get('BuildLimit', '-1')) == 0:
                continue
            require(row.get('PrerequisiteOverride', '').lower() in ('', 'none'),
                    f'Production shortcut bypasses private country/tech gates: {kind}')
    # Every authored shortcut remains an ordinary alternative list on its
    # source type and any friendly production copy. These lists do not bypass
    # the native original's ForbiddenHouses when both Harriers share artwork.
    for original in rules['AircraftTypes'].values():
        shortcut = rules[original].get('PrerequisiteOverride', '')
        if not shortcut:
            continue
        for kind in {original, rows.get('FFPlayerTypes', {}).get(original, original)}:
            row = effective[kind]
            alternatives = {row.get(f'Prerequisite.List{i}', '')
                            for i in range(1, int(row.get('Prerequisite.Lists', '0')) + 1)}
            require(set(shortcut.split(',')) <= alternatives, f'Lost aircraft shortcut: {kind}')
            require(preloads['rules'].get(kind, {}).get('PrerequisiteOverride') == 'none',
                    f'Aircraft shortcut bypass survives early preload: {kind}')
    harrier = rows.get('FFPlayerTypes', {}).get('ORCA')
    if harrier:
        require('FFPLAYER' in effective['ORCA']['ForbiddenHouses'].split(',')
                and 'FFPLAYER' not in effective[harrier]['ForbiddenHouses'].split(','),
                'Native and private Harrier can share a production slot')

    pads = rows.get('FFReinforcementPads', {})
    if plan.get('reinforcement_schedule'):
        kind = pads.get('Type')
        require(kind in preloads['rules'], 'Reserved reinforcement ground missing early rules preload')
        row = effective[kind]
        for field, value in {'Image': 'CABHUT', 'IsPassable': 'yes', 'Immune': 'yes',
                             'InvisibleInGame': 'yes', 'BaseNormal': 'no', 'KeepAlive': 'no',
                             'Capturable': 'no', 'Unsellable': 'yes', 'BridgeRepairHut': 'no',
                             'DontScore': 'yes', 'ProduceCashAmount': '0'}.items():
            require(row.get(field) == value, f'Unsafe reinforcement reservation {field}')
        actual = [value.split(',') for value in rows['Structures'].values() if value.split(',')[1] == kind]
        expected = set()
        for actor, _, waypoint in coalition(plan):
            p = plan['map']['perk_layouts'][str(waypoint)]['units']
            require(pads[actor] == str(p['y'] * 1000 + p['x']), 'Reservation detached from arrival waypoint')
            expected.update((p['x'] + dx, p['y'] + dy) for dx in range(5) for dy in range(3))
        if plan.get('plan_version', 1) >= 16:
            for p in plan['map']['enemy_wave_positions'].values():
                expected.update((p['x'] + dx, p['y'] + dy) for dx in range(5) for dy in range(3))
        require(len(actual) == len(expected) and {(int(v[3]), int(v[4])) for v in actual} == expected,
                'Reinforcement apron can be built over')
        require(all(v[0] == 'Neutral' and v[6] == 'None' for v in actual),
                'Reserved ground changes ownership/score accounting')
        if terrain is not None:
            # Each friendly apron is flat; different bases may have different
            # heights, so inspect them separately rather than as one rectangle.
            for actor, _, waypoint in coalition(plan):
                p = plan['map']['perk_layouts'][str(waypoint)]['units']
                require(terrain.clear({(p['x'] + dx, p['y'] + dy)
                                       for dx in range(5) for dy in range(3)}),
                        f'Arrival reservation crosses unsafe terrain: {actor}')
    else:
        require(not pads, 'Disabled reinforcements still reserve player building space')

    for actor, _, waypoint in coalition(plan)[1:]:
        teams = [(key, effective[key]) for key in rows['TeamTypes'].values()
                 if effective[key].get('Name', '').startswith('Fortress helper starting army ' + actor + ' ')]
        army = plan['effects']['starting_units']
        require(len(teams) == (len(army) + 5) // 6, 'Helper starting army lacks explicit orders')
        actual = []
        for key, team in teams:
            require(team['House'] == actor and effective[team['Script']]['0'] == '0,1'
                    and team['AreTeamMembersRecruitable'] == 'no'
                    and team['VeteranLevel'] == str(plan['effects']['veterancy'] + 1),
                    'Helper starting team has wrong ownership, orders or rank')
            force = effective[team['TaskForce']]
            actual.extend(value for field, value in force.items() if field.isdigit())
            starts = [trigger for trigger, value in rows['Actions'].items()
                      if any(action[0] == '4' and action[2] == key
                             for action in parse_action_groups(value)[1])]
            require(len(starts) == 1 and rows['Events'][starts[0]] == '1,13,0,2'
                    and rows['Triggers'][starts[0]].split(',')[0] == actor,
                    'Helper grant is never recruited after its ownership transfer')
        expected = [f'{unit["count"]},{rows.get("FFPlayerTypes", {}).get(unit["type"], unit["type"])}'
                    for unit in army]
        require(sorted(actual) == sorted(expected), 'Helper orders include harvesters or omit starting troops')


def audit_wave_pools(rows, effective, plan, rules, preloads, spawn, terrain):
    """Audit the real dispatch graph, bounded reservations and native option overlay."""
    if plan.get('plan_version', 1) < 16:
        return
    from collections import Counter, defaultdict
    from randomizer.final_fortress.engine import _action, _waypoint
    pools = rows['FFWavePools']
    if plan.get('plan_version', 1) >= 20:
        from randomizer.final_fortress.player_perks import _eligible
        infantry = set(rules['InfantryTypes'].values())
        vehicles = set(rules['VehicleTypes'].values())
        air_stages = plan.get('wave_air_support', [])
        for wave in plan['wave_schedule']:
            stage = next((entry for entry in reversed(air_stages)
                          if entry['from_seconds'] <= wave['seconds']), None)
            for group in wave['groups']:
                require(any(unit['type'] in infantry for unit in group['units']),
                        'Wave lost its infantry component')
                air = set(group.get('air_types', []))
                if stage:
                    require(len(air) == 1 and air <= {unit['type'] for unit in stage['units_by_country'][group['country']]},
                            'Later wave has no configured faction air support')
                    for kind in air:
                        require(kind in vehicles and rules[kind].get('MovementZone') == 'Fly'
                                and _eligible(rules[kind], group['country'])
                                and rules[kind].get('Primary') not in (None, '', 'none'),
                                'Air support is not an eligible armed native flying vehicle')
                    total = sum(unit['count'] for unit in group['units'])
                    amount = sum(unit['count'] for unit in group['units'] if unit['type'] in air)
                    expected = min(max(1, total * stage['percent'] // 100), total - len(group['units']) + 1)
                    require(amount == expected, 'Air support ignores its frozen share or increases the wave budget')
                else:
                    require(not air, 'Air support starts before its configured time')
    require(sum(int(v.split(',')[1]) for v in pools.values()) <= plan['wave_pressure']['max_active_units'],
            'Reusable wave slots exceed the shared living ceiling')
    finished = next(int(k) for k,v in rows['VariableNames'].items() if v == 'Final Fortress finished,0')
    all_types = set()
    for slot, value in pools.items():
        owner, capacity, busy, release = value.split(',')
        aliases = set(rows['FFWavePoolTypes.' + slot].values())
        require(not aliases & all_types, 'Wave pool identities overlap between slots')
        all_types.update(aliases)
        require(1 <= int(capacity) <= 20, 'Whole-wave reservations returned')
        expected = [str(1 + len(aliases)), '36', '0', busy]
        for alias in rows['FFWavePoolTypes.' + slot].values():
            expected += ['61', '2', '0', alias]
            require(effective[alias]['BuildLimit'] == '0' and effective[alias]['Insignificant'] == 'no'
                    and effective[alias]['DontScore'] == 'no', 'Wave pool tracking can be bypassed')
            for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water'):
                require(effective[alias].get(field, 'none').lower() == 'none'
                        or effective[alias][field] in aliases, 'Deployment escapes its reservation')
        event = rows['Events'][release].split(',')
        require(event[:4] == expected[:4]
                and sorted(tuple(event[i:i+4]) for i in range(4,len(event),4))
                == sorted(tuple(expected[i:i+4]) for i in range(4,len(expected),4)),
                'Occupied slot releases before all members disappear')
        require(parse_action_groups(rows['Actions'][release])[1] == [_action(57, int(busy))],
                'Slot is never returned to the pool')
        require(any(v == f'2,Wave pool release {slot},{release}' for v in rows['Tags'].values()),
                'Wave slot releases only once')
    by_chunk = defaultdict(list)
    for gate, value in rows['FFWaveDispatches'].items():
        slot, team, chunk, following = value.split(',')
        by_chunk[chunk].append((gate, slot, team, following))
    actual = defaultdict(Counter)
    for chunk, deliveries in by_chunk.items():
        wave, house, count = rows['FFWaveChunks'][chunk].split(',')
        expected_units = None
        for gate, slot, team, following in deliveries:
            owner, capacity, busy, _ = pools[slot].split(',')
            require(rows['Events'][gate] == f'2,37,0,{busy},37,0,{finished}', 'Dispatch ignores occupancy or run end')
            require(rows['Triggers'][gate].split(',')[3] == '1', 'Future wave delivery starts early')
            actions = parse_action_groups(rows['Actions'][gate])[1]
            expected = [_action(54, trigger=other[0]) for other in deliveries]
            expected += [_action(56, int(busy)), _action(7, team=team), _action(53, trigger=following)]
            require(actions == expected, 'Wave delivery can double-spawn or fail to advance')
            require(parse_action_groups(rows['Actions'][chunk])[1]
                    == [_action(53, trigger=item[0]) for item in deliveries], 'Missing slot availability gates')
            row = effective[team]
            require(row['House'] == owner, 'Slot is owned by another enemy')
            require(row['Waypoint'] == _waypoint(15 + int(owner[-1])), 'Wave still spawns on a construction yard')
            inverse = {v:k for k,v in rows['FFWavePoolTypes.' + slot].items()}
            units = Counter()
            for key,value in effective[row['TaskForce']].items():
                if key.isdigit():
                    amount, alias = value.split(',')
                    require(alias in inverse, 'Wave delivery escapes its population slot')
                    units[inverse[alias]] += int(amount)
            require(sum(units.values()) == int(count) <= int(capacity), 'Wave delivery exceeds slot capacity')
            if plan.get('plan_version', 1) >= 20:
                require(not (any(rules[kind].get('MovementZone') == 'Fly' for kind in units)
                             and any(rules[kind].get('MovementZone') != 'Fly' for kind in units)),
                        'Flying and ground deliveries share a movement team')
            if expected_units is None:
                expected_units = units
            require(units == expected_units, 'Available slot changes the wave roster')
        actual[(int(wave), house)].update(expected_units)
    for index,wave in enumerate(plan['wave_schedule'],1):
        for group in wave['groups']:
            require(actual[(index,group['house'])] == Counter({u['type']:u['count'] for u in group['units']}),
                    'Chunked wave lost or duplicated configured units')
    timers = {int(v.split(',')[2].split()[1]): key for key,v in rows['Triggers'].items()
              if re.fullmatch(r'Wave \d+ interval', v.split(',')[2])}
    for index in range(1,len(plan['wave_schedule'])+1):
        timer = timers[index]
        require(rows['Events'][timer] == f'1,13,0,{plan["wave_interval_seconds"]}',
                'Wave timer lost its five-minute interval')
        require(rows['Triggers'][timer].split(',')[3] == ('0' if index == 1 else '1'),
                'Wave timers run before the preceding delivery completes')
        relay = parse_action_groups(rows['Actions'][timer])[1][0][2]
        visited = set()
        while relay in by_chunk:
            require(relay not in visited and rows['FFWaveChunks'][relay].split(',')[0] == str(index),
                    'Wave dispatch graph loops or skips into another wave')
            visited.add(relay)
            next_relays = {d[3] for d in by_chunk[relay]}
            require(len(next_relays) == 1, 'Slot choice changes wave continuation')
            relay = next_relays.pop()
        expected = {key for key,v in rows['FFWaveChunks'].items() if v.split(',')[0] == str(index)}
        require(visited == expected, 'Wave delivery has unreachable batches')
        end = parse_action_groups(rows['Actions'][relay])[1]
        require(end[0][0] == '4', 'Delivered wave has no native admission marker')
        tail = [_action(53, trigger=timers[index+1])] if index < len(timers) else []
        if rows.get('FFWaveClock'):
            tail.append(_action(56, int(rows['FFWaveClock']['Restart' if index < len(timers) else 'Finished'])))
        require(end[1:] == tail,
                'Delivered wave never starts its successor')
    pad = rows['FFEnemyWavePads']['Type']
    require(pad in preloads['rules'] and effective[pad]['IsPassable'] == 'yes'
            and effective[pad]['LegalTarget'] == 'no', 'Enemy spawn apron is obstructed or targetable')
    placed = {(int(v.split(',')[3]),int(v.split(',')[4])) for v in rows['Structures'].values()
              if v.split(',')[1] == pad}
    for index,wp in enumerate(plan['map']['enemy_waypoints']):
        p = plan['map']['enemy_wave_positions'][str(wp)]
        cells = {(p['x']+dx,p['y']+dy) for dx in range(5) for dy in range(3)}
        require(cells <= placed, 'AI can build over its wave arrival position')
        require(int(rows['Waypoints'][str(16+index)]) == (p['y']+1)*1000+p['x']+2, 'Wrong enemy spawn waypoint')
        if terrain is not None:
            require(terrain.clear(cells), 'Unsafe enemy arrival terrain')
    for team in preloads['ai']['TeamTypes'].values():
        row = effective[team]
        if row['House'].startswith('FFALLY'):
            require(all(value not in ('0,2','0,6','0,7') for key,value in effective[row['Script']].items()
                        if key.isdigit()), 'Helper attack script still insists on immortal buildings')
    boost = plan['mental_ai_boost']
    require(read_sections(spawn)['Settings']['MentalAI'] == ('Yes' if boost else 'No'), 'Spawner lost Mental AI Boost')
    if boost:
        option = read_sections((GAME_ROOT / 'INI/Game Options/Mental AI.ini').read_bytes())
        for section,values in option.items():
            for key,value in values.items():
                require(effective[section].get(key) == value and preloads['rules'][section].get(key) == value,
                        'Native Mental AI Boost setting was lost')
                if key == 'AIBuildCounts':
                    for metadata in ('FFEnemyBuildings','FFPlayerTypes'):
                        alias = rows.get(metadata,{}).get(section)
                        if alias:
                            require(effective[alias].get(key) == value, 'Private factory missed Mental AI Boost')


def audit_friendly_pools(rows, effective, plan, *, finished_name):
    """Review actual friendly deliveries without requiring complete cohort deaths."""
    from collections import Counter, defaultdict
    from randomizer.final_fortress.engine import _action, _waypoint
    effect = plan['effects']['reinforcements']
    pools = rows['FFFriendlyPools']
    require(sum(int(v.split(',')[1]) for v in pools.values()) <= effect['max_active_units'],
            'Friendly pools exceed the shared population cap')
    finished = next(int(k) for k,v in rows['VariableNames'].items() if v == finished_name+',0')
    types = set()
    by_chunk = defaultdict(list)
    for slot,value in pools.items():
        owner,capacity,busy,release = value.split(',')
        aliases = set(rows['FFFriendlyPoolTypes.'+slot].values())
        require(not aliases & types, 'Friendly pools share identities')
        types.update(aliases)
        events = rows['Events'][release].split(',')
        require(events[:4] == [str(len(aliases)+1),'36','0',busy]
                and {tuple(events[i:i+4]) for i in range(4,len(events),4)}
                == {('61','2','0',alias) for alias in aliases}, 'Friendly slot releases with survivors')
        require(parse_action_groups(rows['Actions'][release])[1] == [_action(57,int(busy))]
                and any(v == f'2,Friendly pool release {slot},{release}' for v in rows['Tags'].values()),
                'Friendly slot cannot be reused repeatedly')
        for alias in aliases:
            row = effective[alias]
            require(row['BuildLimit'] == '0' and row['TechLevel'] == '-1'
                    and row['DontScore'] == 'no' and row['Insignificant'] == 'no', 'Untracked friendly gift')
            for field in ('Convert.Deploy','Convert.Land','Convert.Water'):
                require(row.get(field,'none').lower() == 'none' or row[field] in aliases,
                        'Friendly conversion escapes its pool')
    for gate,value in rows['FFFriendlyDispatches'].items():
        slot,team,chunk,following = value.split(',')
        by_chunk[chunk].append((gate,slot,team,following))
    actual = defaultdict(Counter)
    for chunk,deliveries in by_chunk.items():
        arrival,owner,count = rows['FFFriendlyChunks'][chunk].split(',')
        canonical = None
        for gate,slot,team,following in deliveries:
            actor,capacity,busy,_ = pools[slot].split(',')
            require(actor == 'coalition' and rows['Events'][gate] == f'2,37,0,{busy},37,0,{finished}',
                    'Friendly dispatch ignores owner, occupancy or survival end')
            require(rows['Triggers'][gate].split(',')[3] == '1', 'Friendly dispatch starts before its timer')
            expected = [_action(54,trigger=d[0]) for d in deliveries]
            expected += [_action(56,int(busy)),_action(7,team=team),_action(53,trigger=following)]
            require(parse_action_groups(rows['Actions'][gate])[1] == expected, 'Friendly group can double-spawn')
            require(parse_action_groups(rows['Actions'][chunk])[1] == [_action(53,trigger=d[0]) for d in deliveries],
                    'Friendly relay omits available pool slots')
            row = effective[team]
            require(row['House'] == owner and row['VeteranLevel'] == str(effect.get('veterancy',0)+1),
                    'Wrong friendly ownership or Veteran/Elite rank')
            helper = owner != 'FFPLAYER'
            require(effective[row['Script']]['0'] == ('0,1' if helper else '11,5')
                    and row['AreTeamMembersRecruitable'] == ('no' if helper else 'yes'), 'Wrong friendly orders')
            actor_index = next(i for i,(a,_,_) in enumerate(coalition(plan)) if a == owner)
            require(row['Waypoint'] == _waypoint(10+actor_index), 'Friendly gift spawns outside its own apron')
            wp = coalition(plan)[actor_index][2]
            position = plan['map']['perk_layouts'][str(wp)]['units']
            require(int(rows['Waypoints'][str(10+actor_index)]) == (position['y']+1)*1000+position['x']+2,
                    'Friendly arrival does not use the protected center cell')
            inverse = {v:k for k,v in rows['FFFriendlyPoolTypes.'+slot].items()}
            units = Counter()
            for key,value in effective[row['TaskForce']].items():
                if key.isdigit():
                    amount,alias=value.split(',');units[inverse[alias]]+=int(amount)
            require(sum(units.values()) == int(count) <= int(capacity), 'Friendly group exceeds its reservation')
            if canonical is None:canonical=units
            require(units == canonical, 'Slot choice changes friendly roster')
        actual[(int(arrival),owner)].update(canonical)
    triggers = {v.split(',')[2]:k for k,v in rows['Triggers'].items()}
    for owner,_,_ in coalition(plan):
        for index,arrival in enumerate(plan['reinforcement_schedule'],1):
            expected = next(g['units'] for g in arrival['groups'] if g['owner'] == owner)
            require(actual[(index,owner)] == Counter({u['type']:u['count'] for u in expected}),
                    'Friendly arrival loses or duplicates units')
            timer = triggers[f'Friendly arrival {index} {owner} interval']
            delay = effect['first_seconds'] if index == 1 else effect['interval_seconds']
            require(rows['Events'][timer] == f'1,13,0,{delay}', 'Wrong friendly timer duration')
            require(rows['Triggers'][timer].split(',')[3] == ('0' if index==1 else '1'),
                    'Friendly timer starts before its own preceding delivery completes')
            relay = parse_action_groups(rows['Actions'][timer])[1][0][2]
            visited=set()
            while relay in by_chunk:
                require(relay not in visited and rows['FFFriendlyChunks'][relay].split(',')[:2] == [str(index),owner],
                        'Friendly deliveries cross ownership or loop')
                visited.add(relay)
                following={d[3] for d in by_chunk[relay]}
                require(len(following)==1, 'Friendly slots alter delivery order')
                relay=following.pop()
            require(visited == {k for k,v in rows['FFFriendlyChunks'].items() if v.split(',')[:2] == [str(index),owner]},
                    'Friendly delivery has unreachable groups')
            actions=parse_action_groups(rows['Actions'][relay])[1]
            starts=[a[2] for a in actions if a[0]=='53']
            require(starts == ([triggers[f'Friendly arrival {index+1} {owner} interval']]
                               if index<len(plan['reinforcement_schedule']) else []),
                    'Helper capacity controls the human timer or later arrivals are unreachable')
            if owner=='FFPLAYER':
                notice=triggers[f'Friendly arrival {index} capacity notice']
                require(any(a[0]=='53' and a[2]==notice for a in parse_action_groups(rows['Actions'][timer])[1])
                        and any(a[0]=='54' and a[2]==notice for a in actions), 'Missing friendly cap notice lifecycle')
                slots=[v.split(',')[2] for v in pools.values()]
                require(rows['Events'][notice] == ','.join([str(len(slots)+1),'37','0',str(finished),
                            *[token for busy in slots for token in ('36','0',busy)]]),
                        'Capacity notice does not reflect the human pool')


def audit_wave_clock(rows, effective, plan, preloads):
    if plan.get('plan_version',1)<17:return
    from randomizer.final_fortress.engine import _action
    from randomizer.final_fortress.player_perks import needs_countries
    clock=rows['FFWaveClock'];power=clock['Power'];provider=clock['Provider']
    require(power in preloads['rules'] and provider in preloads['rules'], 'Wave clock is not preloaded')
    row=effective[power]
    require(row['UIName']=='NOSTR:Next enemy wave' and row['ShowTimer']=='yes'
            and float(row['RechargeTime'])*60==plan['wave_interval_seconds'], 'Wrong wave countdown label or duration')
    require(row['SW.ShowCameo']=='no' and row['SW.ManualFire']=='no' and row['SW.AutoFire']=='yes'
            and row['SW.AITargeting']=='None' and row['SW.Damage']=='0' and row['SW.TimerVisibility']=='owner',
            'Display-only wave clock can fire or clutter the sidebar')
    registered=list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
    require(registered[int(clock['Index'])]==power, 'Wave reset addresses another superweapon')
    require(parse_action_groups(rows['Actions'][clock['Reset']])[1]
            == [_action(134,int(clock['Index'])),_action(57,int(clock['Restart']))], 'Wave clock does not reset')
    owner='FFPLAYER' if needs_countries(plan) else plan['player_country']
    require(rows['Triggers'][clock['Reset']].split(',')[0]==owner, 'Wave clock reset belongs to another house')
    require(effective[provider]['SuperWeapon']==power and effective[provider]['Power']=='0'
            and effective[provider]['Immune']=='yes' and effective[provider]['IsPassable']=='yes',
            'Wave clock depends on player power or blocks movement')
    require(effective[provider]['EVA.Lost']=='none' and effective[provider]['Explosion']=='none',
            'Removing the display-only clock creates a false combat notification')
    placed=[v.split(',') for v in rows['Structures'].values() if v.split(',')[1]==provider]
    require(len(placed)==1 and placed[0][3:5]==['113','71'], 'Wave clock provider overlaps another reserved area')
    require(rows['Events'][clock['Remove']] == f'1,36,0,{clock["Finished"]}'
            and parse_action_groups(rows['Actions'][clock['Remove']])[1]
                == [_action(54,trigger=clock['Remove']),_action(32)]
            and rows['Tags'][placed[0][6]] == f'2,Wave clock remove,{clock["Remove"]}',
            'Wave countdown remains after the final wave')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Directory for generated audit artifacts')
    parser.add_argument('--profiles', nargs='+', choices=(
                        'baseline', 'helpers', 'maximum', 'defenses', 'powers', 'upgrades', 'secondary',
                        'arsenal', 'reinforcements', 'arsenal-first', 'reinforcements-first',
                        'healing', 'recon', 'limits', 'income', 'enemy-powers', 'powerhouses', 'utilities-first',
                        'veteran', 'elite', 'reinforcements-veteran', 'reinforcements-rookie'),
                        default=['baseline', 'helpers', 'maximum'])
    parser.add_argument('--difficulties', nargs='+', choices=DIFFICULTY_IDS, default=list(DIFFICULTY_IDS))
    parser.add_argument('--mental-ai-boost', action='store_true', help='Audit the installed Mental AI Boost option')
    parser.add_argument('--terrain', action='store_true', help='Check flat ground/resources; requires the system LZO2 library')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = load_config()
    _, rules = installed_rules_registry(synchronous=True)
    source_path = GAME_ROOT / config['map']['source']
    source_data = source_path.read_bytes()
    source = read_sections(source_data)
    terrain = None
    if args.terrain:
        from fortress_terrain import Terrain
        terrain = Terrain(source)
    if not ART_CACHE_PATH.exists():
        require(extract_mix_files_sync([('ARTMO.INI', ART_CACHE_PATH)]), 'Installed art unavailable')
    art = {key.casefold(): value for key, value in read_sections(ART_CACHE_PATH.read_bytes()).items()}
    ai = load_ai_rules()
    manifest = []
    utilities = ['automatic_healing', 'reconnaissance', 'unique_unit_capacity', 'special_building_income']
    loadouts = {
        'baseline': [], 'helpers': ['allied_helpers'], 'maximum': [entry['id'] for entry in config['perks']],
        'powers': ['support_powers', 'faction_superweapon', 'allied_helpers'],
        'upgrades': ['power_upgrades'], 'arsenal': ['special_unit_access'], 'arsenal-first': ['special_unit_access'],
        'reinforcements': ['periodic_reinforcements'], 'reinforcements-first': ['periodic_reinforcements', 'allied_helpers'],
        'reinforcements-veteran': ['periodic_reinforcements', 'allied_helpers'],
        'reinforcements-rookie': ['periodic_reinforcements', 'allied_helpers'],
        'secondary': ['faction_superweapon', 'allied_helpers', 'power_upgrades',
                      'tier_1_training', 'tier_2_training', 'tier_3_training'],
        'defenses': ['starting_defenses'], 'healing': ['automatic_healing'], 'recon': ['reconnaissance'],
        'limits': ['unique_unit_capacity', 'special_unit_access'], 'income': ['special_building_income'],
        'enemy-powers': [], 'powerhouses': [], 'utilities-first': [*utilities, 'allied_helpers'],
        'veteran': ['reinforcements', 'veteran_escort', 'allied_helpers'],
        'elite': ['reinforcements', 'veteran_escort', 'allied_helpers'],
    }
    from randomizer.final_fortress.challenges import definition
    for profile in args.profiles:
        selected = loadouts[profile]
        selected_challenges = [entry['id'] for entry in config['challenges'] if profile == 'maximum'
                               or profile == 'enemy-powers' and definition(entry)['effect'] in ('power', 'power_group')
                               or profile == 'powerhouses' and entry['enemy_effect_id'] == 'powerhouse']
        for country in SIDE_COUNTRIES:
            for difficulty in args.difficulties:
                name = f'{profile}-{country}-{difficulty}'
                plan = build_run_plan(
                    config, difficulty=difficulty, seed='FF-MAP-AUDIT-' + name,
                    player_country=country, selected_perks=selected,
                    perk_ranks={entry['id']: (1 if (profile == 'secondary' and entry['id'] == 'faction_superweapon'
                                                  or profile == 'arsenal-first' and entry['id'] == 'special_unit_access'
                                                  or profile == 'reinforcements-first' and entry['id'] == 'periodic_reinforcements'
                                                  or profile == 'utilities-first' and entry['id'] in utilities)
                                             else 1 if profile == 'veteran' and entry['id'] == 'veteran_escort'
                                             else 7 if profile == 'reinforcements-veteran' and entry['id'] == 'periodic_reinforcements'
                                             else 6 if profile == 'reinforcements-rookie' and entry['id'] == 'periodic_reinforcements'
                                             else len(ranks(entry))) for entry in config['perks']},
                    selected_challenges=selected_challenges,
                    challenge_stacks={entry['id']: maximum(entry) for entry in config['challenges']},
                    wave_multiplier=10 if profile == 'maximum' else 1, mental_ai_boost=args.mental_ai_boost)
                preloads = {}
                data = build_map(GAME_ROOT, {'id': hashlib.md5(name.encode()).hexdigest(), 'plan': plan},
                                 rules, preloads=preloads)
                spawn = spawn_data(plan, data)
                counts = audit_map(data, spawn, preloads, plan, rules, source, art, ai, terrain)
                (args.output / (name + '.map')).write_bytes(data)
                (args.output / (name + '.spawn.ini')).write_bytes(spawn)
                manifest.append({'name': name, 'map_sha256': hashlib.sha256(data).hexdigest(),
                                 'camp_countries': [camp['guard_country'] for camp in plan['map']['camps']],
                                 'waves': [{'minute': wave['seconds'] // 60,
                                            'infantry': sum(unit['count'] for group in wave['groups'] for unit in group['units']
                                                            if unit['type'] in rules['InfantryTypes'].values()),
                                            'air': sum(unit['count'] for group in wave['groups'] for unit in group['units']
                                                       if unit['type'] in group.get('air_types', []))}
                                           for wave in plan['wave_schedule']],
                                 'bytes': len(data), 'registries': counts})
        print(f'{profile}: {len(SIDE_COUNTRIES) * len(args.difficulties)} Miners in the Sun configurations audited', flush=True)
    require(source_path.read_bytes() == source_data, 'Installed source map changed during audit')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: one map, {len(manifest)} configurations; artifacts: {args.output}')


if __name__ == '__main__':
    main()
