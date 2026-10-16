"""Keep large earned veteran rosters within native country INI limits."""

import re

from randomizer.maps._shared import MAX_COUNTRY_VETERAN_VALUE_LENGTH
from randomizer.maps.base import compact_player_clone_ids
from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.ui.cameos import installed_rules_registry


def compact_coop_veteran_ids(lines, countries):
    current = all_section_value_maps_preserve(lines)
    by_name = {str(name).upper(): values for name, values in current.items()}
    _, installed = installed_rules_registry(synchronous=True)
    native = {str(name).upper() for name in installed}
    aliases_needed = set()
    fields = []
    for country in sorted(countries):
        for field, value in by_name.get(str(country).upper(), {}).items():
            if str(field).lower() not in {
                'veteraninfantry', 'veteranunits', 'veteranaircraft', 'veteranbuildings',
            }:
                continue
            fields.append((country, field, str(value)))
            if len(str(value)) > MAX_COUNTRY_VETERAN_VALUE_LENGTH:
                aliases_needed.update(
                    item.strip().upper() for item in str(value).split(',')
                    if item.strip().upper().startswith(('MORP', 'MORH', 'MORG'))
                    and item.strip().upper() in by_name
                    and item.strip().upper() not in native
                )
    if not aliases_needed:
        return
    reserved = set(by_name) | native
    for registry in (current, installed):
        for values in registry.values():
            reserved.update(str(value).upper() for value in values.values())
    aliases = compact_player_clone_ids(aliases_needed, reserved)
    # Do this after all reward graphs and mutation indices are complete, so
    # every exact reference uses the same alias, including native support lists.
    pattern = re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(
        re.escape(name) for name in sorted(aliases, key=len, reverse=True)
    ) + r')(?![A-Za-z0-9_])', re.I)
    replace = lambda match: aliases[match.group().upper()]
    for country, field, value in fields:
        if len(pattern.sub(replace, value)) > MAX_COUNTRY_VETERAN_VALUE_LENGTH:
            raise ValueError(f'{country} {field} exceeds the native veteran roster limit.')
    for index, line in enumerate(lines):
        if line.lstrip().startswith('[') or '=' in line:
            lines[index] = pattern.sub(replace, line)
