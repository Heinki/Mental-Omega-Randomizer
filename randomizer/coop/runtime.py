"""Compare the native multiplayer runtime without including player saves."""

import hashlib
import json

from randomizer.coop.compatibility import FINGERPRINT_POLICY, normalize_text, resolve_path
from randomizer.maps.ini import all_section_value_maps


REQUIRED_FILES = (
    'version', 'gamemd.exe', 'Syringe.exe', 'Ares.dll', 'cncnet5.dll', 'cncnet5mo.dll',
    'INI/Map Code/Co-Op Easy.ini', 'INI/Map Code/Co-Op Medium.ini',
    'INI/Map Code/Co-Op Hard.ini',
    'INI/MentalOmegaMaps.ini',
)
OPTIONAL_FILES = ('Phobos.dll', 'rulesmo.ini', 'artmo.ini')


def installation_details(root):
    """Normalize checked text only; binaries retain exact byte fingerprints."""
    files, raw_files = {}, {}
    for name in (*REQUIRED_FILES, *OPTIONAL_FILES):
        path = resolve_path(root, name)
        key = name.casefold()
        if name in OPTIONAL_FILES and not path.exists():
            files[key] = raw_files[key] = 'absent'
            continue
        data = path.read_bytes()
        raw_files[key] = hashlib.sha256(data).hexdigest()
        if name == 'version' or name.endswith('.ini'):
            data = normalize_text(data)
        if name == 'INI/MentalOmegaMaps.ini':
            # Generated lobby entries differ between players and do not affect
            # native co-op spawn settings. Compare only installed mission rows.
            sections = all_section_value_maps(data.decode('latin-1').splitlines())
            native = {section.replace('\\', '/').casefold(): values
                      for section, values in sections.items()
                      if section.replace('\\', '/').casefold().startswith(
                          'mapsmo/cooperative/coop_')}
            data = json.dumps(native, sort_keys=True).encode()
        files[key] = hashlib.sha256(data).hexdigest()
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'fingerprint_policy': FINGERPRINT_POLICY, 'fingerprint': fingerprint,
            'files': files, 'raw_files': raw_files}


def validate_runtime(local, remote):
    if not isinstance(remote, dict) or remote.get('fingerprint_policy') != FINGERPRINT_POLICY:
        raise ValueError('Mental Omega compatibility check differs. Update both launchers.')
    if local['fingerprint'] != remote.get('fingerprint'):
        remote_files = remote.get('files')
        if not isinstance(remote_files, dict):
            raise ValueError('Invalid Mental Omega runtime fingerprint.')
        changed = sorted(name for name in set(local['files']) | set(remote_files)
                         if local['files'].get(name) != remote_files.get(name))
        raise ValueError('Mental Omega runtime differs: ' + ', '.join(changed)
                         + '. Use matching game files; see the connection log for hashes.')
