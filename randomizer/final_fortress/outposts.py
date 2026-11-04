"""Reviewed MO camp outposts, created once for the human who collects the crate."""

from copy import deepcopy
from math import ceil

from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
from randomizer.maps.buff_values import _register_map_type


FACTION_BUILDINGS = {
    'allies': ('GAPOWR', 'GAPILE', 'GAREFN', 'GAAIRC', 'GAWEAP', 'GACNST'),
    'soviets': ('NAPOWR', 'NAHAND', 'NAREFN', 'NARADR', 'NAWEAP', 'NACNST'),
    'epsilon': ('YAPOWR', 'YABRCK', 'YARIREFN', 'YAPSIS', 'YAWEAP', 'YACNST'),
    'foehn': ('FATRAP', 'FABARR', 'FAREFN', 'FACYBR', 'FAWEAP', 'FACNST'),
}
FACTION_DEFENSES = {
    'allies': ('GAPILL', 'NASAM', 'ATESLA'),
    'soviets': ('NALASR', 'NAFLAK', 'TESLA'),
    'epsilon': ('YAGGUN', 'YARAIL', 'YAHADE'),
    'foehn': ('FASONI', 'FAGUAR', 'FARAIL'),
}


def requested_buildings(family, rules):
    """Cumulative ranks retain their positions and budget native power at every rank."""
    generator, barracks, refinery, radar, factory, yard = FACTION_BUILDINGS[family]
    basic, aa, advanced = FACTION_DEFENSES[family]
    structures = [(barracks, 1), (refinery, 2), (radar, 3), (factory, 4),
                  (refinery, 5), (factory, 5), (yard, 6),
                  (basic, 1), (basic, 1), (aa, 3), (aa, 3),
                  (advanced, 4), (advanced, 4), (basic, 5), (advanced, 5),
                  (basic, 6), (aa, 6), (aa, 6), (advanced, 6)]
    generators = []
    output = int(rules[generator]['Power'])
    for rank in range(1, 7):
        load = -sum(int(rules[kind].get('Power', '0')) for kind, level in structures if level <= rank)
        count = max(len(generators), 1, ceil(load / output))
        generators.extend((generator, rank) for _ in range(count - len(generators)))
    return [*generators, *structures]


def resolve_outposts(plan):
    """Freeze source-reviewed placements; launching never needs a terrain decoder."""
    family = dict(zip(SIDE_COUNTRIES, SIDE_FAMILIES))[plan['player_country']]
    layouts = plan['map'].get('outpost_layouts', {}).get(family)
    if layouts is None or len(layouts) != len(plan['map']['camps']):
        raise ValueError('Forward Outposts requires reviewed placements for this map and faction.')
    rank = plan['effects']['outpost_rank']
    for camp, layout in zip(plan['map']['camps'], layouts):
        if layout['camp_id'] != camp['id']:
            raise ValueError('Forward Outposts placement does not match its camp.')
        camp['outpost'] = {'structures': [deepcopy(entry) for entry in layout['structures']
                                         if entry['rank'] <= rank],
                          'omitted': [deepcopy(entry) for entry in layout['omitted'] if entry['rank'] <= rank]}


def prepare_outpost(writer, plan, rules, camp, aliases, finished):
    """Reserve foundations and create the entire outpost only after collection.

    Native action 125 addresses a building by ID, avoiding DTA's heap-index
    creation action. It moves blocking units aside. Passable reservations
    prevent construction on the reviewed foundations until recovery.
    Creation actions are split to respect the native 511-byte INI limit.
    No ownership transfers or per-building local variables are needed.
    """
    from .engine import _action, _place
    from .messages import message_actions
    from .placement import foundation, installed_art
    from .player_perks import coalition, register_building_equivalent
    from randomizer.maps.ini import section_value_map
    from randomizer.maps.powers import _waypoint_label

    structures = camp.get('outpost', {}).get('structures', [])
    if not structures:
        return {}
    if not hasattr(writer, '_outpost_types'):
        writer._outpost_types = {}
        writer._outpost_art = installed_art()
        reservation = writer.key()
        row = deepcopy(rules['CABHUT'])
        row.update(Image='CABHUT', Name='Final Fortress reserved outpost foundation',
                   InvisibleInGame='yes', IsPassable='yes', Immune='yes', LegalTarget='no',
                   Selectable='no', Capturable='no', Unsellable='yes', Repairable='no',
                   CanBeOccupied='no', BridgeRepairHut='no', BaseNormal='no',
                   Insignificant='yes', DontScore='yes', KeepAlive='no', RadarInvisible='yes',
                   TechLevel='-1', BuildLimit='0', AIBuildThis='no', Sight='0', Power='0',
                   Powered='no', ProduceCashStartup='0', ProduceCashAmount='0', ProduceCashDelay='0')
        writer.sections[reservation] = row
        _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', reservation)
        writer._outpost_reservation = reservation
    release, tag = writer.trigger(camp['id'] + ' release outpost foundations', [(13, 0, 0)],
                                  [_action(32)], disabled=True)
    points = {**section_value_map(writer.lines, 'Waypoints'), **writer.sections.get('Waypoints', {})}
    next_waypoint = max(99, *(int(key) for key in points if key.isdigit())) + 1
    actions = []
    for entry in structures:
        original = entry['type']
        if original not in writer._outpost_types:
            source = aliases.get(original, original)
            alias = writer.key()
            row = deepcopy(writer.sections.get(source, rules[original]))
            row.update(Image=row.get('Image', original), TechLevel='-1', BuildLimit='0',
                       Capturable='no', Unsellable='yes', UndeploysInto='none', AIBuildThis='no',
                       AllowedToStartInMultiplayer='no', ProduceCashStartup='0')
            writer.sections[alias] = row
            _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', alias)
            writer._outpost_types[original] = alias
            writer.put('FFOutpostTypes', original, alias)
            if row.get('IsBaseDefense', 'no').lower() == 'yes' and plan['effects']['defense_veterancy']:
                for actor, _, _ in coalition(plan):
                    existing = writer.sections[actor].get('VeteranBuildings', '')
                    writer.put(actor, 'VeteranBuildings', ','.join(filter(None, [existing, alias])))
            # Factories, refinery docks and tech gates accept the outpost copy
            # alongside the ordinary player type without unlocking foreign tech.
            register_building_equivalent(writer, rules, original, alias, aliases,
                                         preserve_native=True, current_prerequisites=True)
            for section, current in list(writer.sections.items()):
                for field in ('BuiltAt', 'Dock'):
                    values = current.get(field, rules.get(section, {}).get(field, '')).split(',')
                    if source in values or original in values:
                        current[field] = ','.join(dict.fromkeys([*values, alias]))
        alias = writer._outpost_types[original]
        p = entry['position']
        writer.put('Waypoints', next_waypoint, p['y'] * 1000 + p['x'])
        actions.append(['125', '10', alias, '0', '0', '0', '0', _waypoint_label(next_waypoint)])
        next_waypoint += 1
        row = {'Image': original, **rules[original]}
        for dx, dy in foundation(row, writer._outpost_art):
            _place(writer, 'Structures', f'Neutral,{writer._outpost_reservation},256,'
                   f'{p["x"] + dx},{p["y"] + dy},64,{tag},1,0,1,0,0,None,None,None,0,0')
        writer.put('FFOutpostStructures.' + camp['id'], str(len(actions) - 1),
                   f'{alias},{p["x"]},{p["y"]},{next_waypoint - 1}')
    pickups = {}
    for seat, (actor, _, _) in enumerate(coalition(plan)[:len(plan.get('coop_players', [])) or 1]):
        following = None
        for offset in reversed(range(0, len(actions), 8)):
            chunk = actions[offset:offset + 8]
            if following:
                chunk = [*chunk, _action(53, trigger=following)]
            following, _ = writer.trigger(f'{camp["id"]} outpost create {actor} {offset}',
                [(13, 0, 0), (37, 0, finished)], chunk, disabled=True, owner=actor)
        notice, _ = writer.trigger(f'{camp["id"]} outpost recovery {actor}',
            [(13, 0, 0), (37, 0, finished)],
            [_action(22, trigger=release),
             *message_actions(camp['display_name'] + ': faction outpost deploying'),
             *(message_actions('Terrain limits this outpost; some structures omitted')
               if camp['outpost']['omitted'] else []), _action(53, trigger=following)],
            disabled=True, owner=actor)
        pickups[seat] = [_action(53, trigger=notice)]
        writer.put('FFOutpostClaims.' + camp['id'], actor, notice)
    return pickups
