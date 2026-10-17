"""Display challenge factions from authored opponents, without changing rules."""

from __future__ import annotations

from collections.abc import Mapping


_COUNTRY_GROUPS = ('Allies', 'Soviets', 'Epsilon', 'Foehn')


def challenge_color_group(mission: Mapping) -> str | None:
    """Return a pure opponent faction, Mixed, or no challenge presentation.

    ``side`` and ``player_country`` describe the selectable human house and
    cannot identify a challenge's opponents. Native country indices form
    four consecutive groups of three in the installed challenge catalogue.
    Unknown or incomplete metadata keeps the caller's existing presentation.
    """
    if not isinstance(mission, Mapping):
        return None
    if (mission.get('mission_category') != 'challenge'
            and not mission.get('challenge_name')):
        return None
    enemies = mission.get('enemy_houses')
    if not isinstance(enemies, (tuple, list)) or not enemies:
        return None
    groups = set()
    for enemy in enemies:
        if not isinstance(enemy, (tuple, list)) or len(enemy) != 3:
            return None
        country = enemy[0]
        if type(country) is not int or not 0 <= country < 12:
            return None
        groups.add(_COUNTRY_GROUPS[country // 3])
    return next(iter(groups)) if len(groups) == 1 else 'Mixed'


def challenge_faction_label(mission: Mapping) -> str | None:
    """Describe the opposing faction using the same identity as its color."""
    return challenge_color_group(mission)
