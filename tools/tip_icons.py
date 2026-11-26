"""Media icons in the status bar tip (TipBox: "Next", "Pre", "Play", "Pause" after the back button).

The firmware draws that tip as text with its font, apps/Font30_8Bit.vft. This adds Material Symbols as glyphs of
that font at Private Use code points (none used by the font) and puts those characters in Language/TipBox.txt, so the
firmware draws the icons itself, where and in the colour it draws the text.

Font30_8Bit.vft ("VIFT"):
  0x00  UTF-16 "VIFT", u16 version (0x0301), u16 0
  0x0c  u32 header size (0x18), u32 size of the compressed glyph table, u8 height (30), u8 bits per pixel (8), u16 0
  0x18  zlib: glyph table, 65536 x (u16 width, u16 compressed size, u32 offset) for U+0000..U+FFFF (width 0: none)
  then  glyph blobs, each its own zlib stream at <offset> from the end of the table:
        width x height bytes of alpha, row by row, and one more byte (0)

Data/TipBox.data: the tip's colour (stock: yellow) becomes the one of the status bar's own symbols (home, back).

usage: tip_icons.py <apps dir> <out apps dir> <Material Symbols cache dir> [--icons]
       writes Data/TipBox.data (the colour); with --icons also Font30_8Bit.vft and Language/TipBox.txt (the icons
       instead of the words; not used: the words read better)
"""
import os
import struct
import sys
import zlib
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
from fetch_icons import svg, render   # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
from uidata import UiData, U, rec_name   # noqa: E402

ICON_PX = 28                  # icon size inside the 30 px line (the tip is drawn smaller than the font)
PAD = 1                       # empty columns left and right of the icon
GLYPHS = {                    # code point: Material Symbol
    0xe000: 'play_arrow',
    0xe001: 'pause',
    0xe002: 'skip_next',
    0xe003: 'skip_previous',
}
COLOUR = (139, 144, 144)      # RGB of the status bar's home / back symbols
STR_COL = 0x1b0               # text record: colours (normal, focus, selected, disabled), BGR
TIPS = {                      # line of TipBox.txt (0 = first entry) -> code point, in every language
    0: 0xe002,                # next track
    1: 0xe001,                # pause
    2: 0xe000,                # play
    3: 0xe003,                # previous track
    4: 0xe002,                # next station
    5: 0xe003,                # previous station
}


def glyph(cache, name, height):
    out = os.path.join(cache, f'.{name}_tip.png')
    render(svg(cache, name), '#ffffff', (ICON_PX, ICON_PX), out)
    alpha = Image.open(out).convert('RGBA').getchannel('A')
    os.remove(out)
    w = ICON_PX + 2 * PAD
    cell = Image.new('L', (w, height), 0)
    cell.paste(alpha, (PAD, (height - ICON_PX) // 2 + 1))
    return w, cell.tobytes() + b'\0'


def add_glyphs(font, cache):
    d = bytearray(font)
    assert d[:8] == 'VIFT'.encode('utf-16le'), 'not a VIFT font'
    hdr, tsize, height, bpp = struct.unpack_from('<IIBB', d, 0x0c)
    assert hdr == 0x18 and bpp == 8, 'unexpected VIFT header'
    table = bytearray(zlib.decompress(bytes(d[hdr:hdr + tsize])))
    assert len(table) == 65536 * 8
    blobs = bytearray(d[hdr + tsize:])
    for cp, name in GLYPHS.items():
        assert struct.unpack_from('<H', table, cp * 8)[0] == 0, f'U+{cp:04X} is used by the font'
        w, pixels = glyph(cache, name, height)
        z = zlib.compress(pixels, 9)
        struct.pack_into('<HHI', table, cp * 8, w, len(z), len(blobs))
        blobs += z
    t = zlib.compress(bytes(table), 9)
    struct.pack_into('<I', d, 0x10, len(t))
    return bytes(d[:hdr]) + t + bytes(blobs)


def set_tips(txt):
    """TipBox.txt (UTF-16): '{' TAB key TAB language 1 TAB ... '}' per entry. The key (the Chinese source text) is
    what the firmware looks the entry up by: kept; every language column becomes the icon"""
    text = txt.decode('utf-16')
    lines = text.split('\r\n') if '\r\n' in text else text.split('\n')
    sep = '\r\n' if '\r\n' in text else '\n'
    k = -1
    for i, line in enumerate(lines):
        if not line.startswith('{'):
            continue
        k += 1
        if k in TIPS:
            cols = line.split('\t')
            lines[i] = '\t'.join(cols[:2] + [chr(TIPS[k]) if c not in ('', '}') else c for c in cols[2:]])
    return sep.join(lines).encode('utf-16')


def set_colour(data):
    """the tip text ("ViewShowStrTip") in COLOUR"""
    u = UiData(data)
    w, base = u.windows[0]
    n = 0
    for t, o in w.children(base):
        if t == 0 and rec_name(w.raw, o) == 'ViewShowStrTip':
            struct.pack_into('<I', w.raw, o + STR_COL, COLOUR[2] << 16 | COLOUR[1] << 8 | COLOUR[0])
            n += 1
    assert n == 1, 'ViewShowStrTip not found'
    return u.build()


def main(src, out, cache, icons=False):
    def io(name, fn):
        os.makedirs(os.path.dirname(os.path.join(out, name)), exist_ok=True)
        # always from the stock files: running this twice must not append the glyphs twice
        open(os.path.join(out, name), 'wb').write(fn(open(os.path.join(src, name), 'rb').read()))
    io(os.path.join('Data', 'TipBox.data'), set_colour)
    print(f'{out}: tip colour {COLOUR}')
    if icons:
        io('Font30_8Bit.vft', lambda b: add_glyphs(b, cache))
        io(os.path.join('Language', 'TipBox.txt'), set_tips)
        print(f'{out}: {len(GLYPHS)} icons at U+E000.. in the font, {len(TIPS)} tips')


if __name__ == '__main__':
    main(*sys.argv[1:4], icons='--icons' in sys.argv[4:])
