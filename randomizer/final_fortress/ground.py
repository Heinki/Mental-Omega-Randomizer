"""Paint reserved arrivals with native pavement, preserving other map cells."""

import base64
import struct

from randomizer.maps.ini import find_section_bounds, section_value_map


# TEMPERATMD.INI: TileSet0046 (LAT Pavement), PVCLR01.TEM, one subtile.
PAVEMENT_TILE = 534
CELL = struct.Struct('<HHIBBB')


def _decode_lzo(data, expected):
    """Decode the bounded LZO1X blocks used by native IsoMapPack5 data.

    This keeps map generation portable: Windows does not need a system LZO
    library. Changed blocks are written as valid LZO literal runs below.
    """
    cursor = 0
    output = bytearray()

    def byte():
        nonlocal cursor
        if cursor >= len(data):
            raise ValueError('Truncated Fortress terrain block.')
        value = data[cursor]
        cursor += 1
        return value

    def extended(value, base):
        if value:
            return value
        value = base
        while True:
            extra = byte()
            if extra:
                return value + extra
            value += 255

    def literals(count):
        nonlocal cursor
        if cursor + count > len(data) or len(output) + count > expected:
            raise ValueError('Invalid Fortress terrain literal length.')
        output.extend(data[cursor:cursor + count])
        cursor += count

    state = 0
    if data and data[0] > 17:
        count = byte() - 17
        literals(count)
        state = 4 if count >= 4 else count
    while True:
        command = byte()
        if command < 16 and state == 0:
            literals(extended(command, 15) + 3)
            state = 4
            continue
        if command < 16:
            count = 3 if state == 4 else 2
            distance = (2049 if state == 4 else 1) + (command >> 2) + (byte() << 2)
            trailing = command & 3
        elif command >= 64:
            count = (command >> 5) + 1
            distance = 1 + ((command >> 2) & 7) + (byte() << 3)
            trailing = command & 3
        else:
            count = extended(command & (31 if command >= 32 else 7),
                             31 if command >= 32 else 7) + 2
            offset = byte() | (byte() << 8)
            trailing = offset & 3
            distance = offset >> 2
            if command >= 32:
                distance += 1
            else:
                distance += (command & 8) << 11
                if distance == 0:
                    if count != 3 or cursor != len(data) or len(output) != expected:
                        raise ValueError('Invalid Fortress terrain end marker.')
                    return output
                distance += 16384
        if not 0 < distance <= len(output) or len(output) + count > expected:
            raise ValueError('Invalid Fortress terrain match.')
        for _ in range(count):
            output.append(output[-distance])
        literals(trailing)
        state = trailing


def _literal_lzo(data):
    """Encode a native LZO1X block without platform-specific compression."""
    size = len(data)
    if size < 4:
        raise ValueError('Fortress terrain block is too short.')
    if size <= 238:
        prefix = bytes([size + 17])
    else:
        zeros, remainder = divmod(size - 19, 255)
        prefix = b'\0' + b'\0' * zeros + bytes([remainder + 1])
    return prefix + data + b'\x11\0\0'


def pave_spawn_areas(lines, cells):
    """Replace only arrival cells' tile/subtile; retain heights and overlays.

    Original compressed blocks survive verbatim unless an arrival touches
    them. Only generated map bytes change; installed maps remain untouched.
    """
    if section_value_map(lines, 'Map').get('theater', '').casefold() != 'temperate':
        raise ValueError('Fortress spawn pavement requires temperate terrain.')
    packed = base64.b64decode(''.join(section_value_map(lines, 'IsoMapPack5').values()),
                             validate=True)
    blocks = []
    raw = bytearray()
    cursor = 0
    while cursor + 4 <= len(packed):
        size, length = struct.unpack_from('<HH', packed, cursor)
        cursor += 4
        if not 0 < size <= len(packed) - cursor or not 0 < length <= 8192:
            raise ValueError('Invalid Fortress packed terrain header.')
        block = packed[cursor:cursor + size]
        raw.extend(_decode_lzo(block, length))
        blocks.append((block, length))
        cursor += size
    if cursor != len(packed) or len(raw) % CELL.size:
        raise ValueError('Invalid Fortress terrain record length.')
    changed = bytearray(raw)
    remaining = set(cells)
    for offset in range(0, len(raw), CELL.size):
        x, y, tile, subtile, height, extra = CELL.unpack_from(raw, offset)
        if (x, y) in cells:
            CELL.pack_into(changed, offset, x, y, PAVEMENT_TILE, 0, height, extra)
            remaining.discard((x, y))
    if remaining:
        raise ValueError('Fortress spawn pavement extends outside existing terrain.')
    encoded = bytearray()
    offset = 0
    for original, length in blocks:
        chunk = changed[offset:offset + length]
        block = original if chunk == raw[offset:offset + length] else _literal_lzo(chunk)
        encoded.extend(struct.pack('<HH', len(block), length))
        encoded.extend(block)
        offset += length
    value = base64.b64encode(encoded).decode('ascii')
    start, end = find_section_bounds(lines, 'IsoMapPack5')
    lines[start + 1:end] = [f'{index // 70 + 1}={value[index:index + 70]}'
                            for index in range(0, len(value), 70)]
