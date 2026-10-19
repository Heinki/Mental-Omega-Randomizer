"""Create authoritative slot data from reusable player settings."""

from importlib.resources import files
import json

from .data import CATALOGUE_CHECKSUM
from .manifest import parse_manifest


def generate_manifest(settings, seed):
    # Imports stay lazy so AP can enumerate the catalogue without generating a run.
    from ._vendor.randomizer.generation.service import RunGenerator
    from ._vendor.Archipelago.run_manifest import build_run_manifest, gameplay_config_snapshot

    settings = dict(settings)
    category = settings.get('mission_category') or (
        'coop' if settings.get('coop_mode') else 'campaign'
    )
    if category not in {'campaign', 'coop'}:
        raise ValueError('Archipelago supports campaign and co-op mission categories only.')
    settings['mission_category'] = category
    settings['coop_mode'] = category == 'coop'
    filename = ('generation_coop_missions.json' if settings.get('coop_mode')
                else 'generation_missions.json')
    missions = json.loads(files(__package__).joinpath(filename).read_text(encoding='utf-8'))
    generator = RunGenerator(settings, missions)
    state = generator.generate(seed)
    config = gameplay_config_snapshot(generator.config)
    config['seed'] = seed
    return parse_manifest(build_run_manifest(
        state, config, catalogue_checksum=CATALOGUE_CHECKSUM,
    ))
