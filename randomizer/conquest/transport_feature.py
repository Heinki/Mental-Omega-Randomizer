"""Developer switch matching Mental Omega's experimental source-only gate."""

COOP_FEATURE_ENABLED = True


def enabled(config):
    return COOP_FEATURE_ENABLED and config.get('coop_mode') is True


def player_count(value):
    if isinstance(value, bool) or str(value) not in {'2', '3', '4'}:
        raise ValueError('Experimental Conquest co-op requires 2, 3, or 4 players.')
    return int(value)


def require_enabled():
    if not COOP_FEATURE_ENABLED:
        raise ValueError('Experimental co-op is disabled in this build.')
