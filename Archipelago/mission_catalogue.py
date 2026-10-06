"""Read mission data for installed-game and clean release builds."""

from importlib.resources import files
import json

from randomizer.core.paths import BATTLE_CLIENT_INI
from randomizer.missions.catalogue import parse_missions


def generation_missions(path=None):
    """Use installed missions when available, otherwise the reviewed snapshot."""
    path = BATTLE_CLIENT_INI if path is None else path
    if path.is_file():
        missions = parse_missions(path)
    else:
        missions = json.loads(
            files(__package__).joinpath('generation_missions.json').read_text(
                encoding='utf-8'
            )
        )
    if not missions or len({mission['code'] for mission in missions}) != len(missions):
        raise ValueError('Archipelago requires a nonempty mission catalogue with unique codes.')
    return missions
