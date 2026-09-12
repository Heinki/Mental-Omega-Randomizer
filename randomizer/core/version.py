"""Single source of truth for launcher and APWorld release versions."""

APP_VERSION = '1.37'
APWORLD_VERSION = '0.6.4'
ARCHIPELAGO_VERSION = '0.6.7'
APWORLD_CONTAINER_VERSION = 8


def release_versions():
    """Return version metadata consumed by every release builder."""
    return {
        'app_version': APP_VERSION,
        'apworld_version': APWORLD_VERSION,
        'archipelago_version': ARCHIPELAGO_VERSION,
        'apworld_container_version': APWORLD_CONTAINER_VERSION,
    }
