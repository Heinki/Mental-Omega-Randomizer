"""Map-supported skirmish countries and launch-only faction identities."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def _map_catalogue(path):
    from randomizer.skirmish import all_section_value_maps_preserve
    if not path.is_file():
        return {}
    return {
        name.replace('\\', '/').casefold(): {
            key.casefold(): value.split(';', 1)[0].strip()
            for key, value in values.items()
        }
        for name, values in all_section_value_maps_preserve(
            path.read_text(encoding='latin-1').splitlines()).items()
    }


def map_countries(root, definition, *, rows=None):
    """Respect native map side exclusions and disabled country overrides."""
    from randomizer.skirmish import GAME, all_section_value_maps_preserve, playable_countries
    root = Path(root).resolve()
    source = (root / definition['path']).resolve()
    if not source.is_relative_to(root):
        raise ValueError('Skirmish map must belong to this installation.')
    if rows is None:
        rows = all_section_value_maps_preserve(source.read_text(encoding='latin-1').splitlines())
    if GAME == 'dta':
        from randomizer.coop.catalogue import inherited_sections
        rows = inherited_sections(root, source)
    filename = 'MentalOmegaMaps.ini' if GAME == 'mo' else 'MPMaps.ini'
    catalogue = _map_catalogue(root / 'INI' / filename)
    key = source.relative_to(root).with_suffix('').as_posix().casefold()
    metadata = dict(catalogue.get(key, {}))
    seen = set()
    while metadata.get('basesection'):
        parent = metadata.pop('basesection').replace('\\', '/').casefold()
        if parent in seen or parent not in catalogue:
            raise ValueError('Invalid Skirmish catalogue BaseSection.')
        seen.add(parent)
        metadata = {**catalogue[parent], **metadata}
    countries = playable_countries()
    denied = {
        int(token.strip()) for token in metadata.get('disallowedplayersides', '').split(',')
        if token.strip()
    }
    overrides = {name.casefold(): {key.casefold(): value for key, value in values.items()}
                 for name, values in rows.items()}
    return {
        label: country for index, (label, country) in enumerate(countries.items())
        if index not in denied
        and overrides.get(country.casefold(), {}).get('multiplay', 'yes').casefold()
        not in ('no', 'false', '0')
    }


def mission_countries(mission):
    """Use discovered map support, including for runs saved before the picker."""
    from randomizer.skirmish import playable_countries
    countries = playable_countries()
    supported = mission.get('skirmish_map', {}).get('countries', tuple(countries.values()))
    return {label: country for label, country in countries.items() if country in supported}


def faction_for_country(country):
    from randomizer.skirmish import GAME, playable_countries
    if GAME == 'mo':
        from randomizer.challenges.catalogue import SIDE_COUNTRIES, SIDE_FAMILIES
        family = SIDE_FAMILIES[SIDE_COUNTRIES.index(country)]
        return dict(allies='Allies', soviets='Soviets', epsilon='Epsilon', foehn='Foehn')[family]
    return next(label for label, value in playable_countries().items() if value == country)


def selected_mission(mission, selections):
    """Keep the saved mission code, map weight, and progression receipt intact."""
    if not mission or not mission.get('skirmish'):
        return mission
    countries = mission_countries(mission)
    country = selections.get(mission['scenario']) if isinstance(selections, dict) else None
    if country not in countries.values():
        country = mission['skirmish_country']
    if country not in countries.values():
        raise ValueError('This Skirmish has no supported selected faction.')
    label = next(label for label, value in countries.items() if value == country)
    faction = faction_for_country(country)
    return dict(mission, skirmish_country=country, side=faction, faction=faction,
                title=f'1v1 Skirmish: {mission["skirmish_map"]["name"]} ({label})')


def catalogue_report(root):
    """Inventory actual installed maps and their permitted player countries."""
    from randomizer.skirmish import GAME, discover_maps
    maps = discover_maps(root)
    return {
        'game': GAME,
        'map_count': len(maps),
        'maps': [dict(path=relative, name=definition['name'],
                      factions=map_countries(root, definition))
                 for relative, definition in maps.items()],
    }


if __name__ == '__main__':
    import json
    from randomizer.core.paths import GAME_ROOT
    print(json.dumps(catalogue_report(GAME_ROOT), indent=2))
