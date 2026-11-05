"""Small persistence helpers shared by config and active seed state."""

import json
import os
import threading
from pathlib import Path


def atomic_write_text(path, text, encoding='utf-8', *, durable=False):
    """Replace a text file only after its complete new content reaches disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp'
    )
    try:
        with temporary_path.open('w', encoding=encoding) as stream:
            stream.write(text)
            if durable:
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        if durable and os.name == 'posix':
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_json_object(path):
    """Read one required JSON object; let caller decide recovery/logging."""
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'JSON root must be an object: {path}')
    return data


def atomic_write_json(path, data, *, indent=2, durable=False):
    """Serialize an object consistently through atomic text replacement."""
    options = {'indent': indent}
    if indent is None:
        options['separators'] = (',', ':')
    atomic_write_text(path, json.dumps(data, **options), durable=durable)
