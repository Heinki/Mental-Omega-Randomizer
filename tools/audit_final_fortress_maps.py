"""Audit configurations of a selected Fortress map without launching a game.

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
from randomizer.final_fortress.maps import perk_layout, select_map, source_lines
from randomizer.final_fortress.perks import ranks
from randomizer.final_fortress.player_perks import coalition, human_actor, needs_countries
from randomizer.final_fortress.planning import build_run_plan
from randomizer.maps.ini import all_section_value_maps_preserve, parse_action_groups
from randomizer.ui.cameos import ART_CACHE_PATH, extract_mix_files_sync, installed_rules_registry


def read_sections(data):
    return all_section_value_maps_preserve(data.decode('latin-1').splitlines())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_wave_rosters(config, rules):
    """Check every composition, including types a particular seed never draws."""
    from randomizer.final_fortress.config import stage_compositions, wave_rosters
    from randomizer.final_fortress.engine import _MapWriter
    from randomizer.final_fortress.player_perks import _eligible
    from randomizer.maps.enemy_powerhouses import POWERHOUSE_UNITS_BY_FAMILY

    infantry = set(rules['InfantryTypes'].values())
    vehicles = set(rules['VehicleTypes'].values())
    families = dict(zip(SIDE_COUNTRIES, SIDE_FAMILIES))
    for country, stages in wave_rosters(config, 'normal').items():
        kinds = set()
        for stage in stages:
            for composition in stage_compositions(stage):
                units = [unit['type'] for unit in composition['units']]
                label = f'{country}/{stage["from_seconds"]}/{composition["id"]}'
                require(len(units) == len(set(units)), f'Duplicate wave identity: {label}')
                require(set(units) & infantry and set(units) & vehicles,
                        f'Wave composition requires infantry and vehicles: {label}')
                for kind in units:
                    require(kind in infantry | vehicles and _eligible(rules[kind], country)
                            and rules[kind].get('MovementZone') != 'Fly',
                            f'Ineligible ground wave unit {kind}: {label}')
                kinds.update(units)
        for stage in config.get('wave_air_support', []):
            for unit in stage['units_by_country'][country]:
                kind = unit['type']
                require(kind in vehicles and _eligible(rules[kind], country)
                        and rules[kind].get('MovementZone') == 'Fly'
                        and rules[kind].get('Primary') not in (None, '', 'none'),
                        f'Ineligible air wave unit {kind}: {country}')
                kinds.add(kind)
        # Include all Challenge heavies and recursive conversion forms together;
        # a different seed must not overflow the native release event limit.
        kinds.update(POWERHOUSE_UNITS_BY_FAMILY[families[country]])
        aliases = _MapWriter([]).wave_types(
            [{'units': [{'type': kind, 'count': 1} for kind in sorted(kinds)]}], rules)
        require(len(aliases) <= 30, f'Wave roster exceeds native tracking limit: {country}')


def audit_special_rosters(config):
    """Keep every portable special unit covered without duplicate purchases."""
    from randomizer.rewards.catalogue import BUFF_TARGETS, SPECIAL_REWARD_UNIT_IDS

    perks = {entry['id']: entry for entry in config['perks']}
    for country, family in zip(SIDE_COUNTRIES, SIDE_FAMILIES):
        expected = {kind for kind in SPECIAL_REWARD_UNIT_IDS
                    if BUFF_TARGETS[kind]['category'] in ('infantry', 'units', 'aircraft')
                    and {value.lower() for value in BUFF_TARGETS[kind]['factions']} & {family, 'neutral'}}
        campaign = set(ranks(perks['special_unit_access'])[-1]['effects']['special_units_by_country'][country])
        stolen = set(ranks(perks['stolen_tech_access'])[-1]['effects']['special_units_by_country'][country])
        require(len(stolen) == 4, f'Stolen tech must cover four units: {country}')
        require(not campaign & stolen, f'Special and stolen-tech purchases overlap: {country}')
        require(campaign | stolen == expected, f'Incomplete special unit roster: {country}')


def resource_overlay_indices(rules):
    return {int(key) for key, kind in rules.get('OverlayTypes', {}).items()
            if key.isdigit() and rules.get(kind, {}).get('Tiberium', 'no').lower() in ('yes', 'true')}


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


def reserved_arrival_cells(rows, effective, art, types):
    """Inspect complete footprints of invisible reservations and visible pads."""
    return {(int(fields[3]) + dx, int(fields[4]) + dy)
            for value in rows.get('Structures', {}).values()
            if (fields := value.split(','))[1] in types
            for dx, dy in footprint(effective[fields[1]], art)}


def audit_score_colors(spawn, plan, rules):
    """Compare score matching with emitted houses and the installed palette."""
    from randomizer.final_fortress.colors import remap_score_scheme

    ui = all_section_value_maps_preserve(
        (GAME_ROOT / 'uimd.ini').read_bytes().decode('latin-1').splitlines())['Colors']
    palette = list(rules['Colors'])
    humans = {row['Name']: int(row['Color']) for section, row in spawn.items()
              if section == 'Settings' or section.startswith('Other')}
    countries = {value: key for key, value in rules['Countries'].items()}
    for actor in plan.get('coalition_scores', []):
        if actor['name'] is not None:
            color = humans[actor['name']]
        else:
            house = next(key for key, value in spawn['HouseCountries'].items()
                         if value == countries[actor['actor']])
            color = int(spawn['HouseColors'][house])
        native_scheme = 2 * palette.index(ui[f'Slot{color + 1}.ColorScheme']) + 1
        require(remap_score_scheme(actor['scheme'], plan) == native_scheme,
                f'Kill rewards cannot match {actor["actor"]} at native color {color}')


def audit_map(data, spawn, preloads, plan, rules, source, art, ai, terrain=None):
    rules = {section: {**row, **source.get(section, {})} for section, row in rules.items()}
    rows = read_sections(data)
    resource_overlays = resource_overlay_indices(rules)
    camp_guard_tags = {value.split(',')[1] for value in rows.get('FFCampTracking', {}).values()}
    effective = deepcopy(rules)
    for section, values in ai.items():
        effective.setdefault(section, {}).update(values)
    for section, values in rows.items():
        effective.setdefault(section, {}).update(values)
    ids = {section.casefold(): section for section in effective}
    audit_native_production(rows, effective, plan, rules, source, preloads)

    # Only reserved arrival tiles may change; overlays and scenery stay exact.
    for section in ('OverlayPack', 'OverlayDataPack', 'Terrain'):
        require(rows.get(section) == source.get(section), f'Source terrain changed: {section}')
    if plan.get('plan_version', 1) < 33:
        require(rows.get('IsoMapPack5') == source.get('IsoMapPack5'), 'Source terrain changed: IsoMapPack5')
    elif terrain is not None:
        # Independent native LZO decoding also validates the portable writer.
        import struct
        from fortress_terrain import _unpack
        expected = bytearray(_unpack(source['IsoMapPack5'], lzo=True))
        positions = list(plan['map']['enemy_wave_positions'].values())
        if plan.get('reinforcement_schedule') or plan['effects'].get('lab_reserve_units'):
            positions.extend(plan['map']['perk_layouts'][str(w)]['units'] for _, _, w in coalition(plan))
        cells = {(p['x'] + dx, p['y'] + dy) for p in positions for dx in range(5) for dy in range(3)}
        found = set()
        for offset in range(0, len(expected), 11):
            x, y = struct.unpack_from('<HH', expected, offset)
            if (x, y) in cells:
                struct.pack_into('<IB', expected, offset + 4, 534, 0)
                found.add((x, y))
        require(found == cells, 'Spawn pavement has missing map cells')
        require(_unpack(rows['IsoMapPack5'], lzo=True) == expected,
                'Spawn pavement is missing or terrain outside arrivals changed')
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
    audit_exact_type_lists(rows, effective, plan, rules, preloads)
    power_bonus = plan['effects'].get('generator_power_percent', 0)
    if power_bonus:
        from math import ceil
        for original, alias in rows.get('FFPlayerTypes', {}).items():
            base = rules.get(original, {})
            if original in rules['BuildingTypes'].values() and float(base.get('Power', '0')) > 0:
                require(effective[alias]['Power'] == str(ceil(float(base['Power']) * (1 + power_bonus / 100))),
                        'Generator power bonus does not match the purchased rank')
                if float(base.get('ExtraPower', '0')) > 0:
                    require(effective[alias]['ExtraPower'] == str(ceil(float(base['ExtraPower']) * (1 + power_bonus / 100))),
                            'Bio Reactor passenger power missed the generator bonus')
    technos = {unit for registry in registries[:4] for unit in effective[registry].values()}
    if plan.get('plan_version', 1) >= 23:
        audit_feedback_fixes(rows, effective, plan, rules, preloads)
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
            require(not any(';' in field for field in action), 'INI comment truncates a native action')
            if action[0] == '11' and action[2].startswith('NOSTR:'):
                require(len(action[2].encode('latin-1')) <= 31, 'Native trigger message will be truncated')
            if action[0] in ('4', '5', '7', '80'):
                require(action[2] in rows['TeamTypes'].values(), f'Unknown action team: {action[2]}')
            if action[0] in ('7', '80'):
                team = effective[action[2]]
                require(team.get('Full') == 'no',
                        'Scripted reinforcements can spawn nested inside transports')
                if team.get('Name', '').startswith(('Final Fortress wave ', 'Final Fortress AI controller')):
                    require(action[0] == '80' and action[7] == team['Waypoint'],
                            'Hostile reinforcements lack an explicit matching spawn waypoint')
    for key, value in rows['Triggers'].items():
        if value.split(',')[2].startswith('Cash reward '):
            tags = [tag.split(',') for tag in rows['Tags'].values() if tag.split(',')[2] == key]
            require(tags and all(tag[0] == '0' for tag in tags),
                    'Persistent cash reward can hang native TeamLeavesMap cleanup after payment')
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
    audit_allied_clocks(rows, effective, plan, preloads)
    audit_lab_support(rows, effective, plan, rules, preloads, terrain)
    from fortress_economy_audit import audit_economy
    audit_economy(rows, effective, plan, rules, preloads)

    # Every purchased support unlock must be registered and granted to each
    # friendly house, including ranks beyond the proxy's two building slots.
    powers = plan['effects']['support_powers']
    from randomizer.final_fortress.powers import power_rewards
    blueprints = ({entry['superweapon']: entry for entry in power_rewards(plan, rules)}
                  if plan.get('plan_version', 1) >= 9 else {})
    if plan['effects'].get('power_upgrade_stacks') and not powers:
        clocks = {rows.get('FFWaveClock', {}).get('Power'),
                  rows.get('FFLabSupport', {}).get('ShieldPower'),
                  *[rows[section]['Power'] for section in rows.get('FFAlliedClocks', {}).values()]}
        require({k:v for k,v in rows.get('SuperWeaponTypes', {}).items() if v not in clocks}
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
            require(power.get('ShowTimer', 'no') == rules[original].get('ShowTimer', 'no')
                    and power.get('SW.TimerVisibility', 'all') == rules[original].get('SW.TimerVisibility', 'all'),
                    f'Friendly power lost its native countdown visibility: {actor}.{original}')
            if plan.get('plan_version', 1) >= 31:
                require(power.get('EVA.Detected') == 'none' and power.get('Message.Detected') == 'NOSTR:',
                        'Hidden friendly provider announces a newly discovered superweapon building')
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
                require(power.get('SW.AllowAI') == ('no' if human_actor(plan, actor) else 'yes'),
                        f'Wrong helper power access for {actor}')
                require(any(effective.get(value.split(',')[1], {}).get('SuperWeapon')
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
        require(original in effective or key in native_structures, f'Unknown added structure: {original}')
        # Some shipped scenery IDs are absent from the extracted rules. Keep
        # source objects and use their art foundations where available.
        row = dict(effective.get(original, {}))
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
        from randomizer.final_fortress.placement import deployment_cells
        deployment = (deployment_cells(x, y) if plan.get('plan_version', 1) >= 23 else
                      {(x + dx, y + dy) for dx in range(-2, 2) for dy in range(-1, 2)})
        require(not deployment & occupied.keys(), f'MCV deployment overlap: waypoint {waypoint}')
    for category in ('Infantry', 'Units'):
        for key, value in rows.get(category, {}).items():
            if key in source.get(category, {}):
                continue
            fields = value.split(',')
            x, y = map(int, fields[3:5])
            pads = rows.get('FFReinforcementPads', {})
            pad_types = {pads.get('Type'), pads.get('MarkerType')}
            require((x, y) not in occupied or occupied[(x, y)] in pad_types,
                    f'Starting unit overlaps a building at {(x, y)}')
            require(fields[0] == 'Neutral', 'Private starting objects must use native ownership transfers')
            if terrain is not None:
                tag = fields[8 if category == 'Infantry' else 7]
                overlays = resource_overlays if tag in camp_guard_tags else ()
                require(terrain.clear({(x, y)}, allowed_overlays=overlays),
                        f'Unit outside playable walkable terrain at {(x, y)}')

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
    audit_score_colors(spawn_rows, plan, effective)
    humans = len(plan.get('coop_players', [])) or 1
    friendly_slots = [*range(humans), *range(humans + 3, 4 + len(plan['allied_countries']))]
    for slot in friendly_slots:
        allies = set(map(int, spawn_rows[f'Multi{slot + 1}_Alliances'].values()))
        require(allies == set(friendly_slots) - {slot},
                'Coalition alliances do not protect helpers/player during unrestricted hostile targeting')
    require(int(spawn_rows['Settings']['AIPlayers']) == 4 + len(plan['allied_countries']) - humans, 'Wrong AI count')
    require(spawn_rows['Settings']['MapSHA1'] == hashlib.sha1(data).hexdigest(), 'Wrong scenario digest')
    for value in [spawn_rows['Settings']['Side'], *spawn_rows['HouseCountries'].values()]:
        require(int(value) in indices, f'Unresolved spawner country {value}')
    if plan.get('plan_version', 1) >= 7:
        buildings = [*plan['effects']['starting_buildings'], *plan['effects']['defense_types'],
                     *plan['effects'].get('starting_power_buildings', [])]
    if plan['effects'].get('starting_power_buildings') or plan.get('plan_version', 1) >= 38:
        balance = sum(int(rules[kind].get('Power', '0')) for kind in buildings)
        require(balance >= 0,
                'Granted buildings start with insufficient power')
        if plan.get('plan_version', 1) >= 38 and plan['effects'].get('starting_buildings'):
            require(balance > 0, 'Starting buildings have no spare power')
    if plan.get('plan_version', 1) >= 7:
        required_transfers = (1 + sum(unit['count'] for unit in plan['effects']['starting_units'])
                              + sum(unit['count'] for unit in plan['effects']['starting_harvesters'])
                              + len(buildings) + len(plan['effects']['starting_defenses'])
                              + (len(powers) if plan.get('plan_version', 1) >= 9 else int(bool(powers))))
        if rows.get('FFWaveClock'):
            required_transfers += 1
        if rows.get('FFAlliedClocks'):
            required_transfers += 1
        if plan.get('coop_players') and plan['effects'].get('reveal_map') and not powers:
            required_transfers += 1
        require(plan['initial_transfer_kills'] == required_transfers, 'Starting power transfers counted as combat kills')
    return {registry: len(set(effective[registry].values())) for registry in registries}


def audit_native_production(rows, effective, plan, rules, source, preloads):
    """Preserve every faction's native units, buildings and production paths."""
    from randomizer.final_fortress.player_perks import _eligible

    def paths(row):
        values = [row.get('Prerequisite.List0', row.get('Prerequisite', ''))]
        values.extend(row.get(f'Prerequisite.List{index}', '')
                      for index in range(1, int(row.get('Prerequisite.Lists', '0')) + 1))
        values.extend(part for part in row.get('PrerequisiteOverride', '').split(',')
                      if part and part.lower() != 'none')
        return [{part.strip() for part in value.split(',') if part.strip()} for value in values]

    aliases = rows.get('FFPlayerTypes', {})
    for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes'):
        for original in rules[category].values():
            native = rules[original]
            if not 0 <= int(native.get('TechLevel', '-1')) <= 10 or native.get('BuildLimit') == '0':
                continue
            unit = aliases.get(original, original)
            row = effective[unit]
            for actor, country, _ in coalition(plan):
                if not _eligible(native, country):
                    continue
                label = f'{original}/{country}/{actor}'
                actual_country = actor if needs_countries(plan) else country
                require(_eligible(row, actual_country), f'Native country access lost: {label}')
                require(0 <= int(row.get('TechLevel', '-1')) <= int(native['TechLevel']),
                        f'Native tech level locked or increased: {label}')
                limit = row.get('BuildLimit')
                native_limit = native.get('BuildLimit')
                require(limit != '0' and (limit is None
                        or native_limit is not None and int(limit) >= int(native_limit)),
                        f'Native production limit tightened: {label}')
                for path in paths(native):
                    expected = {aliases.get(part, part) for part in path}
                    require(any(candidate <= expected for candidate in paths(row)),
                            f'Native production path lost: {label}: {",".join(sorted(path))}')
                for field in ('Prerequisite.Negative', 'FactoryOwners.Forbidden', 'Prerequisite.RequiredTheaters'):
                    require(not row.get(field) or row.get(field) == native.get(field),
                            f'Native production gained a restriction: {label}/{field}')
    for original in rules['BuildingTypes'].values():
        restriction = source.get(original, {}).get('TechLevel')
        if restriction is None or 0 <= int(restriction) <= 10:
            continue
        copies = {original}
        for mapping in ('FFPlayerTypes', 'FFEnemyBuildings'):
            if original in rows.get(mapping, {}):
                copies.add(rows[mapping][original])
        for unit in copies:
            require(effective[unit]['TechLevel'] == restriction,
                    f'Source map building lock lost: {original}/{unit}')
            if unit in preloads['rules'] and 'TechLevel' in preloads['rules'][unit]:
                require(preloads['rules'][unit]['TechLevel'] == restriction,
                        f'Source map building lock lost in early preload: {original}/{unit}')


def audit_arsenal(rows, effective, plan, rules, preloads, terrain):
    """Review generated production gates, arrival identities and capacity events."""
    from randomizer.final_fortress.arsenal import TYPE_REFERENCE_FIELDS, production_factory, reviewed_rules
    from randomizer.final_fortress.engine import _waypoint

    access = plan['effects'].get('special_access', [])
    mapping = rows.get('FFSpecialAccess', {})
    require(set(mapping) == set(access), 'Special access does not match purchased rank')
    reviewed, forms = reviewed_rules(rules, access)
    friends = {actor for actor, _, _ in coalition(plan)}
    for original, alias in mapping.items():
        row = effective[alias]
        require(alias in preloads['rules'], f'Special unit missing early preload: {original}')
        require(row['TechLevel'] == '1', f'Special access is unbuildable: {original}')
        require(set(row['Owner'].split(',')) == friends
                and set(row['RequiredHouses'].split(',')) == friends,
                f'Special access leaked to native/enemy countries: {original}')
        require(row['Prerequisite'] == production_factory(original, plan['player_country'], reviewed),
                f'Special access retained a mission prerequisite: {original}')
        private_factory = rows.get('FFPlayerTypes', {}).get(row['Prerequisite'])
        alternatives = {key: value for key, value in row.items() if key.startswith('Prerequisite.')}
        require(not any(key.startswith('FactoryOwners') or key == 'BuiltAt' for key in row)
                and all(key == 'Prerequisite.Lists' or re.fullmatch(r'Prerequisite\.List[1-9]\d*', key)
                        and private_factory and value == private_factory for key, value in alternatives.items()),
                f'Special access retained a hidden production gate: {original}')
        if private_factory:
            require(any(value == private_factory for key, value in alternatives.items() if key != 'Prerequisite.Lists'),
                    f'Special access cannot use the fortified factory: {original}')
        if original in reviewed['AircraftTypes'].values():
            require(row['Prerequisite'] in row.get('Dock', '').split(','),
                    f'Special plane cannot dock at its own airfield: {original}')
        native_limit = reviewed[original].get('BuildLimit')
        from randomizer.final_fortress.utilities import supported_pairs
        expected_limit = str(int(native_limit) + plan['effects'].get('unique_limit_stacks', 0)) if (
            native_limit and int(native_limit) > 0 and (original, 'build_limit') in supported_pairs()) else native_limit
        require(row.get('BuildLimit') == expected_limit,
                f'Special unit lost its unique limit: {original}')
        if int(row.get('BuildLimit', '0')) > 0:
            category = next(category for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
                            if alias in effective[category].values())
            registered = list(dict.fromkeys(effective[category].values()))
            require(registered.index(alias) < 512,
                    f'Special unit limit exceeds native ownership counter capacity: {original}')
        require(not any('MORP' in value for value in row.values()), f'Unresolved roster alias: {original}')
        for field, value in row.items():
            if re.fullmatch(r'(?:Elite)?(?:Primary|Secondary|Weapon\d+)', field):
                require(value.lower() in ('none', '') or value in effective,
                        f'Unresolved special unit weapon: {original}.{field}')
        for field in TYPE_REFERENCE_FIELDS:
            value = row.get(field, '')
            require(all(part.lower() in ('none', '') or part in effective for part in value.split(',')),
                    f'Unresolved special dependency: {original}.{field}')
    aliases = rows.get('FFPlayerTypes', {})
    technos = {kind for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')
               for kind in effective[category].values()}
    for original in forms:
        alias = aliases[original]
        row = effective[alias]
        require(alias in technos and alias in preloads['rules'],
                f'Special dependency is not preloaded and registered: {original}')
        require(not any('MORP' in value for value in row.values()),
                f'Special dependency retains campaign clone references: {original}')
        if original not in access and original in rules:
            from randomizer.final_fortress.player_perks import _eligible
            payload = any(original in reviewed[source].get('InitialPayload.Types', '').split(',')
                          for source in forms)
            if payload and _eligible(rules[original], plan['player_country']):
                require(row['TechLevel'] == rules[original]['TechLevel'],
                        f'Special payload blocked ordinary production: {original}')
        for field in TYPE_REFERENCE_FIELDS:
            if field in reviewed[original]:
                expected = ','.join(aliases.get(kind, kind) for kind in reviewed[original][field].split(','))
                require(row.get(field) == expected, f'Special dependency escaped private copies: {original}.{field}')
        for field, weapon in row.items():
            if not re.fullmatch(r'(?:Elite)?(?:Primary|Secondary|Weapon\d+)|DeathWeapon', field):
                continue
            require(weapon.lower() in ('none', '') or weapon in effective,
                    f'Special dependency has an unresolved weapon: {original}.{field}')
            if weapon in effective:
                for reference in ('Warhead', 'Projectile'):
                    value = effective[weapon].get(reference, '')
                    require(value.lower() in ('none', '') or value in effective,
                            f'Special weapon has an unresolved {reference}: {original}')
    from randomizer.rewards.catalogue import STANDALONE_UNIT_RULE_TEMPLATES
    for original in forms:
        for definitions in STANDALONE_UNIT_RULE_TEMPLATES.get(original, {}).values():
            for section in definitions:
                if section in rules:
                    require(effective[section] == rules[section],
                            f'Special dependency changed native combat rules: {section}')
    schedule = plan.get('reinforcement_schedule', [])
    if not schedule:
        return
    effect = plan['effects']['reinforcements']
    if plan.get('plan_version', 1) >= 17:
        audit_friendly_pools(rows, effective, plan, finished_name='Final Fortress finished', preloads=preloads)
        return
    triggers = {value.split(',')[2]: key for key, value in rows['Triggers'].items()}
    flags = {value.rsplit(',', 1)[0]: int(key) for key, value in rows['VariableNames'].items()}
    all_types = set()
    counts = []
    for index, arrival in enumerate(schedule, 1):
        prefix = f'Friendly arrival {index}'
        spawn = triggers[prefix + ' spawn']
        _, actions = parse_action_groups(rows['Actions'][spawn])
        teams = [effective[action[2]] for action in actions if action[0] == '80']
        require(len(teams) == len(coalition(plan)), 'Reinforcement arrival lost a friendly house')
        count = 0
        identities = set()
        for group, team in zip(arrival['groups'], teams):
            require(team['House'] == group['owner'], 'Wrong reinforcement owner')
            require(team['VeteranLevel'] == str(effect.get('veterancy', 0) + 1),
                    'Wrong Rookie/Veteran/Elite reinforcement rank')
            helper = plan.get('plan_version', 1) >= 14 and not human_actor(plan, group['owner'])
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


def audit_exact_type_lists(rows, effective, plan, rules, preloads):
    """Inspect native capacity, cannon and attachment links in emitted maps."""
    from randomizer.final_fortress.player_perks import _eligible

    mappings = [rows.get(name, {}) for name in
                ('FFPlayerTypes', 'FFEnemyBuildings', 'FFEnemyBaseUnits', 'FFEnemyFortifications')]
    native_pads = set(rules['General'].get('PadAircraft', '').split(',')) - {''}
    pads = set(effective['General'].get('PadAircraft', '').split(',')) - {''}
    require(native_pads <= pads, 'Airfield capacity lost a native aircraft')
    for aliases in mappings:
        for original in native_pads & aliases.keys():
            require(aliases[original] in pads, f'Aircraft bypasses airfield capacity: {original}/{aliases[original]}')
    if pads != native_pads:
        require(preloads['rules'].get('General', {}).get('PadAircraft')
                == effective['General']['PadAircraft'], 'Airfield capacity list missing early preload')

    for power in rules['SuperWeaponTypes'].values():
        native = set(rules[power].get('EMPulse.Cannons', '').split(',')) - {''}
        cannons = set(effective[power].get('EMPulse.Cannons', '').split(',')) - {''}
        require(native <= cannons, f'Native EMPulse cannon lost: {power}')
        for aliases in mappings:
            for original in native & aliases.keys():
                require(aliases[original] in cannons, f'Private cannon cannot fire: {power}/{original}')
        if cannons != native:
            require(preloads['rules'].get(power, {}).get('EMPulse.Cannons')
                    == effective[power]['EMPulse.Cannons'], f'Cannon list missing early preload: {power}')

    groups = [(mappings[0], [country for _, country, _ in coalition(plan)]),
              (mappings[1], plan['enemy_countries'])]
    for aliases, countries in groups:
        for original in rules['BuildingTypes'].values():
            base = rules[original]
            host = base.get('PowersUpBuilding')
            if host not in aliases or not any(_eligible(base, country) for country in countries):
                continue
            require(original in aliases, f'Private generator lost its upgrade: {original}')
            alias = aliases[original]
            require(effective[alias].get('PowersUpBuilding') == aliases[host],
                    f'Upgrade cannot attach to private generator: {original}')
            require(preloads['rules'].get(alias, {}).get('PowersUpBuilding') == aliases[host],
                    f'Upgrade attachment missing early preload: {original}')


def audit_logistics(rows, effective, plan, rules, reviewed):
    """Inspect actual cargo, firing eligibility and structure conversion graphs."""
    from randomizer.final_fortress.utilities import supported_pairs
    from randomizer.final_fortress.player_perks import _eligible

    effects = plan['effects']
    capacity = effects.get('transport_capacity_stacks', 0)
    health = effects.get('infrastructure_health_percent', 0)
    open_topped = effects.get('open_topped', False)
    if not (capacity or health or open_topped):
        return
    aliases = rows.get('FFPlayerTypes', {})
    pairs = supported_pairs()
    buildings = set(rules['BuildingTypes'].values())
    technos = {kind for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')
               for kind in reviewed[category].values()}
    for original, base in reviewed.items():
        if original not in technos:
            continue
        alias = aliases.get(original, original)
        row = effective[alias]
        belongs = (original in aliases or _eligible(base, plan['player_country'])
                   or original in effects.get('special_access', []))
        if not belongs:
            continue
        if original in buildings:
            defense = base.get('IsBaseDefense', 'no').lower() == 'yes'
            production = base.get('Factory', '').lower() in ('buildingtype', 'infantrytype', 'unittype', 'aircrafttype')
            economy = (any(base.get(field, 'no').lower() == 'yes' for field in
                           ('Refinery', 'Grinding', 'Cloning', 'OrePurifier', 'FactoryPlant'))
                       or float(base.get('Power', '0')) > 0 or float(base.get('ProduceCashAmount', '0')) > 0)
            eligible = not defense and float(base.get('Strength', '0')) > 1 and (production or economy)
            if health and eligible:
                require(original in aliases and int(row['Strength']) == int(base['Strength']) * (100 + health) // 100,
                        f'Infrastructure health missing or applied twice: {original}')
                for field, value in base.items():
                    if field.startswith(('Factory', 'Prerequisite')) and field != 'PrerequisiteOverride':
                        require(row.get(field) == value, f'Infrastructure changed production gates: {original}.{field}')
                for field, value in rules['AI'].items():
                    if original in value.split(','):
                        require(alias in effective['AI'].get(field, value).split(','),
                                f'Helper AI cannot recognize private infrastructure: {original}.{field}')
                mobile = base.get('UndeploysInto')
                if mobile in reviewed:
                    require(mobile in aliases and row['UndeploysInto'] == aliases[mobile]
                            and effective[aliases[mobile]]['DeploysInto'] == alias,
                            f'Infrastructure conversion returns to native copies: {original}')
            elif health and not defense and original in aliases:
                require(row.get('Strength') == base.get('Strength'),
                        f'Infrastructure health affected a support/tech building: {original}')
            continue
        sealed = (base.get('InitialPayload.Types', '').lower() not in ('', 'none')
                  and base.get('NoManualEnter', 'no').lower() == 'yes'
                  and base.get('NoManualUnload', 'no').lower() == 'yes')
        cargo = int(base.get('Passengers', '0')) > 0 and base.get('Gunner', 'no').lower() != 'yes' and not sealed
        expected = int(base.get('Passengers', '0')) + (
            capacity if cargo and (original, 'passenger_capacity') in pairs else 0)
        require(int(row.get('Passengers', '0')) == expected,
                f'Transport capacity differs from reviewed eligibility: {original}')
        if open_topped and cargo and (original, 'open_topped') in pairs:
            require(original in aliases and row.get('OpenTopped', 'no').lower() == 'yes',
                    f'Reviewed open-topped transport cannot fire: {original}')
        else:
            require(row.get('OpenTopped') == base.get('OpenTopped'),
                    f'Open-topped perk changed an excluded/native transport: {original}')
        for field in ('Gunner', 'InitialPayload.Nums', 'NoManualEnter', 'NoManualUnload'):
            require(row.get(field) == base.get(field), f'Transport perk changed payload behavior: {original}.{field}')


def audit_utilities_and_challenges(rows, effective, plan, rules, preloads):
    """Inspect actual private utility types, enemy powers and Powerhouse teams."""
    from randomizer.final_fortress.enemy_powers import rewards_for
    from randomizer.final_fortress.utilities import supported_pairs
    from randomizer.config.tuning import stacked_self_heal_amount, stacking_amount

    effects = plan['effects']
    from randomizer.final_fortress.arsenal import reviewed_rules
    reviewed, _ = reviewed_rules(rules, set(effects.get('special_access', [])))
    pairs = supported_pairs()
    buildings = set(rules['BuildingTypes'].values())
    changed = dict(healing_stacks=0, recon_stacks=0, unique_limit_stacks=0, income_stacks=0)
    for original, alias in rows.get('FFPlayerTypes', {}).items():
        row, base = effective[alias], reviewed[original]
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
    audit_logistics(rows, effective, plan, rules, reviewed)
    # Gate/list additions are allowed on native identities; perk stats and
    # challenge power behavior must remain confined to private definitions.
    for original in (
            set(rules['InfantryTypes'].values()) | set(rules['VehicleTypes'].values())
            | set(rules['AircraftTypes'].values()) | buildings):
        for field in ('Strength', 'Sight', 'Sensors', 'SensorsSight', 'SelfHealing', 'SelfHealing.Amount',
                      'SelfHealing.Rate', 'BuildLimit', 'ProduceCashAmount', 'ProduceCashDelay',
                      'Passengers', 'OpenTopped', 'InitialPayload.Types', 'InitialPayload.Nums', 'Gunner'):
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
            require(power.get('ShowTimer', 'no') == rules[original].get('ShowTimer', 'no')
                    and power.get('SW.TimerVisibility', 'all') == rules[original].get('SW.TimerVisibility', 'all'),
                    f'Hostile power lost its native countdown visibility: {actor}.{original}')
            if plan.get('plan_version', 1) >= 31:
                require(power.get('EVA.Detected') == 'none' and power.get('Message.Detected') == 'NOSTR:',
                        'Hidden hostile provider announces a newly discovered superweapon building')
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
            require(any(effective.get(value.split(',')[1], {}).get('SuperWeapon') == alias
                        for value in rows['Structures'].values()), 'Enemy power has no real launch provider')
    require(len(rows.get('FFEnemyPowers', {})) == sum(map(len, expected_powers.values())),
            'Unexpected hostile power without a selected Challenge')
    native_sources = {alias: original for mapping in ('FFPlayerTypes', 'FFEnemyBuildings', 'FFEnemyFortifications')
                      for original, alias in rows.get(mapping, {}).items()}
    for original in rules['SuperWeaponTypes'].values():
        actual = dict(effective[original])
        # Native building ability routing appends private designators,
        # inhibitors and cannons. Check identities without treating them as buffs.
        for field in ('SW.Designators', 'SW.Inhibitors', 'EMPulse.Cannons'):
            native = rules[original].get(field)
            if native is not None and actual.get(field) != native:
                require({native_sources.get(kind, kind) for kind in actual[field].split(',')}
                        == set(native.split(',')), f'Native power targeting changed: {original}/{field}')
                actual[field] = native
        require(actual == rules[original], f'Native power changed by enemy Challenge: {original}')
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
                if plan.get('wave_priorities'):
                    early = {value.split(',')[1] for value in rows['FFWaveDispatches'].values()
                             if value.split(',')[-1] in ('early', 'fixed')}
                    teams = [effective[key] for key in early if effective[key] in teams]
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
    starting_only = plan.get('plan_version', 1) >= 30
    protected_yards = set(rows.get('FFEnemyStartingYards', {}).values())
    damage_fields = (*IMMUTABLE, 'LegalTarget', 'ThreatPosed', 'SpecialThreatValue')
    for original, alias in rows.get('FFEnemyBuildings', {}).items():
        require(alias in preloads['rules'], f'Enemy building missing early preload: {original}')
        if starting_only:
            require(all(effective[alias].get(key) == rules[original].get(key) for key in damage_fields),
                    f'Ordinary enemy construction gained immunity or lost normal targeting: {original}')
        else:
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
        if starting_only or yard.get('ConstructionYard', 'no').lower() != 'yes':
            require(all(effective[alias].get(key) == rules[original].get(key) for key in damage_fields),
                    f'Ordinary enemy docking/deploying unit gained immunity or lost targeting: {original}')
        if starting_only:
            require(effective[alias].get('DeploysInto') not in protected_yards,
                    'Produced enemy MCV can deploy into a protected starting yard')
    for actor, country in zip(sorted(enemies), plan['enemy_countries']):
        require(effective[actor].get('StartInMultiplayer.WithConst') == 'yes',
                'Enemy does not start with a protected construction yard')
        starting_yard = next(kind for kind in effective['AI']['BuildConst'].split(',')
                             if _eligible(effective[kind], actor))
        require(starting_yard in (protected_yards if starting_only else rows['FFEnemyBuildings'].values())
                and effective[starting_yard]['Immune'] == 'yes',
                'Enemy construction-yard start can select a destructible native yard')
        native = next(kind for kind in rules['VehicleTypes'].values() if _eligible(rules[kind], country)
                      and rules.get(rules[kind].get('DeploysInto'), {}).get('ConstructionYard', 'no').lower() == 'yes')
        alias = rows['FFEnemyBaseUnits'][native]
        require(actor in effective[alias]['RequiredHouses'].split(','), 'Enemy MCV belongs to the wrong country')
        if starting_only:
            require(effective[alias].get('Immune', 'no').lower() == 'no'
                    and effective[alias].get('LegalTarget', 'yes').lower() == 'yes',
                    'Produced enemy MCV is invincible or cannot be targeted')
        else:
            require(effective[alias]['Immune'] == 'yes', 'Legacy enemy MCV lost its frozen immunity')
        yard = effective[alias]['DeploysInto']
        require(yard in rows['FFEnemyBuildings'].values(), 'Enemy MCV lost its own expansion yard')
        if starting_only:
            require(yard not in protected_yards and effective[yard].get('Immune', 'no').lower() == 'no'
                    and effective[yard].get('LegalTarget', 'yes').lower() == 'yes',
                    'Produced enemy MCV deploys into an invincible or untargetable expansion yard')
        else:
            require(effective[yard]['Immune'] == 'yes', 'Legacy enemy MCV lost its frozen yard immunity')
        for power in effective[actor].get('AI.PowerPlants', '').split(','):
            if power:
                require(power in rows['FFEnemyBuildings'].values(), 'Enemy AI requests a native unprotected power plant')
    if starting_only:
        require(protected_yards and not protected_yards & set(rows['FFEnemyBuildings'].values()),
                'Starting yards share identities with ordinary produced yards')
        require('FFEnemyStartingYards' not in preloads['rules'], 'Starting-yard audit metadata leaked into rules')
        for alias in protected_yards:
            row = effective[alias]
            require(alias in preloads['rules'] and all(row.get(key) == value for key, value in IMMUTABLE.items())
                    and row['LegalTarget'] == 'no' and row['TechLevel'] == '-1' and row['BuildLimit'] == '1'
                    and row['AIBuildThis'] == 'no'
                    and row['UndeploysInto'].lower() == 'none',
                    'Protected starting yard can be produced, packed up, targeted or destroyed')
        for original, yard in rows['FFEnemyStartingYards'].items():
            for kind, alias in rows['FFEnemyBuildings'].items():
                if original in rules[kind].get('Prerequisite', '').split(','):
                    require(any(yard in value.split(',') for field, value in effective[alias].items()
                                if field == 'Prerequisite' or field.startswith('Prerequisite.List')),
                            f'Protected starting yard cannot unlock normal construction: {kind}')
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
            require(terrain.clear({(p['x'], p['y'])}), f'Camp crate cell is obstructed: {camp["id"]}')
            require(terrain.clear(cells, allowed_overlays=resource_overlay_indices(rules)),
                    f'Camp guards/crate are inaccessible or outside bounds: {camp["id"]}')
            locations.append(terrain.bounds.project(p['x'], p['y'], terrain.heights[(p['x'], p['y'])]))
            _, tag, _, _ = rows['FFCampTracking'][camp['id']].split(',')
            guards = [value.split(',') for category, field in (('Infantry', 8), ('Units', 7))
                      for value in rows.get(category, {}).values() if value.split(',')[field] == tag]
            require(len(guards) == count and all(guard[6] == 'Area Guard' for guard in guards),
                    'Camp garrison is missing or has global attack orders')
            require({(int(g[3]),int(g[4])) for g in guards}
                    == {(v['x'],v['y']) for v in guard_positions(camp)}, 'Camp ignores reviewed guard positions')
            if not plan.get('coop_players'):
                claim = next(key for key, value in rows['Triggers'].items()
                             if value.split(',')[2] == 'Camp ' + camp['id'] + ' claim'
                             + (' FFPLAYER' if plan.get('plan_version', 1) >= 32 else ''))
                require(f'1,0,{4475 + plan["map"]["player_waypoint"]}' in rows['Events'][claim],
                        'Camp reward is not restricted to the human start house')
                tag = rows['CellTags'][str(p['y'] * 1000 + p['x'])]
                linked = rows['Tags'][tag].split(',')[2]
                chain = set()
                while linked in rows['Triggers'] and linked not in chain:
                    chain.add(linked)
                    linked = rows['Triggers'][linked].split(',')[1]
                require(claim in chain, 'Camp crate cell is not connected to reward claim')
            if plan.get('plan_version',1) >= 18:
                balance=plan['camp_balance']
                starter = balance.get('starter_camps') if plan.get('plan_version', 1) >= 21 else None
                is_starter = bool(starter and camp['id'] in starter['camp_ids'])
                profile = starter if is_starter else balance
                ceiling = starter['max_guards_by_difficulty'][plan['difficulty']] if is_starter else balance['max_guards_per_camp']
                require(count == min(profile['guards_by_difficulty'][plan['difficulty']]*plan['wave_multiplier'],
                                     ceiling,balance['max_guards_per_camp'],balance['max_total_guards']//len(plan['map']['camps'])),
                        'Camp population ignores difficulty, multiplier or shared limits')
                if plan.get('plan_version', 1) >= 21:
                    require(camp['starter_camp'] == is_starter, 'Starter camp classification is not frozen correctly')
                if is_starter:
                    require(camp['special_unit'] is None and camp['composition_id'] == 'starter_infantry',
                            'Starter camp rolled a heavy, hero or advanced wave formation')
                    pool = {unit['type'] for unit in starter['units_by_country'][camp['guard_country']]}
                    require(all(unit['type'] in pool and unit['type'] in rules['InfantryTypes'].values()
                                and int(rules[unit['type']]['TechLevel']) == 1 for unit in camp['guards']),
                            'Starter camp contains something other than configured basic infantry')
                    require(count < min(balance['guards_by_difficulty'][plan['difficulty']]*plan['wave_multiplier'],
                                        balance['max_guards_per_camp'],balance['max_total_guards']//len(plan['map']['camps'])),
                            'Starter camp is not smaller than outer camps')
                if plan.get('plan_version', 1) >= 19:
                    require(camp['guard_country'] in SIDE_COUNTRIES, 'Camp uses an unknown faction roster')
                else:
                    require(camp['guard_country'] == plan['enemy_countries'][camp['enemy_index']], 'Camp uses foreign faction guards')
                require(camp['special_unit'] is None or any(u['type']==camp['special_unit'] for u in camp['guards']),
                        'Camp lost its selected special unit')
                pickup = plan.get('plan_version', 1) >= 25
                cleared = next(key for key,value in rows['Triggers'].items()
                               if value.split(',')[2] == 'Camp '+camp['id']+(' ready' if pickup else ' cleared'))
                clear_actions=parse_action_groups(rows['Actions'][cleared])[1]
                clear_markers=[effective[a[2]]['Name'] for a in clear_actions if a[0]=='4']
                if pickup:
                    require(not clear_markers and 'camp_clear:'+camp['id'] not in plan['gem_rewards'],
                            'Camp startup awards points before player pickup')
                    require(plan['gem_rewards']['camp:'+camp['id']]==camp['gems'],
                            'Camp pickup does not award its Defensive Points')
                else:
                    require(len(clear_markers)==1 and clear_markers[0].startswith('MFF_'), 'Camp clear has no durable Defensive Points receipt')
                    require(plan['gem_rewards']['camp_clear:'+camp['id']]==camp['gems']
                            and plan['gem_rewards']['camp:'+camp['id']]==0, 'Camp Defensive Points still require crate collection')
                require(any(a[0]=='108' for a in clear_actions), 'Camp has no random reward crate')
        if plan.get('plan_version', 1) >= 19:
            families = [SIDE_FAMILIES[SIDE_COUNTRIES.index(camp['guard_country'])] for camp in plan['map']['camps']]
            require(len(set(families[:4])) == 4 and max(families.count(family) for family in set(families)) <= 2,
                    'Camp roster selection omits or overrepresents a faction')
        anchor = plan['map'].get('camps_below_waypoint')
        if anchor is not None:
            cell = int(rows['Waypoints'][str(anchor)])
            x, y = cell % 1000, cell // 1000
            u, v = terrain.bounds.project(x, y, terrain.heights[(x, y)])
            require(len(locations) == 6 and all(cy > v and abs(cx - u) < terrain.bounds.width_local / 4
                                                for cx, cy in locations),
                    'Camps are not below the configured reference start')
        elif plan['map'].get('camp_minimum_spacing'):
            require(len(locations) == 6
                    and max(x for x, y in locations) - min(x for x, y in locations) > .6 * terrain.bounds.width_local
                    and max(y for x, y in locations) - min(y for x, y in locations) > .3 * terrain.bounds.height_local,
                    'Southern camps are not spread across the playable approaches')
        else:
            require(len(locations) == 6 and max(x for x, y in locations) - min(x for x, y in locations)
                    > .65 * terrain.bounds.width_local
                    and max(y for x, y in locations) - min(y for x, y in locations) > .6 * terrain.bounds.height_local,
                    'Camps do not span the playable map')


def audit_generator_access(rows, effective, plan, terrain):
    """Review actual native utility foundations, exits and flat arrival routes."""
    if plan.get('plan_version', 1) < 37:
        return
    # Inspect emitted foundations and transfer ownership independently of
    # the launch-time clearance validation and configured generator list.
    from randomizer.final_fortress.placement import installed_art
    art = installed_art()
    access = set()
    friendly_generators = []
    for actor, country, waypoint in coalition(plan):
        layout = perk_layout(plan['map'], waypoint, country)
        p = layout['units']
        access.update((p['x'] + dx, p['y'] + dy)
                      for dx in range(-2, 7) for dy in range(-2, 5))
        production = {(p['x'], p['y']) for p in layout['buildings'][1:
                      len(plan['effects'].get('starting_buildings', []))]}
        triggers = {key for key, value in rows['Triggers'].items()
                    if value.split(',')[2] == 'Starting perks ' + actor}
        tags = {key for key, value in rows['Tags'].items() if value.split(',')[2] in triggers}
        start = int(rows['Waypoints'][str(waypoint)])
        for value in rows['Structures'].values():
            fields = value.split(',')
            if fields[6] not in tags:
                continue
            row = effective[fields[1]]
            x, y = map(int, fields[3:5])
            cells = {(x + dx, y + dy) for dx, dy in footprint(row, art)}
            if int(row.get('Power', '0')) > 0:
                friendly_generators.append((actor, cells))
                require((x - start % 1000) ** 2 + (y - start // 1000) ** 2 <= 19 ** 2,
                        f'Generator detached from its MCV: {actor} at {(x, y)}')
            elif (x, y) in production:
                access.update((cx + dx, cy + dy) for cx, cy in cells
                              for dx in range(-1, 2) for dy in range(-1, 2))
    require(all(not cells & access for actor, cells in friendly_generators),
            'Friendly generator blocks a production exit or reinforcement apron')
    if terrain is not None:
        from collections import deque
        blocked = set()
        for value in rows['Structures'].values():
            fields = value.split(',')
            row = dict(effective.get(fields[1], {}))
            if row.get('IsPassable', 'no').lower() == 'yes':
                continue
            row.setdefault('Image', fields[1])
            x, y = map(int, fields[3:5])
            blocked.update((x + dx, y + dy) for dx, dy in footprint(row, art))
        for actor, country, waypoint in coalition(plan):
            p = perk_layout(plan['map'], waypoint, country)['units']
            start = int(rows['Waypoints'][str(waypoint)])
            cx, cy = start % 1000, start // 1000
            pending = deque([(p['x'] + 2, p['y'] + 1)])
            visited = set(pending)
            escaped = False
            while pending:
                x, y = pending.popleft()
                if (x - cx) ** 2 + (y - cy) ** 2 > 22 ** 2:
                    escaped = True
                    break
                for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if (cell not in visited and cell not in blocked and terrain.clear({cell})
                            and terrain.heights[cell] == terrain.heights[(x, y)]):
                        visited.add(cell)
                        pending.append(cell)
            require(escaped, f'Reinforcement apron has no walkable exit beyond generators: {actor}')


def audit_arrival_fixes(rows, effective, plan, rules, preloads, terrain):
    """Inspect production shortcuts, reserved ground and explicit helper orders."""
    if plan.get('plan_version', 1) < 14:
        return
    audit_generator_access(rows, effective, plan, terrain)
    if plan.get('plan_version', 1) >= 15:
        from math import atan2, hypot, pi, tau
        for actor, _, waypoint in coalition(plan):
            cell = int(rows['Waypoints'][str(waypoint)])
            center = (cell % 1000, cell // 1000)
            layout = perk_layout(plan['map'], waypoint, plan['player_country'])
            if plan.get('plan_version', 1) >= 33:
                count = 8 if len(layout['defenses']) == 32 else 4
                if plan.get('plan_version', 1) >= 35:
                    require(count == 8, f'Defense layout still has four-turret batteries: {actor}')
                for index in range(0, len(layout['defenses']), count):
                    group = layout['defenses'][index:index + count]
                    angles = sorted(atan2(p['y'] - center[1], p['x'] - center[0]) % tau for p in group)
                    gap = max(b - a for a, b in zip(angles, [*angles[1:], angles[0] + tau]))
                    require(len(group) == count and (gap <= pi / 2 if count == 8 else gap < pi),
                            f'Defense rank {index // count + 1} does not cover the full perimeter of {actor}')
                    require(all((6 if count == 8 else 8) <= hypot(p['x'] - center[0], p['y'] - center[1]) <= 32 for p in group),
                            f'Defense ring is inside deployment space or detached from {actor}')
                if plan.get('plan_version', 1) >= 35:
                    kinds = plan['effects'].get('defense_types', [])
                    rank = plan.get('perk_ranks', {}).get('starting_defenses', 0)
                    require(len(kinds) == rank * 8, f'Wrong unlocked defense density for {actor}')
                    positions = {(p['x'], p['y']) for p in layout['defenses']}
                    actual = [value.split(',') for value in rows['Structures'].values()
                              if tuple(map(int, value.split(',')[3:5])) in positions]
                    expected = {(rows.get('FFPlayerTypes', {}).get(kind, kind), p['x'], p['y'])
                                for kind, p in zip(kinds, layout['defenses'])}
                    require(len(actual) == len(kinds)
                            and {(f[1], int(f[3]), int(f[4])) for f in actual} == expected,
                            f'Placed defenses do not match unlocked full rings for {actor}')
                    transfers = {key for key, value in rows['Triggers'].items()
                                 if value.split(',')[2] == 'Starting perks ' + actor}
                    tags = {key for key, value in rows['Tags'].items() if value.split(',')[2] in transfers}
                    require(all(f[6] in tags for f in actual), f'Defense ring has incorrect ownership: {actor}')
            else:
                require(all(hypot(p['x'] - center[0], p['y'] - center[1]) >= 20
                            for p in layout['defenses']), f'Defense still occupies the central base: {actor}')
            if plan.get('plan_version', 1) < 33 and actor == 'FFPLAYER' and plan['map']['id'] == 'miners_in_the_sun':
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
    if plan.get('reinforcement_schedule') or plan['effects'].get('lab_reserve_units'):
        kind = pads.get('Type')
        require(kind in preloads['rules'], 'Reserved reinforcement ground missing early rules preload')
        row = effective[kind]
        for field, value in {'Image': 'CABHUT', 'IsPassable': 'yes', 'Immune': 'yes',
                             'InvisibleInGame': 'yes', 'BaseNormal': 'no', 'KeepAlive': 'no',
                             'Capturable': 'no', 'Unsellable': 'yes', 'BridgeRepairHut': 'no',
                             'DontScore': 'yes', 'ProduceCashAmount': '0'}.items():
            require(row.get(field) == value, f'Unsafe reinforcement reservation {field}')
        actual = [value.split(',') for value in rows['Structures'].values() if value.split(',')[1] == kind]
        marker = pads.get('MarkerType')
        markers = [value.split(',') for value in rows['Structures'].values() if value.split(',')[1] == marker]
        if plan.get('plan_version', 1) >= 33:
            require(marker is None, 'Spawn visibility still depends on a building graphic')
        expected = set()
        for actor, _, waypoint in coalition(plan):
            p = plan['map']['perk_layouts'][str(waypoint)]['units']
            require(pads[actor] == str(p['y'] * 1000 + p['x']), 'Reservation detached from arrival waypoint')
            expected.update((p['x'] + dx, p['y'] + dy) for dx in range(5) for dy in range(3))
        if plan.get('plan_version', 1) >= 16:
            for p in plan['map']['enemy_wave_positions'].values():
                expected.update((p['x'] + dx, p['y'] + dy) for dx in range(5) for dy in range(3))
        from randomizer.final_fortress.placement import installed_art
        art = installed_art()
        require(reserved_arrival_cells(rows, effective, art, {kind, marker}) == expected,
                'Reinforcement apron can be built over')
        require(all(v[0] == 'Neutral' and v[6] == 'None' for v in [*actual, *markers]),
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
        if human_actor(plan, actor):
            continue
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
        slot, team, chunk, following, *phase = value.split(',')
        by_chunk[chunk].append((gate, slot, team, following, phase[0] if phase else 'early'))
    actual = defaultdict(Counter)
    for chunk, deliveries in by_chunk.items():
        wave, house, count = rows['FFWaveChunks'][chunk].split(',')
        expected_units = {}
        for gate, slot, team, following, phase in deliveries:
            owner, capacity, busy, _ = pools[slot].split(',')
            event = f'2,37,0,{busy},37,0,{finished}'
            if plan.get('wave_priorities') and phase != 'fixed':
                event = f'3,37,0,{busy},37,0,{finished},{36 if phase == "late" else 37},0,{rows["FFWavePriority"]["Late"]}'
            require(rows['Events'][gate] == event, 'Dispatch ignores occupancy, elapsed priority phase or run end')
            require(rows['Triggers'][gate].split(',')[3] == '1', 'Future wave delivery starts early')
            actions = parse_action_groups(rows['Actions'][gate])[1]
            expected = [_action(54, trigger=other[0]) for other in deliveries]
            expected += [_action(56, int(busy)),
                         _action(80, team=team, waypoint=effective[team]['Waypoint']),
                         _action(53, trigger=following)]
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
            if phase not in expected_units:
                expected_units[phase] = units
            require(units == expected_units[phase], 'Available slot changes the wave roster')
        actual[(int(wave), house)].update(expected_units['early' if 'early' in expected_units else 'fixed'])
        if plan.get('wave_priorities'):
            from randomizer.final_fortress.wave_priority import priority
            policy = plan['wave_priorities']
            if plan['wave_schedule'][int(wave) - 1]['seconds'] >= policy['late_seconds']:
                require(set(expected_units) == {'fixed'}, 'Already-late delivery has redundant phase copies')
            else:
                require(set(expected_units) == {'early', 'late'}, 'Queued delivery has no elapsed-time upgrade path')
            if 'late' in expected_units and int(count) >= 10:
                # Late replacements must favor advanced/special units even
                # when the queue is still delivering the opening wave.
                require(sum(n for kind, n in expected_units['late'].items() if priority(kind, policy)) >= int(count) // 2,
                        f'Capacity-delayed delivery is still dominated by low-tier units: '
                        f'wave {wave}, {house}, {dict(expected_units["late"])}')
    if plan.get('wave_priorities'):
        policy = plan['wave_priorities']
        late = rows['FFWavePriority']['Late']
        triggers = [k for k, v in rows['Triggers'].items() if v.split(',')[2] == 'Late enemy delivery priorities']
        require(len(triggers) == 1 and rows['Events'][triggers[0]] == f'1,13,0,{policy["late_seconds"]}'
                and rows['Triggers'][triggers[0]].split(',')[3] == '0'
                and parse_action_groups(rows['Actions'][triggers[0]])[1] == [_action(56, int(late))],
                'Late priorities depend on queue progress instead of absolute simulation time')
    for index,wave in enumerate(plan['wave_schedule'],1):
        for group in wave['groups']:
            require(actual[(index,group['house'])] == Counter({u['type']:u['count'] for u in group['units']}),
                    'Chunked wave lost or duplicated configured units')
            if plan.get('wave_priorities'):
                policy = plan['wave_priorities']
                stage = next((s for s in reversed(policy['stages']) if s['from_seconds'] <= wave['seconds']), None)
                if stage:
                    ground = [u for u in group['units'] if u['type'] not in group.get('air_types', [])]
                    low = [u for u in ground if not priority(u['type'], policy)]
                    high = [u for u in ground if priority(u['type'], policy)]
                    if high:
                        total = sum(u['count'] for u in ground)
                        minimum = min(total - len(low), total * (stage['advanced_percent'] + stage['special_percent']) // 100)
                        require(sum(u['count'] for u in high) >= minimum, 'Late wave lost its advanced-unit share')
                if wave['seconds'] >= policy['late_seconds']:
                    # Actual serialized ground batches must place every heavy
                    # before weaker units, so a full cap cannot admit T1 first.
                    sequence = []
                    for chunk, deliveries in by_chunk.items():
                        if rows['FFWaveChunks'][chunk].split(',')[:2] != [str(index), group['house']]:
                            continue
                        _, slot, team, _, _ = next(d for d in deliveries if d[-1] == 'fixed')
                        inverse = {v: k for k, v in rows['FFWavePoolTypes.' + slot].items()}
                        kinds = [inverse[v.split(',')[1]] for k, v in effective[effective[team]['TaskForce']].items() if k.isdigit()]
                        sequence.extend(priority(kind, policy) for kind in kinds if kind not in group.get('air_types', []))
                    require(sequence == sorted(sequence, reverse=True), 'Low-tier deliveries precede waiting heavy units')
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
    from randomizer.final_fortress.placement import installed_art
    art = installed_art()
    marker = rows['FFEnemyWavePads'].get('MarkerType')
    placed = reserved_arrival_cells(rows, effective, art, {pad, marker})
    if plan.get('plan_version', 1) >= 33:
        require(marker is None, 'Spawn visibility still depends on a building graphic')
        scorch = {(int(fields[1]), int(fields[2])) for value in rows.get('Smudge', {}).values()
                  if (fields := value.split(','))[0] == 'BURNT01'}
        require(not placed & scorch, 'Spawn markers still use scorch decals')
    else:
        marked = {(int(fields[1]), int(fields[2])) for value in rows.get('Smudge', {}).values()
                  if (fields := value.split(','))[0] == 'BURNT01'}
        require(placed <= marked, 'Reserved arrival cells have no visible ground marking')
    for index,wp in enumerate(plan['map']['enemy_waypoints']):
        p = plan['map']['enemy_wave_positions'][str(wp)]
        cells = {(p['x']+dx,p['y']+dy) for dx in range(5) for dy in range(3)}
        require(cells <= placed, 'AI can build over its wave arrival position')
        require(int(rows['Waypoints'][str(16+index)]) == (p['y']+1)*1000+p['x']+2, 'Wrong enemy spawn waypoint')
        base = int(rows['Waypoints'][str(wp)])
        friends = [int(rows['Waypoints'][str(point)]) for point in (
            plan['map']['player_waypoint'], *plan.get('allied_waypoints', []))]
        require(all(max(abs(x - base % 1000), abs(y - base // 1000)) <= 16
                    and all(max(abs(x - friend % 1000), abs(y - friend // 1000)) >= 32
                            for friend in friends) for x, y in cells),
                'Enemy wave apron is detached from its own base or intrudes into a friendly base')
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


def audit_friendly_pools(rows, effective, plan, *, finished_name, preloads):
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
            if plan.get('plan_version', 1) >= 36:
                category = 'InfantryTypes' if alias in effective['InfantryTypes'].values() else 'VehicleTypes'
                registered = list(dict.fromkeys(effective[category].values()))
                require(registered.index(alias) < 512, 'Friendly survivor counter exceeds native type capacity')
                require(alias in preloads['rules'], 'Friendly survivor identity is not preloaded')
                for field in ('Image', 'Strength', 'Primary', 'Secondary',
                              'Convert.Deploy', 'Convert.Land', 'Convert.Water'):
                    require(preloads['rules'][alias].get(field) == row.get(field),
                            f'Friendly reinforcement buff/conversion was not preloaded: {alias}.{field}')
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
            expected += [_action(56,int(busy)),
                         _action(80,team=team,waypoint=effective[team]['Waypoint']),
                         _action(53,trigger=following)]
            require(parse_action_groups(rows['Actions'][gate])[1] == expected, 'Friendly group can double-spawn')
            require(parse_action_groups(rows['Actions'][chunk])[1] == [_action(53,trigger=d[0]) for d in deliveries],
                    'Friendly relay omits available pool slots')
            row = effective[team]
            require(row['House'] == owner and row['VeteranLevel'] == str(effect.get('veterancy',0)+1),
                    'Wrong friendly ownership or Veteran/Elite rank')
            helper = not human_actor(plan, owner)
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
            if human_actor(plan, owner):
                notice=triggers[f'Friendly arrival {index} {owner} capacity notice']
                reminder=triggers[f'Friendly arrival {index} {owner} capacity reminder']
                timer_actions=parse_action_groups(rows['Actions'][timer])[1]
                for key in (notice, reminder):
                    require(_action(53,trigger=key) in timer_actions
                            and _action(54,trigger=key) in actions, 'Missing friendly cap notice lifecycle')
                waiting=['37','0',str(finished), *[token for v in pools.values()
                         for token in ('36','0',v.split(',')[2])]]
                require(rows['Events'][notice] == ','.join([str(len(pools)+1),*waiting])
                        and rows['Events'][reminder] == ','.join([str(len(pools)+2),'13','0','30',*waiting]),
                        'Capacity notices do not reflect the shared pool')
                require(any(v == f'2,Friendly arrival {index} {owner} capacity reminder,{reminder}'
                            for v in rows['Tags'].values()), 'Capacity reminder does not repeat')
                notice_actions=parse_action_groups(rows['Actions'][notice])[1]
                require(notice_actions == parse_action_groups(rows['Actions'][reminder])[1]
                        and any(a[0]=='11' and 'capacity' in a[2] for a in notice_actions)
                        and any(a[0]=='11' and str(effect['max_active_units']) in a[2] for a in notice_actions),
                        'Capacity notice omits its reason or shared limit')
            if plan.get('plan_version', 1) >= 29 and human_actor(plan, owner):
                require(any(a[0] == '11' and a[2].startswith('NOSTR:Player ') for a in actions)
                        and any(a[0] == '11' and 'reinforcements' in a[2] for a in actions),
                        'Friendly deliveries have no visible arrival confirmation')
            if owner in rows.get('FFAlliedClocks', {}):
                clock = rows[rows['FFAlliedClocks'][owner]]
                flag = clock['Restart' if index < len(plan['reinforcement_schedule']) else 'Finished']
                require(_action(56, int(flag)) in actions,
                        'Allied countdown advances before full delivery or stays after its last arrival')


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
    position = plan['map'].get('wave_clock_position', {'x': 113, 'y': 71})
    require(len(placed)==1 and placed[0][3:5]==[str(position['x']), str(position['y'])],
            'Wave clock provider overlaps another reserved area')
    require(rows['Events'][clock['Remove']] == f'1,36,0,{clock["Finished"]}'
            and parse_action_groups(rows['Actions'][clock['Remove']])[1]
                == [_action(54,trigger=clock['Remove']),_action(32)]
            and rows['Tags'][placed[0][6]] == f'2,Wave clock remove,{clock["Remove"]}',
            'Wave countdown remains after the final wave')


def audit_allied_clocks(rows, effective, plan, preloads):
    """Review owner-local display clocks and their native ownership/removal paths."""
    from randomizer.final_fortress.engine import _action
    clocks = rows.get('FFAlliedClocks', {})
    expected = {actor: start for actor, _, start in coalition(plan)
                if human_actor(plan, actor)} if plan.get('plan_version', 1) >= 31 and plan['reinforcement_schedule'] else {}
    require(set(clocks) == set(expected), 'Allied countdown missing, unpurchased, or granted to an AI helper')
    powers = list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
    for owner, metadata in clocks.items():
        require(metadata not in preloads['rules'] and 'FFAlliedClocks' not in preloads['rules'],
                'Allied clock metadata leaked into early rules')
        clock = rows[metadata]
        power, provider = clock['Power'], clock['Provider']
        require(power in preloads['rules'] and provider in preloads['rules'], 'Allied countdown lacks early registration')
        row = effective[power]
        require(row['UIName'] == 'NOSTR:Next allied reinforcements'
                and float(row['RechargeTime']) * 60 == plan['effects']['reinforcements']['first_seconds']
                and row['ShowTimer'] == 'yes' and row['SW.TimerVisibility'] == 'owner'
                and row['SW.RequiredHouses'] == owner and clock['Owner'] == owner,
                'Allied countdown has wrong timing, visibility or owner')
        require(all(row.get(field) == value for field, value in {
            'Type': 'GenericWarhead', 'SW.ShowCameo': 'no', 'SW.AutoFire': 'yes',
            'SW.ManualFire': 'no', 'SW.AITargeting': 'None', 'SW.Damage': '0',
            'EVA.Ready': 'none', 'EVA.Activated': 'none', 'EVA.Detected': 'none',
            'Message.Detected': 'NOSTR:', 'SW.ActivationSound': 'none'}.items()),
            'Allied display clock causes combat, alerts or a sidebar button')
        require(powers[int(clock['Index'])] == power, 'Allied clock reset addresses another power')
        actions = parse_action_groups(rows['Actions'][clock['Reset']])[1]
        expected_reset = []
        effect = plan['effects']['reinforcements']
        if effect['first_seconds'] != effect['interval_seconds']:
            expected_reset.append(['132', '11', clock['Index'], '0', '0', '0', '0', str(effect['interval_seconds'] * 15)])
        require(actions == [*expected_reset, _action(134, int(clock['Index'])), _action(57, int(clock['Restart']))]
                and rows['Triggers'][clock['Reset']].split(',')[0] == owner,
                'Allied countdown reset changes another player or ignores its interval')
        placed = [value.split(',') for value in rows['Structures'].values() if value.split(',')[1] == provider]
        require(len(placed) == 1 and effective[provider]['SuperWeapon'] == power
                and effective[provider]['Immune'] == effective[provider]['IsPassable'] == 'yes'
                and effective[provider]['Power'] == '0' and effective[provider]['EVA.Lost'] == 'none',
                'Allied countdown has no harmless, independent provider')
        tag = placed[0][6]
        require(rows['Tags'][tag].split(',')[-1] == clock['Remove']
                and rows['Events'][clock['Remove']] == f'1,36,0,{clock["Finished"]}'
                and parse_action_groups(rows['Actions'][clock['Remove']])[1]
                == [_action(54, trigger=clock['Remove']), _action(32)],
                'Allied countdown outlives final delivery or survival end')
        transfer = rows['Triggers'][clock['Remove']].split(',')[1]
        require(parse_action_groups(rows['Actions'][transfer])[1]
                == [_action(14, 4475 + expected[owner]), _action(54, trigger=transfer)],
                'Allied countdown is transferred to the wrong player')


def audit_pickup_reward(rows, effective, plan, camp, ready):
    """Inspect every collector's pickup and complete frozen reward composition."""
    from collections import Counter
    from randomizer.final_fortress.engine import _action, _waypoint
    startup = parse_action_groups(rows['Actions'][ready])[1]
    require(not any(a[0] in ('4', '7', '80', '11') for a in startup),
            'Camp startup delivers a reward or announces a false clearance')
    enabled = {a[2] for a in startup if a[0] == '53'}
    actors = (coalition(plan) if plan.get('plan_version', 1) >= 32 else
              coalition(plan)[:len(plan.get('coop_players', [])) or 1])
    if plan.get('plan_version', 1) >= 39:
        actors = [*actors, *[(f'FFENEMY{i + 1}', country, start)
                  for i, (country, start) in enumerate(zip(
                      plan['enemy_countries'], plan['map']['enemy_waypoints']))]]
    tag = rows['CellTags'][str(camp['position']['y'] * 1000 + camp['position']['x'])]
    linked = rows['Tags'][tag].split(',')[2]
    chain = set()
    while linked in rows['Triggers']:
        require(linked not in chain, 'Camp pickup trigger cycle')
        chain.add(linked)
        linked = rows['Triggers'][linked].split(',')[1]
    require(chain == enabled and len(chain) == len(actors),
            'Camp cell does not enable and link every eligible collector exactly once')
    expected = Counter({rows.get('FFPlayerTypes', {}).get(unit['type'], unit['type']): unit['count']
                        for unit in camp['crate_reward']['units']})
    waypoint = _waypoint(20 + plan['map']['camps'].index(camp))
    shared_claim = None
    for actor, _, start in actors:
        chain = plan.get('coop_players') or plan.get('plan_version', 1) >= 32
        name = 'Camp ' + camp['id'] + ' claim' + (' ' + actor if chain else '')
        claim = next(key for key, value in rows['Triggers'].items() if value.split(',')[2] == name)
        require(claim in enabled and rows['Triggers'][claim].split(',')[3] == '1',
                'Camp pickup is not enabled exactly by its startup gate')
        require(f'1,0,{4475 + start}' in rows['Events'][claim], 'Camp pickup belongs to another collector')
        actions = parse_action_groups(rows['Actions'][claim])[1]
        if plan.get('plan_version', 1) >= 32:
            shared = actions[0][2]
            require(actions[0][0] == '56' and f'37,0,{shared}' in rows['Events'][claim],
                    'Camp pickup can repeat its reward')
            if shared_claim is None:
                shared_claim = shared
            require(shared == shared_claim, 'Collectors can claim the same camp more than once')
            if camp['crate_reward']['credits']:
                selectors = {a[2] for a in actions if a[0] == '56' and a[2] != shared}
                recipient_start = start if human_actor(plan, actor) else plan['map']['player_waypoint']
                cash = [key for key, value in rows['Events'].items()
                        if any(value == '1,36,0,' + flag for flag in selectors)]
                require(len(cash) == 1 and parse_action_groups(rows['Actions'][cash[0]])[1]
                        == [_action(14, 4475 + recipient_start)],
                        'Crate cash is delivered to the helper or another player')
        require(any(a[0] == '4' and effective[a[2]]['Name'].startswith('MFF_') for a in actions),
                'Camp pickup has no durable receipt')
        # The durable camp receipt drives the existing collection total and
        # Defensive Points. AI pickups must emit that same receipt once.
        run_prefix = next(effective[a[2]]['Name'].split('_E')[0] for a in actions if a[0] == '4')
        receipt = run_prefix + '_E' + hashlib.sha256(('camp:' + camp['id']).encode()).hexdigest()[:8]
        require(sum(a[0] == '4' and effective[a[2]]['Name'] == receipt for a in actions) == 1,
                'Camp pickup omits or duplicates its collection/Defensive Points receipt')
        if plan.get('coop_players'):
            slot = next(i for i, friend in enumerate(coalition(plan)) if friend[0] == actor) if human_actor(plan, actor) else 0
            recipient_receipt = run_prefix + '_E' + hashlib.sha256(
                f'camp_pick:{slot}:{camp["id"]}'.encode()).hexdigest()[:8]
            require(sum(a[0] == '4' and effective[a[2]]['Name'] == recipient_receipt for a in actions) == 1,
                    'Camp pickup omits or duplicates its human recipient receipt')
        require(not any(a[0] in ('7', '108') for a in actions),
                'Camp pickup uses implicit placement or creates a second crate')
        delivered = Counter()
        for action in actions:
            if action[0] != '80':
                continue
            team = effective[action[2]]
            recipient = actor if human_actor(plan, actor) else 'FFPLAYER'
            require(team['House'] == (recipient if needs_countries(plan) else plan['player_country']),
                    'Camp squad belongs to another player')
            require(action[7] == team['Waypoint'] == waypoint, 'Camp squad has no explicit arrival cell')
            units = [value.split(',') for key, value in effective[team['TaskForce']].items() if key.isdigit()]
            require(len(units) == 1, 'Camp reward still relies on a mixed reinforcement team')
            for count, kind in units:
                delivered[kind] += int(count)
        require(delivered == expected, 'Camp squad omits part of its frozen reward')


def audit_feedback_fixes(rows, effective, plan, rules, preloads):
    """Review emitted camp pickups and the actual building-bound Drakuv power."""
    runtime = {category: list(dict.fromkeys([
        *rules[category].values(), *preloads['rules'].get(category, {}).values(),
        *rows.get(category, {}).values()])) for category in ('InfantryTypes', 'VehicleTypes')}
    from randomizer.final_fortress.engine import _action
    for camp in plan['map']['camps']:
        pickup = plan.get('plan_version', 1) >= 25
        key = next(key for key, value in rows['Triggers'].items()
                   if value.split(',')[2] == 'Camp ' + camp['id'] + (' ready' if pickup else ' cleared'))
        clear, tag, transfer, count = rows['FFCampTracking'][camp['id']].split(',')
        finished = next(index for index, value in rows['VariableNames'].items()
                        if value == 'Final Fortress finished,0')
        if pickup:
            require(clear == key and rows['Events'][clear] == '1,13,0,0',
                    'Camp crate does not become available at startup')
            require(rows['Tags'][tag].split(',') == ['2', 'Camp ' + camp['id'] + ' ownership', transfer]
                    and rows['Events'][transfer] == '1,13,0,0',
                    'Camp guard ownership still depends on a destruction event')
            require(rows['Triggers'][clear].split(',')[1] == '<none>',
                    'Camp startup is attached to guard ownership')
            stops = [trigger for trigger, actions in rows['Actions'].items()
                     if _action(54, trigger=transfer) in parse_action_groups(actions)[1]]
            require(len(stops) == 1 and rows['Events'][stops[0]] == '1,13,0,1',
                    'Camp ownership keeps transferring guards after startup')
            audit_pickup_reward(rows, effective, plan, camp, clear)
        else:
            require(clear == key and rows['Events'][clear] == f'2,37,0,{finished},48,0,0',
                'Camp clearance does not observe attached-object destruction')
            require(rows['Tags'][tag].split(',') == ['1', 'Camp ' + camp['id'] + ' cleared', clear],
                'Camp reward fires before every guard is destroyed')
            require(rows['Triggers'][clear].split(',')[1] == transfer
                and rows['Events'][transfer] == '1,0,0,0',
                'Camp ownership consumes its destruction tag before combat')
        require(parse_action_groups(rows['Actions'][transfer])[1]
                == [_action(14, 4475 + plan['map']['enemy_waypoints'][camp['enemy_index']])],
                'Camp ownership changes unrelated objects or belongs to another enemy')
        if not pickup:
            starts = [trigger for trigger, actions in rows['Actions'].items()
                      if _action(22, trigger=transfer) in parse_action_groups(actions)[1]]
            require(len(starts) == 1 and rows['Events'][starts[0]] == '1,13,0,0',
                'Camp ownership is not forced once independently of its AND destruction tag')
        guards = [value.split(',') for category, field in (('Infantry', 8), ('Units', 7))
                  for value in rows.get(category, {}).values() if value.split(',')[field] == tag]
        require(len(guards) == int(count) == sum(unit['count'] for unit in camp['guards']),
                'Camp destruction tag omits guards or includes unrelated attachments')
        aliases = {guard[1] for guard in guards}
        for force in rows.get('TaskForces', {}).values():
            require(not any(key.isdigit() and value.split(',')[1] in aliases
                            for key, value in effective[force].items()),
                    'Team recruitment can strip a camp guard destruction tag')
        for alias in aliases:
            require(alias in preloads['rules'], 'Camp guard definition is not loaded before houses')
            category = next(category for category, kinds in runtime.items() if alias in kinds)
            require(runtime[category].index(alias) < 512, 'Camp guard exceeds native ownership counter capacity')
            require(effective[alias]['DontScore'] == 'no', 'Camp guard no longer awards combat score')
            require(effective[alias]['DefaultToGuardArea'] == 'yes'
                    and effective[alias]['GuardRange'] == '6', 'Camp guards can pursue a global attack')
            require(all(effective[alias].get(field, 'none').lower() == 'none'
                        for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water')),
                    'Camp conversion can replace a tagged guard without a death')
        clear_actions = parse_action_groups(rows['Actions'][clear])[1]
        require(clear_actions[0] == _action(54, trigger=clear), 'Camp clearance can repeat its reward')
        require(sum(action[0] == '108' for action in clear_actions) == 1,
                'Camp clearance does not create exactly one crate')
        if plan.get('plan_version', 1) >= 24:
            from randomizer.final_fortress.camps import guard_positions
            for point in [camp['position'], *guard_positions(camp)]:
                for waypoint in plan['map']['enemy_waypoints']:
                    cell = int(rows['Waypoints'][str(waypoint)])
                    require(max(abs(point['x'] - cell % 1000), abs(point['y'] - cell // 1000)) >= 40,
                            'Camp lies inside a protected enemy base')
        friends = [plan['map']['player_waypoint'], *plan.get('allied_waypoints', [])]
        if camp['id'] == 'north_east_camp':
            from randomizer.final_fortress.camps import guard_positions
            for point in guard_positions(camp):
                for waypoint in friends:
                    cell = int(rows['Waypoints'][str(waypoint)])
                    require(max(abs(point['x'] - cell % 1000), abs(point['y'] - cell // 1000)) >= 32,
                            'Western approach camp intrudes on a friendly start')
    drakuv = rows.get('FFDrakuvPower')
    if drakuv:
        power, provider, payload = (drakuv[field] for field in ('Power', 'Provider', 'Payload'))
        require(all(kind in preloads['rules'] for kind in (power, provider, payload)),
                'Drakuv power/provider/payload is not loaded before the scenario')
        require(effective[provider]['SuperWeapon2'] == power and effective[power]['Deliver.Types'] == payload,
                'Field Bureau bypasses its reviewed Drakuv delivery')
        require(effective[payload]['Image'] == 'RAVA' and effective[payload]['Trainable'] == 'yes'
                and effective[payload]['BuildTimeMultiplier'] == '1', 'Unsafe Drakuv payload template')
        require(runtime['VehicleTypes'].index(payload) < 512, 'Drakuv payload exceeds native counter capacity')
        require(provider in effective[power]['SW.Designators'].split(','), 'Private Field Bureau cannot target Drakuv')
        require(effective[power]['RechargeTime'] == rules['DrakuvSpecial']['RechargeTime']
                and effective[power]['Money.Amount'] == rules['DrakuvSpecial']['Money.Amount'],
                'Building-bound Drakuv lost native recharge or price')


def audit_lab_support(rows, effective, plan, rules, preloads, terrain):
    """Review objective attachment, single-use guards and isolated native healing."""
    from collections import Counter
    from randomizer.final_fortress.engine import _action, _waypoint

    info = rows.get('FFLabSupport', {})
    health_percent = plan['effects'].get('lab_health_percent', 0)
    original = plan['map']['protected_building']['type']
    base_health = int(rules[original]['Strength'])
    require(int(effective['FFOBJECTIVE']['Strength']) == base_health * (100 + health_percent) // 100,
            'Lab durability is missing, compounded across ranks, or multiplied by friendly houses')
    require(effective[original]['Strength'] == rules[original]['Strength'],
            'Lab durability changed the native building type')
    require(not health_percent or plan['plan_version'] >= 28, 'Lab durability changed an older frozen plan')
    objectives = [v.split(',') for v in rows['Structures'].values() if v.split(',')[1] == 'FFOBJECTIVE']
    require(len(objectives) == 1 and objectives[0][2] == '256', 'Upgraded Lab does not start at full health')
    repair = plan['effects'].get('lab_emergency_repair', False)
    reserve = plan['effects'].get('lab_reserve_units', [])
    require(bool(info) == bool(repair or reserve), 'Lab support differs from the purchased loadout')
    if not info:
        return
    require('FFLabSupport' not in preloads['rules'], 'Lab audit metadata leaked into early rules')
    flags = {value.rsplit(',', 1)[0]: key for key, value in rows['VariableNames'].items()}
    finished = flags['Final Fortress finished']
    lab = [value.split(',') for value in rows['Structures'].values()
           if value.split(',')[1] == 'FFOBJECTIVE']
    require(len(lab) == 1, 'Lab support creates a second objective')
    tag = rows['Tags'][lab[0][6]].split(',')
    require(tag[0] == '2', 'Lab support lost the persistent objective tag')
    chain, current = [], tag[2]
    while current in rows['Triggers']:
        require(current not in chain, 'Lab support contains a linked trigger cycle')
        chain.append(current)
        current = rows['Triggers'][current].split(',')[1]
    names = {rows['Triggers'][key].split(',')[2]: key for key in chain}
    loss = names['Final Fortress objective destroyed']
    ownership = names['Final Fortress objective ownership']
    require(rows['Events'][loss] == '1,48,0,0'
            and _action(68) in parse_action_groups(rows['Actions'][loss])[1],
            'Emergency support removed native objective defeat')
    require(rows['Events'][ownership] == '1,13,0,0'
            and _action(14, 4475 + plan['map']['player_waypoint'])
            in parse_action_groups(rows['Actions'][ownership])[1],
            'Emergency support changed Lab ownership routing')

    def actions_for(field, event, used_field):
        key, used = info[field], info[used_field]
        require(key in chain, 'Lab health trigger is not attached to the objective')
        require(rows['Events'][key] == f'3,37,0,{finished},37,0,{used},{event},0,0',
                'Lab support lacks finish/once guards or uses the wrong health event')
        actions = parse_action_groups(rows['Actions'][key])[1]
        require(actions[:2] == [_action(56, int(used)), _action(54, trigger=key)],
                'Lab support consumes its use after applying effects and can recurse')
        require(rows['Triggers'][key].split(',')[3] == '0', 'Lab health support starts disabled')
        require(not any(a == _action(57, int(used)) for value in rows['Actions'].values()
                        for a in parse_action_groups(value)[1]), 'Lab support can recharge during a run')
        return actions

    require(effective['AudioVisual']['ConditionRed'] == rules['AudioVisual']['ConditionRed']
            and effective['AudioVisual']['ConditionYellow'] == rules['AudioVisual']['ConditionYellow'],
            'Lab support changes global health thresholds')
    shield_seconds = plan['effects'].get('lab_reserve_shield_seconds', 0)
    require(bool(info.get('ShieldWeapon')) == bool(shield_seconds and reserve),
            'Lab reserve shield differs from the frozen loadout')
    if repair:
        actions = actions_for('Repair', 43, 'RepairUsed')
        weapon, warhead, armor = (info[k] for k in ('Weapon', 'Warhead', 'Armor'))
        require(all(kind in preloads['rules'] for kind in (weapon, warhead)),
                'Emergency repair weapon or warhead is missing its early preload')
        require(preloads['rules']['ArmorTypes'][armor] == rules[plan['map']['protected_building']['type']]['Armor']
                and effective['FFOBJECTIVE']['Armor'] == armor,
                'Lab repair changes native armor behavior or heals shared building armor')
        require(effective[weapon]['Damage'] == '-' + effective['FFOBJECTIVE']['Strength']
                and effective[weapon]['Warhead'] == warhead, 'Emergency repair does not restore full health')
        require(effective[warhead]['Verses'] == ','.join(['0%'] * 11)
                and effective[warhead]['Versus.' + armor] == '100%'
                and effective[warhead]['PercentAtMax'] == '1', 'Lab healing leaks to other armor or loses HP to falloff')
        require({key for key in effective[warhead] if key.startswith('Versus.')} == {'Versus.' + armor},
                'Emergency repair targets another custom armor')
        registry = list(dict.fromkeys([*rules['WeaponTypes'].values(),
            *preloads['rules'].get('WeaponTypes', {}).values(), *rows.get('WeaponTypes', {}).values()]))
        blasts = [a for a in actions if a[0] == '42']
        require(len(blasts) == 1 and registry[int(blasts[0][2])] == weapon
                and blasts[0][7] == _waypoint(19), 'Repair explosion has the wrong native weapon index/waypoint')
        p = plan['map']['protected_building']['position']
        require(rows['Waypoints']['19'] == str((p['y'] + 1) * 1000 + p['x'] + 1),
                'Emergency repair misses the Lab foundation')
    if reserve:
        actions = actions_for('Reserve', 42, 'ReserveUsed')
        fallback = actions_for('ReserveFallback', 43, 'ReserveUsed')
        require(actions[2:] == fallback[2:], 'Large-hit reserve fallback changes its grant')
        if shield_seconds:
            weapon, warhead, armor = (info[k] for k in ('ShieldWeapon', 'ShieldWarhead', 'Armor'))
            registry = list(dict.fromkeys(effective['SuperWeaponTypes'].values()))
            require(plan['plan_version'] >= 27 and info['ShieldFrames'] == str(shield_seconds * 15),
                    'Lab shield has the wrong native frame duration or changed an older frozen plan')
            power = info['ShieldPower']
            require(registry[int(info['ShieldIndex'])] == power
                    and actions[2] == ['129', '11', info['ShieldIndex'], '0', '0', '0', '0', '100']
                    and not any(action[0] == '42' for action in actions),
                    'Lab shield bypasses the Ares effect path or is not readied before reserve deployment')
            require(all(kind in preloads['rules'] for kind in (weapon, warhead, power)),
                    'Lab shield weapon/warhead is missing its early preload')
            shield = effective[power]
            require(all(shield.get(field) == value for field, value in {
                'Type': 'GenericWarhead', 'SW.AITargeting': 'Self', 'SW.AIRequiresTarget': 'none',
                'SW.AITargeting.Constraints': 'none', 'SW.AITargeting.Preference': 'none',
                'SW.UseAITargeting': 'yes', 'SW.AutoFire': 'yes', 'SW.ManualFire': 'no',
                'SW.ShowCameo': 'no', 'SW.InitialReady': 'no', 'SW.Shots': '1',
                'SW.RequiredHouses': 'FFPLAYER', 'SW.AllowAI': 'no', 'SW.AllowPlayer': 'yes',
                'SW.Damage': '0', 'SW.Warhead': warhead, 'IsPowered': 'no', 'ShowTimer': 'no',
                'DisableableFromShell': 'no', 'EVA.Ready': 'none', 'EVA.Activated': 'none',
                'EVA.Detected': 'none', 'Message.Detected': 'NOSTR:', 'SW.Sound': 'none',
                'SW.ActivationSound': 'none', 'SW.CreateRadarEvent': 'no',
            }.items()), 'Lab shield has unsafe targeting, alerts, repeat shots or player controls')
            require(float(shield['RechargeTime']) * 60 > plan['survival_seconds'],
                    'Lab shield can activate naturally before the health threshold')
            require(info['ShieldOwner'] == 'FFPLAYER'
                    and all(rows['Triggers'][info[field]].split(',')[0] == 'FFPLAYER'
                            for field in ('Reserve', 'ReserveFallback')),
                    'Health trigger charges another house or has no owning house')
            activated = info['ShieldActivated']
            require(rows['Triggers'][activated].split(',')[0] == 'FFPLAYER'
                    and rows['Events'][activated]
                    == f'3,37,0,{finished},36,0,{info["ReserveUsed"]},75,0,{info["ShieldIndex"]}'
                    and any(action[0] == '11' and action[2] == f'NOSTR:Lab shield active: {shield_seconds}s'
                            for action in parse_action_groups(rows['Actions'][activated])[1])
                    and not any(action[0] == '11' and 'Lab shield' in action[2] for action in actions),
                    'Lab shield is announced before its actual power activation')
            require(effective['FFOBJECTIVE'][info['ShieldSlot']] == power
                    and preloads['rules']['FFOBJECTIVE'][info['ShieldSlot']] == power
                    and [kind for kind in effective['BuildingTypes'].values()
                         if power in (effective[kind].get('SuperWeapon'), effective[kind].get('SuperWeapon2'))]
                    == ['FFOBJECTIVE'], 'Lab is not the unique early-loaded shield provider and self target')
            require(effective[weapon]['Damage'] == '0' and effective[weapon]['Warhead'] == warhead,
                    'Lab shield deals conventional damage or healing')
            require(preloads['rules']['ArmorTypes'][armor] == rules[plan['map']['protected_building']['type']]['Armor']
                    and effective['FFOBJECTIVE']['Armor'] == armor
                    and effective['FFOBJECTIVE']['IronCurtain.Modifier'] == '1',
                    'Reserve-only shield loses its Lab armor or changes its duration multiplier')
            require(effective[warhead]['Verses'] == ','.join(['0%'] * 11)
                    and {k: v for k, v in effective[warhead].items() if k.startswith('Versus.')}
                    == {'Versus.' + armor: '100%'}, 'Lab shield can protect nearby enemies or infantry')
            require(all(effective[warhead].get(field) == value for field, value in {
                'IronCurtain.Duration': str(shield_seconds * 15), 'IronCurtain.Cap': str(shield_seconds * 15),
                'AllowZeroDamage': 'yes', 'EffectsRequireDamage': 'no', 'EffectsRequireVerses': 'yes',
            }.items()), 'Lab shield stacks, skips zero damage, or misses its armor filter')
            require(effective['CombatDamage']['IronCurtainDuration'] == rules['CombatDamage']['IronCurtainDuration'],
                    'Reserve shield changes every native Iron Curtain duration')
            require(all(effective[kind].get('Armor') != armor for kind in effective['BuildingTypes'].values()
                        if kind != 'FFOBJECTIVE'), 'Reserve shield armor leaked to another building')
            p = plan['map']['protected_building']['position']
            require(rows['Waypoints']['19'] == str((p['y'] + 1) * 1000 + p['x'] + 1),
                    'Reserve-only shield misses the Lab foundation')
        if repair:
            require(chain.index(info['ReserveFallback']) < chain.index(info['Repair']),
                    'Emergency healing can swallow the large-hit reserve fallback')
            require(info['ReserveUsed'] != info['RepairUsed'], 'Repair and reserve consume each other')
        deliveries = list(actions)
        if plan.get('plan_version', 1) >= 29:
            relay = info['ReserveDeploy']
            require(any(a == _action(53, trigger=relay) for a in actions),
                    'Lab reserve never enables its delivery relay')
            visited = set()
            while relay:
                require(relay not in visited and rows['Events'][relay] == f'1,37,0,{finished}'
                        and rows['Triggers'][relay].split(',')[3] == '1',
                        'Lab reserve relay loops, starts early, or ignores survival end')
                visited.add(relay)
                batch = parse_action_groups(rows['Actions'][relay])[1]
                require(1 <= sum(a[0] == '80' for a in batch) <= 6
                        and all(a[0] in ('80', '53') for a in batch),
                        'Lab reserve delivery batch is oversized or has unrelated actions')
                deliveries.extend(batch)
                following = [a[2] for a in batch if a[0] == '53']
                require(len(following) <= 1, 'Lab reserve relay forks or repeats a delivery')
                relay = following[0] if following else None
        teams = [a for a in deliveries if a[0] == '80']
        require(len(teams) == len(reserve) * len(coalition(plan)), 'Reserve omits a friendly roster')
        for index, (actor, _, start) in enumerate(coalition(plan)):
            actual = Counter()
            expected = Counter({rows.get('FFPlayerTypes', {}).get(u['type'], u['type']): u['count'] for u in reserve})
            for action in teams:
                team = effective[action[2]]
                if team['House'] != actor:
                    continue
                require(team['Waypoint'] == action[7] == _waypoint(10 + index),
                        'Lab reserve arrives at an occupied MCV or another house')
                require(team['VeteranLevel'] == str(plan['effects'].get('lab_reserve_veterancy', 0) + 1),
                        'Lab reserve loses its purchased Veteran/Elite rank')
                require(effective[team['Script']]['0'] == ('11,5' if human_actor(plan, actor) else '0,1'),
                        'Lab reserve takes control away from a human or strands an AI helper')
                force = effective[team['TaskForce']]
                roster = [v.split(',') for k, v in force.items() if k.isdigit()]
                require(len(roster) == 1, 'Lab reserve uses partial-placement-prone mixed teams')
                for count, kind in roster:
                    actual[kind] += int(count)
            require(actual == expected, 'Lab reserve has the wrong faction units, buffs or owner')
            p = plan['map']['perk_layouts'][str(start)]['units']
            require(rows['FFReinforcementPads'][actor] == str(p['y'] * 1000 + p['x']),
                    'Lab reserve has no protected arrival apron')
            if terrain is not None:
                require(terrain.clear({(p['x'] + 2, p['y'] + 1)}), 'Lab reserve arrival terrain is blocked')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Directory for generated audit artifacts')
    parser.add_argument('--map', dest='map_id', help='Fortress map ID (default: configured original map)')
    parser.add_argument('--lab-reserve-rank', type=int, choices=range(1, 11),
                        help='Override the emergency squad rank for selected reserve profiles')
    parser.add_argument('--starting-army-rank', type=int, choices=range(1, 9),
                        help='Override the Starting army rank for selected army profiles')
    parser.add_argument('--reinforcement-rank', type=int, choices=range(1, 13),
                        help='Override the periodic reinforcement rank for selected arrival profiles')
    parser.add_argument('--starting-buildings-rank', type=int, choices=range(1, 6),
                        help='Override the Starting buildings rank for selected building profiles')
    parser.add_argument('--special-building-limit-rank', type=int, choices=range(1, 4),
                        help='Override the Special Building Limit rank for selected capacity profiles')
    parser.add_argument('--special-access-rank', type=int, choices=range(1, 5),
                        help='Override campaign/stolen-tech ranks, capped at each perk maximum')
    parser.add_argument('--profiles', nargs='+', choices=(
                        'baseline', 'helpers', 'maximum', 'defenses', 'defenses-first', 'defenses-second',
                        'defenses-third', 'powers', 'upgrades', 'secondary',
                        'arsenal', 'arsenal-buildings', 'fortified-buildings', 'native-tech', 'native-tech-specials', 'stolen-tech', 'all-specials', 'starting-army', 'combined-armies', 'starting-buildings', 'buildings-and-defenses',
                        'reinforcements', 'arsenal-first', 'reinforcements-first',
                        'healing', 'recon', 'limits', 'income', 'enemy-powers', 'powerhouses', 'utilities-first',
                        'veteran', 'elite', 'reinforcements-veteran', 'reinforcements-rookie',
                        'lab-repair', 'lab-reserve', 'lab-support', 'lab-support-helpers',
                        'lab-health-first', 'lab-health-middle', 'lab-health', 'lab-health-support',
                        'construction', 'production', 'building-limits', 'economy-first',
                        'generators', 'generators-first',
                        'transport-capacity', 'open-topped', 'infrastructure', 'logistics',
                        'logistics-first', 'logistics-middle',
                        'fundraising-1', 'fundraising-2', 'fundraising-3', 'fundraising-4',
                        'fundraising-mixed', 'fundraising-guest'),
                        default=['baseline', 'helpers', 'maximum'])
    parser.add_argument('--difficulties', nargs='+', choices=DIFFICULTY_IDS, default=list(DIFFICULTY_IDS))
    parser.add_argument('--mental-ai-boost', action='store_true', help='Audit the installed Mental AI Boost option')
    parser.add_argument('--humans', type=int, choices=(1, 2, 3), default=1, help='Emit solo or co-op native maps/spawns')
    parser.add_argument('--player-color', type=int, help='Installed multiplayer color index for the host')
    parser.add_argument('--terrain', action='store_true', help='Check flat ground/resources; requires the system LZO2 library')
    args = parser.parse_args()
    if args.player_color is not None:
        from randomizer.skirmish import multiplayer_colors
        require(args.player_color in multiplayer_colors(GAME_ROOT).values(), 'Unknown installed player color')
    args.output.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config = select_map(config, args.map_id or config['map']['id'])
    _, rules = installed_rules_registry(synchronous=True)
    audit_wave_rosters(config, rules)
    audit_special_rosters(config)
    source_path = GAME_ROOT / config['map']['source']
    source_data = source_path.read_bytes()
    source = all_section_value_maps_preserve(source_lines(GAME_ROOT, config['map']))
    terrain = None
    if args.terrain:
        from fortress_terrain import Terrain
        terrain = Terrain(source)
        require(max(terrain.heights.values()) <= config['map'].get('maximum_terrain_height', 14),
                'Configured maximum terrain height understates the source map')
    if not ART_CACHE_PATH.exists():
        require(extract_mix_files_sync([('ARTMO.INI', ART_CACHE_PATH)]), 'Installed art unavailable')
    art = {key.casefold(): value for key, value in read_sections(ART_CACHE_PATH.read_bytes()).items()}
    ai = load_ai_rules()
    manifest = []
    utilities = ['automatic_healing', 'reconnaissance', 'unique_unit_capacity', 'special_building_income']
    loadouts = {
        'baseline': [], 'helpers': ['allied_helpers'], 'maximum': [entry['id'] for entry in config['perks']],
        'starting-army': ['reinforcements', 'allied_helpers'],
        'combined-armies': ['reinforcements', 'periodic_reinforcements', 'allied_helpers', 'veteran_escort'],
        'starting-buildings': ['starting_buildings', 'allied_helpers'],
        'buildings-and-defenses': ['starting_buildings', 'starting_defenses', 'allied_helpers'],
        'powers': ['support_powers', 'faction_superweapon', 'allied_helpers'],
        'upgrades': ['power_upgrades'], 'arsenal': ['special_unit_access'], 'arsenal-first': ['special_unit_access'],
        'arsenal-buildings': ['special_unit_access', 'starting_buildings', 'fortified_infrastructure'],
        'fortified-buildings': ['starting_buildings', 'fortified_infrastructure'],
        'native-tech': [entry['id'] for entry in config['perks']
                        if entry['id'] not in ('special_unit_access', 'stolen_tech_access')],
        'native-tech-specials': [entry['id'] for entry in config['perks']],
        'stolen-tech': ['stolen_tech_access'],
        'all-specials': ['special_unit_access', 'stolen_tech_access', 'allied_helpers'],
        'transport-capacity': ['transport_capacity'], 'open-topped': ['open_topped_transports'],
        'infrastructure': ['fortified_infrastructure'],
        'generators': ['more_power'], 'generators-first': ['more_power'],
        **{profile: ['transport_capacity', 'open_topped_transports', 'fortified_infrastructure',
                     'special_unit_access', 'stolen_tech_access', 'allied_helpers']
           for profile in ('logistics', 'logistics-first', 'logistics-middle')},
        'reinforcements': ['periodic_reinforcements'], 'reinforcements-first': ['periodic_reinforcements', 'allied_helpers'],
        'reinforcements-veteran': ['periodic_reinforcements', 'allied_helpers'],
        'reinforcements-rookie': ['periodic_reinforcements', 'allied_helpers'],
        'secondary': ['faction_superweapon', 'allied_helpers', 'power_upgrades',
                      'tier_1_training', 'tier_2_training', 'tier_3_training'],
        'defenses': ['starting_defenses', 'allied_helpers'],
        'defenses-first': ['starting_defenses', 'allied_helpers'],
        'defenses-second': ['starting_defenses', 'allied_helpers'],
        'defenses-third': ['starting_defenses', 'allied_helpers'],
        'healing': ['automatic_healing'], 'recon': ['reconnaissance'],
        'limits': ['unique_unit_capacity', 'special_unit_access'], 'income': ['special_building_income'],
        'enemy-powers': [], 'powerhouses': [], 'utilities-first': [*utilities, 'allied_helpers'],
        'veteran': ['reinforcements', 'veteran_escort', 'allied_helpers'],
        'elite': ['reinforcements', 'veteran_escort', 'allied_helpers'],
        'lab-repair': ['lab_emergency_repair'], 'lab-reserve': ['lab_reserve_squad'],
        'lab-support': ['lab_emergency_repair', 'lab_reserve_squad'],
        'lab-support-helpers': ['lab_emergency_repair', 'lab_reserve_squad', 'allied_helpers'],
        'lab-health-first': ['lab_durability'], 'lab-health-middle': ['lab_durability'],
        'lab-health': ['lab_durability'],
        'lab-health-support': ['lab_durability', 'lab_emergency_repair', 'lab_reserve_squad', 'allied_helpers'],
        'construction': ['cheaper_construction'], 'production': ['cheaper_production'],
        'building-limits': ['special_building_limit'],
        'economy-first': ['cheaper_construction', 'cheaper_production', 'special_building_limit', 'fundraising'],
        **{f'fundraising-{rank}': ['fundraising'] for rank in range(1, 5)},
        'fundraising-mixed': ['fundraising', 'allied_helpers'],
        'fundraising-guest': ['allied_helpers'],
    }
    from randomizer.final_fortress.challenges import definition
    for profile in args.profiles:
        selected = loadouts[profile]
        selected_challenges = [entry['id'] for entry in config['challenges'] if profile == 'maximum'
                               or profile == 'enemy-powers' and definition(entry)['effect'] in ('power', 'power_group')
                               or profile == 'powerhouses' and entry['enemy_effect_id'] == 'powerhouse']
        for country in SIDE_COUNTRIES:
            for difficulty in args.difficulties:
                name = f'{profile}-{country}-{difficulty}' + (f'-coop{args.humans}' if args.humans > 1 else '')
                plan = build_run_plan(
                    config, difficulty=difficulty, seed='FF-MAP-AUDIT-' + name,
                    player_country=country, selected_perks=selected,
                    perk_ranks={entry['id']: (args.special_building_limit_rank if args.special_building_limit_rank is not None
                                                  and entry['id'] == 'special_building_limit'
                                             else min(args.special_access_rank, len(ranks(entry)))
                                                  if args.special_access_rank is not None
                                                  and entry['id'] in ('special_unit_access', 'stolen_tech_access')
                                             else args.starting_buildings_rank if args.starting_buildings_rank is not None
                                                  and entry['id'] == 'starting_buildings'
                                             else args.starting_army_rank if args.starting_army_rank is not None
                                                  and entry['id'] == 'reinforcements'
                                             else args.reinforcement_rank if args.reinforcement_rank is not None
                                                  and entry['id'] == 'periodic_reinforcements'
                                             else {'defenses-first': 1, 'defenses-second': 2, 'defenses-third': 3}[profile]
                                                  if profile in ('defenses-first', 'defenses-second', 'defenses-third')
                                                  and entry['id'] == 'starting_defenses'
                                             else args.lab_reserve_rank if args.lab_reserve_rank is not None
                                                  and entry['id'] == 'lab_reserve_squad'
                                             else 1 if (profile == 'secondary' and entry['id'] == 'faction_superweapon'
                                                  or profile == 'logistics-first' and entry['id'] in (
                                                      'transport_capacity', 'fortified_infrastructure')
                                                  or profile == 'arsenal-first' and entry['id'] == 'special_unit_access'
                                                  or profile == 'reinforcements-first' and entry['id'] == 'periodic_reinforcements'
                                                  or profile == 'utilities-first' and entry['id'] in utilities
                                                  or profile == 'lab-health-first' and entry['id'] == 'lab_durability')
                                             else 2 if profile == 'lab-health-middle' and entry['id'] == 'lab_durability'
                                             else 2 if profile == 'logistics-middle' and entry['id'] in (
                                                 'transport_capacity', 'fortified_infrastructure')
                                             else 1 if profile == 'veteran' and entry['id'] == 'veteran_escort'
                                             else 7 if profile == 'reinforcements-veteran' and entry['id'] == 'periodic_reinforcements'
                                             else 6 if profile == 'reinforcements-rookie' and entry['id'] == 'periodic_reinforcements'
                                             else 1 if profile in ('economy-first', 'generators-first')
                                             else int(profile[-1]) if profile.startswith('fundraising-')
                                                  and profile[-1].isdigit() and entry['id'] == 'fundraising'
                                             else len(ranks(entry))) for entry in config['perks']},
                    selected_challenges=selected_challenges,
                    challenge_stacks={entry['id']: maximum(entry) for entry in config['challenges']},
                    wave_multiplier=10 if profile == 'maximum' else 1, mental_ai_boost=args.mental_ai_boost,
                    coop_players=[f'Fortress{i + 1}' for i in range(args.humans)] if args.humans > 1 else (),
                    player_color=args.player_color,
                    fundraising_ranks=([4, 1, 0][:args.humans] if profile == 'fundraising-mixed'
                                       else [0, 4, 2][:args.humans] if profile == 'fundraising-guest' else None))
                preloads = {}
                data = build_map(GAME_ROOT, {'id': hashlib.md5(name.encode()).hexdigest(), 'plan': plan},
                                 rules, preloads=preloads)
                (args.output / (name + '.map')).write_bytes(data)
                if args.humans > 1:
                    from fortress_coop_audit import audit_coop_artifacts
                    spawn = audit_coop_artifacts(args.output, name, plan, data, preloads, rules)
                else:
                    spawn = spawn_data(plan, data)
                counts = audit_map(data, spawn, preloads, plan, rules, source, art, ai, terrain)
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
        print(f'{profile}: {len(SIDE_COUNTRIES) * len(args.difficulties)} {config["map"]["display_name"]} configurations audited', flush=True)
    require(source_path.read_bytes() == source_data, 'Installed source map changed during audit')
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: one map, {len(manifest)} configurations; artifacts: {args.output}')


if __name__ == '__main__':
    main()
