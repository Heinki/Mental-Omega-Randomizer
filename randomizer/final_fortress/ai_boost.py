"""Use the installed client's native Mental AI Boost game option."""

from copy import deepcopy
from pathlib import Path

from randomizer.maps.ini import all_section_value_maps_preserve


def apply_mental_ai_boost(writer, plan, rules, game_root):
    if not plan.get('mental_ai_boost', False):
        return rules
    path = Path(game_root) / 'INI' / 'Game Options' / 'Mental AI.ini'
    if not path.is_file():
        raise ValueError('Installed Mental AI Boost option is missing: ' + str(path))
    option = all_section_value_maps_preserve(path.read_text(encoding='latin-1').splitlines())
    boosted = deepcopy(rules)
    for section, row in option.items():
        boosted.setdefault(section, {}).update(row)
        for field, value in row.items():
            writer.put(section, field, value)
    return boosted
