"""Preserve native technology gates when Conquest creates private countries/types."""


from randomizer.final_fortress.player_perks import gate_prerequisite_overrides
from .profile import NATIVE_COUNTRIES
from .teams import HOUSE_ALIASES

TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')


def _items(value):
    return [part.strip() for part in str(value or '').split(',')
            if part.strip() and part.strip().casefold() not in ('none', '<none>')]


def _effective(writer, kind):
    return {**writer.rules.get(kind, {}), **writer.sections.get(kind, {})}


def _paths(row, *, shortcuts=False):
    paths = [tuple(_items(row.get('Prerequisite.List0', row.get('Prerequisite'))))]
    count = int(row.get('Prerequisite.Lists', '0'))
    paths.extend(tuple(_items(row.get(f'Prerequisite.List{index}')))
                 for index in range(1, count + 1))
    if shortcuts:
        paths.extend((kind,) for kind in _items(row.get('PrerequisiteOverride')))
    return list(dict.fromkeys(path for path in paths if path))


def _append_paths(writer, kind, paths):
    row = _effective(writer, kind)
    existing = set(_paths(row))
    index = int(row.get('Prerequisite.Lists', '0'))
    for path in paths:
        if path in existing or not path:
            continue
        index += 1
        writer.put(kind, f'Prerequisite.List{index}', ','.join(path))
        existing.add(path)
    if index != int(row.get('Prerequisite.Lists', '0')):
        writer.put(kind, 'Prerequisite.Lists', index)


def repair_technology(writer, members, private):
    """Bridge country plans and complete prerequisite paths, retaining native gates."""
    rules = writer.rules
    actors = [(HOUSE_ALIASES[member['slot']], NATIVE_COUNTRIES[member['loadout']['country']])
              for member in members]
    building_types = set(rules['BuildingTypes'].values())
    copies = {member['slot']: {kind: alias for kind, alias in private[member['slot']].items()
                              if kind in building_types} for member in members}
    equivalents = {}
    for aliases in copies.values():
        for kind, alias in aliases.items():
            equivalents.setdefault(kind.casefold(), []).append(alias)
    registered = {kind for category in TYPE_LISTS
                  for kind in writer.sections.get(category, rules[category]).values()}

    for kind in sorted(registered):
        row = _effective(writer, kind)
        # FactoryOwners tests factory origin countries, not Owner or Side.
        # Explicit aliases retain native required/forbidden plans for every seat.
        for field in ('FactoryOwners', 'FactoryOwners.Forbidden'):
            values = _items(row.get(field))
            native = {value.casefold() for value in values}
            additions = [actor for actor, country in actors if country.casefold() in native]
            if additions:
                writer.put(kind, field, ','.join(dict.fromkeys([*values, *additions])))
        # Negative gates must still detect a copied alternate lab/tech branch.
        # BuiltAt similarly needs to recognize private production buildings.
        for field in ('Prerequisite.Negative', 'BuiltAt'):
            values = _items(row.get(field))
            additions = [alias for value in values for alias in equivalents.get(value.casefold(), ())]
            if additions:
                writer.put(kind, field, ','.join(dict.fromkeys([*values, *additions])))

    # Include private rows too: an inherited shortcut must not bypass its house
    # filters. Native and cloned shortcut paths become ordinary alternatives.
    effective = {kind: _effective(writer, kind) for kind in rules}
    effective.update({kind: _effective(writer, kind) for kind in writer.sections})
    gate_prerequisite_overrides(writer, {}, effective)

    for member in members:
        aliases = private[member['slot']]
        buildings = {kind.casefold(): alias for kind, alias in copies[member['slot']].items()}
        for category in TYPE_LISTS:
            for kind in rules[category].values():
                paths = _paths(rules[kind], shortcuts=True)
                mapped = [tuple(buildings.get(token.casefold(), token) for token in path)
                          for path in paths]
                # Replace all direct dependencies together. Replacing one at a
                # time cannot satisfy an AND path containing two private types.
                _append_paths(writer, kind, [*paths, *mapped])
                if kind in aliases:
                    _append_paths(writer, aliases[kind], [*paths, *mapped])
    validate_technology(writer, members, private)


def validate_technology(writer, members, private):
    """Reject broken native country plans/prerequisite references before launch."""
    rules = writer.rules
    building_types = set(rules['BuildingTypes'].values())
    for member in members:
        actor = HOUSE_ALIASES[member['slot']]
        country = NATIVE_COUNTRIES[member['loadout']['country']]
        aliases = private[member['slot']]
        buildings = {kind.casefold(): alias for kind, alias in aliases.items() if kind in building_types}
        for category in TYPE_LISTS:
            for original in rules[category].values():
                kind = aliases.get(original, original)
                row = _effective(writer, kind)
                for field in ('FactoryOwners', 'FactoryOwners.Forbidden'):
                    if country.casefold() in {v.casefold() for v in _items(rules[original].get(field))}:
                        if actor not in _items(row.get(field)):
                            raise ValueError(f'Conquest technology country gate missing: {kind}.{field}.')
                actual = set(_paths(row))
                for path in _paths(rules[original], shortcuts=True):
                    mapped = tuple(buildings.get(token.casefold(), token) for token in path)
                    if mapped not in actual:
                        raise ValueError(f'Conquest technology prerequisite path missing: {kind}.')


def technology_inventory(rules):
    """Report each installed faction's normal technology-center branches."""
    from .native_effects import eligible
    sides = list(rules['Sides'])
    centers = _items(rules['General'].get('PrerequisiteTech'))
    result = {}
    for label, country in NATIVE_COUNTRIES.items():
        side = sides.index(rules[country]['Side'])
        available = {}
        for kind in centers:
            row = rules.get(kind, {})
            if (not row or not eligible(kind, row, country) or int(row.get('TechLevel', '-1')) < 0
                    or int(row.get('AIBasePlanningSide', '-1')) not in (-1, side)):
                continue
            origins = _items(row.get('FactoryOwners'))
            if origins and country.casefold() not in {v.casefold() for v in origins}:
                continue
            available[kind] = {'name': row.get('Name', kind),
                               'prerequisites': [list(path) for path in _paths(row, shortcuts=True)],
                               'factory_countries': origins}
        result[label] = available
    return result
