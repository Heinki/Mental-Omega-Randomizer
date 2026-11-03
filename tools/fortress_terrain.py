"""Read packed skirmish terrain for the Fortress placement audit (no game UI)."""

import base64
import ctypes
import ctypes.util
import struct


def _lcw(data):
    output = bytearray()
    cursor = 0
    relative = data[:1] == b'\0'
    if relative:
        cursor = 1
    while cursor < len(data):
        command = data[cursor]
        cursor += 1
        if not command & 0x80:
            count = (command >> 4) + 3
            offset = ((command & 15) << 8) | data[cursor]
            cursor += 1
            position = len(output) - offset
        elif not command & 0x40:
            count = command & 63
            if not count:
                break
            output.extend(data[cursor:cursor + count])
            cursor += count
            continue
        elif command == 0xFE:
            count = struct.unpack_from('<H', data, cursor)[0]
            output.extend(bytes([data[cursor + 2]]) * count)
            cursor += 3
            continue
        else:
            count = (command & 63) + 3
            if command == 0xFF:
                count = struct.unpack_from('<H', data, cursor)[0]
                cursor += 2
            offset = struct.unpack_from('<H', data, cursor)[0]
            cursor += 2
            position = len(output) - offset if relative else offset
        for index in range(count):
            output.append(output[position + index])
    return output


def _unpack(section, lzo=False):
    packed = base64.b64decode(''.join(section.values()))
    decoder = None
    if lzo:
        path = ctypes.util.find_library('lzo2')
        if not path:
            raise ValueError('Terrain audit needs the system LZO2 library.')
        decoder = ctypes.CDLL(path).lzo1x_decompress_safe
        decoder.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
    cursor = 0
    output = bytearray()
    while cursor < len(packed):
        size, length = struct.unpack_from('<HH', packed, cursor)
        cursor += 4
        if not size:
            break
        block = packed[cursor:cursor + size]
        cursor += size
        if decoder:
            buffer = ctypes.create_string_buffer(length)
            written = ctypes.c_size_t(length)
            if decoder(block, len(block), buffer, ctypes.byref(written), None):
                raise ValueError('Invalid packed LZO terrain.')
            decoded = buffer.raw[:written.value]
        else:
            decoded = _lcw(block)
        if len(decoded) != length:
            raise ValueError('Packed terrain length mismatch.')
        output.extend(decoded)
    return output


class Terrain:
    def __init__(self, source):
        from randomizer.final_fortress.placement import PlayableBounds
        self.bounds = PlayableBounds(source['Map'])
        self.theater = source['Map']['Theater'].lower()
        # Theater-specific flat LAT tiles, from installed MO theater INIs.
        # Snow's 418-434 are waterfalls/roads, not temperate rough grass.
        common = {0, 65535, *range(131, 148)}
        flat = {
            'temperate': {534, *range(418, 435), *range(463, 510)},
            'snow': {734, *range(696, 713), *range(749, 765)},
            'newurban': {534, 1105, 1553, *range(418, 435),
                         *range(463, 510), *range(852, 860), *range(938, 969),
                         *range(1175, 1193), *range(176, 277)},
        }
        if self.theater not in flat:
            raise ValueError('Unsupported Fortress terrain audit theater: ' + self.theater)
        self.flat_tiles = common | flat[self.theater]
        self.walk_tiles = self.flat_tiles | set(range(29, 49)) | set(range(176, 277)) | set(range(293, 314))
        self.walk_tiles.update(range(444, 456) if self.theater == 'snow' else range(510, 522))
        if self.theater == 'newurban':
            self.walk_tiles.update(range(1106, 1116))
            self.walk_tiles.update(range(1126, 1146))
        self.cells = {(x, y): (tile, height) for x, y, tile, sub, height, extra in
                      struct.iter_unpack('<HHIBBB', _unpack(source['IsoMapPack5'], lzo=True))}
        self.overlays = _unpack(source['OverlayPack'])
        self.objects = set()
        self.heights = {cell: value[1] for cell, value in self.cells.items()}
        for key in source.get('Terrain', {}):
            cell = int(key)
            self.objects.add((cell % 1000, cell // 1000))

    def clear(self, cells, *, allowed_overlays=()):
        if not self.bounds.contains(cells, heights=self.heights):
            return False
        heights = set()
        for x, y in cells:
            tile, height = self.cells.get((x, y), (-1, -1))
            if tile not in self.flat_tiles or (x, y) in self.objects:
                return False
            if not (0 <= x < 512 and 0 <= y < 512):
                return False
            overlay = self.overlays[y * 512 + x]
            if overlay != 255 and overlay not in allowed_overlays:
                return False
            heights.add(height)
        return len(heights) == 1

    def walkable(self, cell, *, allowed_overlays=()):
        """Conservative land connectivity, including native roads and ramps.

        Building placement still requires flat ground through ``clear``.
        Water, cliffs, ice and unknown tile families stay excluded.
        """
        x, y = cell
        if cell not in self.cells or cell in self.objects or not (0 <= x < 512 and 0 <= y < 512):
            return False
        tile, _ = self.cells[cell]
        return (tile in self.walk_tiles and self.bounds.contains({cell}, heights=self.heights)
                and (self.overlays[y * 512 + x] == 255
                     or self.overlays[y * 512 + x] in allowed_overlays))
