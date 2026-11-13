"""Reuse fully validated deterministic battle plans within one process."""

from copy import deepcopy
from functools import lru_cache, wraps
import json


def cached_plan(builder):
    """Cache exact frozen inputs, returning independent mutable documents.

    A new configuration or any changed input still runs the complete builder
    and its validation. Failed builds are never cached. Saved plans are still
    compared with the resulting plan by the persistence layer on every read.
    """
    @lru_cache(maxsize=8)
    def calculate(config_json, options_json):
        return builder(json.loads(config_json), **json.loads(options_json))

    @wraps(builder)
    def build(config, **options):
        config_json = json.dumps(config, separators=(',', ':'))
        options_json = json.dumps(options, separators=(',', ':'))
        return deepcopy(calculate(config_json, options_json))

    return build
