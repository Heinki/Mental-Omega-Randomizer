"""Apply an approved update after the launcher exits, retaining rollback files."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import time

from .storage import atomic_write_json, read_json_object
from .update_profile import APWORLD_NAME, EXECUTABLE_NAME, PRODUCT_NAME
from .updater import file_sha256, fresh_process_environment, version_key


def _wait_for_parent(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # Parent already exited.
            return
        raise OSError('Could not wait for the original launcher to close.')
    try:
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise TimeoutError('The original launcher did not close. No update was applied.')
    finally:
        kernel.CloseHandle(handle)


def _replace(source, destination):
    # The PyInstaller bootloader or antivirus can hold the old file briefly
    # after the Python process exits. Never terminate a process to unlock it.
    deadline = time.monotonic() + 90
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def _restart(target):
    return subprocess.Popen(
        [str(target)], cwd=target.parent, env=fresh_process_environment(),
        close_fds=True,
    )


def apply_update(request_path):
    """Only the two fixed product assets can be installed; never game/save files."""
    request_path = Path(request_path).resolve()
    directory = request_path.parent
    request = read_json_object(request_path)
    target = Path(request['target']).resolve()
    version_key(request['version'])
    if (request.get('format') != 1 or target.name != EXECUTABLE_NAME
            or directory.parent.name != 'updates'
            or directory.parent.parent.parent.resolve() != target.parent
            or directory != Path(sys.executable).resolve().parent):
        raise ValueError('Invalid update location or executable.')
    entries = request.get('files')
    if (not isinstance(entries, list) or len(entries) != 2
            or any(not isinstance(entry, dict) for entry in entries)
            or {entry.get('name') for entry in entries} != {EXECUTABLE_NAME, APWORLD_NAME}):
        raise ValueError('Update must contain exactly the launcher and matching APWorld.')
    pid = request.get('parent_pid')
    if type(pid) is not int or pid <= 0 or pid == os.getpid():
        raise ValueError('Invalid launcher process.')

    # A helper can start before cleanup completes, but only a successful window
    # shutdown creates this approval. A canceled/failed shutdown expires safely.
    deadline = time.monotonic() + 120
    approval = directory / 'approved'
    while not approval.is_file():
        if time.monotonic() >= deadline:
            return
        time.sleep(0.25)
    _wait_for_parent(pid)

    for entry in entries:
        if file_sha256(directory / entry['name']) != entry.get('sha256'):
            raise ValueError(f'Update checksum mismatch: {entry["name"]}. No files were replaced.')

    backups = directory / 'backup'
    backups.mkdir(exist_ok=False)
    moved = []
    installed = []
    try:
        for entry in entries:
            name = entry['name']
            destination = target.parent / name
            if destination.exists():
                _replace(destination, backups / name)
                moved.append(name)
            _replace(directory / name, destination)
            installed.append(name)
        _restart(target)
    except Exception as original:
        failures = []
        for name in reversed(installed):
            try:
                _replace(target.parent / name, directory / name)
            except OSError as exc:
                failures.append(str(exc))
        for name in reversed(moved):
            try:
                _replace(backups / name, target.parent / name)
            except OSError as exc:
                failures.append(str(exc))
        if not failures and target.is_file():
            try:
                _restart(target)
            except OSError:
                pass
        detail = 'Previous files restored.' if not failures else (
            f'Manual recovery files: {backups}. ' + '; '.join(failures)
        )
        raise RuntimeError(f'{original}\n\n{detail}') from original
    try:
        atomic_write_json(directory / 'result.json', {
            'updated': True, 'version': request['version'], 'backup': str(backups),
        })
    except OSError:
        pass  # Diagnostic output must not report a successful install as failed.


def main(request_path):
    try:
        if os.name != 'nt' or not getattr(sys, 'frozen', False):
            raise RuntimeError('Updates must be applied by the packaged Windows launcher.')
        apply_update(request_path)
        return 0
    except Exception as exc:
        try:
            ctypes.windll.user32.MessageBoxW(
                None, f'Update could not finish.\n\n{exc}',
                f'{PRODUCT_NAME} Update', 0x10,
            )
        except Exception:
            pass
        return 1
