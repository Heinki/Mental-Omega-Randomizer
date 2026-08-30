"""Normalization for optional seed-wide content-access limits."""


DEFAULT_ACCESS_LIMIT = 1


def normalize_access_limits(value):
    """Return positive unit/building and power caps with legacy-safe defaults."""
    source = value if isinstance(value, dict) else {}

    def positive_int(key):
        try:
            result = int(source.get(key, DEFAULT_ACCESS_LIMIT))
        except (TypeError, ValueError):
            result = DEFAULT_ACCESS_LIMIT
        return max(1, result)

    return {
        'enabled': bool(source.get('enabled', False)),
        'units': positive_int('units'),
        'powers': positive_int('powers'),
    }
