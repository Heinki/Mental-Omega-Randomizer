"""Read native TMP ground metadata instead of guessing from tile-set numbers.

TMP header layout: https://github.com/OlafvdSpek/xcc/blob/master/misc/cc_structures.h
Only flat pavement, roads, clear and rough ground can carry starting grants.
"""

from functools import lru_cache
import struct

from randomizer.maps.ini import all_section_value_maps_preserve
from .assets import asset
from .profile import GAME


THEATERS = {
    'temperate': ('temperat', 'tem'), 'snow': ('snow', 'sno'),
    'urban': ('urban', 'urb'), 'newurban': ('urbann', 'ubn'),
    'desert': ('desert', 'des'), 'lunar': ('lunar', 'lun'),
}


class NativeGround:
    def __init__(self, theater):
        registry, self.extension = THEATERS[theater]
        name = registry + ('mo.ini' if GAME == 'mo' else 'md.ini')
        data = asset(name)
        if not data:
            raise ValueError('Installed Conquest theater registry is missing: ' + name)
        rows = all_section_value_maps_preserve(data.decode('latin-1').splitlines())
        self.files = []
        for name in sorted(n for n in rows if n.startswith('TileSet') and n[7:].isdigit()):
            row = {k: v.split(';', 1)[0].strip() for k, v in rows[name].items()}
            # Bridge decks and tunnel portals are not building foundations,
            # even where their TMP surface reports ordinary pavement.
            excluded = any(word in row.get('SetName', '').casefold()
                           for word in ('bridge', 'tunnel')) or 'NonMarbleMadness' in row
            self.files.extend(None if excluded else f"{row['FileName']}{i + 1:02d}.{self.extension}"
                              for i in range(int(row.get('TilesInSet', '0'))))

    @lru_cache(maxsize=4096)
    def subtiles(self, tile):
        # Native map editors use 65535 for the theater's clear tile.
        if tile == 65535:
            tile = 0
        if not 0 <= tile < len(self.files) or self.files[tile] is None:
            return frozenset()
        name = self.files[tile]
        data = asset(name)
        if not data or len(data) < 16:
            raise ValueError('Installed Conquest ground artwork is missing: ' + name)
        width, height = struct.unpack_from('<II', data)
        count = width * height
        if not 0 < count <= 256 or 16 + count * 4 > len(data):
            raise ValueError('Invalid Conquest ground artwork: ' + name)
        result = set()
        for sub in range(count):
            offset = struct.unpack_from('<I', data, 16 + sub * 4)[0]
            if not offset:
                continue
            if offset < 16 + count * 4 or offset + 52 > len(data):
                raise ValueError('Truncated Conquest ground artwork: ' + name)
            land, ramp = data[offset + 41:offset + 43]
            # Type 0 is native default clear ground, used throughout DTA.
            if land in (0, 11, 12, 13, 14) and ramp == 0:
                result.add(sub)
        return frozenset(result)

    def flat(self, tile, sub):
        return sub in self.subtiles(tile)


@lru_cache(maxsize=6)
def native_ground(theater):
    return NativeGround(theater)
