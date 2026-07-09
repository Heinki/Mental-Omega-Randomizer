from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parent / 'config'
CONFIG_PATH = CONFIG_DIR / 'mental_omega_randomizer.yaml'

DEFAULT_CONFIG = {
    'player_name': 'Commander',
    'game': 'Mental Omega',
    'seed': '',
    'campaign_filter': 'All Campaigns',
    'mission_goal': 15,
    'rewards_per_objective': 1,
    'difficulty': 'Normal',
    'game_speed': '3 - Medium',
    'archipelago': {
        'enabled': False,
        'server': '',
        'slot_name': 'Commander',
        'password': '',
        'future_world_name': 'Mental Omega',
    },
    'generation': {
        'starting_unlocked_missions': 3,
        'enabled_reward_types': ['access', 'buff'],
        'randomize_unit_access': True,
        'include_buff_rewards': True,
        'enabled_buff_types': [
            'production',
            'cost',
            'speed',
            'armor',
            'health',
            'sight',
            'damage',
            'reload',
            'rof',
            'range',
            'ammo',
            'self_healing',
            'cloak',
            'sensors',
            'guard_range',
            'veteran',
        ],
        'safe_player_country_buffs': True,
        'allow_shared_country_buffs': False,
        'buff_allied_helpers': False,
        'transient_rulesmo_buffs': False,
        'experimental_house_buffs': False,
    },
}


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def load_config():
    loaded = read_simple_yaml(CONFIG_PATH)
    config = deep_merge(DEFAULT_CONFIG, loaded)
    if not CONFIG_PATH.exists():
        save_config(config)
    return config


def save_config(config):
    write_simple_yaml(CONFIG_PATH, deep_merge(DEFAULT_CONFIG, config))
