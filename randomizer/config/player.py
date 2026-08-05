"""Read and persist launcher/player options in a small YAML subset."""

from randomizer.core.paths import CONFIG_DIR, LEGACY_CONFIG_DIR
from randomizer.core.storage import atomic_write_text
from randomizer.config.static import static_config_section


CONFIG_PATH = CONFIG_DIR / 'mental_omega_randomizer.yaml'
LEGACY_CONFIG_PATH = LEGACY_CONFIG_DIR / CONFIG_PATH.name

DEFAULT_CONFIG = static_config_section(
    'default_player_config.json', 'defaults', dict
)
UNIT_BUFF_CATALOGUE_VERSION = 1
UNIT_BUFF_TYPES_INTRODUCED = {
    1: ('passenger_capacity', 'open_topped'),
}
POWER_BUFF_CATALOGUE_VERSION = 1
POWER_BUFF_TYPES_INTRODUCED = {
    1: ('vision',),
}
ENEMY_STACK_MODEL_VERSION = 2


def deep_copy(value):
    if isinstance(value, dict):
        return {key: deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deep_copy(item) for item in value]
    return value


def deep_merge(defaults, loaded):
    merged = deep_copy(defaults)
    for key, value in (loaded or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def migrate_loaded_config(loaded):
    """Enable newly introduced buff types once without restoring old toggles."""
    if not isinstance(loaded, dict):
        return False
    generation = loaded.get('generation')
    if not isinstance(generation, dict):
        return False
    changed = False
    if generation.get('reward_mode') == 'Chaos (Experimental)':
        generation['reward_mode'] = 'Chaos'
        changed = True
    try:
        version = max(0, int(generation.get('unit_buff_catalogue_version', 0)))
    except (TypeError, ValueError):
        version = 0
    enabled = generation.get('enabled_buff_types')
    if isinstance(enabled, list):
        for introduced_version in range(
            version + 1,
            UNIT_BUFF_CATALOGUE_VERSION + 1,
        ):
            for buff_type in UNIT_BUFF_TYPES_INTRODUCED.get(
                introduced_version, ()
            ):
                if buff_type not in enabled:
                    enabled.append(buff_type)
                    changed = True
    if version < UNIT_BUFF_CATALOGUE_VERSION:
        generation['unit_buff_catalogue_version'] = (
            UNIT_BUFF_CATALOGUE_VERSION
        )
        changed = True
    try:
        power_version = max(
            0, int(generation.get('power_buff_catalogue_version', 0))
        )
    except (TypeError, ValueError):
        power_version = 0
    enabled_power = generation.get('enabled_power_buff_types')
    if isinstance(enabled_power, list):
        for introduced_version in range(
            power_version + 1,
            POWER_BUFF_CATALOGUE_VERSION + 1,
        ):
            for buff_type in POWER_BUFF_TYPES_INTRODUCED.get(
                introduced_version, ()
            ):
                if buff_type not in enabled_power:
                    enabled_power.append(buff_type)
                    changed = True
    if power_version < POWER_BUFF_CATALOGUE_VERSION:
        generation['power_buff_catalogue_version'] = (
            POWER_BUFF_CATALOGUE_VERSION
        )
        changed = True
    enemy_scaling = generation.get('enemy_scaling')
    if isinstance(enemy_scaling, dict):
        try:
            enemy_version = max(
                0, int(enemy_scaling.get('stack_model_version', 1))
            )
        except (TypeError, ValueError):
            enemy_version = 1
        if enemy_version < ENEMY_STACK_MODEL_VERSION:
            caps = enemy_scaling.get('caps')
            if isinstance(caps, dict):
                for effect_id, cap in tuple(caps.items()):
                    if cap == 3:
                        caps[effect_id] = 5
                        changed = True
            enemy_scaling['stack_model_version'] = (
                ENEMY_STACK_MODEL_VERSION
            )
            changed = True
    return changed


def parse_scalar(value):
    value = value.strip()
    if not value:
        return ''
    if value in ("''", '""'):
        return ''
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"')
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(',')]
    lowered = value.lower()
    if lowered == 'true':
        return True
    if lowered == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        return value


def quote_yaml_string(value):
    if value == '':
        return "''"
    needs_quote = (
        value.strip() != value
        or value.lower() in {'true', 'false', 'null'}
        or value.startswith(('-', '[', '{', '#', '!', '&', '*'))
        or any(char in value for char in [':', '#', "'", '"'])
    )
    if not needs_quote:
        try:
            int(value)
        except ValueError:
            return value
    return "'" + value.replace("'", "''") + "'"


def scalar_to_yaml(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(scalar_to_yaml(item) for item in value) + ']'
    return quote_yaml_string(str(value))


def read_simple_yaml(path):
    if not path.exists():
        return {}

    root = {}
    stack = [(-1, root)]
    for raw_line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        line = raw_line.strip()
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == '':
            child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def write_simple_yaml(path, data):
    lines = [
        '# Mental Omega Randomizer standalone player config.',
        '# This is intentionally Archipelago-shaped for a future AP world,',
        '# but the current launcher still runs fully offline.',
        '',
    ]

    def append_mapping(mapping, indent=0):
        prefix = ' ' * indent
        for key, value in mapping.items():
            if isinstance(value, dict):
                lines.append(f'{prefix}{key}:')
                append_mapping(value, indent + 2)
            else:
                lines.append(f'{prefix}{key}: {scalar_to_yaml(value)}')

    append_mapping(data)
    atomic_write_text(path, '\n'.join(lines) + '\n')


def load_config():
    migrate_legacy_config()
    loaded = read_simple_yaml(CONFIG_PATH)
    migrated = migrate_loaded_config(loaded)
    config = deep_merge(DEFAULT_CONFIG, loaded)
    if migrated or not CONFIG_PATH.exists():
        save_config(config)
    return config


def save_config(config):
    write_simple_yaml(CONFIG_PATH, deep_merge(DEFAULT_CONFIG, config))


def migrate_legacy_config():
    """Move pre-package player YAML into its grouped configuration folder."""
    if CONFIG_PATH.exists() or not LEGACY_CONFIG_PATH.is_file():
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_CONFIG_PATH.replace(CONFIG_PATH)
