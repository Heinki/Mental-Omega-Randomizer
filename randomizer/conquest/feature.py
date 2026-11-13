"""Build-time switch for Conquest mode."""

CONQUEST_FEATURE_ENABLED = True


def enabled():
    """Use the same release gate in source and packaged launchers."""
    return CONQUEST_FEATURE_ENABLED is True
