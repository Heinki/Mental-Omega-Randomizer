"""Installed, registered two-player Mental Omega co-op missions."""

from pathlib import Path

from randomizer.config.static import load_static_config
from randomizer.coop.prototype import _map_config
from randomizer.coop.compatibility import resolve_path
from randomizer.missions.catalogue import (
    BASE_BUILD, NO_BUILD_PRODUCTION,
    TRUE_NO_BUILD, normalize_long_description,
)

COOP_BUILD_CLASSIFICATIONS = dict(load_static_config('missions.json')['coop_build_classifications'])


def discover_coop_missions(game_root: Path) -> list[dict]:
    missions = []
    folder = resolve_path(game_root, 'MapsMO/Cooperative')
    sources = (path for path in folder.iterdir() if path.is_file()
               and path.name.casefold().startswith('coop_')
               and path.suffix.casefold() == '.map')
    for source in sorted(sources, key=lambda path: path.name.casefold()):
        try:
            _, _, metadata, _, family = _map_config(game_root, source.stem)
        except (OSError, ValueError):
            continue
        title = metadata.get('description') or metadata.get('name') or source.stem
        classification = COOP_BUILD_CLASSIFICATIONS.get(source.stem.upper())
        if classification is None:
            raise ValueError(f'Missing co-op build classification: {source.stem.upper()}')
        missions.append({
            'index': len(missions) + 1,
            'code': source.stem.upper(),
            'coop_name': source.stem.lower(),
            'scenario': source.name,
            'title': title,
            'side': {'allies': 'Allies', 'soviets': 'Soviets',
                     'epsilon': 'Epsilon'}[family],
            'briefing': normalize_long_description(metadata.get('briefing', '')),
            'objectives': [],
            'objective_count': 1,
            'build_classification': classification,
            'no_build': classification != BASE_BUILD,
            'true_no_build': classification == TRUE_NO_BUILD,
            'no_build_production': classification == NO_BUILD_PRODUCTION,
            'operation': False,
            # Co-op maps have no campaign stage metadata. Treat them as the
            # Shop opening economy class until co-op reward tiers are tuned.
            'reward_class': 'act_1',
            'reward_multiplier': 1,
        })
    return missions
