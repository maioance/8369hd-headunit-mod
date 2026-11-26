"""Flat restyle of the full-screen climate page (apps/Data/AirCondition.data), with the same pieces as the
climate strip (climabar.mod): Material Symbols, white / grey, Noto digits, the thin fan panel.

  top row:  one chip per active function (A/C, AUTO, DUAL, MAX, REAR, REC, ...), symbol + label
  centre:   the airflow pictograms of the climate strip, one per side (lit per direction), seat heating
  bottom:   temperatures in Noto, fan panel with 7 bars

Each element keeps its stock image index; only the artwork, sizes and positions change.
Colours, symbols and positions are at the top; tools/build_overlay.sh rebuilds everything.

usage: build_aircondition.py <AirCondition.data> <out AirCondition.data>
"""
import os
import struct
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window, I, U, rec_name   # noqa: E402
from build_volume_bar import image_blob              # noqa: E402
from fetch_icons import svg, render                  # noqa: E402
import teal_to_white                                 # noqa: E402

# --- colours (RGB) -----------------------------------------------------------------------------
from theme import CARD, CARD_LINE, ACCENT as ON, OFF, TEXT   # noqa: E402  (tools/theme.py)
HEAT = (240, 140, 64)        # seat heating: orange, like the seat heating lights (teal_to_white keeps it)
FONT = '/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf'
DIGIT_FONT = '/usr/share/fonts/google-noto/NotoSans-Regular.ttf'
CACHE = os.path.join(os.path.dirname(__file__), '../climabar/icons_src')

# --- top row chips: image index -> (Material symbol or None, label) ----------------------------
CHIP_W, CHIP_H, CHIP_ICON, CHIP_FONT = 100, 38, 24, 15
CHIPS = {
    0: ('ac_unit', 'A/C'),
    1: ('mode_fan', 'AUTO'),            # auto, high intensity
    2: ('mode_fan', 'AUTO'),            # auto, low intensity
    3: ('sync_disabled', 'SYNC'),       # the firmware shows this one while the zones are separate (SYNC off)
    4: ('windshield_defrost_front', 'MAX'),
    6: ('lightbulb', ''),
    11: ('windshield_defrost_rear', 'REAR'),
    7: ('lock', 'REAR'),                # rear controls locked
    8: ('car_fan_recirculate_2', 'REC'),
    9: ('car_fan_recirculate_2', 'REC A'),   # automatic recirculation (second state of the same element)
    10: ('air', 'FRESH'),
}
CHIP_DIM = {3}                          # drawn grey: it means "off"
# chip x per element name (window coordinates, the window starts at screen y 72); y = CHIP_Y
CHIP_Y = 16
CHIP_X = {
    'ViewShowImageAcOn': 16, 'ViewShowImageAutoHighWind': 124, 'ViewShowImageAutoLowWind': 124,
    'ViewShowImageDual': 232, 'ViewShowImageMaxFront': 340, '#6': 448,
    'ViewShowImageRearLight': 588, 'ViewShowImageRearLock': 696, 'ViewShowImageInCycle': 804,
    'ViewShowImageOutCycle': 912,
}

# --- centre: airflow pictogram, the Material symbol of the climate strip with all three directions --------
# It is split into its parts (person, windshield, face arrow, feet arrow): each side shows the whole symbol in
# grey, and every active direction is drawn on top in teal (with the person), so any combination lights up.
FLOW_SYMBOL = 'car_defrost_mid_low_left'
FLOW_PX = 200                 # pictogram size (canvas 274 x 232, as the stock seat)
SEAT_RECT = {'left': (170, 150, 274, 232), 'right': (570, 150, 274, 232)}
HEAT_ICON = 'heat'

# --- temperature digits (image font of the text fields): index -> glyph ---------------------------
DIGIT_H = 33
DIGIT_PAD = 3                # transparent rows above and below the digits
DIGITS = {37: '0', 38: '9', 39: '8', 40: '7', 41: '6', 42: '5', 43: '4', 44: '3', 45: '2', 46: '1',
          47: '.', 48: '°C', 49: 'HI', 50: 'LO'}

# temperature text fields (digit images are wider than the stock ones): name -> (x, y, w, h), window coordinates
TEMP_RECT = {
    'ViewShowStrLeftTemperature': (40, 472, 200, 40),
    'ViewShowStrRightTemperature': (784, 472, 200, 40),
}
TEMP_ALIGN = {'ViewShowStrLeftTemperature': 36, 'ViewShowStrRightTemperature': 38}   # 36 left, 38 right

# --- fan panel (window 1, 484 x 88) --------------------------------------------------------------
PANEL_LINE = (235, 240, 242, 230)
FAN_ICONS = [(96, 46, 22), (358, 38, 32)]    # (x, y, size) of the small / large fan symbol; 20 px from the bars


def rgb_hex(c):
    return '#%02x%02x%02x' % c


def material(name, colour, px):
    out = os.path.join(CACHE, f'.{name}_ac.png')
    render(svg(CACHE, name), rgb_hex(colour), (px, px), out)
    im = Image.open(out).convert('RGBA')
    os.remove(out)
    return im


def chip(symbol, label, colour=ON):
    k = 4
    im = Image.new('RGBA', (CHIP_W * k, CHIP_H * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, CHIP_W * k - 1, CHIP_H * k - 1), radius=CHIP_H * k // 2,
                                         fill=CARD + (255,), outline=CARD_LINE + (255,), width=k)
    im = im.resize((CHIP_W, CHIP_H), Image.LANCZOS)
    font = ImageFont.truetype(FONT, CHIP_FONT)
    tw = ImageDraw.Draw(im).textlength(label, font=font) if label else 0
    iw = CHIP_ICON if symbol else 0
    gap = 4 if symbol and label else 0
    x = round((CHIP_W - (iw + gap + tw)) / 2)
    if symbol:
        im.alpha_composite(material(symbol, colour, CHIP_ICON), (x, (CHIP_H - CHIP_ICON) // 2))
    if label:
        ImageDraw.Draw(im).text((x + iw + gap, CHIP_H / 2), label, font=font, fill=colour + (255,), anchor='lm')
    return im


def centred(icon, size):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    im.alpha_composite(icon, ((size[0] - icon.width) // 2, (size[1] - icon.height) // 2))
    return im


def pill(size, colour):
    w, h = size
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=h * k // 2, fill=colour + (255,))
    return im.resize(size, Image.LANCZOS)


def glyph(text):
    font = ImageFont.truetype(DIGIT_FONT, round(DIGIT_H / 0.72))   # Noto digit height is ~0.72 em
    asc = font.getbbox('0')[1]
    w = round(font.getlength(text)) + 1
    im = Image.new('RGBA', (w, DIGIT_H + 2 * DIGIT_PAD), (0, 0, 0, 0))   # round glyphs overshoot the digit height
    ImageDraw.Draw(im).text((0, DIGIT_PAD - asc), text, font=font, fill=TEXT + (255,))
    return im


def fan_panel(size):
    k = 4
    w, h = size
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def bez(p0, p1, p2, n=24):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]
    top = 10
    pts = [(4, h), (40, 30)] + bez((40, 30), (52, top), (78, top))[1:] + [(w - 78, top)] \
        + bez((w - 78, top), (w - 52, top), (w - 40, 30))[1:] + [(w - 4, h)]
    d.line([(x * k, y * k) for x, y in pts], fill=PANEL_LINE, width=2 * k, joint='curve')
    im = im.resize(size, Image.LANCZOS)
    for x, y, s in FAN_ICONS:
        im.alpha_composite(material('mode_fan_2', (235, 240, 242), s), (x, y))
    return im


def flow_parts(px):
    """Alpha masks of the parts of FLOW_SYMBOL: person, ws (windshield), face, feet - by connected component."""
    im = material(FLOW_SYMBOL, (255, 255, 255), px)
    a = im.getchannel('A')
    w, h = im.size
    pa = a.load()
    seen = [[False] * w for _ in range(h)]
    parts = {n: Image.new('L', (w, h), 0) for n in ('person', 'ws', 'face', 'feet')}
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0][x0] or pa[x0, y0] == 0:
                continue
            stack, comp = [(x0, y0)], []
            seen[y0][x0] = True
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and pa[nx, ny]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            cx = sum(p[0] for p in comp) / len(comp) / w
            cy = sum(p[1] for p in comp) / len(comp) / h
            name = 'ws' if cy < 0.4 and cx > 0.5 else 'person' if cx < 0.55 else 'face' if cy < 0.68 else 'feet'
            dst = parts[name].load()
            for x, y in comp:
                dst[x, y] = pa[x, y]
    return parts


def tinted(masks, colour):
    im = Image.new('RGBA', masks[0].size, colour + (0,))
    a = masks[0]
    for m in masks[1:]:
        a = ImageChops.lighter(a, m)
    im.putalpha(a)
    return im


def size_of(u, k):
    return U(u.images[k], 4), U(u.images[k], 8)


def build_images(u):
    for k, (symbol, label) in CHIPS.items():
        u.images[k] = image_blob(chip(symbol, label, OFF if k in CHIP_DIM else ON))
    # divider between the two sides: a thin quiet line
    line = Image.new('RGBA', size_of(u, 5), (0, 0, 0, 0))
    ImageDraw.Draw(line).rectangle((1, 0, 2, line.height), fill=CARD_LINE + (255,))
    u.images[5] = image_blob(line)
    # airflow (12 / 13 seat = whole symbol grey; 14 windshield, 15 / 17 face, 16 / 18 feet = person + part, teal)
    size = SEAT_RECT['left'][2:]
    p = flow_parts(FLOW_PX)
    whole = [p['person'], p['ws'], p['face'], p['feet']]
    left = {12: tinted(whole, OFF), 14: tinted([p['person'], p['ws']], ON),
            15: tinted([p['person'], p['face']], ON), 16: tinted([p['person'], p['feet']], ON)}
    mirror = lambda im: im.transpose(Image.FLIP_LEFT_RIGHT)
    for k, im in left.items():
        u.images[k] = image_blob(centred(im, size))
    u.images[13] = image_blob(centred(mirror(left[12]), size))
    u.images[17] = image_blob(centred(mirror(left[15]), size))
    u.images[18] = image_blob(centred(mirror(left[16]), size))
    u.images.append(image_blob(centred(mirror(left[14]), size)))   # right windshield (new image)
    # seat heating: symbol + level pills (20 off, 21 on)
    u.images[19] = image_blob(centred(material(HEAT_ICON, HEAT, 56), size_of(u, 19)))
    u.images[20] = image_blob(pill(size_of(u, 20), OFF))
    u.images[21] = image_blob(pill(size_of(u, 21), HEAT))
    # temperature glyphs
    for k, text in DIGITS.items():
        u.images[k] = image_blob(glyph(text))
    # fan panel and its bars (odd index = lit, even = off)
    u.images[22] = image_blob(fan_panel(size_of(u, 22)))
    for k in range(23, 37):
        u.images[k] = image_blob(pill(size_of(u, k), ON if k % 2 else OFF).copy())


def relayout(u):
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    ws_right = len(u.images) - 1
    side = {14: 'left', 15: 'left', 16: 'left', 17: 'right', 18: 'right'}
    n_ws = 0
    for t, rel in w.children(base):
        if rec_name(raw, rel) in TEMP_RECT:
            struct.pack_into('<iiII', raw, rel + 0x19c, *TEMP_RECT[rec_name(raw, rel)])
            struct.pack_into('<I', raw, rel + 0x1c8, TEMP_ALIGN[rec_name(raw, rel)])
        if t != 4:
            continue
        k = I(raw, rel + 0x104)
        name = rec_name(raw, rel) or f'#{k}'
        if k in side:
            s = side[k]
            if k == 14:                       # two windshield elements: left, then right
                s = 'left' if n_ws == 0 else 'right'
                if n_ws:
                    struct.pack_into('<i', raw, rel + 0x104, ws_right)
                n_ws += 1
            struct.pack_into('<iiII', raw, rel + 0xd4, *SEAT_RECT[s])
        if name in CHIP_X:
            struct.pack_into('<iiII', raw, rel + 0xd4, CHIP_X[name], CHIP_Y, CHIP_W, CHIP_H)
    u.windows[0] = (Window(bytes(raw), base), base)


def main(src, out):
    u = UiData(open(src, 'rb').read())
    build_images(u)
    relayout(u)
    open(out, 'wb').write(u.build())
    teal_to_white.main([out])          # the teal accents (drawn here and in the kept stock art) white, as everywhere
    print(f'{out}: restyled')


if __name__ == '__main__':
    main(*sys.argv[1:3])
