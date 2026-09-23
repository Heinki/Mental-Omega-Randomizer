"""Installed, registered two-player Mental Omega co-op missions."""

from pathlib import Path

from randomizer.coop.prototype import _map_config
from randomizer.missions.catalogue import BASE_BUILD, normalize_long_description


def discover_coop_missions(game_root: Path) -> list[dict]:
    missions = []
    folder = game_root / 'MapsMO' / 'Cooperative'
    for source in sorted(folder.glob('coop_*.map')):
        try:
            _, _, metadata, _, family = _map_config(game_root, source.stem)
        except (OSError, ValueError):
            continue
        title = metadata.get('description') or metadata.get('name') or source.stem
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
            'build_classification': BASE_BUILD,
            'no_build': False,
            'true_no_build': False,
            'no_build_production': False,
            'operation': False,
            'reward_class': '',
            'reward_multiplier': 1,
        })
    return missions
