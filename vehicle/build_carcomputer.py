"""Flat restyle of the "Vehicle information" screen (apps/Data/CarComputer.data), in the style of the
climate strip and the radio.

  left:   four flat cards (fuel, outside temperature, seat belts, handbrake): icon, grey label, white value
  right:  the car seen from above; open doors / boot in the warning colour
  bottom: three flat cards (engine speed, current speed, mileage)

The firmware fills in the texts; this only redraws the artwork and moves / recolours the text fields.
Colours and positions are at the top; tools/build_overlay.sh rebuilds everything.

usage: build_carcomputer.py <CarComputer.data> <out CarComputer.data>
"""
import os
import struct
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window, I, U, rec_name   # noqa: E402
from build_volume_bar import image_blob              # noqa: E402
from extract_images import decode                    # noqa: E402
from fetch_icons import svg, render                  # noqa: E402

# --- colours (RGB) -----------------------------------------------------------------------------
# tools/theme.py: TEXT icons and values (white-grey, as the climate strip symbols), DIM labels, WARN open doors / boot
from theme import TEXT, DIM, WARN, GLASS, GLASS_CARD_ALPHA, GLASS_LINE_ALPHA   # noqa: E402  cards: glass, as on Radio
ON = TEXT                                                           # the icons
RADIUS = 14
ICON_PX = 34                 # stock symbol height inside the cards
STOCK_PX = {}                # per image index
HANDBRAKE_PX = 42            # height of the drawn handbrake symbol
MATERIAL_PX = 50             # Material Symbols canvas (the symbol fills ~80% of it)

# --- icons: Material Symbols (https://fonts.google.com/icons) per image index; None = the stock symbol,
#     recoloured (Material has no seat-belt symbol; the handbrake one is drawn)
ICONS = {
    0: 'local_gas_station',    # fuel
    1: 'thermostat',           # outside temperature
    2: None,                   # seat belts
    3: 'handbrake',            # drawn as vectors (handbrake() below)
    5: 'readiness_score',      # engine speed
    11: 'speed',               # current speed
    12: 'route',               # mileage
}
CACHE = os.path.join(os.path.dirname(__file__), '../climabar/icons_src')

# --- layout (screen coordinates; the title bar ends at y 69) -----------------------------------
ROW_X, ROW_W, ROW_H = 24, 380, 86
ROW_Y = (84, 182, 280, 378)            # fuel, outside temperature, seat belts, handbrake
CAR_XY = (492, 172)                    # car + door overlays (436 x 203)
BOT_Y, BOT_W, BOT_H = 484, 316, 96
BOT_X = (24, 354, 684)                 # engine speed, current speed, mileage
TEXT_X = 84                            # label / value start inside a card (after the icon)
LABEL_DY, VALUE_DY = 10, 44            # rows; the bottom cards use +4 / +6 more

ALIGN_LEFT = 36
STR_RECT, STR_COL, STR_ALIGN = 0x19c, 0x1b0, 0x1c8
IMG_RECT, IMG_INDEX = 0xd4, 0x104


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def glyph(im, keep, height=ICON_PX):
    """The light symbol of a stock icon, recoloured teal, cropped and scaled to ICON_PX."""
    px = im.load()
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    op = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            v = keep(r, g, b)
            if v > 0 and a:
                op[x, y] = ON + (min(255, a * v // 255),)
    out = out.crop(out.getbbox())
    s = height / out.height
    return out.resize((max(1, round(out.width * s)), height), Image.LANCZOS)


def handbrake(h=32):
    """The handbrake warning symbol, drawn as vectors (4x supersampled) so it stays smooth:
    a ring with "!" inside and an arc on each side."""
    k = 4
    H = h * k
    W = round(H * 1.25)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = (W / 2, H / 2)
    st = round(H * 0.09)
    col = ON + (255,)
    r = H * 0.31
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=col, width=st)
    R = H * 0.5 - st / 2
    box = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
    d.arc(box, 130, 230, fill=col, width=st)
    d.arc(box, -50, 50, fill=col, width=st)
    bw = st * 0.55
    d.rounded_rectangle((c[0] - bw, c[1] - r * 0.6, c[0] + bw, c[1] + r * 0.08), radius=bw, fill=col)
    d.ellipse((c[0] - bw * 1.1, c[1] + r * 0.32, c[0] + bw * 1.1, c[1] + r * 0.32 + bw * 2.2), fill=col)
    return im.resize((W // k, h), Image.LANCZOS)


def material(name):
    out = os.path.join(CACHE, name + '_cc.png')
    render(svg(CACHE, name), '#%02x%02x%02x' % ON, (MATERIAL_PX, MATERIAL_PX), out)
    im = Image.open(out).convert('RGBA')
    os.remove(out)
    return im


def card(w, h, icon, icon_cx):
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=RADIUS * k, fill=GLASS + (GLASS_CARD_ALPHA,),
                                         outline=GLASS + (GLASS_LINE_ALPHA,), width=k)
    im = im.resize((w, h), Image.LANCZOS)
    im.alpha_composite(icon, (icon_cx - icon.width // 2, (h - icon.height) // 2))
    return im


def build_images(u):
    img = [decode(b) for b in u.images]
    # left icons: light glyph on a dark teal disc -> keep the bright part
    disc = lambda r, g, b: max(0, min(255, (max(r, g, b) - 80) * 255 // 140))
    for k in range(4):
        if ICONS[k] == 'handbrake':
            icon = handbrake(HANDBRAKE_PX)
        else:
            icon = material(ICONS[k]) if ICONS[k] else glyph(img[k], disc, STOCK_PX.get(k, ICON_PX))
        u.images[k] = image_blob(card(ROW_W, ROW_H, icon, 44))
    # bottom icons: white glyph on a teal gradient -> keep pixels that are white (red channel high)
    white = lambda r, g, b: max(0, min(255, (r - 150) * 3))
    for k in (5, 11, 12):
        icon = material(ICONS[k]) if ICONS[k] else glyph(img[k].crop((0, 0, 90, img[k].height)), white)
        u.images[k] = image_blob(card(BOT_W, BOT_H, icon, 44))
    # door / boot overlays: same shape, warning colour
    for k in range(6, 11):
        im = img[k]
        a = im.getchannel('A').point(lambda v: v * 3 // 4)
        flat = Image.new('RGBA', im.size, WARN + (0,))
        flat.putalpha(a)
        u.images[k] = image_blob(flat)


def relayout(u):
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    texts = []
    for t, rel in w.children(base):
        if t == 4:
            k = I(raw, rel + IMG_INDEX)
            if k < 4:
                rect = (ROW_X, ROW_Y[k], ROW_W, ROW_H)
            elif k in (5, 11, 12):
                rect = (BOT_X[(5, 11, 12).index(k)], BOT_Y, BOT_W, BOT_H)
            else:
                rect = CAR_XY + (436, 203)
            struct.pack_into('<iiII', raw, rel + IMG_RECT, *rect)
        elif U(raw, rel) >= 460:
            texts.append(rel)
    # text fields come in (label, value) pairs: 4 rows, then the 3 bottom cards
    boxes = [(ROW_X, y, ROW_W, 0) for y in ROW_Y] + [(x, BOT_Y, BOT_W, 4) for x in BOT_X]
    for n, rel in enumerate(texts):
        x, y, cw, extra = boxes[n // 2]
        value = n % 2
        dy = (VALUE_DY + extra + 2 if value else LABEL_DY + extra)
        struct.pack_into('<iiII', raw, rel + STR_RECT, x + TEXT_X, y + dy, cw - TEXT_X - 12, 30)
        struct.pack_into('<I', raw, rel + STR_ALIGN, ALIGN_LEFT)
        c = bgr(TEXT if value else DIM)
        struct.pack_into('<II', raw, rel + STR_COL, c, c)
    u.windows[0] = (Window(bytes(raw), base), base)


def main(src, out):
    u = UiData(open(src, 'rb').read())
    build_images(u)
    relayout(u)
    open(out, 'wb').write(u.build())
    print(f'{out}: restyled')


if __name__ == '__main__':
    main(*sys.argv[1:3])
