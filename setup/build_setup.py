"""Setup screens (apps/Data/Setup*.data and BmwSoundSetting.data, the volume page) in the style of Home / Radio / Bluetooth / Trip computer.

- list rows (the opaque dark-teal 1024 x 87 / 660 x 50 bars): see-through with a hairline under them; pressed /
  selected: the glass a step lighter with the red bar on the left (as the Radio list). The stock line icons of the
  Setup menu are kept (same drawing), white;
- panels: glass cards; full-screen backgrounds: none (the wallpaper shows, as on the other screens);
- buttons (pills, grey / orange buttons, keypad keys, steering-wheel keys): glass, pressed lighter with a white
  outline; their stock symbol / digit is kept, white;
- sliders: grey track, red fill (as the Radio band slider); knobs, crosshair, selected radio button: red;
- OFF / ON switches: grey track / red track, white knob;
- text colours: pressed and selected white (stock: pure green / red / cyan); selected rows have the red bar.

Screens not touched: GPS info / path, touch calibration (stock look), WallPaper and BtSetup (home/, bt/ builders).

usage: build_setup.py <stock apps/Data dir> <out apps/Data dir>
"""
import os
import struct
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window                     # noqa: E402
from build_volume_bar import image_blob               # noqa: E402
from extract_images import decode                     # noqa: E402
from theme import TEXT, DIM, CARD, CARD_LINE, LINE_RED   # noqa: E402
from theme import GLASS, GLASS_CARD_ALPHA, GLASS_LINE_ALPHA, GLASS_PRESSED_ALPHA, GLASS_PRESSED_LINE   # noqa: E402

K = 4                                                  # supersampling for rounded shapes
STR_COL, BTN_TEXT = 0x1b0, 0x110
ROW_ON_ALPHA = 40                                      # a pressed / selected row: discreet, its red text stays readable
TEXT_COLOURS = {(0, 255, 0): TEXT,                     # pressed
                (255, 0, 0): TEXT,                     # selected (Language, ...): the row's red bar marks it
                (0, 255, 255): TEXT}                   # selected (Sound preset): idem


# --- drawing -----------------------------------------------------------------------------------------------------
def rgba(c, a=255):
    return tuple(c[:3]) + (a,)


def rounded(size, box, radius, fill=None, outline=None, width=1):
    w, h = size
    im = Image.new('RGBA', (w * K, h * K), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle(tuple(v * K for v in box), radius=radius * K, fill=fill, outline=outline,
                                         width=width * K)
    return im.resize(size, Image.LANCZOS)


def glass(size, pressed=False, radius=14, inset=0):
    w, h = size
    box = (inset, inset, w - inset - 1, h - inset - 1)
    if pressed:
        return rounded(size, box, radius, rgba(GLASS, GLASS_PRESSED_ALPHA), GLASS_PRESSED_LINE, 2)
    return rounded(size, box, radius, rgba(GLASS, GLASS_CARD_ALPHA), rgba(GLASS, GLASS_LINE_ALPHA), 1)


def dialog(size):
    """an opaque card for pop-ups over a page (must stay readable over anything)"""
    w, h = size
    return rounded(size, (0, 0, w - 1, h - 1), 16, rgba(CARD), rgba(CARD_LINE), 1)


def glyph_mask(im, bg=None, threshold=40):
    """the drawing on a stock image as an alpha mask: pixels far from the background colour (most common colour)"""
    im = im.convert('RGBA')
    px = im.getdata()
    if bg is None:
        from collections import Counter
        bg = Counter(p[:3] for p in px if p[3] > 200).most_common(1)[0][0]
    a = [0] * len(px)
    for i, (r, g, b, al) in enumerate(px):
        d = max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2]))
        if d > threshold and al > 0:
            a[i] = min(255, (d - threshold) * 255 // max(1, 160 - threshold)) * al // 255
    m = Image.new('L', im.size)
    m.putdata(a)
    return m


def coloured(mask, colour):
    im = Image.new('RGBA', mask.size, rgba(colour))
    im.putalpha(mask)
    return im


def bright_mask(im, level=150):
    """the light drawing (white symbol / digit) of a stock button"""
    im = im.convert('RGBA')
    a = [min(255, max(0, (min(r, g, b) - level) * 255 // (255 - level))) * al // 255 for r, g, b, al in im.getdata()]
    m = Image.new('L', im.size)
    m.putdata(a)
    return m


def row(size, pressed, icon=None):
    """a list row: see-through, hairline under it; pressed / selected: lighter glass + red bar"""
    w, h = size
    if pressed:
        im = rounded(size, (6, 3, w - 7, h - 4), 10, rgba(GLASS, ROW_ON_ALPHA), None)
        ImageDraw.Draw(im).rectangle((6, 14, 9, h - 15), fill=rgba(LINE_RED))
    else:
        im = Image.new('RGBA', size, (0, 0, 0, 0))
        ImageDraw.Draw(im).line([(16, h - 1), (w - 16, h - 1)], fill=rgba(GLASS, GLASS_LINE_ALPHA))
    if icon is not None:
        im.alpha_composite(coloured(icon, TEXT))
    return im


def list_item(size, selected):
    """an item of a short list (Sound presets): nothing / glass with the red bar"""
    w, h = size
    if not selected:
        return Image.new('RGBA', size, (0, 0, 0, 0))
    im = rounded(size, (4, 4, w - 5, h - 5), 10, rgba(GLASS, ROW_ON_ALPHA), None)
    ImageDraw.Draw(im).rectangle((4, 16, 7, h - 17), fill=rgba(LINE_RED))
    return im


def button(size, pressed, symbol=None, radius=None):
    w, h = size
    im = glass(size, pressed, radius if radius is not None else min(14, h // 2 - 1))
    if symbol is not None:
        im.alpha_composite(coloured(symbol, TEXT))
    return im


def pill(size, pressed):
    w, h = size
    return glass(size, pressed, radius=h // 2 - 1, inset=1)


def track(size, fill):
    """a slider bar: grey track or red fill, same rounded shape as the stock one"""
    w, h = size
    t = max(4, min(8, h // 4))
    y0 = (h - t) // 2
    col = rgba(LINE_RED) if fill else rgba(GLASS, 70)
    return rounded(size, (0, y0, w - 1, y0 + t - 1), t // 2, col, None)


def vtrack(size, fill):
    w, h = size
    t = max(4, min(10, w // 3))
    x0 = (w - t) // 2
    return rounded(size, (x0, 0, x0 + t - 1, h - 1), t // 2, rgba(LINE_RED) if fill else rgba(GLASS, 70), None)


def switch(size, on):
    """OFF / ON switch: track (grey / red), white knob; the stock text OFF / ON is dropped (the knob side says it)"""
    w, h = size
    im = rounded(size, (1, 1, w - 2, h - 2), h // 2 - 1, rgba(LINE_RED) if on else rgba(GLASS, 60), None)
    r = h // 2 - 4
    cx = w - 3 - r if on else 3 + r
    knob = Image.new('RGBA', (w * K, h * K), (0, 0, 0, 0))
    ImageDraw.Draw(knob).ellipse(((cx - r) * K, (h // 2 - r) * K, (cx + r) * K, (h // 2 + r) * K), fill=rgba(TEXT))
    im.alpha_composite(knob.resize(size, Image.LANCZOS))
    return im


def frame(size, chosen):
    w, h = size
    return rounded(size, (0, 0, w - 1, h - 1), 10, None, rgba(LINE_RED) if chosen else rgba(GLASS, GLASS_LINE_ALPHA),
                   2 if chosen else 1)


def recolour(im, colour):
    """every visible pixel in `colour`, brightness kept relative to the brightest one (alpha kept)"""
    im = im.convert('RGBA')
    px = list(im.getdata())
    top = max((max(p[:3]) for p in px if p[3] > 0), default=1) or 1
    out = [tuple(min(255, c * max(p[:3]) // top) for c in colour) + (p[3],) for p in px]
    o = Image.new('RGBA', im.size)
    o.putdata(out)
    return o


def clear(size):
    return Image.new('RGBA', size, (0, 0, 0, 0))


# --- per screen: image index -> new image (from the stock image) -----------------------------------------------------
def icon_row(stock_normal, pressed):
    """a Setup menu row with the stock line icon (taken from the normal row, left part only)"""
    w, h = stock_normal.size
    left = stock_normal.crop((0, 0, 110, h))
    icon = Image.new('L', (w, h), 0)
    icon.paste(glyph_mask(left, threshold=30), (0, 0))
    return row((w, h), pressed, icon)


def menu_rows(u):
    """SetupLhxPndMenu: rows (0, 1), (3, 4) ... (23, 24); 2 is the chevron"""
    pairs = [(0, 1)] + [(n, n + 1) for n in range(3, 25, 2)]
    out = {}
    stock = [decode(b) for b in u.images]
    for n, p in pairs:
        out[n] = icon_row(stock[n], False)
        out[p] = icon_row(stock[n], True)
    out[2] = recolour(stock[2], DIM)
    return out


SIMPLE = {
    'SetupBasic': {0: lambda im: row(im.size, False), 1: lambda im: row(im.size, True),
                   3: lambda im: dialog_with_buttons(im), 5: lambda im: dialog_with_buttons(im),
                   4: lambda im: button(im.size, True)},
    'SetupLanguage': {0: lambda im: row(im.size, False), 1: lambda im: row(im.size, True)},
    'SetupRadioArea': {0: lambda im: row(im.size, False), 1: lambda im: row(im.size, True),
                       2: lambda im: recolour(im, DIM), 3: lambda im: recolour(im, LINE_RED)},
    'SetupAudio': {0: lambda im: glass(im.size, radius=16), 2: lambda im: vtrack(im.size, False),
                   3: lambda im: vtrack(im.size, True), 5: lambda im: recolour(im, LINE_RED),
                   6: lambda im: recolour(im, LINE_RED), 7: lambda im: recolour(im, TEXT),
                   8: lambda im: pill(im.size, False), 9: lambda im: pill(im.size, True),
                   10: lambda im: list_item(im.size, False), 11: lambda im: list_item(im.size, True)},
    'SetupVideo': {1: lambda im: track(im.size, False), 2: lambda im: track(im.size, True),
                   3: lambda im: pill(im.size, False), 4: lambda im: pill(im.size, True)},
    'SetupConfig': {0: lambda im: glass(im.size, radius=16), 1: lambda im: row(im.size, False),
                    2: lambda im: row(im.size, True), 3: lambda im: recolour(im, TEXT),
                    4: lambda im: recolour(im, LINE_RED), 5: lambda im: recolour(im, TEXT),
                    6: lambda im: recolour(im, LINE_RED), 7: lambda im: clear(im.size),
                    8: lambda im: switch(im.size, False), 9: lambda im: switch(im.size, True),
                    10: lambda im: track(im.size, False), 11: lambda im: track(im.size, True)},
    'SetupMainKey': {0: lambda im: glass(im.size, radius=16), 1: lambda im: row(im.size, False),
                     2: lambda im: row(im.size, True), 3: lambda im: switch(im.size, False),
                     4: lambda im: switch(im.size, True), 5: lambda im: button(im.size, False),
                     6: lambda im: button(im.size, True)},
    'SetupFactory': {0: lambda im: glass(im.size, radius=16), 1: lambda im: row(im.size, False),
                     2: lambda im: row(im.size, True)},
    'SetupScreenSaver': {0: lambda im: glass(im.size, radius=16), 1: lambda im: row(im.size, False),
                         2: lambda im: row(im.size, True)},
    'SetupDebug': {0: lambda im: row(im.size, False), 1: lambda im: row(im.size, True),
                   2: lambda im: button(im.size, False), 3: lambda im: button(im.size, True)},
    'SetupTime': {0: lambda im: glass(im.size, radius=16), 1: lambda im: glass(im.size, radius=12),
                  2: lambda im: pill(im.size, False), 3: lambda im: dialog(im.size),
                  4: lambda im: row(im.size, False), 5: lambda im: row(im.size, True),
                  6: lambda im: button(im.size, False), 7: lambda im: button(im.size, True)},
    'SetupLogo': {0: lambda im: glass(im.size, radius=16), 1: lambda im: row(im.size, False),
                  2: lambda im: row(im.size, True), 3: lambda im: frame(im.size, False),
                  4: lambda im: frame(im.size, True), 5: lambda im: button(im.size, False),
                  6: lambda im: button(im.size, True)},
    'SetupWheel': {0: lambda im: clear(im.size), 1: lambda im: button(im.size, False),
                   2: lambda im: button(im.size, True), 15: lambda im: dialog_with_buttons(im),
                   **{k: (lambda pressed: lambda im: button(im.size, pressed, bright_mask(im), 14))(k % 2 == 0)
                      for k in range(3, 15)}},           # keys: odd normal, even pressed
    'SetupPassword': {0: lambda im: glass(im.size, radius=14),
                      **{k: (lambda pressed: lambda im: button(im.size, pressed, bright_mask(im), 14))(k % 2 == 0)
                         for k in range(1, 25)}},
    'SetupUpdate': {0: lambda im: clear(im.size), 1: lambda im: button(im.size, False),
                    2: lambda im: button(im.size, False), 3: lambda im: button(im.size, True)},
    'SetupUpdateOta': {0: lambda im: glass(im.size, radius=16), 1: lambda im: pill(im.size, False)},
    'SetupUpdateApp': {0: lambda im: track(im.size, False), 1: lambda im: track(im.size, True)},
    # Setup > Volume settings
    'BmwSoundSetting': {0: lambda im: glass(im.size, radius=16), 1: lambda im: pill(im.size, False),
                        2: lambda im: pill(im.size, True), 3: lambda im: button(im.size, False, glyph_mask(im), 16)},
}


def dialog_with_buttons(im):
    """a stock pop-up (grey box with two grey buttons drawn in): an opaque card with two glass buttons in the same
    places (found as the darker rounded areas of the stock image)"""
    w, h = im.size
    out = dialog((w, h))
    px = im.convert('RGB').load()
    m = 8                                          # skip the box's own outline
    bg = px[w // 2, h // 3]
    differs = lambda x, y: sum(abs(a - b) for a, b in zip(px[x, y], bg)) > 12
    ys = [y for y in range(m, h - m) if differs(w // 4, y)]
    if ys:
        cy = (ys[0] + ys[-1]) // 2
        y0, y1 = ys[0], ys[-1]
        for lo, hi in ((m, w // 2), (w // 2, w - m)):       # the left and the right button, each where it is
            xs = [x for x in range(lo, hi) if differs(x, cy)]
            if xs:
                out.alpha_composite(glass((xs[-1] - xs[0] + 1, y1 - y0 + 1), radius=10), (xs[0], y0))
    return out


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def rgb_of(v):
    return (v & 255, (v >> 8) & 255, (v >> 16) & 255)


# --- files -----------------------------------------------------------------------------------------------------
def text_colours(u):
    for wi, (w, base) in enumerate(u.windows):
        raw = bytearray(w.raw)
        for t, rel in w.children(base):
            off = rel + STR_COL if t == 0 else rel + BTN_TEXT + STR_COL if t == 1 else None
            if off is None or off + 16 > len(raw):
                continue
            cols = list(struct.unpack_from('<4I', raw, off))
            for i, v in enumerate(cols):
                rgb = (v & 255, (v >> 8) & 255, (v >> 16) & 255)
                if rgb in TEXT_COLOURS:
                    c = TEXT_COLOURS[rgb]
                    cols[i] = c[2] << 16 | c[1] << 8 | c[0]
            struct.pack_into('<4I', raw, off, *cols)
        # lists / sliders keep the same four colours elsewhere in their record: white, green, red (or cyan), grey
        for t, rel in w.children(base):
            if t in (0, 1):
                continue
            size = struct.unpack_from('<I', raw, rel)[0]
            for o in range(rel, rel + size - 15, 4):
                c = struct.unpack_from('<4I', raw, o)
                if c[0] == 0xffffff and c[1] == 0x00ff00 and c[2] in (0x0000ff, 0xffff00) and c[3] == 0x3c3c3c:
                    struct.pack_into('<II', raw, o + 4, *(bgr(TEXT_COLOURS[rgb_of(v)]) for v in c[1:3]))
        u.windows[wi] = (Window(bytes(raw), base), base)


def build(name, src, out):
    u = UiData(open(src, 'rb').read())
    stock = [decode(b) for b in u.images]
    spec = menu_rows(u) if name == 'SetupLhxPndMenu' else {k: f(stock[k]) for k, f in SIMPLE[name].items()}
    for k, im in spec.items():
        assert im.size == stock[k].size, (name, k, im.size, stock[k].size)
        u.images[k] = image_blob(im)
    text_colours(u)
    open(out, 'wb').write(u.build())
    return len(spec)


def main(fw, out):
    os.makedirs(out, exist_ok=True)
    for name in ['SetupLhxPndMenu'] + list(SIMPLE):
        n = build(name, os.path.join(fw, name + '.data'), os.path.join(out, name + '.data'))
        print(f'{name}: {n} images')


if __name__ == '__main__':
    main(*sys.argv[1:3])
