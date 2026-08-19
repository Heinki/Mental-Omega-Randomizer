"""Minimal read-only support for unencrypted Westwood MIX archives."""

import struct
import zlib
from pathlib import Path


class MixFormatError(ValueError):
    """Raised when a MIX archive cannot be read safely."""


def _classic_hash(filename):
    encoded = bytearray(str(filename).upper().encode('ascii'))
    encoded.extend(b'\0' * (-len(encoded) % 4))
    result = 0
    for offset in range(0, len(encoded), 4):
        value = int.from_bytes(encoded[offset:offset + 4], 'little')
        result = (((result << 1) | (result >> 31)) + value) & 0xFFFFFFFF
    return result


def _crc_hash(filename):
    encoded = bytearray(str(filename).upper().encode('ascii'))
    remainder = len(encoded) % 4
    if remainder:
        fill = encoded[len(encoded) // 4 * 4]
        encoded.append(remainder)
        encoded.extend(bytes([fill]) * (3 - remainder))
    return zlib.crc32(encoded) & 0xFFFFFFFF


def mix_hashes(filename):
    """Return both filename hashes used by classic and TS/RA2 MIX files."""
    name = Path(filename).name
    try:
        return (_crc_hash(name), _classic_hash(name))
    except UnicodeEncodeError as exc:
        raise MixFormatError(f'Unsupported non-ASCII MIX member name: {name}') from exc


class MixArchive:
    """Read named members without loading a complete archive into memory."""

    ENTRY = struct.Struct('<III')

    def __init__(self, path):
        self.path = Path(path)
        self._stream = None
        self._entries = {}
        self._data_start = 0

    def __enter__(self):
        self._stream = self.path.open('rb')
        try:
            self._read_index()
        except Exception:
            self._stream.close()
            self._stream = None
            raise
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        if self._stream is not None:
            self._stream.close()
        self._stream = None

    def _read_exact(self, count):
        data = self._stream.read(count)
        if len(data) != count:
            raise MixFormatError(f'Truncated MIX archive header: {self.path.name}')
        return data

    def _read_index(self):
        first_word = struct.unpack('<H', self._read_exact(2))[0]
        if first_word:
            header_offset = 0
        else:
            self._stream.seek(0)
            flags = struct.unpack('<I', self._read_exact(4))[0]
            if flags & 0x2:
                raise MixFormatError(
                    f'Encrypted MIX archive is unsupported: {self.path.name}'
                )
            header_offset = 4

        self._stream.seek(header_offset)
        file_count = struct.unpack('<H', self._read_exact(2))[0]
        self._read_exact(4)  # Declared data size; some MO archives leave it stale.
        entries = {}
        for _index in range(file_count):
            member_hash, offset, length = self.ENTRY.unpack(
                self._read_exact(self.ENTRY.size)
            )
            entries[member_hash] = (offset, length)
        self._entries = entries
        self._data_start = header_offset + 6 + file_count * self.ENTRY.size

    def read(self, filename):
        """Return one named member, or ``None`` when absent."""
        entry = next(
            (
                self._entries.get(member_hash)
                for member_hash in mix_hashes(filename)
                if member_hash in self._entries
            ),
            None,
        )
        if entry is None:
            return None
        offset, length = entry
        absolute_offset = self._data_start + offset
        archive_size = self.path.stat().st_size
        if absolute_offset > archive_size or length > archive_size - absolute_offset:
            raise MixFormatError(
                f'Invalid MIX member bounds for {filename} in {self.path.name}'
            )
        self._stream.seek(absolute_offset)
        data = self._stream.read(length)
        if len(data) != length:
            raise MixFormatError(
                f'Truncated MIX member {filename} in {self.path.name}'
            )
        return data


def extract_mix_members(mix_paths, requests):
    """Extract requested ``(name, output)`` pairs in archive precedence order.

    Returns ``(extracted_names, missing_names, skipped_archives)``. Earlier
    archives win, matching the launcher's existing descending-name scan.
    """
    pending = {
        str(Path(name).name).upper(): Path(output)
        for name, output in requests
    }
    extracted = []
    skipped = []
    for mix_path in (Path(path) for path in mix_paths):
        if not pending:
            break
        try:
            with MixArchive(mix_path) as archive:
                for name in tuple(pending):
                    data = archive.read(name)
                    if data is None:
                        continue
                    output_path = pending[name]
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(data)
                    pending.pop(name)
                    extracted.append(name)
        except (OSError, MixFormatError) as exc:
            skipped.append(f'{mix_path.name}: {exc}')
    return extracted, list(pending), skipped
