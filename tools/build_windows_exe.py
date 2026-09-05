"""Build and verify the Windows launcher with a Windows Python runtime.

This driver mirrors build_exe.ps1 but can also run through Windows Python in
Wine, allowing Linux maintainers to produce the same PyInstaller target.
"""

from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


REQUIRED_PYTHON = '3.14.6'
REQUIRED_WEBSOCKETS = '17.0'
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f'{label} is missing: {path}')
    return path


def write_version_info(path: Path, app_version: str) -> None:
    parts = [int(value) for value in app_version.split('.')]
    parts.extend([0] * (4 - len(parts)))
    version_tuple = ', '.join(str(value) for value in parts[:4])
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Mental Omega Randomizer contributors'),
          StringStruct(u'FileDescription', u'Mental Omega Randomizer Launcher'),
          StringStruct(u'FileVersion', u'{app_version}'),
          StringStruct(u'InternalName', u'MentalOmegaRandomizer'),
          StringStruct(u'OriginalFilename', u'MentalOmegaRandomizer.exe'),
          StringStruct(u'ProductName', u'Mental Omega Randomizer Launcher'),
          StringStruct(u'ProductVersion', u'{app_version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""",
        encoding='utf-8',
    )


def write_config_manifest(config_dir: Path, path: Path) -> None:
    files = {}
    for source in sorted(config_dir.rglob('*')):
        if not source.is_file() or 'player' in source.relative_to(config_dir).parts:
            continue
        if source.suffix.lower() != '.json' and not (
            source.suffix.lower() == '.ini'
            and source.name.startswith('Randomizer')
        ):
            continue
        relative = source.relative_to(config_dir).as_posix()
        files[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    path.write_text(
        json.dumps({'format': 1, 'files': files}, indent=2),
        encoding='utf-8',
    )


def prepare_tcl_bundle(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination)
    init_path = destination / 'init.tcl'
    original_path = destination / '_mor_original_init.tcl'
    init_path.replace(original_path)
    init_path.write_text(
        '# Mental Omega Randomizer bundled Tcl bootstrap\n'
        'set ::tcl_library [file dirname [info script]]\n'
        'source [file join $::tcl_library _mor_original_init.tcl]\n',
        encoding='utf-8',
    )


def run_checked(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    print('+', subprocess.list2cmdline(command), flush=True)
    return subprocess.run(command, check=True, **kwargs)


def build(output: Path) -> None:
    if os.name != 'nt':
        raise RuntimeError(
            'A Windows Python runtime is required. On Linux use build_exe_wine.sh.'
        )
    if platform.python_version() != REQUIRED_PYTHON:
        raise RuntimeError(
            f'Python {REQUIRED_PYTHON} is required; '
            f'found {platform.python_version()}.'
        )

    import PyInstaller
    import websockets

    if PyInstaller.__version__ != '6.21.0':
        raise RuntimeError(f'PyInstaller 6.21.0 is required; found {PyInstaller.__version__}.')
    if websockets.__version__ != REQUIRED_WEBSOCKETS:
        raise RuntimeError(
            f'websockets {REQUIRED_WEBSOCKETS} is required; '
            f'found {websockets.__version__}.'
        )

    sys.path.insert(0, str(PROJECT_ROOT))
    bytecode_ready = compileall.compile_file(
        PROJECT_ROOT / 'launcher_gui.py', force=True, quiet=1
    ) and compileall.compile_dir(
        PROJECT_ROOT / 'randomizer', force=True, quiet=1
    )
    if not bytecode_ready:
        raise RuntimeError('Source bytecode refresh failed; EXE was not built.')
    from randomizer.config.static import (
        REQUIRED_STATIC_CONFIGS,
        validate_static_configs,
    )
    from randomizer.core.version import APP_VERSION

    validate_static_configs(REQUIRED_STATIC_CONFIGS)
    run_checked(
        [sys.executable, '-m', 'unittest', 'randomizer.launch.self_check', '-v'],
        cwd=PROJECT_ROOT,
    )

    python_root = Path(sys.base_prefix)
    icon = require_path(PROJECT_ROOT / 'mo-logo-puzzle-icon.ico', 'Launcher icon')
    configs = require_path(PROJECT_ROOT / 'configs', 'Static config directory')
    assets = require_path(PROJECT_ROOT / 'assets', 'Asset directory')
    runtime_hook = require_path(
        PROJECT_ROOT / 'tools' / 'pyinstaller_tk_runtime.py',
        'Tcl/Tk runtime hook',
    )
    tkinter_binary = require_path(
        python_root / 'DLLs' / '_tkinter.pyd', '_tkinter runtime'
    )
    tkinter_package = require_path(
        python_root / 'Lib' / 'tkinter', 'tkinter package'
    )
    tcl_binary = require_path(python_root / 'DLLs' / 'tcl86t.dll', 'Tcl DLL')
    tk_binary = require_path(python_root / 'DLLs' / 'tk86t.dll', 'Tk DLL')
    tcl_data = require_path(python_root / 'tcl' / 'tcl8.6', 'Tcl scripts')
    tk_data = require_path(python_root / 'tcl' / 'tk8.6', 'Tk scripts')

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    old_runtime = output.parent / 'RandomizerLauncherRuntime'

    with tempfile.TemporaryDirectory(prefix='mor-windows-build-') as temporary:
        staging = Path(temporary)
        version_info = staging / 'version.txt'
        manifest = staging / 'bundle_manifest.json'
        tcl_bundle = staging / '_tcl_data'
        dist = staging / 'dist'
        work = staging / 'work'
        spec = staging / 'spec'
        pyinstaller_config = staging / 'pyinstaller-config'
        write_version_info(version_info, APP_VERSION)
        write_config_manifest(configs, manifest)
        prepare_tcl_bundle(tcl_data, tcl_bundle)

        separator = os.pathsep
        add_data = lambda source, target: f'{source}{separator}{target}'
        command = [
            sys.executable,
            '-m',
            'PyInstaller',
            '--noconfirm',
            '--clean',
            '--onefile',
            '--runtime-tmpdir',
            '.',
            '--noupx',
            '--optimize',
            '1',
            '--windowed',
            '--icon',
            str(icon),
            '--version-file',
            str(version_info),
            '--add-data',
            add_data(icon, '.'),
            '--add-data',
            add_data(configs / '*.json', 'configs'),
            '--add-data',
            add_data(configs / '*.ini', 'configs'),
            '--add-data',
            add_data(configs / 'README.md', 'configs'),
            '--add-data',
            add_data(configs / 'rewards', r'configs\rewards'),
            '--add-data',
            add_data(manifest, 'configs'),
            '--add-data',
            add_data(assets, 'assets'),
            '--add-binary',
            add_data(tkinter_binary, '.'),
            '--add-data',
            add_data(tkinter_package, 'tkinter'),
            '--add-binary',
            add_data(tcl_binary, '.'),
            '--add-binary',
            add_data(tk_binary, '.'),
            '--add-data',
            add_data(tcl_bundle, '_tcl_data'),
            '--add-data',
            add_data(tk_data, '_tk_data'),
            '--runtime-hook',
            str(runtime_hook),
            '--exclude-module',
            'logging.handlers',
            '--exclude-module',
            'ftplib',
            '--exclude-module',
            'smtplib',
            '--name',
            'MentalOmegaRandomizer',
            '--distpath',
            str(dist),
            '--workpath',
            str(work),
            '--specpath',
            str(spec),
            str(PROJECT_ROOT / 'launcher_gui.py'),
        ]
        environment = os.environ.copy()
        environment['PYINSTALLER_CONFIG_DIR'] = str(pyinstaller_config)
        run_checked(command, cwd=PROJECT_ROOT, env=environment)

        built = require_path(
            dist / 'MentalOmegaRandomizer.exe', 'Built launcher'
        )
        archive = run_checked(
            [
                sys.executable,
                '-m',
                'PyInstaller.utils.cliutils.archive_viewer',
                '-l',
                str(built),
            ],
            capture_output=True,
            text=True,
        ).stdout
        normalized_archive = archive.replace('\\', '/')
        while '//' in normalized_archive:
            normalized_archive = normalized_archive.replace('//', '/')
        required_entries = (
            "'_tkinter.pyd'",
            "'tcl86t.dll'",
            "'tk86t.dll'",
            "'_tcl_data/init.tcl'",
            "'_tk_data/tk.tcl'",
        )
        missing = [
            entry for entry in required_entries
            if entry not in normalized_archive
        ]
        if missing:
            raise RuntimeError(
                'Built launcher is missing required Tcl/Tk entries: '
                + ', '.join(missing)
            )
        # Exercise the bundled launch controller before replacing the player EXE.
        run_checked([str(built), '--launch-self-check'], cwd=dist, timeout=120)
        shutil.copy2(built, output)

    if old_runtime.exists():
        if old_runtime.name != 'RandomizerLauncherRuntime':
            raise RuntimeError(f'Refusing unexpected runtime path: {old_runtime}')
        shutil.rmtree(old_runtime)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f'Built Windows launcher v{APP_VERSION}: {output}')
    print(f'SHA256 {digest}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output',
        type=Path,
        default=PROJECT_ROOT.parent / 'MentalOmegaRandomizer.exe',
    )
    arguments = parser.parse_args()
    build(arguments.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
