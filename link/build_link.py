"""The wireless CarPlay / Android Auto connect screens (apps/Data/CarPlay.data, AutoWireless.data).

Stock: one line of text in the middle ("Please use your mobile phone to connect to Bluetooth:", the unit's Bluetooth
name under it). Restyled: an illustration (phone - link - car) added as a static image control, the instruction
shorter and dim (vehicle/fix_titles.py), the Bluetooth name white - the one thing to find on the phone -
and the link state under it. The three texts stay the firmware's own controls (it fills them in); only their places,
sizes and colours change.

usage: build_link.py <stock Data dir> <out Data dir> <Material Symbols cache dir>
"""
import os
import struct
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window, U, rec_name     # noqa: E402
from build_volume_bar import image_blob            # noqa: E402
from fetch_icons import svg, render                # noqa: E402
from add_belt_control import add_child             # noqa: E402
from theme import TEXT, DIM, LINE_RED              # noqa: E402

SCREENS = ('CarPlay', 'AutoWireless')
STR_RECT, STR_FONT, STR_COL, STR_ALIGN = 0x19c, 0x1ac, 0x1b0, 0x1c8
ALIGN_CENTRE = 37
STATIC = ord('c')                                  # an image control with no handler shows its 'c' picture

ART = (342, 104, 340, 120)                         # the illustration: x, y, w, h
SYMBOL_PX = 84
TEXTS = {                                          # control -> (rect, font px, colour)
    'ViewShowStrBtName': ((112, 248, 800, 40), 30, DIM),        # the instruction
    'ViewShowStrLocalName': ((112, 296, 800, 56), 30, TEXT),    # the Bluetooth name: white (this text keeps 30 px)
    'ViewShowStrLinkInfo': ((112, 366, 800, 40), 30, DIM),      # link state
}


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def symbol(cache, name, colour, px):
    out = os.path.join(cache, f'.{name}_link.png')
    render(svg(cache, name), '#%02x%02x%02x' % colour, (px, px), out)
    im = Image.open(out).convert('RGBA')
    os.remove(out)
    return im


def illustration(cache):
    """phone, three dots in the accent red, car - centred in ART"""
    w, h = ART[2], ART[3]
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    phone, car = symbol(cache, 'smartphone', TEXT, SYMBOL_PX), symbol(cache, 'directions_car', TEXT, SYMBOL_PX)
    im.alpha_composite(phone, (0, (h - phone.height) // 2))
    im.alpha_composite(car, (w - car.width, (h - car.height) // 2))
    k = 4
    dots = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(dots)
    x0, x1 = phone.width + 30, w - car.width - 30
    for i in range(3):
        cx, cy, r = (x0 + (x1 - x0) * (i + 0.5) / 3) * k, h / 2 * k, 6 * k
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=LINE_RED + (255 if i == 1 else 150,))
    im.alpha_composite(dots.resize((w, h), Image.LANCZOS))
    return im


def static_image(template, rect, index):
    """an image control record (the template has no name, so no handler): always its 'c' picture"""
    rec = bytearray(template)
    struct.pack_into('<iiII', rec, 0xd4, *rect)
    struct.pack_into('<I', rec, 0xe4, STATIC)
    struct.pack_into('<IIII', rec, 0x100, STATIC, index, 0, 0)
    return bytes(rec)


def template_record(fw):
    """a stock static image control (Home's first decoration) to copy"""
    u = UiData(open(os.path.join(fw, 'Main.data'), 'rb').read())
    w, base = u.windows[0]
    t, rel = next((t, rel) for t, rel in w.children(base) if t == 4 and not rec_name(w.raw, rel))
    return bytes(w.raw[rel:rel + U(w.raw, rel)])


def build(src, out, cache, template):
    u = UiData(open(src, 'rb').read())
    wi = next(i for i, (w, base) in enumerate(u.windows)
              if any(rec_name(w.raw, rel) in TEXTS for _, rel in w.children(base)))
    w, base = u.windows[wi]
    raw = bytearray(w.raw)
    for t, rel in w.children(base):
        name = rec_name(raw, rel)
        if t == 0 and name in TEXTS:
            rect, px, colour = TEXTS[name]
            struct.pack_into('<iiII', raw, rel + STR_RECT, *rect)
            struct.pack_into('<I', raw, rel + STR_FONT, px)
            struct.pack_into('<I', raw, rel + STR_ALIGN, ALIGN_CENTRE)
            struct.pack_into('<III', raw, rel + STR_COL, bgr(colour), bgr(colour), bgr(colour))
    w = Window(bytes(raw), base)
    u.images.append(image_blob(illustration(cache)))
    u.windows[wi] = (add_child(w, base, static_image(template, ART, len(u.images) - 1), 4), base)
    data = u.build()
    UiData(data)                                   # parses back
    open(out, 'wb').write(data)


def main(fw, out, cache):
    template = template_record(fw)
    for name in SCREENS:
        build(os.path.join(fw, name + '.data'), os.path.join(out, name + '.data'), cache, template)
        print(f'{name}: restyled')


if __name__ == '__main__':
    main(*sys.argv[1:4])
