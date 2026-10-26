"""Protected starting yards and defenses, with ordinary destructible expansions."""

from copy import deepcopy

from randomizer.maps.buff_values import _register_map_type


IMMUTABLE = dict(Immune='yes', ImmuneToPsionics='yes', ImmuneToSaboteurs='yes',
                 ImmuneToEMP='yes', Capturable='no', CanBeOccupied='no',
                 Unsellable='yes', CanBeReversed='no', Bombable='no',
                 Spyable='no', Warpable='no', ImmuneToTemporal='yes',
                 ImmuneToAbduction='yes', **{'Chronoshift.Allow': 'no'})


def protect_enemy_buildings(writer, plan, rules, aliases):
    """Route production separately from the protected initial construction yards."""
    from .player_perks import _eligible, register_building_equivalent
    if plan.get('plan_version', 1) < 13:
        return
    starting_only = plan.get('plan_version', 1) >= 30
    countries = list(zip((f'FFENEMY{i + 1}' for i in range(3)), plan['enemy_countries']))
    categories = {kind: category for category in ('BuildingTypes', 'VehicleTypes', 'InfantryTypes', 'AircraftTypes')
                  for kind in rules[category].values()}
    referenced = {kind for _, country in countries
                  for kind in rules[country].get('AI.PowerPlants', '').split(',') if kind}
    referenced.update(kind for value in rules['AI'].values() for kind in value.split(',')
                      if kind in rules['BuildingTypes'].values())
    referenced.update(row['DeploysInto'] for kind, row in rules.items()
                      if kind in categories and row.get('DeploysInto') in rules['BuildingTypes'].values())
    buildings = []
    for original in rules['BuildingTypes'].values():
        row = rules[original]
        if not any(_eligible(row, country) for _, country in countries):
            continue
        if (int(row.get('TechLevel', '-1')) < 0 and original not in referenced
                and row.get('ConstructionYard', 'no').lower() != 'yes'):
            continue
        aliases.setdefault(original, writer.key())
        buildings.append(original)
    deployers = {original for original in rules['VehicleTypes'].values()
                 if rules[original].get('DeploysInto') in buildings}
    mcvs = {original for original in deployers
            if rules[rules[original]['DeploysInto']].get('ConstructionYard', 'no').lower() == 'yes'}
    docking = {original for original, category in categories.items() if category != 'BuildingTypes'
               if any(kind in buildings for kind in rules[original].get('Dock', '').split(','))}
    added_units = set()

    def include_unit(original):
        if original not in categories or original in added_units:
            return
        added_units.add(original)
        aliases.setdefault(original, writer.key())
        for field in ('Convert.Deploy', 'Convert.Land', 'Convert.Water', 'UnloadingClass'):
            target = rules[original].get(field, '')
            if target in categories and categories[target] != 'BuildingTypes':
                include_unit(target)

    for original in sorted(deployers | docking):
        include_unit(original)
    for original in [*buildings, *sorted(added_units)]:
        alias = aliases[original]
        row = deepcopy(writer.sections.get(alias, rules[original]))
        eligible = [name for name, country in countries if _eligible(rules[original], country)]
        row.update(Image=row.get('Image', original), Owner=','.join([
            rules[original].get('Owner', ''), *eligible]), RequiredHouses=','.join(eligible) or 'Neutral',
            ForbiddenHouses='', AllowedToStartInMultiplayer='no')
        if not starting_only and (original in buildings or original in mcvs):
            row.update(IMMUTABLE)
            if plan.get('plan_version', 1) >= 16:
                # Immortal structures must not absorb helper attack orders.
                # This applies to normal AI production as well as scripted gifts.
                row.update(LegalTarget='no', ThreatPosed='0', SpecialThreatValue='0')
        for field in ('Prerequisite', 'PrerequisiteOverride', 'Prerequisite.Negative', 'Dock'):
            if field in row:
                row[field] = ','.join(aliases.get(kind.strip(), kind.strip()) for kind in row[field].split(','))
        for field in ('FreeUnit', 'DeploysInto', 'UndeploysInto', 'PowersUpBuilding', 'UnloadingClass',
                      'Convert.Deploy', 'Convert.Land', 'Convert.Water'):
            if row.get(field) in aliases:
                row[field] = aliases[row[field]]
        writer.sections[alias] = row
        _register_map_type(writer.sections, writer.lines, rules, categories[original], alias)
        forbidden = writer.sections.get(original, {}).get('ForbiddenHouses', rules[original].get('ForbiddenHouses', ''))
        writer.put(original, 'ForbiddenHouses', ','.join(dict.fromkeys([
            *filter(None, forbidden.split(',')), *(name for name, _ in countries)])))
        writer.put('FFEnemyBuildings' if original in buildings else 'FFEnemyBaseUnits', original, alias)
    for original in buildings:
        register_building_equivalent(writer, rules, original, aliases[original], aliases,
                                     preserve_native=plan.get('plan_version', 1) >= 14,
                                     current_prerequisites=plan.get('plan_version', 1) >= 40)
    native_yards = rules['AI']['BuildConst'].split(',')
    starting_yards = []
    if starting_only:
        for original in native_yards:
            if original not in buildings:
                continue
            alias = writer.key()
            row = deepcopy(writer.sections[aliases[original]])
            row.update(IMMUTABLE)
            # These types exist only for WithConst startup. No vehicle deploys
            # into them, and they cannot pack up into a mobile invincible MCV.
            row.update(TechLevel='-1', BuildLimit='1', AIBuildThis='no', UndeploysInto='none',
                       LegalTarget='no', ThreatPosed='0', SpecialThreatValue='0')
            writer.sections[alias] = row
            _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', alias)
            writer.put('FFEnemyStartingYards', original, alias)
            register_building_equivalent(writer, rules, original, alias, aliases, preserve_native=True,
                                         current_prerequisites=plan.get('plan_version', 1) >= 40)
            starting_yards.append(alias)
    for actor, _ in countries:
        writer.put(actor, 'StartInMultiplayer.WithConst', 'yes')
        for field, value in tuple(writer.sections[actor].items()):
            writer.put(actor, field, ','.join(aliases.get(kind, kind) for kind in value.split(',')))
    # Ares chooses the first buildable BuildConst entry for WithConst starts.
    # The private protected starts precede ordinary expansion yards. Native
    # yards forbid private enemies, so WithConst chooses a protected start;
    # production and MCV DeploysInto still use the normal vulnerable aliases.
    writer.put('AI', 'BuildConst', ','.join([
        *native_yards, *starting_yards, *(aliases[kind] for kind in native_yards if kind in aliases)]))
    for field, value in rules['AI'].items():
        additions = [aliases[kind] for kind in value.split(',') if kind in aliases]
        if additions:
            current = writer.sections.get('AI', {}).get(field, value)
            writer.put('AI', field, ','.join(dict.fromkeys([*current.split(','), *additions])))
    defaults = {'GDI': 'AlliedBaseDefenses', 'Nod': 'SovietBaseDefenses', 'ThirdSide': 'ThirdBaseDefenses'}
    for side in sorted({rules[country]['Side'] for _, country in countries}):
        native = rules.get(side, {}).get('AI.BaseDefenses', rules['AI'].get(defaults.get(side, ''), ''))
        writer.put(side, 'AI.BaseDefenses', ','.join(dict.fromkeys([
            *filter(None, native.split(',')), *(aliases[kind] for kind in native.split(',') if kind in aliases)])))


def place_fortifications(writer, plan, rules, aliases):
    from .engine import _place, _transfer_tag
    definition = plan['map'].get('enemy_defenses')
    if plan.get('plan_version', 1) < 13 or definition is None:
        return
    guards = {}
    for index, (country, waypoint) in enumerate(zip(plan['enemy_countries'], plan['map']['enemy_waypoints'])):
        actor = f'FFENEMY{index + 1}'
        tag = _transfer_tag(writer, waypoint, 'Enemy fortification ownership ' + actor)
        types = definition['types_by_country'][country]
        for slot, position in enumerate(definition['layouts'][str(waypoint)]):
            original = types[slot % len(types)]
            if original not in aliases:
                raise ValueError(f'Enemy fortification {original} lacks an isolated indestructible type.')
            if original not in guards:
                alias = writer.key()
                row = deepcopy(writer.sections[aliases[original]])
                row.update(IMMUTABLE)
                row.update(Powered='no', Power='0', TechLevel='-1', BuildLimit='0', AIBuildThis='no')
                if plan.get('plan_version', 1) >= 16:
                    row.update(LegalTarget='no', ThreatPosed='0', SpecialThreatValue='0')
                writer.sections[alias] = row
                _register_map_type(writer.sections, writer.lines, rules, 'BuildingTypes', alias)
                writer.put('FFEnemyFortifications', original, alias)
                guards[original] = alias
            _place(writer, 'Structures', f'Neutral,{guards[original]},256,{position["x"]},'
                   f'{position["y"]},64,{tag},1,0,1,0,0,None,None,None,0,0')
