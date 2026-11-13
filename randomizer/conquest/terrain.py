"""Decode installed terrain for complete native RA2 placement validation."""

import base64
import struct
from functools import lru_cache
from .assets import asset
from randomizer.maps.ini import all_section_value_maps_preserve
from randomizer.final_fortress.ground import _decode_lzo
from randomizer.final_fortress.placement import PlayableBounds


THEATER_FILES = {'temperate': 'temperatmd.ini', 'snow': 'snowmd.ini', 'urban': 'urbanmd.ini',
                 'newurban': 'urbannmd.ini', 'desert': 'desertmd.ini', 'lunar': 'lunarmd.ini'}
BUILDABLE_TILES = {theater: frozenset((0, 65535)) for theater in THEATER_FILES}


@lru_cache(maxsize=6)
def flat_ground(theater):
    """Resolve flat LAT and road sets from this mod's own theater registry.

    Tile numbers differ between mods and theaters. Native General fields
    identify the clear/sand/grass/paving families; never reuse DTA indices.
    Ramp, cliff, bridge, water, ice and equipment sets remain excluded.
    """
    data = asset(THEATER_FILES[theater])
    if not data:
        raise ValueError('Installed Conquest theater registry is missing: ' + theater)
    rows = {name: {k: v.split(';', 1)[0].strip() for k, v in row.items()}
            for name, row in all_section_value_maps_preserve(data.decode('latin-1').splitlines()).items()}
    general = rows['General']
    fields = ('ClearTile', 'RoughTile', 'ClearToRoughLat', 'SandTile', 'ClearToSandLat',
              'GreenTile', 'ClearToGreenLat', 'PaveTile', 'MiscPaveTile', 'ClearToPaveLat',
              'PavedRoads', 'PavedRoadEnds', 'DirtRoadJunction', 'DirtRoadCurve', 'DirtRoadStraight')
    selected = {int(general[field]) for field in fields if general.get(field, '').isdigit()}
    tiles, offset = {65535}, 0
    for name in sorted(n for n in rows if n.startswith('TileSet') and n[7:].isdigit()):
        size = int(rows[name].get('TilesInSet', '0'))
        if int(name[7:]) in selected:
            tiles.update(range(offset, offset + size))
        offset += size
    return frozenset(tiles)


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
            output.extend(data[cursor : cursor + count])
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


def unpack(section, *, lzo=False):
    packed = base64.b64decode(''.join(section.values()), validate=True)
    result = bytearray()
    cursor = 0
    while cursor < len(packed):
        size, length = struct.unpack_from('<HH', packed, cursor)
        cursor += 4
        block = packed[cursor : cursor + size]
        if len(block) != size:
            raise ValueError('Truncated native RA2 terrain block.')
        cursor += size
        decoded = _decode_lzo(block, length) if lzo else _lcw(block)
        if len(decoded) != length:
            raise ValueError('native RA2 terrain block length mismatch.')
        result.extend(decoded)
    return result


class Terrain:
    def __init__(self, source):
        self.bounds = PlayableBounds(source['Map'])
        self.theater = source['Map']['Theater'].casefold()
        if self.theater not in BUILDABLE_TILES:
            raise ValueError('Unsupported Conquest terrain theater: ' + self.theater)
        self.flat_tiles = flat_ground(self.theater)
        raw = unpack(source['IsoMapPack5'], lzo=True)
        if len(raw) % 11 == 4 and raw[-4:] == b'\0' * 4:
            raw = raw[:-4]  # native RA2 editor's native trailing map-pack sentinel.
        self.cells = {
            (x, y): (tile, sub, height)
            for x, y, tile, sub, height, extra in struct.iter_unpack('<HHIBBB', raw)
        }
        self.overlays = unpack(source['OverlayPack'])
        self.objects = {(int(key) % 1000, int(key) // 1000) for key in source.get('Terrain', {})}
        self.heights = {cell: value[2] for cell, value in self.cells.items()}

    def clear(self, cells, *, flat_tiles=None, occupied=()):
        cells = set(cells)
        if flat_tiles is None:
            flat_tiles = self.flat_tiles
        if not cells or cells.intersection(occupied) or cells.intersection(self.objects):
            return False
        if not self.bounds.contains(cells, heights=self.heights):
            return False
        heights = set()
        for x, y in cells:
            tile, sub, height = self.cells.get((x, y), (-1, 0, 0))
            if tile not in flat_tiles or not 0 <= x < 512 or not 0 <= y < 512:
                return False
            if self.overlays[y * 512 + x] != 255:
                return False
            heights.add(height)
        return len(heights) == 1
