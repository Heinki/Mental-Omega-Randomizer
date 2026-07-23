"""Extract and decode Mental Omega unit cameo PCX files for the Tk UI."""

import json
import os
import re
import struct
import subprocess
import threading
import zlib
from pathlib import Path

from randomizer_diagnostics import event as log_event
from randomizer_paths import CAMEO_CACHE_DIR, GAME_ROOT, MAP_RENDERER_DIR


ART_CACHE_PATH = CAMEO_CACHE_DIR / 'artmo.ini'
RULES_CACHE_PATH = CAMEO_CACHE_DIR / 'rulesmo.ini'
SAFE_ASSET_NAME = re.compile(r'^[A-Za-z0-9_.-]+$')
_ART_CAMEO_NAMES = None
_RULES_ART_NAMES = None
_RULES_SIDEBAR_NAMES = None
_RULES_SECTION_VALUES = None
_EXTRACTION_LOCK = threading.Lock()
_PENDING_LOCK = threading.Lock()
_ATTEMPTED_CAMEOS = set()
_PENDING_EXTRACTIONS = set()
MIX_READER_ASSEMBLY_NAMES = (
    'NLog.dll',
    'CNCMaps.Shared.dll',
    'CNCMaps.FileFormats.dll',
)


def powershell_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def mix_reader_assembly_paths():
    return [MAP_RENDERER_DIR / name for name in MIX_READER_ASSEMBLY_NAMES]


def powershell_mix_reader_load_script():
    """Load marked renderer assemblies without modifying their Zone.Identifier streams."""
    return '\n'.join(
        '[void][Reflection.Assembly]::Load([IO.File]::ReadAllBytes('
        + powershell_literal(path)
        + '))'
        for path in mix_reader_assembly_paths()
    )


def extract_mix_files(requests):
    """Extract requested MIX members using the renderer's bundled MIX reader."""
    normalized = tuple(sorted(
        (str(Path(source).name).upper(), str(Path(output)))
        for source, output in requests
    ))
    if threading.current_thread() is threading.main_thread():
        # MIX scans can take several seconds on large installations. Never run
        # one in Tk's event thread; the next ordinary refresh will consume the
        # completed cache files.
        with _PENDING_LOCK:
            if normalized in _PENDING_EXTRACTIONS:
                return False
            _PENDING_EXTRACTIONS.add(normalized)

        def worker():
            try:
                with _EXTRACTION_LOCK:
                    _extract_mix_files(requests)
            finally:
                with _PENDING_LOCK:
                    _PENDING_EXTRACTIONS.discard(normalized)

        threading.Thread(
            target=worker, name='MentalOmegaCameoExtractor', daemon=True
        ).start()
        return False
    # Requests use one shared handoff file. Cache construction and UI cameo
    # loading can run on background threads, so serialize the complete handoff
    # and PowerShell read rather than only protecting the JSON write.
    with _EXTRACTION_LOCK:
        return _extract_mix_files(requests)


def _extract_mix_files(requests):
    pending = []
    for source_name, output_path in requests:
        source_name = Path(source_name).name
        if not SAFE_ASSET_NAME.fullmatch(source_name):
            continue
        output_path = Path(output_path)
        if output_path.exists() and output_path.stat().st_size > 0:
            continue
        pending.append({'name': source_name.upper(), 'output': str(output_path)})
    if not pending:
        return True

    assembly_paths = mix_reader_assembly_paths()
    if any(not path.exists() for path in assembly_paths):
        log_event(
            'cameo_extraction_unavailable',
            assemblies={path.name: path.exists() for path in assembly_paths},
        )
        return False

    CAMEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request_path = CAMEO_CACHE_DIR / (
        f'extract_requests-{os.getpid()}-{threading.get_ident()}.json'
    )
    request_path.write_text(json.dumps(pending), encoding='utf-8')
    script = f"""
$ErrorActionPreference = 'Stop'
{powershell_mix_reader_load_script()}
$pending = [Collections.Generic.List[object]]::new()
$decodedRequests = Get-Content -Raw {powershell_literal(request_path)} | ConvertFrom-Json
foreach($request in $decodedRequests) {{
    $pending.Add($request)
}}
foreach($mixPath in (Get-ChildItem {powershell_literal(GAME_ROOT / '*.mix')} | Sort-Object Name -Descending)) {{
    if($pending.Count -eq 0) {{ break }}
    $foundHere = [Collections.Generic.List[object]]::new()
    $stream = [IO.File]::OpenRead($mixPath.FullName)
    try {{
        try {{
            $mix = New-Object CNCMaps.FileFormats.MixFile($stream, $mixPath.Name, $false)
            foreach($request in @($pending.ToArray())) {{
                if($mix.ContainsFile([string]$request.name)) {{ $foundHere.Add($request) }}
            }}
        }} catch {{
            # Some installations contain MIX-like archives unsupported by the
            # renderer reader. Skip that file instead of aborting the complete
            # cameo scan and freezing every later UI refresh.
            continue
        }}
    }} finally {{
        $stream.Dispose()
    }}
    # Virtual files share their MIX stream. Reopen it for every extraction so
    # reading one cameo cannot leave the next virtual file at the wrong offset.
    foreach($request in $foundHere) {{
        $extractStream = [IO.File]::OpenRead($mixPath.FullName)
        try {{
            $extractMix = New-Object CNCMaps.FileFormats.MixFile($extractStream, $mixPath.Name, $false)
            $virtualFile = $extractMix.OpenFile(
                [string]$request.name,
                [CNCMaps.FileFormats.FileFormat]::Ukn,
                [CNCMaps.FileFormats.VirtualFileSystem.CacheMethod]::NoCache
            )
            try {{
                $parent = [IO.Path]::GetDirectoryName([string]$request.output)
                [IO.Directory]::CreateDirectory($parent) | Out-Null
                $bytes = $virtualFile.Read([int]$virtualFile.Length)
                [IO.File]::WriteAllBytes([string]$request.output, $bytes)
            }} finally {{
                if($virtualFile) {{ $virtualFile.Dispose() }}
            }}
        }} finally {{
            $extractStream.Dispose()
        }}
        $pending.Remove($request) | Out-Null
    }}
}}
if($pending.Count -gt 0) {{
    Write-Output ('Missing MIX assets: ' + (($pending | ForEach-Object {{ $_.name }}) -join ', '))
}}
"""
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            cwd=GAME_ROOT,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    finally:
        request_path.unlink(missing_ok=True)
    log_event(
        'cameo_extraction_finished',
        requested=[item['name'] for item in pending],
        returncode=result.returncode,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )
    return result.returncode == 0


def _iter_ini_records(path, strict_sections=False):
    """Yield section and value records from an installed INI-like file."""
    for raw_line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw_line.strip()
        section_pattern = r'^\[([^]]+)\]$' if strict_sections else r'^\[([^]]+)\]'
        section_match = re.match(section_pattern, line)
        if section_match:
            yield 'section', section_match.group(1).strip(), None
            continue
        if not line or line.startswith(';') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        yield 'value', key.strip(), value.split(';', 1)[0].strip()


def _read_ini_sections(path):
    """Read complete installed INI sections, retaining prior registry behavior."""
    sections = {}
    current_values = None
    for record_type, key, value in _iter_ini_records(path, strict_sections=True):
        if record_type == 'section':
            current_values = {}
            sections[key] = current_values
        elif current_values is not None:
            current_values[key] = value
    return sections


def _extract_ini_key_mapping(cache_path, source_name, key_name, upper_value=False):
    """Return safe values for one INI key, indexed by upper-case section."""
    if not cache_path.exists():
        extract_mix_files([(source_name, cache_path)])
    if not cache_path.exists():
        return {}

    mapping = {}
    section = ''
    for record_type, key, value in _iter_ini_records(cache_path):
        if record_type == 'section':
            section = key.upper()
            continue
        if not section or key.lower() != key_name.lower():
            continue
        if SAFE_ASSET_NAME.fullmatch(value):
            mapping[section] = value.upper() if upper_value else value
    return mapping


def installed_rules_registry():
    """Return installed rules sections and ordered SuperWeaponType IDs.

    Power clones need the complete installed section, not a map-overridden
    version. Keeping this on the existing rules cache also works in packaged
    mode without placing a loose global rulesmo.ini in the game directory.
    """
    global _RULES_SECTION_VALUES
    if _RULES_SECTION_VALUES is None:
        if not RULES_CACHE_PATH.exists():
            extract_mix_files([('RULESMO.INI', RULES_CACHE_PATH)])
        if not RULES_CACHE_PATH.exists():
            return (), {}

        _RULES_SECTION_VALUES = _read_ini_sections(RULES_CACHE_PATH)

    sections = {
        section: dict(values)
        for section, values in _RULES_SECTION_VALUES.items()
    }
    superweapon_types = tuple(sections.get('SuperWeaponTypes', {}).values())
    return superweapon_types, sections


def art_cameo_names():
    global _ART_CAMEO_NAMES
    if _ART_CAMEO_NAMES is not None:
        return _ART_CAMEO_NAMES
    mapping = _extract_ini_key_mapping(
        ART_CACHE_PATH, 'ARTMO.INI', 'CameoPCX'
    )
    if mapping or ART_CACHE_PATH.exists():
        _ART_CAMEO_NAMES = mapping
    return mapping


def rules_art_names():
    global _RULES_ART_NAMES
    if _RULES_ART_NAMES is not None:
        return _RULES_ART_NAMES
    mapping = _extract_ini_key_mapping(
        RULES_CACHE_PATH, 'RULESMO.INI', 'Image', upper_value=True
    )
    if mapping or RULES_CACHE_PATH.exists():
        _RULES_ART_NAMES = mapping
    return mapping


def rules_sidebar_names():
    """Return installed SidebarPCX filenames keyed by rules section."""
    global _RULES_SIDEBAR_NAMES
    if _RULES_SIDEBAR_NAMES is not None:
        return _RULES_SIDEBAR_NAMES
    mapping = _extract_ini_key_mapping(
        RULES_CACHE_PATH, 'RULESMO.INI', 'SidebarPCX'
    )
    if mapping or RULES_CACHE_PATH.exists():
        _RULES_SIDEBAR_NAMES = mapping
    return mapping


def png_chunk(kind, payload):
    return (
        struct.pack('>I', len(payload))
        + kind
        + payload
        + struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _reject_pcx(pcx_path, reason):
    log_event('cameo_decode_rejected', path=str(pcx_path), reason=reason)
    return False


def decode_pcx_to_png(pcx_path, png_path):
    data = Path(pcx_path).read_bytes()
    if len(data) < 897 or data[0] != 0x0A or data[2] != 1 or data[3] != 8:
        return _reject_pcx(pcx_path, 'unsupported_header_or_encoding')

    x_min = int.from_bytes(data[4:6], 'little')
    y_min = int.from_bytes(data[6:8], 'little')
    x_max = int.from_bytes(data[8:10], 'little')
    y_max = int.from_bytes(data[10:12], 'little')
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    planes = data[65]
    bytes_per_line = int.from_bytes(data[66:68], 'little')
    if width <= 0 or height <= 0 or planes != 1 or bytes_per_line < width:
        return _reject_pcx(pcx_path, 'invalid_dimensions_or_plane_layout')
    if data[-769] != 0x0C:
        return _reject_pcx(pcx_path, 'missing_256_color_palette')

    expected = bytes_per_line * height
    decoded = bytearray()
    cursor = 128
    data_end = len(data) - 769
    while cursor < data_end and len(decoded) < expected:
        value = data[cursor]
        cursor += 1
        if value & 0xC0 == 0xC0:
            run = value & 0x3F
            if cursor >= data_end:
                return _reject_pcx(pcx_path, 'truncated_rle_run')
            value = data[cursor]
            cursor += 1
            decoded.extend([value] * run)
        else:
            decoded.append(value)
    if len(decoded) < expected:
        return _reject_pcx(pcx_path, 'truncated_pixel_data')

    palette = data[-768:]
    rgb = bytearray(width * height * 3)
    output = 0
    for y in range(height):
        row_start = y * bytes_per_line
        for color_index in decoded[row_start:row_start + width]:
            palette_index = color_index * 3
            rgb[output:output + 3] = palette[palette_index:palette_index + 3]
            output += 3

    scanlines = b''.join(
        b'\x00' + bytes(rgb[y * width * 3:(y + 1) * width * 3])
        for y in range(height)
    )
    png = (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + png_chunk(b'IDAT', zlib.compress(scanlines, level=9))
        + png_chunk(b'IEND', b'')
    )
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(png)
    return True


def ensure_requested_cameos(requested):
    """Extract and decode a mapping of stable UI keys to PCX filenames."""
    missing_pcxs = []
    for cameo_name in set(requested.values()):
        pcx_path = CAMEO_CACHE_DIR / cameo_name.lower()
        png_path = pcx_path.with_suffix('.png')
        if (
            cameo_name.upper() not in _ATTEMPTED_CAMEOS
            and (not pcx_path.exists() or pcx_path.stat().st_size == 0)
            and not png_path.exists()
        ):
            missing_pcxs.append((cameo_name, pcx_path))
    if missing_pcxs:
        _ATTEMPTED_CAMEOS.update(name.upper() for name, _path in missing_pcxs)
        extract_mix_files(missing_pcxs)

    result = {}
    for asset_id, cameo_name in requested.items():
        pcx_path = CAMEO_CACHE_DIR / cameo_name.lower()
        png_path = pcx_path.with_suffix('.png')
        if not png_path.exists() and pcx_path.exists():
            try:
                decode_pcx_to_png(pcx_path, png_path)
            except OSError:
                pass
        if png_path.exists():
            result[asset_id] = png_path
    return result


def ensure_unit_cameos(unit_ids):
    cameo_names = art_cameo_names()
    art_names = rules_art_names()
    requested = {}
    for unit_id in unit_ids:
        unit_id = str(unit_id).upper()
        cameo_name = cameo_names.get(art_names.get(unit_id, unit_id))
        if cameo_name:
            requested[unit_id] = cameo_name
    return ensure_requested_cameos(requested)


def ensure_superweapon_cameos(superweapon_ids):
    """Resolve the installed sidebar icon for each requested superweapon."""
    sidebar_names = rules_sidebar_names()
    requested = {}
    for superweapon_id in superweapon_ids:
        superweapon_id = str(superweapon_id).upper()
        cameo_name = sidebar_names.get(superweapon_id)
        if cameo_name:
            requested[superweapon_id] = cameo_name
    return ensure_requested_cameos(requested)
