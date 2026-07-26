"""House/country discovery for campaign maps.

Functions here only interpret map ownership. Buff planning and clone mutation
belong in their respective modules.
"""

from randomizer.core.collections import comma_items, unique_in_order
from randomizer.maps.ini import all_section_value_maps, section_value_map


def map_house_records(lines, sections=None):
    """Return map house metadata after one case-insensitive INI parse."""
    sections = sections if sections is not None else all_section_value_maps(lines)
    by_lower = {name.lower(): values for name, values in sections.items()}
    houses = by_lower.get('houses', {})
    records = {}
    for name in houses.values():
        name = name.strip()
        if not name:
            continue
        values = by_lower.get(name.lower(), {})
        country = values.get('country') or name.replace(' House', '')
        country_values = by_lower.get(country.lower(), {})
        records[name] = {
            'name': name,
            'country': country,
            'parent_country': country_values.get('parentcountry', ''),
            'side': country_values.get('side', ''),
            'allies': comma_items(values.get('allies', '')),
            'player': values.get('playercontrol', '').lower() == 'yes',
        }
    return records


def canonical_house_name(records, value):
    """Resolve FinalAlert House/Country aliases without guessing."""
    wanted = str(value or '').strip().lower()
    if not wanted or wanted in {'<none>', 'none', 'neutral'}:
        return ''

    for name in records:
        if wanted in {name.lower(), name.removesuffix(' House').lower()}:
            return name

    country_matches = [
        name
        for name, record in records.items()
        if wanted == (record.get('country') or '').strip().lower()
    ]
    return country_matches[0] if len(country_matches) == 1 else ''


def player_house_from_map(lines, records=None):
    """Return authoritative human house, preferring ``[Basic] Player``."""
    records = records if records is not None else map_house_records(lines)
    basic_player = section_value_map(lines, 'Basic').get('player', '')
    primary_house = canonical_house_name(records, basic_player)
    if primary_house:
        return primary_house
    for name, record in records.items():
        if record.get('player'):
            return name
    return ''


def player_country_from_map(lines):
    """Return authoritative human country with vanilla fallback."""
    records = map_house_records(lines)
    house = player_house_from_map(lines, records=records)
    if house:
        return records.get(house, {}).get('country') or house.replace(' House', '')
    return 'UnitedStates'


def player_controlled_houses(lines, records=None):
    """Return authoritative then secondary player-controlled map houses."""
    records = records if records is not None else map_house_records(lines)
    primary_house = player_house_from_map(lines, records=records)
    return unique_in_order(
        ([primary_house] if primary_house else [])
        + [name for name, record in records.items() if record.get('player')]
    )


def country_inherits_from(lines, country, ancestor, sections=None):
    """Return whether country equals/inherits one ancestor."""
    wanted = (ancestor or '').strip().lower()
    current = (country or '').strip()
    visited = set()
    sections = sections if sections is not None else all_section_value_maps(lines)
    by_lower = {name.lower(): values for name, values in sections.items()}
    while current and current.lower() not in visited:
        current_lower = current.lower()
        if current_lower == wanted:
            return True
        visited.add(current_lower)
        values = by_lower.get(current_lower, {})
        parent = values.get('parentcountry', '').strip()
        if not parent or parent.lower() == current_lower:
            break
        current = parent
    return False


def production_owner_countries(lines, countries, sections=None):
    """Return concrete countries plus each ParentCountry chain."""
    sections = sections if sections is not None else all_section_value_maps(lines)
    by_lower = {
        str(name).lower(): (str(name), values)
        for name, values in sections.items()
    }
    result = []
    seen = set()
    for country in countries or ():
        current = str(country or '').strip()
        chain_seen = set()
        while current and current.lower() not in chain_seen:
            current_lower = current.lower()
            chain_seen.add(current_lower)
            if current_lower not in seen:
                seen.add(current_lower)
                result.append(current)
            _section_name, values = by_lower.get(current_lower, ('', {}))
            parent = str(values.get('parentcountry', '') or '').strip()
            if not parent or parent.lower() == current_lower:
                break
            current = parent
    return result


def resolve_configured_helper_houses(records, configured_houses, player_houses=()):
    """Resolve reviewed helper names; reject missing/ambiguous entries."""
    player_names = {str(name or '').lower() for name in player_houses}
    resolved = []
    rejected = []
    for value in configured_houses or ():
        house = canonical_house_name(records, value)
        if not house:
            rejected.append(str(value))
            continue
        if house.lower() in player_names:
            continue
        resolved.append(house)
    return (unique_in_order(resolved), unique_in_order(rejected))


def is_buffable_helper_house(record):
    """Reject neutral/cinematic placeholders as helper armies."""
    name = (record.get('name') or '').lower()
    country = (record.get('country') or '').lower()
    parent = (record.get('parent_country') or '').lower()
    blocked = ('neutral', 'civilian', 'special', 'placeholder', 'cinematic')
    if parent in blocked:
        return False
    return not any(token in name or token in country for token in blocked)


def country_family(record):
    """Classify one map house record into playable production family."""
    text = ' '.join([
        record.get('name') or '',
        record.get('country') or '',
        record.get('parent_country') or '',
        record.get('side') or '',
    ]).lower()
    country_text = ' '.join([
        record.get('name') or '',
        record.get('country') or '',
        record.get('parent_country') or '',
    ]).lower()

    if 'fourthside' in text:
        return 'foehn'
    if any(token in country_text for token in (
        'foehn', 'coronia', 'haiheadquarters', 'hai_headquarters', 'lastbastion'
    )):
        return 'foehn'
    if (
        any(token in country_text for token in ('guild1', 'guild2', 'guild3'))
        and 'europeans' not in country_text
    ):
        return 'foehn'
    if any(token in country_text for token in (
        'psicorps', 'psi_corps', 'scorpion', 'epsilon', 'yuri', 'headquaters'
    )):
        return 'epsilon'
    if any(token in country_text for token in (
        'ussr', 'soviet', 'russia', 'latin', 'chinese', 'iraq', 'cuba', 'libya'
    )):
        return 'soviets'
    if any(token in country_text for token in (
        'unitedstates', 'europeans', 'euro_alliance', 'pacific', 'guild'
    )):
        return 'allies'
    if 'thirdside' in text:
        return 'epsilon'
    if 'nod' in text:
        return 'soviets'
    if 'gdi' in text:
        return 'allies'
    return ''
