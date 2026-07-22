"""Static campaign helper/enemy house policy.

Only ``allies`` are eligible for player rewards when the setting is enabled.
Every player-controlled map house is included independently. ``enemies`` is an
explicit review list; any unlisted AI house is still denied by default.

The allowlists were cross-checked against the Mental Omega mission wiki. A
force listed as an opponent at any mission phase remains denied even if it can
later break free, transfer, or become friendly, because map-local stat changes
exist from scenario load and cannot be removed safely during that transition.
"""

from randomizer_static_config import load_static_config


_MISSION_CONFIG = load_static_config('missions.json')

MISSION_HOUSE_CONFIG = {
    code: {key: tuple(values) for key, values in entry.items()}
    for code, entry in _MISSION_CONFIG['house_config'].items()
}


# Houses whose physical factories become player-usable through a local
# capture/current-object script rather than Action 36's full-house transfer.
# This policy is deliberately separate from MISSION_HOUSE_CONFIG: these
# houses are production discovery sources only and must never become reward
# helpers or receive player buffs merely because their base is later taken.
MISSION_PLAYER_PRODUCTION_HOUSES = {
    code: tuple(values)
    for code, values in _MISSION_CONFIG['player_production_houses'].items()
}

# These missions deliberately split human control across multiple HouseTypes.
# Building-free powers must exist for each phase/hero house because mission
# logic can require activation by that exact trigger owner. Other missions keep
# the authoritative [Basic] Player-only grant to avoid empowering temporary
# PlayerControl/script houses unnecessarily.
MISSION_PLAYER_POWER_HOUSES = {
    code: tuple(values)
    for code, values in _MISSION_CONFIG['player_power_houses'].items()
}


def mission_house_config(code):
    """Return immutable helper/enemy lists for a catalogue mission code."""
    entry = MISSION_HOUSE_CONFIG.get(str(code or '').upper(), {})
    return {
        'allies': tuple(entry.get('allies', ())),
        'enemies': tuple(entry.get('enemies', ())),
    }


def mission_player_production_houses(code):
    """Return map houses whose captured factories become player-usable."""
    return tuple(
        MISSION_PLAYER_PRODUCTION_HOUSES.get(str(code or '').upper(), ())
    )


def mission_player_power_houses(code):
    """Return reviewed multi-house recipients for building-free powers."""
    return tuple(MISSION_PLAYER_POWER_HOUSES.get(str(code or '').upper(), ()))
