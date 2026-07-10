import unittest

from randomizer_cameos import decode_pcx_to_png
from randomizer_paths import CAMEO_CACHE_DIR


class CameoDecoderTests(unittest.TestCase):
    def test_decodes_indexed_pcx_to_png_without_external_packages(self):
        header = bytearray(128)
        header[0] = 0x0A
        header[2] = 1
        header[3] = 8
        header[8:10] = (1).to_bytes(2, 'little')  # x_max: width 2
        header[10:12] = (0).to_bytes(2, 'little')
        header[65] = 1
        header[66:68] = (2).to_bytes(2, 'little')
        palette = bytearray(768)
        palette[3:6] = bytes((255, 0, 0))
        palette[6:9] = bytes((0, 255, 0))
        pcx = bytes(header) + bytes((1, 2)) + b'\x0c' + bytes(palette)

        CAMEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        source = CAMEO_CACHE_DIR / '_decoder_test.pcx'
        target = CAMEO_CACHE_DIR / '_decoder_test.png'
        try:
            source.write_bytes(pcx)

            self.assertTrue(decode_pcx_to_png(source, target))
            self.assertEqual(target.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        finally:
            source.unlink(missing_ok=True)
            target.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
