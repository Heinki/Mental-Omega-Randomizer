"""Native RA2/Ares battles, isolated countries, AI and safe starting grants."""

from collections import Counter, deque
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import re
import tempfile

from randomizer.core.paths import CAMEO_CACHE_DIR
from randomizer.maps.ini import IniLines, all_section_value_maps_preserve
from randomizer.maps.hooks import append_hook_team
from randomizer.skirmish import discover_maps, _serialize as _native_serialize
from randomizer.final_fortress.engine import _MapWriter, _action, _transfer_tag, _place
from randomizer.final_fortress.placement import foundation
from .profile import (GAME, TITLE, NATIVE_COUNTRIES, RULES_FILE, ART_FILE, AI_FILE,
                      INSTALLATION_FILES, installed_rules, read_ini)
from .catalogue import (FACTIONS, DIFFICULTIES, RULES_VERSION, BATTLE_CREDITS_PER_RANK,
                        AIRCRAFT_BUILDINGS, ROSTERS, FACTORIES, ESCORT_ROSTERS)
from .teams import HOUSE_ALIASES, COLOR_SCHEMES, participants
from .players import human
from .terrain import Terrain, BUILDABLE_TILES
from .native_effects import apply_effects, eligible, items

CONQUEST_GROUND = BUILDABLE_TILES


def _serialize(rows):
    # Preserve the native scenario header and installed INI section order.
    # Newly generated sections are merged in canonical order below.
    return _native_serialize(rows)


def installation_fingerprint(root):
    from .transport_lobby import installation_details
    return installation_details(Path(root))[0]


def _validate_runtime(root, battle=None):
    for relative in INSTALLATION_FILES:
        path = root / relative
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'{TITLE} installation is incomplete: {relative}. Repair the game, then retry.')
    rules = installed_rules()
    mobile = set(rules['InfantryTypes'].values()) | set(rules['VehicleTypes'].values())
    buildings = set(rules['BuildingTypes'].values())
    infantry = set(rules['InfantryTypes'].values())
    vehicles = set(rules['VehicleTypes'].values())
    for country, force in ROSTERS.items():
        native = NATIVE_COUNTRIES[country]
        if native not in rules['Countries'].values() or rules[native]['Side'] not in rules['Sides']:
            raise ValueError('Installed native faction registry is incompatible with Conquest: ' + country)
        for kind, registry in [*((k, mobile) for k in (*force[:3], force[6])),
                               *((k, buildings) for k in (*force[3:6], force[7], FACTORIES[country], AIRCRAFT_BUILDINGS[country])),
                               *((k, infantry) for k in ESCORT_ROSTERS[country]['infantry']),
                               *((k, vehicles) for k in ESCORT_ROSTERS[country]['vehicles'])]:
            if kind not in registry:
                raise ValueError(f'{TITLE} no longer provides Conquest type {kind} for {country}.')
    # Scores identify repeated Computer names by the actual native scheme.
    colors = list(rules['Colors'])
    ui = read_ini(root / 'uimd.ini').get('Colors', {})
    actual = tuple(2 * colors.index(ui[f'Slot{i+1}.ColorScheme']) + 1 for i in range(8))
    if actual != COLOR_SCHEMES:
        raise ValueError('Installed multiplayer score colors changed; update the Conquest adapter before playing.')
    if battle:
        for member in participants(battle):
            force = member['loadout']['force']
            if not set(force['units']) <= mobile or not set(force['structures']) <= buildings:
                raise ValueError('A committed starting force is no longer installed.')
    return rules


def _map_rows(source):
    return {name: {key: value.split(';', 1)[0].strip() for key, value in values.items()}
            for name, values in all_section_value_maps_preserve(Path(source).read_bytes().decode('latin-1').splitlines()).items()}


def map_fingerprint(root, source):
    rows = _map_rows(source)
    canonical = _native_serialize({section: rows[section] for section in sorted(rows)})
    return hashlib.sha256(canonical.encode('latin-1')).hexdigest()


def _clear_scenario_scripts(rows):
    """Convert authored standard maps into ordinary Conquest skirmishes.

    Remove the complete source trigger graph, including attached object tags.
    Native terrain, scenery, resources and authored start positions remain.
    """
    houses = set(rows.get('Houses', {}).values())
    for section in ('Triggers', 'Events', 'Actions', 'Tags', 'CellTags', 'VariableNames',
                    'TeamTypes', 'TaskForces', 'ScriptTypes', 'AITriggerTypes',
                    'AITriggerTypesEnable', 'Houses', 'Countries', 'Digest', *houses):
        rows.pop(section, None)
    for section, tag_index in (('Structures', 6), ('Units', 7), ('Infantry', 8), ('Aircraft', 7)):
        for key, value in rows.get(section, {}).items():
            fields = value.split(',')
            fields[tag_index] = 'None'
            if fields[0] in houses and fields[0] not in ('Neutral', 'Special'):
                fields[0] = 'Neutral'
            rows[section][key] = ','.join(fields)


def catalogue(root):
    """Use actual installed standard maps and their authored faction restrictions."""
    root = Path(root).resolve()
    _validate_runtime(root)
    result = []
    for relative, definition in discover_maps(root).items():
        if not 2 <= len(definition['starts']) <= 8:
            continue
        source = Path(definition['path']).resolve()
        rows = _map_rows(source)
        if (rows.get('Basic', {}).get('IgnoreGlobalAITriggers', 'no').casefold() in ('yes', 'true', '1') or
            not rows.get('IsoMapPack5') or not rows.get('OverlayPack')):
            continue
        countries = [label for label, native in NATIVE_COUNTRIES.items() if native in definition['countries']]
        if not countries or rows.get('Map', {}).get('Theater', '').casefold() not in CONQUEST_GROUND:
            continue
        from randomizer.skirmish_factions import _map_catalogue
        metadata = dict(_map_catalogue(root / ('INI/MentalOmegaMaps.ini' if GAME == 'mo' else 'INI/MPMaps.ini')).get(
            source.relative_to(root).with_suffix('').as_posix().casefold(), {}))
        seen = set()
        while metadata.get('basesection'):
            parent = metadata.pop('basesection').replace('\\', '/').casefold()
            if parent in seen:
                raise ValueError('Cyclic native map metadata.')
            seen.add(parent)
            inherited = _map_catalogue(root / ('INI/MentalOmegaMaps.ini' if GAME == 'mo' else 'INI/MPMaps.ini')).get(parent, {})
            metadata = {**inherited, **metadata}
        if any(row.get('humanplayersonly', 'no').casefold() in ('yes', 'true', '1')
               for row in (metadata, {k.casefold(): v for k, v in rows.get('Basic', {}).items()})):
            continue
        positions = {str(w): [int(rows['Waypoints'][str(w)]) % 1000, int(rows['Waypoints'][str(w)]) // 1000]
                     for w in definition['starts']}
        result.append(dict(path=source.relative_to(root).as_posix(), name=definition['name'],
            starts=list(definition['starts']), positions=positions, countries=countries,
            sha256=map_fingerprint(root, source)))
    if not result:
        raise ValueError(f'No compatible 2–8-player {TITLE} skirmish maps were found.')
    return result, installation_fingerprint(root)


def marker(attempt_id):
    if not isinstance(attempt_id, str) or not re.fullmatch('[0-9a-f]{32}', attempt_id):
        raise ValueError('Invalid Conquest attempt ID.')
    return ('RCQ_' if GAME == 'reloaded' else 'MCQ_') + attempt_id + '_START'


class ConquestWriter(_MapWriter):
    def __init__(self, lines, rules, root):
        super().__init__(lines)
        self.rules, self.root = rules, root
        self.sections['Countries'] = dict(rules['Countries'])

    def key(self):
        while True:
            self.counter += 1
            key = f'CQ{self.counter:06X}'
            if key not in self.rules and key not in self.sections:
                return key

    def register(self, category, kind):
        registry = self.sections.setdefault(category, dict(self.rules.get(category, {})))
        if kind not in registry.values():
            registry[str(max((int(k) for k in registry if k.isdigit()), default=-1) + 1)] = kind
        if category == 'Countries' and len(registry) > 32:
            raise ValueError('Conquest exceeded the native 32-country limit.')

    def transfer_tag(self, waypoint, name):
        return _transfer_tag(self, waypoint, name)

    def place(self, category, kind, position, *, tag, veterancy=0):
        x, y = position['x'], position['y']
        experience = veterancy * 100
        if category == 'Structures':
            value = f'Neutral,{kind},256,{x},{y},64,{tag},1,0,1,0,0,None,None,None,0,0'
        elif category == 'Infantry':
            value = f'Neutral,{kind},256,{x},{y},0,Guard,64,{tag},{experience},-1,0,0,0'
        else:
            native = self.rules.get(kind, self.sections.get(kind, {}))
            mission = 'Harvest' if native.get('Harvester', 'no').lower() == 'yes' else 'Guard'
            value = f'Neutral,{kind},256,{x},{y},64,{mission},{tag},{experience},-1,0,-1,0,0'
        _place(self, category, value)

    def finish(self):
        rows = all_section_value_maps_preserve(self.lines)
        for section in sorted(self.sections):
            rows.setdefault(section, {}).update(self.sections[section])
        return _serialize(rows).encode('latin-1')


def _starting_structure_type(writer, kind, cache, *, template=None, refinery=True):
    """Starting refineries supply exactly the committed collector count."""
    from randomizer.final_fortress.player_perks import register_building_equivalent
    source = template or kind
    if source in cache:
        return cache[source]
    alias = cache[source] = writer.key()
    native = writer.sections[template] if template else writer.rules[kind]
    writer.sections[alias] = dict(native, Image=native.get('Image', kind),
        FreeUnit='none', TechLevel='-1', BuildLimit='0', AIBuildThis='no')
    writer.register('BuildingTypes', alias)
    veterans = items(writer.sections.get('Neutral', {}).get('VeteranBuildings',
                     writer.rules.get('Neutral', {}).get('VeteranBuildings')))
    if source in veterans:
        writer.put('Neutral', 'VeteranBuildings', ','.join(dict.fromkeys([*veterans, alias])))
    register_building_equivalent(writer, writer.rules, kind, alias, {}, preserve_native=True)
    return alias


def _treasury(writer, loadout, waypoint, candidates, occupied, tag):
    credits = BATTLE_CREDITS_PER_RANK * loadout['perks'].get('battle_treasury', 0)
    if not credits:
        return
    position = next((p for p in candidates if p not in occupied), None)
    if position is None:
        raise ValueError('No safe position for Battle Treasury. Retry or use autobattle.')
    x, y = position
    occupied.add((x, y))
    alias = writer.key()
    row = deepcopy(writer.rules['CABHUT'])
    row.update(Image='GAPILL', Name='Conquest battle treasury', InvisibleInGame='yes',
        IsPassable='yes', Immune='yes', LegalTarget='no', Selectable='no', Capturable='no',
        Insignificant='yes', DontScore='yes', KeepAlive='no', RadarInvisible='yes',
        ProduceCashStartup=str(credits), ProduceCashAmount='0', ProduceCashDelay='0',
        Unsellable='yes', CanBeOccupied='no', TechLevel='-1')
    writer.sections[alias] = row
    writer.register('BuildingTypes', alias)
    writer.place('Structures', alias, dict(x=x, y=y), tag=tag)


def _placements(writer, source, sides, *, private_types=None):
    terrain = Terrain(source)
    flat_tiles = terrain.flat_tiles
    art = {key.casefold(): row for key, row in read_ini(CAMEO_CACHE_DIR / ART_FILE).items()}
    occupied = set(terrain.objects)
    rules = writer.rules
    walls = {i for i, kind in enumerate(rules['OverlayTypes'].values())
             if rules.get(kind, {}).get('Wall', '').casefold() in ('yes', 'true', '1')}

    def cells(kind, x, y):
        return {(x + dx, y + dy) for dx, dy in foundation({'Image': kind, **rules[kind]}, art)}

    for value in source.get('Structures', {}).values():
        row = value.split(',')
        occupied.update(cells(row[1], int(row[3]), int(row[4])))
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            row = value.split(',')
            occupied.add((int(row[3]), int(row[4])))
    centers = {}
    # Only occupied seats spawn an MCV. Reserving unused neighboring starts
    # can consume the entire building area on tightly paired city maps.
    for index in sorted({waypoint for _, waypoint in sides}):
        cell = source.get('Waypoints', {}).get(str(index))
        if cell is None:
            continue
        x, y = int(cell) % 1000, int(cell) // 1000
        centers[index] = (x, y)
        occupied.update((x + dx, y + dy) for dx in range(-4, 5) for dy in range(-4, 5))
        # Keep two escape lanes open through any starting production compound.
        occupied.update((x + step, y + width) for step in range(5, 13) for width in (-1, 0, 1))
        occupied.update((x + width, y + step) for step in range(5, 13) for width in (-1, 0, 1))
    refinery_cache, reports = {}, []
    for loadout, waypoint in sides:
        private = (private_types or {}).get(waypoint, {})
        force = loadout['force']
        cx, cy = centers[waypoint]
        height = terrain.heights.get((cx, cy), 0)
        walkable = {(x, y) for x in range(cx - 26, cx + 27) for y in range(cy - 26, cy + 27)
                    if 0 <= x < 512 and 0 <= y < 512 and
                    terrain.heights.get((x, y), 0) == height and
                    terrain.cells.get((x, y), (-1, 0, 0))[0] in flat_tiles and
                    terrain.overlays[y * 512 + x] not in walls and
                    (x, y) not in terrain.objects and terrain.bounds.contains({(x, y)}, heights=terrain.heights)}
        connected, pending = set(), deque([(cx, cy)])
        while pending:
            point = pending.popleft()
            if point in connected or point not in walkable:
                continue
            connected.add(point)
            pending.extend((point[0] + dx, point[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        candidates = sorted((p for p in connected if terrain.clear({p}, flat_tiles=flat_tiles)),
                            key=lambda p: ((p[0] - cx)**2 + (p[1] - cy)**2, p))
        if not candidates:
            raise ValueError(f'No connected clear ground near start {waypoint + 1}. Battle remains pending; autobattle is available.')
        structures = Counter(force['structures'])
        balance = sum(float(rules[k].get('Power', '0')) * count for k, count in structures.items())
        # Purchased node generators are extra capacity. Do not replace the
        # minimum power already promised for the node's other buildings.
        balance -= float(rules[force['power_type']].get('Power', '0')) * loadout['perks'].get('node_power', 0)
        if balance < 0:
            output = float(rules[force['power_type']].get('Power', '0'))
            if output <= 0:
                raise ValueError('The selected faction has no valid starting generator.')
            structures[force['power_type']] += math.ceil(-balance / output)
        tag = writer.transfer_tag(waypoint, 'Conquest starting forces')
        _treasury(writer, loadout, waypoint, candidates, occupied, tag)
        placed = []
        # Large foundations first; every building retains an access apron.
        buildings = [k for k, count in structures.items() for _ in range(count)]
        buildings.sort(key=lambda k: -len(cells(k, 0, 0)))
        for kind in buildings:
            for x, y in candidates:
                footprint = cells(kind, x, y)
                apron = {(px + dx, py + dy) for px, py in footprint
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
                if footprint <= connected and terrain.clear(apron, flat_tiles=flat_tiles, occupied=occupied):
                    occupied.update(apron)
                    output = (_starting_structure_type(writer, kind, refinery_cache, template=private.get(kind))
                              if rules[kind].get('FreeUnit', 'none').lower() not in ('none', '') else private.get(kind, kind))
                    if kind in set(AIRCRAFT_BUILDINGS.values()):
                        pad = {**rules[kind], **writer.sections.get(output, {})}
                        if pad.get('FreeUnit', 'none').casefold() not in ('none', '<none>', ''):
                            output = _starting_structure_type(writer, kind, refinery_cache, template=private.get(kind), refinery=False)
                    writer.place('Structures', output, {'x': x, 'y': y}, tag=tag)
                    placed.append(dict(type=kind, output_type=output, x=x, y=y))
                    break
            else:
                raise ValueError(f'{kind} cannot fit safely near start {waypoint + 1}. Battle remains pending; autobattle is available.')
        for kind, count in force['units'].items():
            if kind not in rules:
                raise ValueError('Missing native starting unit: ' + kind)
            category = 'Infantry' if kind in rules['InfantryTypes'].values() else 'Units'
            for _ in range(count):
                position = next((p for p in candidates if terrain.clear({p}, flat_tiles=flat_tiles, occupied=occupied)), None)
                if position is None:
                    raise ValueError('Starting army cannot fit safely. Battle remains pending; autobattle is available.')
                occupied.add(position)
                writer.place(category, private.get(kind, kind), dict(zip(('x', 'y'), position)), tag=tag,
                             veterancy=0 if kind == force['collector'] else force['veterancy'])
                placed.append(dict(type=kind, output_type=private.get(kind, kind), x=position[0], y=position[1]))
        reports.append(dict(country=loadout['country'], waypoint=waypoint,
                            structures=dict(structures), units=force['units'], placements=placed))
    return reports



def _validate_production(writer, members, private):
    """Catch empty native base/factory selectors before entering gamemd."""
    rules = writer.rules
    sides = list(rules['Sides'])
    for member in members:
        actor = HOUSE_ALIASES[member['slot']]
        country = NATIVE_COUNTRIES[member['loadout']['country']]
        side = sides.index(rules[country]['Side'])
        def allowed(kind):
            row = {**rules.get(kind, {}), **writer.sections.get(kind, {})}
            required = items(row.get('RequiredHouses'))
            return (actor in items(row.get('Owner')) and actor not in items(row.get('ForbiddenHouses'))
                    and (not required or actor in required)
                    and int(row.get('AIBasePlanningSide', '-1')) in (-1, side))
        for section, field in (('General', 'BaseUnit'), ('AI', 'BuildConst'), ('AI', 'BuildWeapons')):
            values = writer.sections.get(section, {}).get(field, rules[section].get(field, ''))
            if not any(allowed(kind) for kind in items(values)):
                raise ValueError(f'{member["loadout"]["country"]} has no valid native {field} for this Conquest seat.')

        for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes'):
            for kind in rules[category].values():
                row = {**rules[kind], **writer.sections.get(kind, {})}
                required = items(row.get('RequiredHouses'))
                native_available = (not required or actor in required) and actor not in items(row.get('ForbiddenHouses'))
                expected = eligible(kind, rules[kind], country) and kind not in private[member['slot']]
                if native_available != expected:
                    raise ValueError(f'Conquest country gate mismatch for {actor}: {kind}.')

        if member['loadout']['perks'].get('factory_training'):
            registered = {kind for category in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
                          for kind in writer.sections.get(category, rules[category]).values()}
            for kind, alias in private[member['slot']].items():
                row = writer.sections[alias]
                if 'Academy.Types' in row:
                    targets = items(row['Academy.Types'])
                    if not targets or any(target not in registered for target in targets):
                        raise ValueError(f'Conquest factory training references unregistered units: {kind}.')


def render(root, state, attempt_id, *, game_speed=2, coop_slot=0, endpoints=None):
    """Freeze all battle bytes before committing an attempt or changing runtime files."""
    from .persistence import validate
    from .ai import route_ai
    validate(state)
    battle = state['pending']
    if not battle or battle['rules_version'] != RULES_VERSION:
        raise ValueError('No supported Conquest battle is pending.')
    if battle['attacker'] == 'ai' and not human(state, battle['defense']['faction']):
        raise ValueError('AI battles against neutral territories use autobattle.')
    root = Path(root).resolve()
    source = (root / battle['map']['path']).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('Assigned battle map is missing. Autobattle remains available.')
    if map_fingerprint(root, source) != battle['map']['sha256']:
        raise ValueError('Assigned battle map changed. Autobattle remains available.')
    if state.get('coop'):
        from .network import validate_endpoints
        validate_endpoints(state, endpoints)
    if type(game_speed) is not int or not 0 <= game_speed <= 6:
        raise ValueError('Invalid game speed.')
    rules = _validate_runtime(root, battle)
    rows = _map_rows(source)
    _clear_scenario_scripts(rows)
    for section, values in rows.items():
        rules.setdefault(section, {}).update(values)
    rows.setdefault('Basic', {}).update(Name='Conquest: ' + battle['map']['name'],
        MultiplayerOnly='yes', IgnoreGlobalAITriggers='no')
    rows['Basic'].pop('Player', None)
    lines = IniLines(_serialize(rows).splitlines())
    writer = ConquestWriter(lines, rules, root)
    members = participants(battle)
    humans = [m for m in members if m['controller'] == 'human']
    if (not 1 <= len(humans) <= 4 or [m['slot'] for m in humans] != list(range(len(humans))) or
        type(coop_slot) is not int or not 0 <= coop_slot < len(humans) or len(humans) > 1 and endpoints is None):
        raise ValueError('Invalid Conquest human seats or local player slot.')
    private = apply_effects(writer, members, battle['difficulty'])
    for side, countries in rules['Sides'].items():
        additions = [HOUSE_ALIASES[m['slot']] for m in members
                     if rules[NATIVE_COUNTRIES[m['loadout']['country']]]['Side'] == side]
        writer.put('Sides', side, ','.join(dict.fromkeys([*items(countries), *additions])))
    _validate_production(writer, members, private)
    grants = _placements(writer, rows, [(m['loadout'], m['waypoint']) for m in members],
                         private_types={m['waypoint']: private[m['slot']] for m in members})
    # Recruit the real AI's gifted opening army so it attacks instead of
    # remaining in Guard while the native AI builds its production base.
    for member in members:
        if member['controller'] != 'ai':
            continue
        army = [{'type': private[member['slot']].get(k, k), 'count': n}
                for k, n in member['loadout']['force']['units'].items()
                if k != member['loadout']['force']['collector']]
        for i in range(0, len(army), 6):
            team = writer.team('Conquest opening army', army[i:i+6], member['waypoint'],
                               owner=HOUSE_ALIASES[member['slot']])
            writer.put(team, 'Recruiter', 'yes')
            writer.put(team, 'VeteranLevel', member['loadout']['force']['veterancy'] + 1)
            writer.trigger('Conquest opening orders', [(13, 0, 2)], [_action(4, team=team)],
                           owner=HOUSE_ALIASES[member['slot']])
    route_ai(writer, members, read_ini(CAMEO_CACHE_DIR / AI_FILE), private)
    # A zero-unit hook team writes the unique attempt identity into the native
    # log. It has no persistent objects that could keep a defeated house alive.
    team, force, script = writer.key(), writer.key(), writer.key()
    append_hook_team(lines, team, force, script, marker(attempt_id), 'Neutral')
    writer.trigger('Conquest battle identity', [(13, 0, 0)], [_action(4, team=team)])
    scenario_sections = {'Map', 'Basic', 'Header', 'Digest', 'Preview', 'PreviewPack', 'IsoMapPack5',
        'OverlayPack', 'OverlayDataPack', 'Waypoints', 'Terrain', 'Structures', 'Units', 'Infantry',
        'Aircraft', 'Triggers', 'Events', 'Actions', 'Tags', 'CellTags', 'VariableNames', 'Lighting'}
    ai_sections = {'TaskForces', 'TeamTypes', 'ScriptTypes', 'AITriggerTypes', 'AITriggerTypesEnable'}
    ai_source = read_ini(CAMEO_CACHE_DIR / AI_FILE)
    # Include new team/force/script definitions and the complete, replaced
    # trigger registry before native multiplayer houses and AI are allocated.
    ai_ids = {v for s in ('TaskForces', 'TeamTypes', 'ScriptTypes')
              for v in writer.sections.get(s, {}).values()}
    ai_changes = {k: deepcopy(v) for k, v in writer.sections.items() if k in ai_sections or k in ai_ids}
    rules_changes = {k: deepcopy(v) for k, v in writer.sections.items()
                    if k not in scenario_sections and k not in ai_sections and k not in ai_ids}
    rule_source = installed_rules()
    for k in sorted(rules_changes):
        rule_source.setdefault(k, {}).update(rules_changes[k])
    rule_source['Countries'] = writer.sections['Countries']
    for k in sorted(ai_changes):
        v = ai_changes[k]
        if k in ('AITriggerTypes', 'AITriggerTypesEnable'):
            ai_source[k] = v
        else:
            ai_source.setdefault(k, {}).update(v)
    preloads = {RULES_FILE: (RULES_MARKER + '\r\n' + _serialize(rule_source)).encode('latin-1'),
                AI_FILE: (AI_MARKER + '\r\n' + _serialize(ai_source)).encode('latin-1')}
    for relative, data in preloads.items():
        writer.put('CQRuntime', relative, hashlib.sha256(data).hexdigest())
    data = writer.finish()
    game_id = int(attempt_id[:8], 16) % (2**31 - 1) + 1
    countries = list(writer.sections['Countries'].values())
    indices = {m['slot']: countries.index(HOUSE_ALIASES[m['slot']]) for m in members}
    local = humans[coop_slot]
    settings = dict(Scenario='spawnmap.ini', Name=local.get('name', 'Commander'),
        Host='Yes' if coop_slot == 0 else 'No', IsSinglePlayer='No',
        PlayerCount=str(len(humans)), AIPlayers=str(len(members) - len(humans)),
        Side=str(indices[coop_slot]), Color=str(coop_slot), IsSpectator='No',
        Seed=str(battle['seed']), GameID=str(game_id), GameSpeed=str(game_speed),
        ShortGame='No', AutoSurrender='No', TechLevel='10', Bases='Yes',
        UnitCount='0', Credits='10000', Crates='No', MCVRedeploy='Yes', FogOfWar='No',
        MultiEngineer='Yes', BuildOffAlly='Yes', Protocol='2', FrameSendRate='7',
        LoadSaveGame='No', UIGameMode='Conquest', UIMapName=battle['map']['name'],
        MapSHA1=hashlib.sha1(data).hexdigest())
    spawn = dict(Settings=settings, SpawnLocations={}, HouseCountries={}, HouseColors={}, HouseHandicaps={})
    if endpoints:
        settings.update(Ip=endpoints[coop_slot]['address'], Port=str(endpoints[coop_slot]['port']))
        for j, slot in enumerate(i for i in range(len(humans)) if i != coop_slot):
            endpoint = endpoints[slot]
            spawn[f'Other{j+1}'] = dict(Name=endpoint['name'], Side=str(indices[slot]), Color=str(slot),
                                       Ip=endpoint['address'], Port=str(endpoint['port']))
    ordinals = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven')
    difficulty = DIFFICULTIES[battle['difficulty']]
    for member in members:
        slot, multi = member['slot'], f'Multi{member["slot"]+1}'
        spawn['SpawnLocations'][multi] = str(member['waypoint'])
        spawn['HouseHandicaps'][multi] = str(1 if member['controller'] == 'human' else difficulty)
        if member['controller'] == 'ai':
            spawn['HouseCountries'][multi] = str(indices[slot])
            spawn['HouseColors'][multi] = str(member['color'])
        allies = [other['slot'] for other in members if other['team'] == member['team'] and other['slot'] != slot]
        spawn[multi + '_Alliances'] = {'HouseAlly' + word: str(other) for word, other in zip(ordinals, allies)}
    return dict(map=data, spawn=_serialize(spawn).encode('latin-1'), preloads=preloads,
                grants=grants, marker=marker(attempt_id), game_id=game_id)


RULES_MARKER = ('; Generated by C&C Reloaded Randomizer Launcher' if GAME == 'reloaded'
                else '; Generated by Mental Omega Randomizer Launcher') + ' Conquest country preload'
AI_MARKER = RULES_MARKER.replace('country preload', 'AI preload')


def _atomic_bytes(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(root, prepared):
    """Install committed bytes under the launcher's exclusive runtime lease."""
    root = Path(root)
    for relative in prepared['preloads']:
        path = root / relative
        if path.exists() and not path.read_bytes().startswith((RULES_MARKER if relative == RULES_FILE else AI_MARKER).encode()):
            raise ValueError(f'Cannot replace custom {relative}. Preserve it before launching Conquest.')
    for relative, data in prepared['preloads'].items():
        _atomic_bytes(root / relative, data)
    _atomic_bytes(root / 'spawnmap.ini', prepared['map'])
    _atomic_bytes(root / 'spawn.ini', prepared['spawn'])


def cleanup(root):
    """Only remove this mode's generated native overrides."""
    for relative, marker_text in ((RULES_FILE, RULES_MARKER), (AI_FILE, AI_MARKER)):
        path = Path(root) / relative
        if path.is_file() and path.read_bytes().startswith(marker_text.encode()):
            path.unlink()


def verify_prepared(root, attempt):
    root = Path(root)
    for relative, key in (('spawnmap.ini', 'map_hash'), ('spawn.ini', 'spawn_hash')):
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != attempt[key]:
            raise ValueError('Prepared Conquest battle changed before launch. Retry preparation.')
    runtime = _map_rows(root / 'spawnmap.ini').get('CQRuntime', {})
    if set(runtime) != {RULES_FILE, AI_FILE} or any(
            hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest for relative, digest in runtime.items()):
        raise ValueError('Prepared Conquest native rules or AI changed before launch.')


def catalogue_report(root):
    """Operational inventory of real installed factions, grants, maps and engine support."""
    from .appearance import army_sprites
    from .native_effects import perk_inventory
    from .technology import technology_inventory
    maps, fingerprint = catalogue(root)
    facings = {label: len(frames) for label, frames in army_sprites().items()}
    return dict(tank_facings=facings, game=GAME, installation_sha256=fingerprint, factions={
        label: dict(country=native, tank=ROSTERS[label][2], infantry=list(ESCORT_ROSTERS[label]['infantry']),
                    vehicles=list(ESCORT_ROSTERS[label]['vehicles'])) for label, native in NATIVE_COUNTRIES.items()},
        native_perks=perk_inventory(installed_rules()),
        technology_centers=technology_inventory(installed_rules()),
        omitted_perks=['hazard_training', 'rapid_rearm'], maps=maps, map_count=len(maps))


if __name__ == '__main__':
    import json
    from randomizer.core.paths import GAME_ROOT
    print(json.dumps(catalogue_report(GAME_ROOT), indent=2))
