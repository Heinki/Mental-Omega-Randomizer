"""Platform-independent comparisons for native co-op text files."""

import hashlib


FINGERPRINT_POLICY = 'mo-conquest-runtime-v1'


def normalize_text(data):
    return data.replace(b'\r\n', b'\n')


def text_hash(data):
    return hashlib.sha256(normalize_text(data)).hexdigest()
