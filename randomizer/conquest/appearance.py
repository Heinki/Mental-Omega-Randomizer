"""Eight transparent facings rendered from each installed faction's tank art.

VXL/HVA layout follows the native Westwood format as documented by OpenRA:
https://github.com/OpenRA/OpenRA/blob/bleed/OpenRA.Mods.Cnc/FileFormats/VxlReader.cs
No game art is bundled or substituted with another game's tanks.
"""

import math
import struct
import zlib

from randomizer.core.paths import CAMEO_CACHE_DIR
from randomizer.ui.cameos import extract_mix_files_sync
from .profile import ART_FILE, installed_rules, read_ini
from .catalogue import ROSTERS


def _asset(name):
    from .assets import asset
    return asset(name)


def _chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)


def _png(width, height, pixels, palette):
    """Neutral remap and pale contour match the DTA strategic markers."""
    scale = 4 if max(palette) <= 63 else 1
    rgba = bytearray(width * height * 4)
    for (x, y), index in pixels.items():
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                offset = (ny * width + nx) * 4
                rgba[offset:offset+4] = bytes((220, 232, 238, 220))
    for (x, y), index in pixels.items():
        offset = (y * width + x) * 4
        if 16 <= index <= 31:
            shade = round(48 + (31 - index) * 12)
            rgba[offset:offset+4] = bytes((shade, shade, shade, 255))
        else:
            rgba[offset:offset+4] = bytes(min(255, c * scale) for c in palette[index*3:index*3+3]) + b'\xff'
    scanlines = b''.join(b'\0' + rgba[y*width*4:(y+1)*width*4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(scanlines)) + _chunk(b'IEND', b''))


def _voxels(data, hva=None):
    """Bounded sparse span reader; retain limb bounds and the resting HVA pose."""
    if not data.startswith(b'Voxel Animation') or len(data) < 802:
        raise ValueError('Invalid native VXL header.')
    limbs, body_size = struct.unpack_from('<I4xI', data, 20)
    if not 1 <= limbs <= 64:
        raise ValueError('Invalid native VXL limb count.')
    body = 802 + limbs * 28
    footer = body + body_size
    if footer + limbs * 92 > len(data):
        raise ValueError('Truncated native VXL model.')
    points = []
    for limb in range(limbs):
        tail = footer + limb * 92
        span_start, _, span_data = struct.unpack_from('<III', data, tail)
        limb_scale = struct.unpack_from('<f', data, tail+12)[0]
        bounds = struct.unpack_from('<6f', data, tail+64)
        xs, ys, zs = struct.unpack_from('<BBB', data, tail+88)
        if not xs or not ys or not zs:
            raise ValueError('Invalid native VXL dimensions.')
        matrix = None
        if hva and len(hva) >= 24:
            frames, count = struct.unpack_from('<II', hva, 16)
            offset = 24 + count * 16 + limb * 48
            if frames and count == limbs and offset + 48 <= len(hva):
                matrix = struct.unpack_from('<12f', hva, offset)
        if matrix and not any(matrix[i] for i in (0,1,2,4,5,6,8,9,10)):
            continue  # Native hidden limb in the resting animation pose.
        starts = struct.unpack_from('<' + 'i' * (xs*ys), data, body+span_start)
        for column, start in enumerate(starts):
            if start < 0:
                continue
            cursor, z = body + span_data + start, 0
            while z < zs:
                if cursor+2 > footer:
                    raise ValueError('Truncated native voxel span.')
                skip, count = data[cursor:cursor+2]
                cursor += 2
                z += skip
                if z + count > zs or cursor+count*2+1 > footer or not skip and not count:
                    raise ValueError('Invalid native voxel span.')
                for index in range(count):
                    color = data[cursor+index*2]
                    if not color:
                        continue
                    local = (column % xs + .5, column // xs + .5, z + index + .5)
                    pos = [bounds[i] + local[i] * (bounds[i+3]-bounds[i]) / (xs,ys,zs)[i] for i in range(3)]
                    if matrix:
                        pos = [sum(matrix[i*4+j] * pos[j] for j in range(3))
                               + matrix[i*4+3] * limb_scale * (bounds[i+3]-bounds[i]) / (xs,ys,zs)[i]
                               for i in range(3)]
                    points.append((*pos, color))
                z += count
                cursor += count*2+1
    return points


def _render_voxels(points, palette):
    projections = []
    for facing in range(8):
        angle = facing * math.pi / 4 + math.pi / 4
        c, s = math.cos(angle), math.sin(angle)
        projection = []
        for x, y, z, color in points:
            rx, ry = x*c-y*s, x*s+y*c
            projection.append((rx, ry*.5-z*.866, ry*.866+z*.5, color))
        projections.append(projection)
    extent = max(max(p[i] for p in projection)-min(p[i] for p in projection)
                 for projection in projections for i in (0,1))
    scale = 46 / max(1, extent)
    frames = []
    for projection in projections:
        cx = (max(p[0] for p in projection)+min(p[0] for p in projection))/2
        cy = (max(p[1] for p in projection)+min(p[1] for p in projection))/2
        pixels = {}
        for x, y, depth, color in sorted(projection, key=lambda p:p[2]):
            px, py = round(28+(x-cx)*scale), round(28+(y-cy)*scale)
            for dx,dy in ((0,0),(1,0),(0,1)):
                if 1 <= px+dx < 55 and 1 <= py+dy < 55:
                    pixels[px+dx,py+dy] = color
        frames.append(_png(56,56,pixels,palette))
    return frames


def army_sprites():
    """Called on the launcher's worker; Tk receives finished PNG bytes only."""
    rules = installed_rules()
    art = {name.upper(): row for name,row in read_ini(CAMEO_CACHE_DIR / ART_FILE).items()}
    palette = _asset('unittem.pal')
    if not palette or len(palette) < 768:
        raise ValueError('Installed unit palette is missing.')
    result = {}
    by_type = {}
    for faction, roster in ROSTERS.items():
        tank = roster[2]
        if tank in by_type:
            result[faction] = by_type[tank]
            continue
        image = rules[tank].get('Image', tank).upper()
        row = art.get(image, {})
        model = _asset(image + '.vxl')
        if model:
            points = _voxels(model, _asset(image + '.hva'))
            if rules[tank].get('Turret', 'no').lower() == 'yes':
                for suffix in ('tur','barl'):
                    data = _asset(image + suffix + '.vxl')
                    if data:
                        points += _voxels(data, _asset(image + suffix + '.hva'))
            if points:
                result[faction] = by_type[tank] = _render_voxels(points,palette)
                continue
        # Native walkers can use SHP art instead of voxels.
        data = _asset(row.get('Image', image) + '.shp')
        if data:
            frames = []
            count = int(row.get('Facings', '8'))
            step = int(row.get('WalkFrames', row.get('StandingFrames', '1')))
            start = int(row.get('StartStandFrame', row.get('StartWalkFrame','0')))
            for facing in range(8):
                w,h,pixels = decode_shp_frame(data,start+(facing*count//8)*step)
                colored = {(x,y):pixels[y*w+x] for y in range(h) for x in range(w) if pixels[y*w+x]}
                frames.append(_png(w,h,colored,palette))
            result[faction] = by_type[tank] = frames
        else:
            raise ValueError('Installed tank artwork is missing: ' + tank)
    return result


def _decode_rle_line(payload, width):
    output = bytearray()
    cursor = 0
    while cursor < len(payload) and len(output) < width:
        value = payload[cursor]
        cursor += 1
        if value:
            output.append(value)
            continue
        if cursor >= len(payload):
            break
        run = payload[cursor]
        cursor += 1
        output.extend(b'\0' * run)
    if len(output) < width:
        output.extend(b'\0' * (width - len(output)))
    return output[:width]


def decode_shp_frame(data, frame_index=0):
    if len(data) < 8:
        raise ValueError('Truncated TS SHP header')
    empty, full_width, full_height, frame_count = struct.unpack_from('<4H', data, 0)
    if empty != 0 or not full_width or not full_height or frame_index >= frame_count:
        raise ValueError('Invalid TS SHP header')
    frame_offset = 8 + frame_index * 24
    if frame_offset + 24 > len(data):
        raise ValueError('Truncated TS SHP frame table')
    x, y, width, height, flags = struct.unpack_from('<4HI', data, frame_offset)
    data_offset = struct.unpack_from('<I', data, frame_offset + 20)[0]
    if not width or not height or data_offset >= len(data):
        raise ValueError('Invalid TS SHP frame')

    cropped = bytearray(width * height)
    cursor = data_offset
    if flags & 0x2:
        for row in range(height):
            if cursor + 2 > len(data):
                raise ValueError('Truncated TS SHP RLE row')
            row_size = struct.unpack_from('<H', data, cursor)[0]
            if row_size < 2 or cursor + row_size > len(data):
                raise ValueError('Invalid TS SHP RLE row')
            decoded = _decode_rle_line(data[cursor + 2:cursor + row_size], width)
            cropped[row * width:(row + 1) * width] = decoded
            cursor += row_size
    else:
        size = width * height
        if cursor + size > len(data):
            raise ValueError('Truncated TS SHP pixels')
        cropped[:] = data[cursor:cursor + size]

    pixels = bytearray(full_width * full_height)
    for row in range(height):
        target_y = y + row
        if target_y >= full_height or x >= full_width:
            continue
        count = min(width, full_width - x)
        start = target_y * full_width + x
        pixels[start:start + count] = cropped[row * width:row * width + count]
    return full_width, full_height, pixels

