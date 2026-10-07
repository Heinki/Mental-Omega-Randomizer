"""Platform-independent comparisons and paths for cooperative game files."""

import hashlib
from pathlib import Path


FINGERPRINT_POLICY = 'text-newlines-v2'


def normalize_text(data):
    return data.replace(b'\r\n', b'\n')


def text_hash(data):
    return hashlib.sha256(normalize_text(data)).hexdigest()


def resolve_path(root, name):
    """Resolve installed Windows filenames on a case-sensitive filesystem."""
    root = Path(root).resolve()
    path = root
    for part in str(name).replace('\\', '/').split('/'):
        if part in {'', '.'}:
            continue
        if part == '..':
            raise ValueError('Unsafe co-op dependency path.')
        exact = path / part
        path = exact if exact.exists() else next(
            (child for child in path.iterdir() if child.name.casefold() == part.casefold()),
            exact,
        )
    if not path.resolve().is_relative_to(root):
        raise ValueError('Unsafe co-op dependency path.')
    return path
