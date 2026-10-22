"""Playable isometric bounds and complete building-foundation validation."""

import re

from randomizer.maps.ini import all_section_value_maps_preserve


class PlayableBounds:
    def __init__(self, section):
        row = {key.lower(): value for key, value in section.items()}
        size = list(map(int, row['size'].split(',')))
        local = list(map(int, row['localsize'].split(',')))
        if len(size) != 4 or len(local) != 4 or min(local[2:]) <= 0:
            raise ValueError('Invalid playable map rectangle.')
        self.width = size[2]
        self.left, self.top, self.width_local, self.height_local = local

    def project(self, x, y, height=0):
        # Native isometric cell top-left, in whole rendered-cell dimensions.
        # See World-Altering Editor GameMath/CellMath.cs; LocalSize is a
        # rendered rectangle, not the bounding box of packed diamond cells.
        return (x - y + self.width - 1) / 2, (x + y - self.width - 1 - height) / 2

    def contains(self, cells, *, margin=0, heights=None, maximum_height=None):
        for x, y in cells:
            levels = [heights.get((x, y), 0)] if heights is not None else [0]
            if maximum_height is not None:
                levels.append(maximum_height)
            for height in levels:
                u, v = self.project(x, y, height)
                if not (self.left + margin <= u and u + 1 <= self.left + self.width_local - margin
                        and self.top + margin <= v and v + 1 <= self.top + self.height_local - margin):
                    return False
        return True


def foundation(row, art):
    image = row.get('Image', '')
    entry = art.get(image.casefold(), {})
    value = row.get('Foundation', entry.get('Foundation', '1x1'))
    match = re.fullmatch(r'(\d+)[xX](\d+)', value)
    if match:
        return {(x, y) for x in range(int(match[1])) for y in range(int(match[2]))}
    if value.lower() != 'custom':
        raise ValueError(f'Unknown building foundation: {image}: {value}.')
    cells = {tuple(map(int, value.split(','))) for key, value in entry.items()
             if re.fullmatch(r'Foundation\.\d+', key)}
    if not cells:
        raise ValueError(f'Empty custom building foundation: {image}.')
    return cells


def installed_art():
    from randomizer.ui.cameos import ART_CACHE_PATH, extract_mix_files_sync
    if not ART_CACHE_PATH.exists() and not extract_mix_files_sync([('ARTMO.INI', ART_CACHE_PATH)]):
        raise ValueError('Installed art foundations are unavailable for safe Fortress placement.')
    return {key.casefold(): value for key, value in all_section_value_maps_preserve(
        ART_CACHE_PATH.read_text(encoding='latin-1').splitlines()).items()}


def validate_placements(writer, rules):
    """Reject off-map added objects before any runtime files are written.

    Evaluate ground level and a conservative 14-level terrain allowance to keep
    elevated foundations inside the visible rectangle without a platform-
    specific LZO dependency at launch. The terrain audit checks actual heights.
    """
    from randomizer.maps.ini import section_value_map
    bounds = PlayableBounds(section_value_map(writer.lines, 'Map'))
    art = installed_art()
    for category in ('Structures', 'Infantry', 'Units'):
        for value in writer.sections.get(category, {}).values():
            fields = value.split(',')
            kind = fields[1]
            x, y = map(int, fields[3:5])
            row = {**rules.get(kind, {}), **writer.sections.get(kind, {})}
            row.setdefault('Image', kind)
            offsets = foundation(row, art) if category == 'Structures' else {(0, 0)}
            cells = {(x + dx, y + dy) for dx, dy in offsets} or {(x, y)}
            if not bounds.contains(cells, maximum_height=14):
                raise ValueError(f'Final Fortress {kind} at ({x}, {y}) extends outside playable map bounds.')
