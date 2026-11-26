"""Export the images of a DATAV1.0 UI file (apps/Data/*.data) as PNG.

Pixel format 3/3 (most 8369HD UI images): RGB565 little endian + one alpha byte per pixel holding a
5-bit alpha (0..31); format 2/3: plain RGB565 (opaque); format 1/3: ARGB8888 (bytes B G R A); format 0/3:
RGB888 (bytes B G R, opaque). Rows padded to 4 bytes, zlib-compressed.   usage: extract_images.py <file.data> <out dir> [index ...]
"""
import os
import struct
import sys
import zlib
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../emulator/tools'))
from uidata import UiData, U  # noqa: E402


def decode(blob):
    hdr, w, h = U(blob, 0), U(blob, 4), U(blob, 8)
    fmt = (U(blob, 0xc), U(blob, 0x10))
    assert fmt in ((3, 3), (2, 3), (1, 3), (0, 3)), f'unsupported pixel format {fmt}'
    px = zlib.decompress(blob[hdr:])
    if fmt == (0, 3):                        # RGB888 (B G R), opaque, rows padded to 4 bytes
        stride = (w * 3 + 3) & ~3
        rows = b''.join(px[y * stride:y * stride + w * 3] for y in range(h))
        b, g, r = Image.frombytes('RGB', (w, h), rows).split()
        return Image.merge('RGB', (r, g, b)).convert('RGBA')
    if fmt == (1, 3):                        # ARGB8888, little endian
        b, g, r, a = Image.frombytes('RGBA', (w, h), px[:w * h * 4]).split()
        return Image.merge('RGBA', (r, g, b, a))
    bpp = 3 if fmt == (3, 3) else 2          # (2, 3): plain RGB565, opaque
    stride = (w * bpp + 3) & ~3
    im = Image.new('RGBA', (w, h))
    out = im.load()
    for y in range(h):
        for x in range(w):
            if bpp == 2:
                v, a = struct.unpack_from('<H', px, y * stride + x * 2)[0], 31
            else:
                v, a = struct.unpack_from('<HB', px, y * stride + x * 3)
            r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
            out[x, y] = ((r * 255 + 15) // 31, (g * 255 + 31) // 63, (b * 255 + 15) // 31, (min(a, 31) * 255 + 15) // 31)
    return im


if __name__ == '__main__':
    u = UiData(open(sys.argv[1], 'rb').read())
    os.makedirs(sys.argv[2], exist_ok=True)
    want = [int(a) for a in sys.argv[3:]] or range(len(u.images))
    for k in want:
        im = decode(u.images[k])
        im.save(os.path.join(sys.argv[2], f'{k:02d}_{im.width}x{im.height}.png'))
    print(f'{len(want)} images -> {sys.argv[2]}')
