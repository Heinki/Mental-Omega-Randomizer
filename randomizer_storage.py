"""Small persistence helpers shared by config and active seed state."""

import json
import os
import threading
from pathlib import Path


def atomic_write_text(path, text, encoding='utf-8'):
    """Replace a text file only after its complete new content reaches disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp'
    )
    try:
        temporary_path.write_text(text, encoding=encoding)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_json_object(path):
    """Read one required JSON object; let caller decide recovery/logging."""
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'JSON root must be an object: {path}')
    return data


def atomic_write_json(path, data):
    """Serialize an object consistently through atomic text replacement."""
    atomic_write_text(path, json.dumps(data, indent=2))
