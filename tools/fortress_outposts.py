"""Prepare reviewed outpost foundations on the actual installed Fortress maps.

This authoring command decodes installed terrain and writes static placements.
The Windows launcher consumes those placements without requiring LZO2.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fortress_terrain import Terrain
from randomizer.core.paths import GAME_ROOT
from randomizer.core.storage import atomic_write_text
from randomizer.final_fortress.maps import source_lines, perk_layout
from randomizer.final_fortress.outposts import FACTION_BUILDINGS, requested_buildings
from randomizer.final_fortress.placement import foundation, installed_art
from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.ui.cameos import installed_rules_registry


def plan_layouts(definition, rules, art):
    source = all_section_value_maps_preserve(source_lines(GAME_ROOT, definition))
    terrain = Terrain(source)
    rules = {**rules, **{key: {**rules.get(key, {}), **row} for key, row in source.items()}}
    resources = {int(key) for key, kind in rules.get('OverlayTypes', {}).items()
                 if key.isdigit() and rules.get(kind, {}).get('Tiberium', 'no').lower() in ('yes', 'true')}

    def footprint(kind, x, y):
        return {(x + dx, y + dy) for dx, dy in foundation({'Image': kind, **rules.get(kind, {})}, art)}

    occupied = set(terrain.objects)
    for value in source.get('Structures', {}).values():
        row = value.split(',')
        occupied.update(footprint(row[1], int(row[3]), int(row[4])))
    for category in ('Infantry', 'Units', 'Aircraft'):
        for value in source.get(category, {}).values():
            row = value.split(',')
            occupied.add((int(row[3]), int(row[4])))
    objective = definition['protected_building']
    occupied.update(footprint(objective['type'], **objective['position']))
    p = definition.get('wave_clock_position', {'x': 113, 'y': 71})
    occupied.add((p['x'], p['y']))
    for camp in definition['camps']:
        p = camp['position']
        # The crate and its immediate approaches remain clear. Guard tiles
        # can host a later outpost: native creation moves surviving units.
        occupied.update((p['x'] + dx, p['y'] + dy) for dx in range(-1, 2) for dy in range(-1, 2))
    for number in [definition['player_waypoint'], *definition['allied_waypoints'], *definition['enemy_waypoints']]:
        cell = int(source['Waypoints'][str(number)])
        x, y = cell % 1000, cell // 1000
        radius = 24 if number in definition['enemy_waypoints'] else 18
        occupied.update((x + dx, y + dy) for dx in range(-radius, radius + 1)
                        for dy in range(-radius, radius + 1))
    # Starting defense rings and the long utility rows extend beyond the
    # central start buffer. Preserve every possible faction's full loadout,
    # including sites where the user did not select those starting perks.
    representatives = ('UnitedStates', 'USSR', 'PsiCorps', 'Guild1')
    for number in [definition['player_waypoint'], *definition['allied_waypoints']]:
        for country, family in zip(representatives, FACTION_BUILDINGS):
            layout = perk_layout(definition, number, country)
            generator, barracks, refinery, radar, factory, _ = FACTION_BUILDINGS[family]
            placements = [(generator, p) for p in layout['power']]
            placements.extend(zip((generator, barracks, refinery, radar, factory), layout['buildings']))
            for kind, p in placements:
                occupied.update((x + dx, y + dy) for x, y in footprint(kind, **p)
                                for dx in range(-1, 2) for dy in range(-1, 2))
            for p in layout['defenses']:
                occupied.update((p['x'] + dx, p['y'] + dy) for dx in range(-1, 3) for dy in range(-1, 3))
    occupied.update((p['x'], p['y']) for p in definition.get('utility_positions', []))
    layouts = {}
    for family in FACTION_BUILDINGS:
        used = set(occupied)
        camps = {}
        requested = requested_buildings(family, rules)
        def available_barracks_sites(camp):
            p = camp['position']
            kind = FACTION_BUILDINGS[family][1]
            available = 0
            for x in range(p['x'] - 32, p['x'] + 33, 3):
                for y in range(p['y'] - 32, p['y'] + 33, 3):
                    apron = {(cx + dx, cy + dy) for cx, cy in footprint(kind, x, y)
                             for dx in range(-1, 2) for dy in range(-1, 2)}
                    available += not apron & occupied and terrain.clear(apron, allowed_overlays=resources)
            return available
        # Give narrow plateau sites first choice; a roomy neighboring camp
        # must not consume their only suitable barracks/generator foundation.
        ordered_camps = sorted(definition['camps'], key=available_barracks_sites)
        for camp in ordered_camps:
            center = camp['position']
            candidates = [(center['x'] + dx, center['y'] + dy)
                          for dx in range(-32, 33) for dy in range(-32, 33)]
            candidates.sort(key=lambda p: ((p[0] - center['x']) ** 2 + (p[1] - center['y']) ** 2, p))
            placed, omitted = {}, []
            # Reserve a complete powered rank-one core together. Greedy
            # placement can put the generator on the only barracks-sized
            # patch even when a different nearby arrangement would fit.
            core = [i for i, (_, rank) in enumerate(requested) if rank == 1]
            options = {}
            for index in core:
                kind = requested[index][0]
                options[index] = []
                for x, y in candidates:
                    cells = footprint(kind, x, y)
                    apron = {(cx + dx, cy + dy) for cx, cy in cells
                             for dx in range(-1, 2) for dy in range(-1, 2)}
                    if not apron & used and terrain.clear(apron, allowed_overlays=resources):
                        options[index].append((x, y, apron))
            core.sort(key=lambda i: len(options[i]))
            attempts = 0

            def place_core(depth, reserved):
                nonlocal attempts
                if depth == len(core):
                    return True
                index = core[depth]
                for x, y, apron in options[index]:
                    attempts += 1
                    if attempts > 20000:
                        return False
                    if not apron & reserved:
                        placed[index] = {'type': requested[index][0], 'position': {'x': x, 'y': y},
                                         'rank': 1, 'height': terrain.heights[(x, y)]}
                        if place_core(depth + 1, reserved | apron):
                            return True
                placed.pop(index, None)
                return False

            if not place_core(0, set()):
                raise ValueError(f'No powered core fits: {definition["id"]}/{family}/{camp["id"]}')
            for entry in placed.values():
                used.update((x + dx, y + dy) for x, y in footprint(entry['type'], **entry['position'])
                            for dx in range(-1, 2) for dy in range(-1, 2))
            # Preserve lower-rank grants on narrow plateaus. Allocate larger
            # footprints first so a generator cannot consume the only barracks site.
            order = sorted(range(len(requested)), key=lambda i: (
                requested[i][1], -len(footprint(requested[i][0], 0, 0)), i))
            for index in order:
                if index in placed:
                    continue
                kind, rank = requested[index]
                for x, y in candidates:
                    cells = footprint(kind, x, y)
                    apron = {(cx + dx, cy + dy) for cx, cy in cells
                             for dx in range(-1, 2) for dy in range(-1, 2)}
                    if not apron & used and terrain.clear(apron, allowed_overlays=resources):
                        placed[index] = {'type': kind, 'position': {'x': x, 'y': y}, 'rank': rank,
                                         'height': terrain.heights[(x, y)]}
                        used.update(apron)
                        break
                else:
                    omitted.append({'type': kind, 'rank': rank})
            # Never promise an underpowered outpost at an intermediate rank.
            # Remove late consumers when a constrained site lost a generator.
            for rank in range(1, 7):
                while sum(int(rules[e['type']].get('Power', '0')) for e in placed.values()
                          if e['rank'] <= rank) < 0:
                    index = next(i for i in reversed(order) if i in placed and placed[i]['rank'] <= rank
                                 and int(rules[placed[i]['type']].get('Power', '0')) < 0)
                    entry = placed.pop(index)
                    omitted.append({'type': entry['type'], 'rank': entry['rank']})
            if not any(e['type'] == FACTION_BUILDINGS[family][1] for e in placed.values()):
                raise ValueError(f'No powered barracks fits: {definition["id"]}/{family}/{camp["id"]}')
            camps[camp['id']] = {'camp_id': camp['id'], 'structures': [placed[i] for i in range(len(requested)) if i in placed],
                                 'omitted': omitted}
        layouts[family] = [camps[camp['id']] for camp in definition['camps']]
    return layouts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Update static source configuration with reviewed placements')
    args = parser.parse_args()
    path = ROOT / 'configs/final_fortress.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    _, rules = installed_rules_registry()
    art = installed_art()
    sections = config['sections']
    for definition in [sections['map'], *sections.get('additional_maps', [])]:
        definition['outpost_layouts'] = plan_layouts(definition, rules, art)
        print(definition['id'], {family: sum(len(c['structures']) for c in camps)
                                 for family, camps in definition['outpost_layouts'].items()}, flush=True)
    if args.write:
        atomic_write_text(path, json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
