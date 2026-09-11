"""Create authoritative slot data from reusable player settings."""

from importlib.resources import files
import json

from .data import CATALOGUE_CHECKSUM
from .manifest import parse_manifest


def generate_manifest(settings, seed):
    # Imports stay lazy so AP can enumerate the catalogue without generating a run.
    from ._vendor.randomizer.generation.service import RunGenerator
    from ._vendor.Archipelago.run_manifest import build_run_manifest, gameplay_config_snapshot

    missions = json.loads(files(__package__).joinpath('generation_missions.json').read_text(encoding='utf-8'))
    generator = RunGenerator(settings, missions)
    state = generator.generate(seed)
    config = gameplay_config_snapshot(generator.config)
    config['seed'] = seed
    return parse_manifest(build_run_manifest(
        state, config, catalogue_checksum=CATALOGUE_CHECKSUM,
    ))
