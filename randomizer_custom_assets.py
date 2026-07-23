"""Deploy config-selected custom sidebar images for generated map content."""

import shutil
import struct
import zlib
import binascii
from pathlib import Path

from randomizer_paths import APP_DIR, CAMEO_CACHE_DIR, GAME_ROOT, SOURCE_DIR


CUSTOM_ASSET_DIR = APP_DIR / 'assets'
BUNDLED_ASSET_DIR = SOURCE_DIR / 'assets'
SIDEBAR_WIDTH = 60
SIDEBAR_HEIGHT = 48


class CustomAssetError(ValueError):
    """Raised when a configured custom image cannot be converted safely."""


def _asset_name(value, suffix):
    name = Path(str(value or '')).name
    if not name or name != str(value) or Path(name).suffix.lower() != suffix:
        raise CustomAssetError(f'Custom sidebar asset must be a plain {suffix} filename: {value!r}')
    return name


def custom_image_path(name):
    """Return a visible configured image, copying its bundled default if needed."""
    target = CUSTOM_ASSET_DIR / name
    if target.is_file():
        return target
    bundled = BUNDLED_ASSET_DIR / name
    if not bundled.is_file():
        raise CustomAssetError(f'Custom sidebar image is missing: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.resolve() != bundled.resolve():
        shutil.copy2(bundled, target)
    return target


def _paeth(left, above, upper_left):
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _decode_png(path):
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise CustomAssetError(f'Custom sidebar image is not a PNG: {path}')
    offset = 8
    header = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        if len(chunk_data) != length:
            raise CustomAssetError(f'Truncated PNG chunk in {path}')
        if chunk_type == b'IHDR':
            header = struct.unpack('>IIBBBBB', chunk_data)
        elif chunk_type == b'IDAT':
            compressed.extend(chunk_data)
        elif chunk_type == b'IEND':
            break
        offset += length + 12
    if not header:
        raise CustomAssetError(f'PNG has no IHDR chunk: {path}')
    width, height, depth, color_type, compression, filtering, interlace = header
    if (
        width < 1 or height < 1 or depth != 8 or color_type not in {2, 6}
        or compression != 0 or filtering != 0 or interlace != 0
    ):
        raise CustomAssetError(
            'Custom sidebar PNG must be non-interlaced 8-bit RGB or RGBA'
        )
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise CustomAssetError(f'Cannot decompress custom PNG {path}: {exc}') from exc
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise CustomAssetError(
            f'Unexpected PNG data length in {path}: {len(raw)} instead of {expected}'
        )
    rows = []
    prior = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = raw[cursor:cursor + stride]
        cursor += stride
        row = bytearray(stride)
        for index, value in enumerate(encoded):
            left = row[index - channels] if index >= channels else 0
            above = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                raise CustomAssetError(f'Unsupported PNG filter {filter_type} in {path}')
            row[index] = (value + predictor) & 0xFF
        pixels = []
        for index in range(0, stride, channels):
            red, green, blue = row[index:index + 3]
            alpha = row[index + 3] if channels == 4 else 255
            # Game cameos have no alpha plane. Composite transparent pixels on black.
            pixels.append((
                red * alpha // 255,
                green * alpha // 255,
                blue * alpha // 255,
            ))
        rows.append(pixels)
        prior = row
    return width, height, rows


def _resize_cover(width, height, pixels, target_width, target_height):
    source_ratio = width / height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = height
        crop_width = height * target_ratio
        crop_x = (width - crop_width) / 2
        crop_y = 0
    else:
        crop_width = width
        crop_height = width / target_ratio
        crop_x = 0
        crop_y = (height - crop_height) / 2
    result = []
    for target_y in range(target_height):
        source_y_start = max(0, int(crop_y + target_y * crop_height / target_height))
        source_y_end = min(
            height,
            max(
                source_y_start + 1,
                int(crop_y + (target_y + 1) * crop_height / target_height + 0.999),
            ),
        )
        row = []
        for target_x in range(target_width):
            source_x_start = max(0, int(crop_x + target_x * crop_width / target_width))
            source_x_end = min(
                width,
                max(
                    source_x_start + 1,
                    int(crop_x + (target_x + 1) * crop_width / target_width + 0.999),
                ),
            )
            samples = [
                pixels[source_y][source_x]
                for source_y in range(source_y_start, source_y_end)
                for source_x in range(source_x_start, source_x_end)
            ]
            sample_count = len(samples)
            row.append(tuple(
                sum(sample[channel] for sample in samples) // sample_count
                for channel in range(3)
            ))
        result.append(row)
    return result


def _pcx_rle(values):
    encoded = bytearray()
    index = 0
    while index < len(values):
        value = values[index]
        run = 1
        while index + run < len(values) and values[index + run] == value and run < 63:
            run += 1
        if run > 1 or value >= 0xC0:
            encoded.extend((0xC0 | run, value))
        else:
            encoded.append(value)
        index += run
    return encoded


def png_to_pcx(source, target):
    width, height, pixels = _decode_png(source)
    pixels = _resize_cover(width, height, pixels, SIDEBAR_WIDTH, SIDEBAR_HEIGHT)
    bytes_per_line = SIDEBAR_WIDTH + (SIDEBAR_WIDTH % 2)
    header = bytearray(128)
    header[0:4] = bytes((10, 5, 1, 8))
    struct.pack_into('<HHHH', header, 4, 0, 0, SIDEBAR_WIDTH - 1, SIDEBAR_HEIGHT - 1)
    struct.pack_into('<HH', header, 12, 72, 72)
    header[64] = 0
    header[65] = 1
    struct.pack_into('<H', header, 66, bytes_per_line)
    struct.pack_into('<H', header, 68, 1)
    body = bytearray(header)
    for row in pixels:
        indices = bytearray(
            ((red >> 5) << 5) | ((green >> 5) << 2) | (blue >> 6)
            for red, green, blue in row
        )
        indices.extend(b'\0' * (bytes_per_line - len(indices)))
        body.extend(_pcx_rle(indices))
    body.append(12)
    for index in range(256):
        body.extend((
            ((index >> 5) & 7) * 255 // 7,
            ((index >> 2) & 7) * 255 // 7,
            (index & 3) * 255 // 3,
        ))
    target.write_bytes(body)
    return target


def deploy_superweapon_sidebar_assets(rewards):
    """Convert active configured PNGs and return deployed game-root PCX paths."""
    deployed = []
    seen = set()
    for reward in rewards:
        image_value = reward.get('superweapon_sidebar_image')
        if not image_value:
            continue
        image_name = _asset_name(image_value, '.png')
        rules = reward.get('superweapon_rules') or {}
        pcx_name = _asset_name(rules.get('SidebarPCX'), '.pcx')
        if not pcx_name.lower().startswith('mor'):
            raise CustomAssetError(
                f'Generated sidebar PCX must use the MOR namespace: {pcx_name!r}'
            )
        key = (image_name.lower(), pcx_name.lower())
        if key in seen:
            continue
        seen.add(key)
        source = custom_image_path(image_name)
        target = GAME_ROOT / pcx_name
        png_to_pcx(source, target)
        deployed.append(target)
    return deployed


def _png_chunk(kind, payload):
    return (
        struct.pack('>I', len(payload))
        + kind
        + payload
        + struct.pack('>I', binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def custom_sidebar_preview(image_value):
    """Return a launcher-ready 60x48 PNG derived from a configured asset."""
    image_name = _asset_name(image_value, '.png')
    source = custom_image_path(image_name)
    target = CAMEO_CACHE_DIR / f'custom-{Path(image_name).stem.lower()}.png'
    if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return target
    width, height, pixels = _decode_png(source)
    pixels = _resize_cover(width, height, pixels, SIDEBAR_WIDTH, SIDEBAR_HEIGHT)
    scanlines = b''.join(
        b'\0' + bytes(channel for pixel in row for channel in pixel)
        for row in pixels
    )
    png = (
        b'\x89PNG\r\n\x1a\n'
        + _png_chunk(
            b'IHDR',
            struct.pack('>IIBBBBB', SIDEBAR_WIDTH, SIDEBAR_HEIGHT, 8, 2, 0, 0, 0),
        )
        + _png_chunk(b'IDAT', zlib.compress(scanlines, level=9))
        + _png_chunk(b'IEND', b'')
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    return target
