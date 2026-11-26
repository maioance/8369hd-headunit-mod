"""Flat restyle of the Bluetooth screens (apps/Data/Bt*.data) and the status bar (SystemBar.data), in the style of
the radio and climate screens.

Every image is redrawn at its stock size (touch areas stay the same):
  left menu    flat tabs, Material Symbols; the open page: teal symbol + teal bar on the left
  keypads      flat rounded keys (pressed: teal), Noto digits / letters
  call screen  flat round buttons: answer green, hang up red, the others dark with a white symbol
  BT Music     generated cover instead of the turntable, Material transport symbols; a long song name on the
               page scrolls; the title bar says "BT Music" (the stock field shows the word "Title")
  lists        flat rows, Material call-direction symbols
  status bar   Material symbols for home / back / Bluetooth / USB / volume (and the Wireless pages' bottom bar);
               the seat-belt symbol control (tools/add_belt_control.py)
Colours, symbols and sizes are at the top; tools/build_overlay.sh rebuilds everything.

usage: build_bt.py <stock Data dir> <out Data dir>
"""
import os
import struct
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window, I, rec_name        # noqa: E402
from add_belt_control import add_belt                 # noqa: E402
from build_volume_bar import image_blob               # noqa: E402
from fetch_icons import svg, render                   # noqa: E402
from extract_images import decode                     # noqa: E402

# --- colours (RGB) -----------------------------------------------------------------------------
from theme import BG, CARD, CARD_LINE, PRESSED, ACCENT as ON, OFF, TEXT, DIM   # noqa: E402  (tools/theme.py)
from theme import GLASS, GLASS_CARD_ALPHA, GLASS_LINE_ALPHA, GLASS_PRESSED_ALPHA, GLASS_PRESSED_LINE   # noqa: E402
GREEN = (46, 160, 96)         # answer / call
RED = (214, 72, 60)           # hang up, missed call
FONT = '/usr/share/fonts/google-noto/NotoSans-Regular.ttf'
CACHE = os.path.join(os.path.dirname(__file__), '../climabar/icons_src')
RADIUS = 14
BELT_PNG = os.path.join(os.path.dirname(__file__), '../climabar/assets/belt.png')

STR_LONG = 0x1c0                          # text longer than the rectangle: 0 / 2 cut with '...', 1 scrolls
STR_TEXT = 0xd4                           # a text field's own text (UTF-16, up to the rectangle)
MUSIC_TITLE = 'BT Music'                  # BT Music title bar
SONG_NAME_MARGIN = 30                     # the scrolling song name on the page stops this far from the screen edge

# --- left menu: tab (by button position, 0..4) -> Material symbol --------------------------------
TABS = ['dialpad', 'history', 'person', 'bluetooth', 'music_note']
TAB_ICON = 40                 # the label under the symbol is drawn by the firmware
TAB_ICON_Y = 22               # top of the symbol inside the 210 x 106 tab
TAB_INSET, TAB_RADIUS = 8, 14  # the selected tab's glass pill: margin inside the tab, corner radius

# --- keypads: image index -> label (normal, pressed pairs); '<' = delete, 'call' = call key ----------
DIAL_KEYS = {13: '1', 15: '2', 17: '3', 19: '*', 21: '<', 23: '4', 25: '5', 27: '6', 29: '0', 31: '+',
             33: '7', 35: '8', 37: '9', 39: '#', 41: 'call'}
TALK_KEYS = {10: '1', 12: '2', 14: '3', 16: '4', 18: '5', 20: '6', 22: '7', 24: '8', 26: '9', 28: '*',
             30: '0', 32: '#'}
BOOK_KEYS = {15: '<', **{17 + 2 * i: chr(65 + i) for i in range(26)}, 69: 'OK'}
KEY_FONT_PX = {'digit': 34, 'letter': 24}

# --- call screen round buttons (BtTalk): index -> (symbol, fill, symbol colour) ---------------------
TALK_BUTTONS = {
    0: ('call', GREEN, (255, 255, 255)),
    1: ('mic', 'glass', TEXT), 2: ('mic_off', 'pressed', TEXT),
    3: ('contacts', 'glass', TEXT), 4: ('contacts', 'pressed', TEXT),
    5: ('dialpad', 'glass', TEXT), 6: ('dialpad', 'pressed', TEXT),
    7: ('call_end', RED, (255, 255, 255)),
}

# --- BT Music --------------------------------------------------------------------------------------
MUSIC_TRANSPORT = {14: ('skip_previous', False), 15: ('skip_previous', True), 16: ('pause', False), 17: ('pause', True),
                   18: ('play_arrow', False), 19: ('play_arrow', True), 20: ('skip_next', False), 21: ('skip_next', True)}
MUSIC_INFO = {11: 'music_note', 12: 'person', 13: 'album'}
from theme import COVER, header_line, LINE_RED   # noqa: E402  placeholder cover gradient; the status bar line

# --- call history (BtRecord) -------------------------------------------------------------------------
RECORD_TABS = {11: ('call_made', False), 12: ('call_made', True), 13: ('call_received', False),
               14: ('call_received', True), 15: ('call_missed', False), 16: ('call_missed', True)}   # True: selected
RECORD_CALL = {17: ('call', GREEN)}
RECORD_ROWS = {18: ('call_made', TEXT), 19: ('call_received', TEXT), 20: ('call_missed', RED),
               21: ('delete', DIM), 22: ('delete', TEXT)}

# --- status bar (SystemBar.data, shared by all screens; BT Music has its own copy): index -> (symbol, colour)
BAR_PX = 34                   # top bar symbols
BAR_BOTTOM_PX = 40            # bottom bar of the Wireless pages
# all white; PRESSED_ICON: pressed, white on a glass circle (as everywhere else)
PRESSED_ICON = 'pressed'
BAR_CIRCLE = 0.75             # the glass circle behind a pressed status bar symbol, of the button's size
SYSTEM_BAR = {0: ('home_app_logo', TEXT), 1: ('home_app_logo', PRESSED_ICON), 2: ('undo', TEXT), 3: ('undo', PRESSED_ICON),
              4: ('bluetooth', TEXT), 6: ('usb', TEXT), 7: ('volume_up', TEXT), 8: ('volume_off', TEXT)}
# (10..13, CarPlay and Android Auto, keep their stock logos)
# white also when pressed, no glass circle (the user's choice)
SYSTEM_BAR_BOTTOM = {10: ('play_circle', TEXT), 11: ('play_circle', TEXT),          # CarPlay (as on Home)
                     12: ('navigation', TEXT), 13: ('navigation', TEXT),            # Android Auto (as on Home)
                     14: ('radio', TEXT), 15: ('radio', TEXT), 16: ('bluetooth', TEXT),
                     17: ('settings', TEXT), 18: ('settings', TEXT)}
MUSIC_BAR = {22: ('usb', TEXT), 23: ('bluetooth', TEXT), 24: ('volume_up', TEXT), 25: ('volume_off', TEXT),
             26: ('home_app_logo', TEXT), 27: ('home_app_logo', PRESSED_ICON), 28: ('undo', TEXT),
             29: ('undo', PRESSED_ICON)}

STR_COL, STR_RECT = 0x1b0, 0x19c
LIST_PAD = 20                 # contacts: text inset left / right inside a row
ROW_GAP = 3                   # empty rows above / below each list row card
# the page right of the menu (Contacts, Record, Pair): stock 209 / 211, 70, 814 x 530 - flush with the screen's right
# edge and the status bar line; with a margin all round instead
CONTENT = (230, 82, 774, 518)
RECORD_FILTERS = ('ViewShowButtonRecordIDriverDialed', 'ViewShowButtonRecordIDriverReceive',
                  'ViewShowButtonRecordIDriverMiss', 'ViewShowButtonDialIDriverCall')
RECORD_BAR_H = 80             # the filter bar (a list row card, 80 high)
BOOK_CALL_X = 306             # Contacts: left edge of the call symbol in the selected row (button 283 + 80 wide)


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def size_of(u, k):
    b = u.images[k]
    return struct.unpack_from('<II', b, 4)


def material(name, colour, px):
    out = os.path.join(CACHE, f'.{name}_bt.png')
    render(svg(CACHE, name), '#%02x%02x%02x' % colour, (px, px), out)
    im = Image.open(out).convert('RGBA')
    os.remove(out)
    return im


def rounded(size, fill, radius=RADIUS, outline=None):
    w, h = size
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=min(radius, h // 2, w // 2) * k,
                                         fill=fill + (255,), outline=(outline + (255,)) if outline else None,
                                         width=k if outline else 0)
    return im.resize(size, Image.LANCZOS)


def glass(size, pressed=False, radius=RADIUS):
    """a card / button as on Home and Radio: see-through glass; pressed / selected: lighter, white outline"""
    w, h = size
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle(
        (0, 0, w * k - 1, h * k - 1), radius=min(radius, h // 2, w // 2) * k,
        fill=GLASS + ((GLASS_PRESSED_ALPHA if pressed else GLASS_CARD_ALPHA),),
        outline=GLASS_PRESSED_LINE if pressed else GLASS + (GLASS_LINE_ALPHA,), width=(2 if pressed else 1) * k)
    return im.resize(size, Image.LANCZOS)


def glass_circle(size, pressed=False, scale=1.0):
    w, h = size
    d = round((min(w, h) - 2) * scale)
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    x0, y0 = (w - d) // 2 * k, (h - d) // 2 * k
    ImageDraw.Draw(im).ellipse(
        (x0, y0, x0 + d * k - 1, y0 + d * k - 1), fill=GLASS + ((GLASS_PRESSED_ALPHA if pressed else GLASS_CARD_ALPHA),),
        outline=GLASS_PRESSED_LINE if pressed else GLASS + (GLASS_LINE_ALPHA,), width=(2 if pressed else 1) * k)
    return im.resize(size, Image.LANCZOS)


def circle(size, fill):
    w, h = size
    d = min(w, h) - 2
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    x0, y0 = (w - d) // 2 * k, (h - d) // 2 * k
    ImageDraw.Draw(im).ellipse((x0, y0, x0 + d * k - 1, y0 + d * k - 1), fill=fill + (255,))
    return im.resize(size, Image.LANCZOS)


def centred(base, top, dy=0):
    base.alpha_composite(top, ((base.width - top.width) // 2, (base.height - top.height) // 2 + dy))
    return base


def label(text, colour, px):
    font = ImageFont.truetype(FONT, px)
    l, t, r, b = font.getbbox(text)
    im = Image.new('RGBA', (r - l + 2, b - t + 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((1 - l, 1 - t), text, font=font, fill=colour + (255,))
    return im


def key(size, text, pressed):
    im = glass(size, pressed)
    colour = TEXT
    if text == '<':
        top = material('backspace', colour, round(size[1] * 0.55))
    elif text == 'call':
        im = rounded(size, GREEN if not pressed else (36, 128, 76))
        top = material('call', (255, 255, 255), round(min(size) * 0.42))
    else:
        top = label(text, colour, KEY_FONT_PX['digit' if text in '0123456789*#+' else 'letter'])
    return centred(im, top)


def thin_line(size):
    w, h = size
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle(((w - 1) // 2, 0, (w - 1) // 2, h), fill=CARD_LINE + (255,))
    return im


# ---- per element kind ------------------------------------------------------------------------------
def restyle_tabs(u):
    """the five menu buttons of window 1: each image gets the symbol of the tab it belongs to; an image that
    is the button's normal look on its own page (the open page) is drawn selected"""
    # the menu window: x 0, y 70, 210 wide (window 1 on most pages, window 0 on BT Music)
    w, base = next((w, b) for w, b in u.windows if [I(w.raw, 0xd4 + 4 * i) for i in range(3)] == [0, 70, 210])
    done = {}
    for t, rel in w.children(base):
        if t != 1:
            continue
        tab = I(w.raw, rel + 0xd8) // 107
        if not 0 <= tab < 5:
            continue
        imgs = [I(w.raw, rel + 0xe4 + 4 * i) for i in range(3)]
        open_page = len(set(imgs)) == 1                 # the page's own tab: one image for every state
        for state, k in enumerate(imgs):
            if k < 0 or k in done:
                continue
            selected = open_page or state > 0
            done[k] = True
            size = size_of(u, k)
            im = Image.new('RGBA', size, (0, 0, 0, 0))
            if selected:                    # a rounded glass pill inside the tab (never touching the screen edge)
                im.alpha_composite(glass((size[0] - 2 * TAB_INSET, size[1] - 2 * TAB_INSET), radius=TAB_RADIUS),
                                   (TAB_INSET, TAB_INSET))
            sym = material(TABS[tab], TEXT, TAB_ICON)                  # white, also selected
            im.alpha_composite(sym, ((size[0] - sym.width) // 2, TAB_ICON_Y))
            u.images[k] = image_blob(im)


def restyle_common(u):
    restyle_tabs(u)
    for k, b in enumerate(u.images):                    # the vertical dividers (8 x 530): none
        w, h = size_of(u, k)
        if w <= 8 and h >= 300:
            u.images[k] = image_blob(Image.new('RGBA', (w, h), (0, 0, 0, 0)))


def restyle_keys(u, keys):
    for k, text in keys.items():
        for pressed in (0, 1):
            u.images[k + pressed] = image_blob(key(size_of(u, k + pressed), text, pressed))


def recolour_texts(u, accent=ON):
    """stock text colours -> ours, in every text colour set (normal, focus, selected, disabled; BGR), wherever it is
    (text fields, button labels, list rows): white -> TEXT, green / cyan / yellow / red -> teal, grey -> OFF"""
    stock = {0xffffff: bgr(TEXT), 0x00ff00: bgr(accent), 0xffff00: bgr(accent), 0x00ffff: bgr(accent),
             0x0000ff: bgr(accent),
             0x3c3c3c: bgr(OFF)}
    for wi in range(len(u.windows)):
        w, base = u.windows[wi]
        raw = bytearray(w.raw)
        for o in range(0, len(raw) - 15, 4):
            q = struct.unpack_from('<IIII', raw, o)
            if q[3] == 0x3c3c3c and all(c in stock for c in q):        # a stock colour set ends with the grey
                struct.pack_into('<IIII', raw, o, *(stock[c] for c in q))
        u.windows[wi] = (Window(bytes(raw), base), base)


def tab_labels_white(u):
    """the menu tabs' names: white in every state (recolour_texts made the selected / open tab teal); the
    selected tab is shown by its glass background"""
    for wi in range(len(u.windows)):
        w, base = u.windows[wi]
        if [I(w.raw, 0xd4 + 4 * i) for i in range(3)] != [0, 70, 210]:
            continue
        raw = bytearray(w.raw)
        for t, rel in w.children(base):
            if t == 1 and 0 <= I(raw, rel + 0xd8) // 107 < 5:
                o = rel + 0x110 + STR_COL
                struct.pack_into('<III', raw, o, bgr(TEXT), bgr(TEXT), bgr(TEXT))
        u.windows[wi] = (Window(bytes(raw), base), base)


def list_text_rect(u, list_name, sub, rect):
    """rectangle of the text inside a list row (sub = offset of the row's text record in the list record)"""
    for wi in range(len(u.windows)):
        w, base = u.windows[wi]
        raw = bytearray(w.raw)
        for t, rel in w.children(base):
            if rec_name(raw, rel) == list_name:
                struct.pack_into('<iiII', raw, rel + sub + STR_RECT, *rect)
        u.windows[wi] = (Window(bytes(raw), base), base)


def row_card(size, fill=CARD):
    w, h = size
    row = Image.new('RGBA', size, (0, 0, 0, 0))
    row.alpha_composite(glass((w, h - 2 * ROW_GAP), radius=10), (0, ROW_GAP))
    return row


def symbols(u, table, px=None):
    for k, (name, colour) in table.items():
        size = size_of(u, k)
        base = glass_circle(size, True, BAR_CIRCLE) if colour == PRESSED_ICON else Image.new('RGBA', size, (0, 0, 0, 0))
        u.images[k] = image_blob(centred(base, material(name, TEXT if colour == PRESSED_ICON else colour,
                                                        px or round(min(size) * 0.8))))


# ---- screens ----------------------------------------------------------------------------------------
def bt_dial(u):
    restyle_common(u)
    u.images[11] = image_blob(Image.new('RGBA', size_of(u, 11), (0, 0, 0, 0)))      # panel behind the keypad
    u.images[12] = image_blob(glass(size_of(u, 12)))                                  # number / status field
    restyle_keys(u, DIAL_KEYS)


def bt_talk(u):
    for k, (name, fill, colour) in TALK_BUTTONS.items():
        size = size_of(u, k)
        base = glass_circle(size, fill == 'pressed') if isinstance(fill, str) else circle(size, fill)
        u.images[k] = image_blob(centred(base, material(name, colour, round(size[1] * 0.42))))
    u.images[8] = image_blob(glass(size_of(u, 8)))                                    # keypad panel
    u.images[9] = image_blob(glass(size_of(u, 9)))                                    # DTMF digits
    restyle_keys(u, TALK_KEYS)
    u.images[34] = image_blob(centred(Image.new('RGBA', size_of(u, 34), (0, 0, 0, 0)),
                                      material('backspace', TEXT, size_of(u, 34)[1])))


COVER_STYLE = 'vinyl'     # 'pulse' | 'vinyl' | 'soundwave' | 'halo'
COVER_GLASS = False       # the frosted-glass card behind the symbol (False: only the record, filling the card's place)


def bt_cover_card(size, style=COVER_STYLE, glass_card=COVER_GLASS):
    """Frosted-glass cover placeholder with uniform 5-bit interior alpha (no alpha rings) and RGB565 TPDF dithering."""
    import math
    import random
    w, h = size
    s = round(min(w, h) * 0.874)   # 194 px inside 222 x 222
    radius = 26
    k = 4
    S = s * k
    cx = cy = S // 2
    rng = random.Random(77)
    if not glass_card:
        s = min(w, h) - 2          # no card: the record takes the whole cover area
        S, cx = s * k, s * k // 2
        cy = cx

    interior_alpha = 49            # 6/31 (~19% opacity): translucent frosted glass with warm depth
    rgb_im = Image.new('RGB', (s, s))
    rpx = rgb_im.load()
    for y in range(s):
        yn = y / (s - 1)
        for x in range(s):
            xn = x / (s - 1)
            if style == 'halo':
                d_c = math.hypot(xn - 0.5, yn - 0.5)
                w_c = math.exp(-(d_c * d_c) / (2 * 0.42 * 0.42))
                r, g, b = 110 + w_c * 130, 115 - w_c * 45, 120 - w_c * 55
            else:
                d_red = math.hypot(xn - 0.80, yn - 0.82)
                w_red = math.exp(-(d_red * d_red) / (2 * 0.50 * 0.50))
                d_ice = math.hypot(xn - 0.18, yn - 0.18)
                w_ice = math.exp(-(d_ice * d_ice) / (2 * 0.55 * 0.55))
                r = 75 + w_red * 160 + w_ice * 115
                g = 82 - w_red * 25  + w_ice * 130
                b = 88 - w_red * 35  + w_ice * 135
            t1 = rng.random() + rng.random() - 1.0
            t2 = (rng.random() + rng.random() - 1.0) * 0.35
            rpx[x, y] = (
                max(0, min(255, round(r + (t1 + t2) * 7.0))),
                max(0, min(255, round(g + (t1 - t2) * 3.5))),
                max(0, min(255, round(b + (t1 + t2) * 7.0))),
            )

    mask_ss = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask_ss).rounded_rectangle((0, 0, S - 1, S - 1), radius=radius * k, fill=interior_alpha)
    card = rgb_im.convert('RGBA')
    card.putalpha(mask_ss.resize((s, s), Image.LANCZOS))

    rim_ss = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim_ss).rounded_rectangle(
        (0, 0, S - 1, S - 1), radius=radius * k,
        outline=GLASS + (GLASS_LINE_ALPHA,), width=k
    )
    card.alpha_composite(rim_ss.resize((s, s), Image.LANCZOS))
    if not glass_card:
        card = Image.new('RGBA', (s, s), (0, 0, 0, 0))

    if style == 'pulse':
        rings = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rings)
        rd.ellipse((cx - 72 * k, cy - 72 * k, cx + 72 * k, cy + 72 * k), outline=GLASS + (36,), width=k)
        rd.ellipse((cx - 56 * k, cy - 56 * k, cx + 56 * k, cy + 56 * k), outline=LINE_RED + (75,), width=round(1.2 * k))
        rd.ellipse(
            (cx - 41 * k, cy - 41 * k, cx + 41 * k, cy + 41 * k),
            fill=LINE_RED + (42,), outline=LINE_RED + (230,), width=round(2.0 * k)
        )
        card.alpha_composite(rings.resize((s, s), Image.LANCZOS))
        centred(card, material('music_note', TEXT, 52))
    elif style == 'vinyl':
        f = 1.0 if glass_card else (s / 2 - 1) / 70.0     # record radius 70 px on the card, else the whole area
        R = lambda r: round(r * f * k)
        v_body = Image.new('RGB', (s, s), (12, 14, 17))
        vpx = v_body.load()
        for y in range(s):
            dy = y - s / 2.0
            for x in range(s):
                dx = x - s / 2.0
                dist = math.hypot(dx, dy)
                if dist <= 70.0 * f:
                    ang = math.atan2(dy, dx)
                    sheen = (math.cos(2.0 * (ang + 0.65)) * 0.5 + 0.5) ** 3.0
                    red_sheen = (math.cos(ang - 0.8) * 0.5 + 0.5) ** 3.2
                    groove = math.sin(dist / f * 2.2) * 0.5 + 0.5
                    vr = 14 + sheen * 32 + red_sheen * 30 + groove * 4.5
                    vg = 16 + sheen * 36 + red_sheen * 7  + groove * 4.5
                    vb = 19 + sheen * 40 + red_sheen * 6  + groove * 5.0
                    t1 = rng.random() + rng.random() - 1.0
                    vpx[x, y] = (
                        max(0, min(255, round(vr + t1 * 6.5))),
                        max(0, min(255, round(vg + t1 * 3.2))),
                        max(0, min(255, round(vb + t1 * 6.5))),
                    )
        vmask_ss = Image.new('L', (S, S), 0)
        ImageDraw.Draw(vmask_ss).ellipse((cx - R(68), cy - R(68), cx + R(68), cy + R(68)), fill=240 if glass_card else 255)
        v_rgba = v_body.convert('RGBA')
        v_rgba.putalpha(vmask_ss.resize((s, s), Image.LANCZOS))
        card.alpha_composite(v_rgba)
        vinyl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vinyl)
        vd.ellipse((cx - R(68), cy - R(68), cx + R(68), cy + R(68)), outline=GLASS + (75,), width=4)
        vd.ellipse((cx - R(55), cy - R(55), cx + R(55), cy + R(55)), outline=GLASS + (32,), width=3)
        vd.ellipse((cx - R(41), cy - R(41), cx + R(41), cy + R(41)), outline=LINE_RED + (52,), width=3)
        vd.ellipse((cx - R(25), cy - R(25), cx + R(25), cy + R(25)), fill=(10, 12, 14, 255))
        vd.ellipse((cx - R(22), cy - R(22), cx + R(22), cy + R(22)), fill=(190, 46, 36, 255), outline=LINE_RED + (255,), width=5)
        card.alpha_composite(vinyl.resize((s, s), Image.LANCZOS))
        centred(card, material('music_note', (240, 244, 246), round(28 * f)))
    elif style == 'soundwave':
        eq = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        ed = ImageDraw.Draw(eq)
        heights = [18, 34, 52, 28, 66, 44, 26, 48, 20]
        bar_w, gap = 5 * k, 12 * k
        total_w = len(heights) * bar_w + (len(heights) - 1) * gap
        x0 = (S - total_w) // 2
        for idx, bh in enumerate(heights):
            bx = x0 + idx * (bar_w + gap)
            ed.rounded_rectangle((bx, cy + 54 * k - bh * k, bx + bar_w, cy + 54 * k), radius=round(2.5 * k), fill=LINE_RED + (82,))
        card.alpha_composite(eq.resize((s, s), Image.LANCZOS))
        centred(card, material('music_note', TEXT, 74), dy=-10)
    else:
        centred(card, material('music_note', TEXT, 82))

    return centred(Image.new('RGBA', (w, h), (0, 0, 0, 0)), card)


def bt_music(u):
    restyle_common(u)
    header(u, 30)                                         # BT Music's own status bar line
    u.images[10] = image_blob(bt_cover_card(size_of(u, 10)))
    symbols(u, {k: (n, DIM) for k, n in MUSIC_INFO.items()}, px=30)
    for k, (name, pressed) in MUSIC_TRANSPORT.items():  # white; pressed: on a glass circle
        size = size_of(u, k)
        base = glass_circle(size, True) if pressed else Image.new('RGBA', size, (0, 0, 0, 0))
        u.images[k] = image_blob(centred(base, material(name, TEXT, 52)))
    symbols(u, MUSIC_BAR, px=BAR_PX)
    add_belt(u, BELT_PNG, label='BtMusic')
    set_text(u, 'ViewShowStrTitle', MUSIC_TITLE)
    scroll_texts(u, {'ViewShowStrID3Title'}, window=1)        # the song name on the page (not the title bar)


def set_text(u, name, text):
    enc = text.encode('utf-16le')
    for wi, (w, base) in enumerate(u.windows):
        raw = bytearray(w.raw)
        for t, rel in w.children(base):
            if t == 0 and rec_name(raw, rel) == name:
                raw[rel + STR_TEXT:rel + STR_RECT] = enc + bytes(STR_RECT - STR_TEXT - len(enc))
        u.windows[wi] = (Window(bytes(raw), base), base)


def scroll_texts(u, names, window):
    w, base = u.windows[window]
    raw = bytearray(w.raw)
    for t, rel in w.children(base):
        if t == 0 and rec_name(raw, rel) in names:
            struct.pack_into('<I', raw, rel + STR_LONG, 1)
            x, w = I(raw, rel + STR_RECT), I(raw, rel + STR_RECT + 8)
            right = 1024 - I(raw, 0xd4) - SONG_NAME_MARGIN       # window-relative right limit
            struct.pack_into('<I', raw, rel + STR_RECT + 8, min(w, right - x))
    u.windows[window] = (Window(bytes(raw), base), base)


PAIR_SYMBOL, PAIR_FONT_PX = 28, 22               # BT Setup's connect / disconnect buttons


def labelled(base, sym, label):
    """a symbol and a word side by side, centred as a group on the button"""
    font = ImageFont.truetype(FONT, PAIR_FONT_PX)
    d = ImageDraw.Draw(base)
    gap = 10
    tw = d.textlength(label, font=font)
    x = round((base.width - (sym.width + gap + tw)) / 2)
    base.alpha_composite(sym, (x, (base.height - sym.height) // 2))
    d.text((x + sym.width + gap, base.height / 2), label, font=font, fill=TEXT + (255,), anchor='lm')
    return base


def bt_setup(u):
    restyle_common(u)
    u.images[10] = image_blob(glass(size_of(u, 10)))                                  # name / pin fields
    for k, (name, label, pressed) in {11: ('link', 'Connect', 0), 12: ('link', 'Connect', 1),
                                      13: ('link_off', 'Disconnect', 0), 14: ('link_off', 'Disconnect', 1)}.items():
        size = size_of(u, k)                            # the buttons have no text field: symbol + label drawn in
        u.images[k] = image_blob(labelled(glass(size, pressed), material(name, TEXT, PAIR_SYMBOL), label))
    u.images[15] = image_blob(glass((CONTENT[2] - 428, size_of(u, 15)[1])))          # connected phone
    content_margins(u)
    u.images[16] = image_blob(thin_line(size_of(u, 16)))


def bt_book(u):
    restyle_common(u)
    u.images[10] = image_blob(glass(size_of(u, 10)))                                  # search field
    for k, pressed in ((11, 0), (12, 1)):                                              # (off-screen) sync button
        size = size_of(u, k)
        u.images[k] = image_blob(centred(glass(size, pressed), material('sync', TEXT, round(size[1] * 0.5))))
    u.images[13] = image_blob(row_card(size_of(u, 13)))                               # list row
    list_text_rect(u, 'ViewShowListPhoneBook', 584, (LIST_PAD, 35, BOOK_CALL_X - 8 - LIST_PAD, 30))   # clear of the call symbol
    symbols(u, {14: ('call', GREEN)}, px=34)
    restyle_keys(u, BOOK_KEYS)
    content_margins(u)


def bt_record(u):
    restyle_common(u)
    u.images[10] = image_blob(row_card((CONTENT[2], size_of(u, 10)[1])))             # list row / filter bar
    content_margins(u)
    for k, (name, selected) in RECORD_TABS.items():     # filter tabs: white; selected on lighter glass
        size = size_of(u, k)
        base = glass(size, True, radius=10) if selected else Image.new('RGBA', size, (0, 0, 0, 0))
        u.images[k] = image_blob(centred(base, material(name, TEXT, 34)))
    symbols(u, RECORD_CALL, px=34)
    symbols(u, RECORD_ROWS, px=28)


def content_margins(u):
    """the page window right of the menu -> CONTENT; its lists as tall as the window, as wide as it on Record"""
    x, y, w, h = CONTENT
    for wi, (win, base) in enumerate(u.windows):
        r = [I(win.raw, 0xd4 + 4 * i) for i in range(4)]
        if r[0] not in (209, 211) or r[1:] != [70, 814, 530]:
            continue
        raw = bytearray(win.raw)
        struct.pack_into('<iiII', raw, 0xd4, x, y, w, h)
        for t, rel in win.children(base):
            n = rec_name(raw, rel)
            if n == 'ViewShowListPhoneBook':
                struct.pack_into('<I', raw, rel + 0xe0, h)
            elif n == 'ViewShowListCallRecord':
                ly = I(raw, rel + 0xd8)
                struct.pack_into('<II', raw, rel + 0xdc, w, h - ly)            # list w, h
                struct.pack_into('<I', raw, rel + 0xec, w)                      # row w
                struct.pack_into('<I', raw, rel + 0x20c, w)                     # row image w
                struct.pack_into('<i', raw, rel + 0xa0c, I(raw, rel + 0xa0c) - (814 - w))   # delete button
            elif n in RECORD_FILTERS:                    # Record: the filter buttons evenly over the bar, centred
                i = RECORD_FILTERS.index(n)
                bw, bh = I(raw, rel + 0xdc), I(raw, rel + 0xe0)
                struct.pack_into('<ii', raw, rel + 0xd4, round((i + 0.5) * w / len(RECORD_FILTERS) - bw / 2),
                                 (RECORD_BAR_H - bh) // 2)
            elif t == 1 and I(raw, rel + 0xe4) == 15 and I(raw, rel + 0xdc) == 347:   # Pair: connected phone
                struct.pack_into('<I', raw, rel + 0xdc, w - I(raw, rel + 0xd4))
        u.windows[wi] = (Window(bytes(raw), base), base)


def header(u, k):
    """the line under the status bar, in the theme's accent (stock: a teal glow)"""
    u.images[k] = image_blob(header_line(size_of(u, k)))


def recolour_teal(u, k):
    """the stock teal glow of an image (bluish pixels) in the theme's accent, shape and transparency kept"""
    im = decode(u.images[k]).convert('RGBA')
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and b > r + 30:
                px[x, y] = ON + (a,)
    u.images[k] = image_blob(im)


def recolour_red(u, k):
    """every pixel of an image in LINE_RED (the status bar line's red), shape and transparency kept"""
    im = decode(u.images[k]).convert('RGBA')
    red = Image.new('RGBA', im.size, LINE_RED + (255,))
    red.putalpha(im.getchannel('A'))
    u.images[k] = image_blob(red)


def bottom_same_when_pressed(u):
    """bottom bar buttons (window 1): the pressed state shows the normal image (CarPlay / Android Auto had another
    symbol pressed, Bluetooth the status bar's)"""
    w, base = u.windows[1]
    raw = bytearray(w.raw)
    for t, rel in w.children(base):
        if t == 1:
            struct.pack_into('<i', raw, rel + 0xe8, I(raw, rel + 0xe4))
    u.windows[1] = (Window(bytes(raw), base), base)


def system_bar(u):
    header(u, 5)
    recolour_red(u, 9)                                    # bottom bar: its top line and lower edge glow, red
    bottom_same_when_pressed(u)
    symbols(u, SYSTEM_BAR, px=BAR_PX)
    symbols(u, SYSTEM_BAR_BOTTOM, px=BAR_BOTTOM_PX)
    add_belt(u, BELT_PNG, label='SystemBar')


SCREENS = {'SystemBar': system_bar, 'BtDial': bt_dial, 'BtTalk': bt_talk, 'BtMusic': bt_music, 'BtSetup': bt_setup,
           'BtBook': bt_book, 'BtRecord': bt_record}


def main(src, out):
    os.makedirs(out, exist_ok=True)
    for name, fn in SCREENS.items():
        u = UiData(open(os.path.join(src, name + '.data'), 'rb').read())
        fn(u)
        recolour_texts(u, ON if name == 'SystemBar' else TEXT)   # BT pages: selected text white too
        tab_labels_white(u)
        open(os.path.join(out, name + '.data'), 'wb').write(u.build())
        print(f'{name}.data restyled')


if __name__ == '__main__':
    main(*sys.argv[1:3])
