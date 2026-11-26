"""Flat, clean OEM Home screen (apps/Data/Main.data), in the style of the radio / climate / Bluetooth screens.

Home styles, chosen with HOME_STYLE (default: 'grid', the installed one). Earlier card styles, kept as options:
  - 'split'   : two-zone card, glowing red divider, contextual footer widgets
  - 'deck'    : top-aligned title with red accent bar, lower instrument dial
  - 'capsule' : central squircle pedestal, bottom title pill capsule
  - 'dial'    : 60-tick dial ring, red glowing underline
  - 'glass', 'tile', 'disc', 'float', 'orb', 'squircle', 'compact', 'ring': simpler cards (two pages of three)
  - 'grid', 'dock', 'hero', 'list': all six functions on one page (see LAYOUTS)

Touch areas and page scrolling stay the firmware's. Home's own status bar gets the seat-belt symbol control.
usage: build_home.py <Main.data> <out Main.data> [<out WallPaper dir>]
"""
import math
import os
import struct
import sys
import zlib
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window                     # noqa: E402
from build_volume_bar import image_blob               # noqa: E402
from fetch_icons import svg, render                   # noqa: E402
from add_belt_control import add_belt                 # noqa: E402
import wallpapers                                     # noqa: E402  (home/wallpapers.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../bt'))
from build_bt import symbols, header, SYSTEM_BAR, BAR_PX   # noqa: E402

# --- colours (RGB) -----------------------------------------------------------------------------
from theme import ACCENT as ON, TEXT, DIM, OFF        # noqa: E402
from theme import GLASS, GLASS_CARD_ALPHA, GLASS_LINE_ALPHA, GLASS_PRESSED_ALPHA, GLASS_PRESSED_LINE   # noqa: E402
from theme import LINE_RED                            # noqa: E402

# Home style (see the docstring)
HOME_STYLE = os.environ.get('HOME_STYLE', 'grid')

SYMBOL_COLOUR = TEXT
CACHE = os.path.join(os.path.dirname(__file__), '../climabar/icons_src')
FONT_REG = '/usr/share/fonts/google-noto/NotoSans-Regular.ttf'
FONT_SEMI = '/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf'

CARD_W = 320
SLOTS_X = (16, 352, 688)      # screen x of the three slots (16 px margins and gaps); page 2: +1024
CARD_TOP, CARD_BOTTOM = 20, 412
RADIUS = 26

# image index -> (Material symbol, card metadata)
CARD_INFO = {
    0:  dict(symbol='play_circle', tag='01 // CONNECT',      sub='WIRELESS PROJECTION',    sub2='iOS  •  Siri  •  Media',      kind='carplay', active=False),
    1:  dict(symbol='play_circle', tag='01 // CONNECT',      sub='WIRELESS PROJECTION',    sub2='iOS  •  Siri  •  Media',      kind='carplay', active=False),
    2:  dict(symbol='radio',       tag='02 // TUNER',        sub='FM / AM  •  RDS STEREO', sub2='87.5  —  98.5  —  108 MHz',   kind='radio',   active=False),
    3:  dict(symbol='radio',       tag='02 // TUNER',        sub='FM / AM  •  RDS STEREO', sub2='87.5  —  98.5  —  108 MHz',   kind='radio',   active=False),
    4:  dict(symbol='navigation',  tag='03 // NAVIGATION',   sub='ANDROID AUTO  •  GPS',   sub2='Maps  •  Traffic  •  Voice',  kind='auto',    active=False),
    5:  dict(symbol='navigation',  tag='03 // NAVIGATION',   sub='ANDROID AUTO  •  GPS',   sub2='Maps  •  Traffic  •  Voice',  kind='auto',    active=False),
    6:  dict(symbol='bluetooth',   tag='04 // PHONE & A2DP', sub='HANDSFREE & STREAM',     sub2='Phonebook  •  BT Audio',      kind='bt',      active=False),
    7:  dict(symbol='bluetooth',   tag='04 // PHONE & A2DP', sub='HANDSFREE & STREAM',     sub2='Phonebook  •  BT Audio',      kind='bt',      active=False),
    8:  dict(symbol='music_note',  tag='04 // NOW PLAYING',  sub='A2DP STREAM ACTIVE',     sub2='Bluetooth Audio Streaming',   kind='bt',      active=True),
    9:  dict(symbol='apps',        tag='05 // LAUNCHER',     sub='SYSTEM APPLICATIONS',    sub2='Climate  •  Vehicle  •  USB', kind='apps',    active=False),
    10: dict(symbol='apps',        tag='05 // LAUNCHER',     sub='SYSTEM APPLICATIONS',    sub2='Climate  •  Vehicle  •  USB', kind='apps',    active=False),
    11: dict(symbol='settings',    tag='06 // SYSTEM',       sub='VEHICLE & DISPLAY',      sub2='Sound  •  Display  •  Car',   kind='setup',   active=False),
    12: dict(symbol='settings',    tag='06 // SYSTEM',       sub='VEHICLE & DISPLAY',      sub2='Sound  •  Display  •  Car',   kind='setup',   active=False),
}
PRESSED_IMAGES = {1, 3, 5, 7, 10, 12}
REMOVE = {13, 14}             # stock arcs and middle underline removed; 15 becomes our subtle page-dot dock pill
HOME_BAR = {16: 4, 18: 6, 19: 7, 20: 8}       # Bluetooth, USB, volume, muted

# --- Apps screen (MainApp.data) ----------------------------------------------------------------
APPS = {0: 'cable',                   # USB CarPlay
        2: 'usb',                     # USB Android Auto
        3: 'airplay',                 # AirPlay
        4: 'cast',                    # Mirror
        5: 'folder',                  # USB (media player)
        6: 'settings_input_antenna',  # DAB
        7: 'directions_car',          # vehicle information
        8: 'mode_fan'}                # climate
APPS_REMOVE = {1}
APP_INSET_X, APP_TOP, APP_BOTTOM, APP_RADIUS = 9, 4, 200, 22
# all eight apps on one page (no hidden second page): 4 columns x 2 rows of 232 x 211 buttons, centred. The Apps
# cards (glass, large symbol, no ring) stay unlike Home's tiles, and the status bar says "Apps".
APP_W = 232
APP_COLS = tuple((1024 - 4 * APP_W) // 2 + c * APP_W for c in range(4))
APP_ROWS = (78, 290)
APP_LABEL = 0x3c4             # the label's rectangle in a button record, relative to the button
APP_SYMBOL_PX, APP_SYMBOL_CY = 84, 78

BTN_TEXT, STR_RECT, STR_FONT, STR_COL, STR_ALIGN = 0x110, 0x19c, 0x1ac, 0x1b0, 0x1c8
ALIGN_LEFT, ALIGN_CENTRE = 36, 37
APP_TEXT_STOCK = bytes.fromhex('ffffff00 00ff0000 ff000000 3c3c3c00')


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def image_blob_argb(im):
    """PIL RGBA image -> native ARGB8888 (fmt 1, 3) UI blob used by stock Main.data (full 8-bit alpha & color)."""
    w, h = im.size
    r, g, b, a = im.convert('RGBA').split()
    bgra = Image.merge('RGBA', (b, g, r, a)).tobytes()
    return struct.pack('<IIIIII', 0x20, w, h, 1, 3, 0) + bytes.fromhex('0100000000000000') + zlib.compress(bgra, 9)


def material(name, colour, px):
    out = os.path.join(CACHE, f'.{name}_home.png')
    render(svg(CACHE, name), '#%02x%02x%02x' % colour, (px, px), out)
    im = Image.open(out).convert('RGBA')
    os.remove(out)
    return im


def draw_glow_line(im, x0, x1, y, col=LINE_RED, max_a=210, glow_r=4):
    """Draw a horizontal glowing line (like header_line) onto RGBA image `im`."""
    px = im.load()
    w = max(1, x1 - x0)
    mid_x = (x0 + x1) / 2.0
    for x in range(max(0, x0), min(im.width, x1)):
        fade = math.exp(-((x - mid_x) / (w * 0.38)) ** 2)
        for dy in range(-glow_r, glow_r + 1):
            yy = y + dy
            if 0 <= yy < im.height:
                a = max_a if dy == 0 else round(max_a * 0.32 * math.exp(-(dy * dy) / 2.2))
                sa = round(a * fade)
                if sa > 0:
                    r0, g0, b0, a0 = px[x, yy]
                    inv = 255 - sa
                    out_a = sa + (a0 * inv + 127) // 255
                    if out_a > 0:
                        out_r = (col[0] * sa + r0 * a0 * inv // 255) // out_a
                        out_g = (col[1] * sa + g0 * a0 * inv // 255) // out_a
                        out_b = (col[2] * sa + b0 * a0 * inv // 255) // out_a
                        px[x, yy] = (min(255, out_r), min(255, out_g), min(255, out_b), min(255, out_a))


def draw_contextual_footer_widget(d, im, w, y_center, meta):
    """Draw a category-specific mini OEM widget at y_center inside a card."""
    f_sub = ImageFont.truetype(FONT_REG, 11)
    f_semi = ImageFont.truetype(FONT_SEMI, 11)
    kind = meta['kind']
    if kind == 'radio':
        for idx, x in enumerate(range(54, w - 53, 8)):
            th = 8 if idx % 4 == 0 else 4
            col = GLASS + (100 if idx % 4 == 0 else 42,)
            d.line([(x, y_center - th // 2), (x, y_center + th // 2)], fill=col, width=1)
        nx = 174
        d.line([(nx, y_center - 8), (nx, y_center + 8)], fill=LINE_RED + (245,), width=2)
        d.ellipse((nx - 2, y_center - 10, nx + 2, y_center - 6), fill=LINE_RED + (245,))
        d.text((44, y_center), '87.5', font=f_sub, fill=DIM + (195,), anchor='rm')
        d.text((w - 44, y_center), '108', font=f_sub, fill=DIM + (195,), anchor='lm')
    elif kind == 'carplay':
        d.text((w // 2, y_center - 7), 'WIRELESS  •  iOS PROJECTION', font=f_sub, fill=DIM + (205,), anchor='mm')
        bar_y = y_center + 9
        d.rounded_rectangle((76, bar_y - 1, w - 76, bar_y + 2), radius=1, fill=GLASS + (38,))
        d.rounded_rectangle((76, bar_y - 1, 178, bar_y + 2), radius=1, fill=LINE_RED + (210,))
        d.ellipse((175, bar_y - 3, 181, bar_y + 4), fill=TEXT + (240,))
    elif kind == 'auto':
        d.text((w // 2, y_center - 7), 'GOOGLE MAPS  •  LIVE TRAFFIC', font=f_sub, fill=DIM + (205,), anchor='mm')
        by = y_center + 9
        for dx in (-64, -48, -32, -16, 0, 16, 32, 48, 64):
            col = LINE_RED + (220,) if dx == 0 else GLASS + (55 if abs(dx) == 32 else 30,)
            h_tick = 5 if dx == 0 else 3
            d.line([(w // 2 + dx, by - h_tick), (w // 2 + dx, by + h_tick)], fill=col, width=2 if dx == 0 else 1)
    elif kind == 'bt':
        if meta.get('active'):
            # Active equalizer bars when BT Music is playing (image 8)
            heights = (5, 9, 14, 8, 16, 11, 6, 13, 7)
            for idx, bh in enumerate(heights):
                bx = w // 2 + (idx - 4) * 10
                col = LINE_RED + (235,) if bh >= 11 else GLASS + (140,)
                d.rounded_rectangle((bx - 2, y_center - bh // 2, bx + 2, y_center + bh // 2), radius=1, fill=col)
        else:
            d.text((w // 2, y_center - 6), 'HANDSFREE  •  A2DP AUDIO', font=f_sub, fill=DIM + (205,), anchor='mm')
            draw_glow_line(im, 88, w - 88, y_center + 9, col=LINE_RED, max_a=130, glow_r=2)
    elif kind == 'apps':
        d.text((w // 2, y_center - 6), 'CLIMATE  •  VEHICLE  •  MEDIA', font=f_sub, fill=DIM + (205,), anchor='mm')
        for dx in (-24, -8, 8, 24):
            col = LINE_RED + (210,) if dx == -24 else GLASS + (65,)
            d.ellipse((w // 2 + dx - 2, y_center + 7, w // 2 + dx + 2, y_center + 11), fill=col)
    else:
        d.text((w // 2, y_center - 6), 'SOUND  •  DISPLAY  •  SYSTEM', font=f_semi, fill=DIM + (205,), anchor='mm')
        draw_glow_line(im, 88, w - 88, y_center + 9, col=GLASS, max_a=80, glow_r=1)


def draw_stage_backdrop(d, w, cy, kind, k):
    """Draw bespoke subtle geometric instrumentation around (w//2*k, cy*k) depending on card kind."""
    cx = (w // 2) * k
    cy_k = cy * k
    if kind == 'radio':
        for r_off, a_val in ((84, 52), (98, 32), (112, 18)):
            rk = r_off * k
            d.arc((cx - rk, cy_k - rk, cx + rk, cy_k + rk), start=150, end=210, fill=LINE_RED + (a_val + 25,), width=2 * k)
            d.arc((cx - rk, cy_k - rk, cx + rk, cy_k + rk), start=330, end=390, fill=LINE_RED + (a_val + 25,), width=2 * k)
    elif kind == 'auto':
        rk = 88 * k
        for deg in range(0, 360, 15):
            rad = math.radians(deg)
            is_card = (deg % 90 == 0)
            r0 = rk - (7 * k if is_card else 4 * k)
            x0, y0 = cx + r0 * math.cos(rad), cy_k + r0 * math.sin(rad)
            x1, y1 = cx + rk * math.cos(rad), cy_k + rk * math.sin(rad)
            col = LINE_RED + (190,) if is_card else GLASS + (36,)
            d.line([(x0, y0), (x1, y1)], fill=col, width=(2 if is_card else 1) * k)
    elif kind in ('carplay', 'bt'):
        for r_off, st, en, col in ((84, 210, 330, LINE_RED + (165,)),
                                   (84, 30, 150, GLASS + (45,)),
                                   (96, 235, 305, GLASS + (30,))):
            rk = r_off * k
            d.arc((cx - rk, cy_k - rk, cx + rk, cy_k + rk), start=st, end=en, fill=col, width=2 * k)
    elif kind == 'apps':
        rk = 84 * k
        for st in (200, 310, 20, 130):
            d.arc((cx - rk, cy_k - rk, cx + rk, cy_k + rk), start=st, end=st + 30,
                  fill=LINE_RED + (150,) if st in (200, 310) else GLASS + (45,), width=2 * k)
    elif kind == 'setup':
        rk = 86 * k
        for deg in range(0, 360, 20):
            rad = math.radians(deg)
            r0 = rk - 5 * k
            x0, y0 = cx + r0 * math.cos(rad), cy_k + r0 * math.sin(rad)
            x1, y1 = cx + rk * math.cos(rad), cy_k + rk * math.sin(rad)
            col = LINE_RED + (170,) if 210 <= deg <= 330 else GLASS + (42,)
            d.line([(x0, y0), (x1, y1)], fill=col, width=2 * k)


def card_split(size, meta, pressed):
    w, h = size
    k = 3
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = 26 * k
    top, bot = CARD_TOP * k, CARD_BOTTOM * k
    split_y = 286 * k

    base_a = 58 if pressed else 26
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r, fill=GLASS + (base_a,))

    footer_mask = Image.new('L', (w * k, h * k), 0)
    ImageDraw.Draw(footer_mask).rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r, fill=255)
    zones = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    zd = ImageDraw.Draw(zones)
    zd.rectangle((0, split_y, w * k, bot), fill=(8, 12, 15, 105))
    zd.rectangle((0, top, w * k, top + 38 * k), fill=(200, 225, 228, 12))
    im.alpha_composite(Image.composite(zones, Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0)), footer_mask))

    d = ImageDraw.Draw(im)
    line_col = (255, 255, 255, 200) if pressed else (GLASS + (50,))
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r,
                        outline=line_col, width=(2 if pressed else 1) * k)

    d.rounded_rectangle((22 * k, (CARD_TOP + 13) * k, 26 * k, (CARD_TOP + 27) * k), radius=2 * k,
                        fill=LINE_RED + (240,))

    draw_stage_backdrop(d, w, 162, meta['kind'], k)

    cx, cy = (w // 2) * k, 162 * k
    mr = 64 * k
    med_outline = LINE_RED + (140,) if meta.get('active') else GLASS + (48,)
    d.ellipse((cx - mr, cy - mr, cx + mr, cy + mr), fill=(10, 14, 18, 96),
              outline=med_outline, width=1 * k)

    im = im.resize((w, h), Image.LANCZOS)
    draw_glow_line(im, 14, w - 14, 286, col=LINE_RED, max_a=195, glow_r=3)

    d = ImageDraw.Draw(im)
    f_tag = ImageFont.truetype(FONT_SEMI, 11)
    d.text((34, CARD_TOP + 20), meta['tag'], font=f_tag, fill=DIM + (220,), anchor='lm')
    d.ellipse((w - 28, CARD_TOP + 17, w - 22, CARD_TOP + 23), fill=LINE_RED + (195,))

    sym = material(meta['symbol'], SYMBOL_COLOUR, 82)
    im.alpha_composite(sym, ((w - sym.width) // 2, 162 - sym.height // 2))

    draw_contextual_footer_widget(d, im, w, 372, meta)
    return im


def card_deck(size, meta, pressed):
    w, h = size
    k = 3
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = 22 * k
    top, bot = CARD_TOP * k, CARD_BOTTOM * k

    base_a = 58 if pressed else 24
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r, fill=GLASS + (base_a,))
    d.rounded_rectangle((14 * k, 110 * k, (w - 14) * k - 1, (CARD_BOTTOM - 14) * k), radius=16 * k,
                        fill=(8, 12, 15, 88), outline=GLASS + (28,), width=1 * k)

    line_col = (255, 255, 255, 200) if pressed else (GLASS + (48,))
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r,
                        outline=line_col, width=(2 if pressed else 1) * k)
    d.rounded_rectangle((22 * k, 42 * k, 26 * k, 88 * k), radius=2 * k, fill=LINE_RED + (245,))

    cx, cy = (w // 2) * k, 236 * k
    dial_r = 80 * k
    for deg in range(0, 360, 10):
        if 60 <= deg <= 120:
            continue
        rad = math.radians(deg)
        is_red = (200 <= deg <= 340)
        r_in = dial_r - (9 * k if deg % 30 == 0 else 5 * k)
        x0, y0 = cx + r_in * math.cos(rad), cy + r_in * math.sin(rad)
        x1, y1 = cx + dial_r * math.cos(rad), cy + dial_r * math.sin(rad)
        col = (LINE_RED + (215 if deg % 30 == 0 else 130,)) if is_red else (GLASS + (80 if deg % 30 == 0 else 36,))
        d.line([(x0, y0), (x1, y1)], fill=col, width=(2 if deg % 30 == 0 else 1) * k)

    ir = 60 * k
    d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=(12, 18, 22, 105),
              outline=GLASS + (44,), width=1 * k)

    im = im.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    f_sub = ImageFont.truetype(FONT_SEMI, 11)
    d.text((38, 82), meta['sub'], font=f_sub, fill=DIM + (215,), anchor='lm')
    f_tag = ImageFont.truetype(FONT_SEMI, 11)
    d.text((w - 22, 54), meta['tag'].split('//')[0].strip(), font=f_tag, fill=LINE_RED + (210,), anchor='rm')

    draw_glow_line(im, 32, w - 32, CARD_BOTTOM - 2, col=LINE_RED, max_a=220, glow_r=3)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 80)
    im.alpha_composite(sym, ((w - sym.width) // 2, 236 - sym.height // 2))
    draw_contextual_footer_widget(d, im, w, 358, meta)
    return im


def card_capsule(size, meta, pressed):
    w, h = size
    k = 3
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = 28 * k
    top, bot = CARD_TOP * k, CARD_BOTTOM * k

    base_a = 58 if pressed else 26
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r, fill=GLASS + (base_a,))
    d.rounded_rectangle((12 * k, (CARD_TOP + 10) * k, (w - 12) * k - 1, (CARD_BOTTOM - 10) * k - 1),
                        radius=20 * k, outline=GLASS + (24,), width=1 * k)

    cx, cy = (w // 2) * k, 160 * k
    half = 64 * k
    d.rounded_rectangle((cx - half, cy - half, cx + half, cy + half), radius=28 * k,
                        fill=(10, 14, 18, 115), outline=GLASS + (54,), width=1 * k)
    d.line([(cx - 32 * k, cy - half), (cx + 32 * k, cy - half)], fill=LINE_RED + (235,), width=2 * k)

    px0, py0, px1, py1 = 36 * k, 292 * k, (w - 36) * k, 346 * k
    d.rounded_rectangle((px0, py0, px1, py1), radius=27 * k,
                        fill=(8, 12, 15, 120), outline=GLASS + (40,), width=1 * k)

    line_col = (255, 255, 255, 200) if pressed else (GLASS + (48,))
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r,
                        outline=line_col, width=(2 if pressed else 1) * k)

    im = im.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(im)

    wm = material(meta['symbol'], GLASS, 136)
    r_ch, g_ch, b_ch, a_ch = wm.split()
    a_ch = a_ch.point(lambda p: (p * 11) // 255)
    wm = Image.merge('RGBA', (r_ch, g_ch, b_ch, a_ch))
    im.alpha_composite(wm, (w - 146, CARD_TOP + 16))

    sym = material(meta['symbol'], SYMBOL_COLOUR, 80)
    im.alpha_composite(sym, ((w - sym.width) // 2, 160 - sym.height // 2))

    f_chev = ImageFont.truetype(FONT_SEMI, 16)
    d.text((56, 318), '‹', font=f_chev, fill=LINE_RED + (220,), anchor='mm')
    d.text((w - 56, 318), '›', font=f_chev, fill=LINE_RED + (220,), anchor='mm')

    f_sub = ImageFont.truetype(FONT_REG, 11)
    d.text((w // 2, 374), meta['sub2'], font=f_sub, fill=DIM + (200,), anchor='mm')
    return im


def card_dial(size, meta, pressed):
    w, h = size
    k = 3
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = 28 * k
    top, bot = CARD_TOP * k, CARD_BOTTOM * k

    base_a = 54 if pressed else 22
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r, fill=GLASS + (base_a,))

    line_col = (255, 255, 255, 200) if pressed else (GLASS + (46,))
    d.rounded_rectangle((2 * k, top, (w - 2) * k - 1, bot - 1), radius=r,
                        outline=line_col, width=(2 if pressed else 1) * k)

    cx, cy = (w // 2) * k, 162 * k
    cr = 80 * k
    for i in range(60):
        deg = i * 6 - 90
        rad = math.radians(deg)
        is_cardinal = (i % 15 == 0)
        is_major = (i % 5 == 0)
        t_len = 10 * k if is_cardinal else (6 * k if is_major else 3 * k)
        r0 = cr - t_len
        x0, y0 = cx + r0 * math.cos(rad), cy + r0 * math.sin(rad)
        x1, y1 = cx + cr * math.cos(rad), cy + cr * math.sin(rad)
        col = (LINE_RED + (235,)) if is_cardinal else (GLASS + (85 if is_major else 34,))
        d.line([(x0, y0), (x1, y1)], fill=col, width=(2 if is_cardinal else 1) * k)

    ir = 58 * k
    d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=(10, 14, 18, 65),
              outline=GLASS + (36,), width=1 * k)

    im = im.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 80)
    im.alpha_composite(sym, ((w - sym.width) // 2, 162 - sym.height // 2))
    draw_glow_line(im, 100, w - 100, 336, col=LINE_RED, max_a=225, glow_r=3)

    f_sub = ImageFont.truetype(FONT_SEMI, 11)
    d.text((w // 2, 362), meta['sub'], font=f_sub, fill=DIM + (205,), anchor='mm')
    return im


# --- design-rule styles (glanceable: one large symbol, a 30+ px label, no small or static "live" text; red only
# for the pressed state and one thin accent; cards are the same glass as Radio / Apps / Trip computer) -------------
G_SYMBOL = 104                # symbol size in the card styles


def glass_box(size, box, pressed, radius=RADIUS, red_line=False):
    """a glass card (as the Apps cards): normal faint, pressed lighter with a white outline"""
    w, h = size
    f = 4
    im = Image.new('RGBA', (w * f, h * f), (0, 0, 0, 0))
    x0, y0, x1, y1 = (v * f for v in box)
    ImageDraw.Draw(im).rounded_rectangle(
        (x0, y0, x1 - 1, y1 - 1), radius=radius * f,
        fill=GLASS + ((GLASS_PRESSED_ALPHA if pressed else GLASS_CARD_ALPHA),),
        outline=GLASS_PRESSED_LINE if pressed else (GLASS + (GLASS_LINE_ALPHA,)), width=(2 if pressed else 1) * f)
    return im.resize((w, h), Image.LANCZOS)


def card_glass(size, meta, pressed):
    """plain glass tile, large symbol, centred label; pressed: lighter glass + short red line"""
    w, h = size
    im = glass_box(size, (0, CARD_TOP, w, CARD_BOTTOM), pressed)
    sym = material(meta['symbol'], SYMBOL_COLOUR, G_SYMBOL)
    im.alpha_composite(sym, ((w - sym.width) // 2, 170 - sym.height // 2))
    if pressed:
        ImageDraw.Draw(im).rounded_rectangle((w // 2 - 28, 352, w // 2 + 28, 355), radius=2, fill=LINE_RED + (255,))
    return im


def card_tile(size, meta, pressed):
    """tile: symbol top left, label bottom left after a thin red bar (the one accent)"""
    w, h = size
    im = glass_box(size, (0, CARD_TOP, w, CARD_BOTTOM), pressed)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 88)
    im.alpha_composite(sym, (36, CARD_TOP + 36))
    ImageDraw.Draw(im).rounded_rectangle((36, 318, 39, 350), radius=1, fill=LINE_RED + (255 if pressed else 200,))
    return im


def card_disc(size, meta, pressed):
    """the symbol on a dark round pedestal with a thin glass ring, a short red arc on top"""
    w, h = size
    im = glass_box(size, (0, CARD_TOP, w, CARD_BOTTOM), pressed)
    f = 4
    ov = Image.new('RGBA', (w * f, h * f), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy, r = w // 2 * f, 172 * f, 84 * f
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(6, 7, 9, 150), outline=GLASS + (60,), width=f)
    d.arc((cx - r, cy - r, cx + r, cy + r), start=240, end=300, fill=LINE_RED + (255 if pressed else 190,),
          width=(3 if pressed else 2) * f)
    im.alpha_composite(ov.resize((w, h), Image.LANCZOS))
    sym = material(meta['symbol'], SYMBOL_COLOUR, 88)
    im.alpha_composite(sym, ((w - sym.width) // 2, 172 - sym.height // 2))
    return im


def card_float(size, meta, pressed, first=False):
    """no card at rest, symbol and label float on the wallpaper, hairlines between the slots;
    pressed: the glass card appears"""
    w, h = size
    im = glass_box(size, (0, CARD_TOP, w, CARD_BOTTOM), True) if pressed else Image.new('RGBA', size, (0, 0, 0, 0))
    if not pressed and not first:            # hairline on the left, between this slot and the previous one
        d = ImageDraw.Draw(im)
        for y in range(CARD_TOP + 70, CARD_BOTTOM - 70):
            t = (y - (CARD_TOP + 70)) / (CARD_BOTTOM - CARD_TOP - 140)
            d.point((0, y), fill=GLASS + (round(60 * math.sin(math.pi * t)),))
    sym = material(meta['symbol'], SYMBOL_COLOUR, G_SYMBOL)
    im.alpha_composite(sym, ((w - sym.width) // 2, 170 - sym.height // 2))
    return im



def pedestal(im, cx, cy, r, pressed, shape='circle', ring=True, fill_a=150):
    """the dark pedestal of 'disc' (round or squircle), thin glass ring, short red arc / line on top"""
    w, h = im.size
    f = 4
    ov = Image.new('RGBA', (w * f, h * f), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    box = (cx * f - r * f, cy * f - r * f, cx * f + r * f, cy * f + r * f)
    fill = GLASS + (GLASS_PRESSED_ALPHA,) if pressed else (6, 7, 9, fill_a)
    line = GLASS_PRESSED_LINE if pressed else GLASS + (60 if ring else 0,)
    red = LINE_RED + (255 if pressed else 190,)
    if shape == 'circle':
        d.ellipse(box, fill=fill, outline=line, width=f)
        d.arc(box, start=240, end=300, fill=red, width=(3 if pressed else 2) * f)
    else:
        d.rounded_rectangle(box, radius=round(r * 0.42) * f, fill=fill, outline=line, width=f)
        d.rounded_rectangle((cx * f - 22 * f, box[1] - 1 * f, cx * f + 22 * f, box[1] + 2 * f), radius=f, fill=red)
    im.alpha_composite(ov.resize((w, h), Image.LANCZOS))


def hairline(im, first):
    if not first:                            # between this slot and the previous one, fading at both ends
        d = ImageDraw.Draw(im)
        for y in range(CARD_TOP + 130, CARD_BOTTOM - 20):
            t = (y - (CARD_TOP + 130)) / (CARD_BOTTOM - CARD_TOP - 150)
            d.point((0, y), fill=GLASS + (round(55 * math.sin(math.pi * t)),))


def card_orb(size, meta, pressed, first=False):
    """7 + 8: no card, the round pedestal floats on the wallpaper; pressed: the pedestal turns to glass"""
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    hairline(im, first)
    pedestal(im, size[0] // 2, 236, 70, pressed)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 72)
    im.alpha_composite(sym, ((size[0] - sym.width) // 2, 236 - sym.height // 2))
    return im


def card_squircle(size, meta, pressed, first=False):
    """as orb, with a rounded-square pedestal and the red line above it"""
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    hairline(im, first)
    pedestal(im, size[0] // 2, 236, 64, pressed, shape='squircle')
    sym = material(meta['symbol'], SYMBOL_COLOUR, 68)
    im.alpha_composite(sym, ((size[0] - sym.width) // 2, 236 - sym.height // 2))
    return im


def card_compact(size, meta, pressed):
    """7, smaller: a compact glass card (236 x 296) with the round pedestal, centred in the column"""
    w, h = size
    im = glass_box(size, ((w - 236) // 2, 96, (w + 236) // 2, 392), pressed, radius=22)
    pedestal(im, w // 2, 214, 58, False)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 60)
    im.alpha_composite(sym, ((w - sym.width) // 2, 214 - sym.height // 2))
    return im


def card_ring(size, meta, pressed, first=False):
    """8, lighter: only a thin ring (no dark fill) with the red arc, the symbol inside; pressed: glass disc"""
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    hairline(im, first)
    pedestal(im, size[0] // 2, 236, 66, pressed, fill_a=0)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 64)
    im.alpha_composite(sym, ((size[0] - sym.width) // 2, 236 - sym.height // 2))
    return im



# --- layouts: the six Home buttons placed freely on ONE page (no swiping: the page-2 decorations move to page 1,
# so the window has nothing beyond x 1024); every button its own size; all above y 468 (the climate strip) --------
# button order: CarPlay, Radio, Auto, BT, Apps, Setup; their images (normal, pressed[, active]) as in Main.data
BUTTON_IMAGES = [(0, 1), (2, 3), (4, 5), (6, 7, 8), (9, 10), (11, 12)]
ROW_ICONS = 'chevron_right'


def tile_h(size, meta, pressed):
    """a wide tile: symbol on the left, the label (firmware text) right of it"""
    w, h = size
    im = glass_box(size, (0, 0, w, h), pressed, radius=18)
    if pressed:
        ImageDraw.Draw(im).rounded_rectangle((0, 18, 3, h - 18), radius=1, fill=LINE_RED + (255,))
    sym = material(meta['symbol'], SYMBOL_COLOUR, 52)
    im.alpha_composite(sym, (28, (h - sym.height) // 2))
    return im


def tile_v(size, meta, pressed, sym_px=64, sym_cy=None):
    """a tile: ring with the symbol, label below"""
    w, h = size
    im = glass_box(size, (0, 0, w, h), pressed, radius=20)
    cy = sym_cy or h // 2 - 22
    pedestal(im, w // 2, cy, round(sym_px * 0.95), pressed, fill_a=0)
    sym = material(meta['symbol'], SYMBOL_COLOUR, sym_px)
    im.alpha_composite(sym, ((w - sym.width) // 2, cy - sym.height // 2))
    return im


def dock_item(size, meta, pressed):
    """no tile: a ring with the symbol; pressed: glass ring"""
    w, h = size
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    pedestal(im, w // 2, 52, 46, pressed, fill_a=0)
    sym = material(meta['symbol'], SYMBOL_COLOUR, 44)
    im.alpha_composite(sym, ((w - sym.width) // 2, 52 - sym.height // 2))
    return im


def list_row(size, meta, pressed):
    """a list row: symbol, label, chevron; a hairline under it; pressed: glass row with the red bar"""
    w, h = size
    im = glass_box(size, (0, 2, w, h - 2), True, radius=12) if pressed else Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if pressed:
        d.rounded_rectangle((0, 14, 3, h - 14), radius=1, fill=LINE_RED + (255,))
    else:
        d.line([(16, h - 1), (w - 16, h - 1)], fill=GLASS + (40,))
    sym = material(meta['symbol'], SYMBOL_COLOUR, 36)
    im.alpha_composite(sym, (24, (h - sym.height) // 2))
    chev = material(ROW_ICONS, DIM, 30)
    im.alpha_composite(chev, (w - 24 - chev.width, (h - chev.height) // 2))
    return im


def layout_grid():
    """2 x 3 tiles, all six on one page"""
    out = []
    for i in range(6):
        r, c = divmod(i, 3)
        x, y, w, h = 24 + c * 334, 90 + r * 222, 310, 206
        out.append(dict(rect=(x, y, w, h), label=(0, h - 64, w, 44), align=ALIGN_CENTRE,
                        draw=lambda sz, m, p: tile_v(sz, m, p, 56, 76)))
    return out


def layout_dock():
    """one row of six rings in the lower middle, the wallpaper free above"""
    out = []
    for i in range(6):
        x, y, w, h = 12 + i * 167, 286, 167, 160
        out.append(dict(rect=(x, y, w, h), label=(0, 108, w, 44), align=ALIGN_CENTRE, draw=dock_item))
    return out


def layout_hero():
    """the main function (Android Auto) as one large tile on the left, the other five as wide tiles on the right"""
    big = dict(rect=(24, 90, 452, 376), label=(0, 290, 452, 44), align=ALIGN_CENTRE,
               draw=lambda sz, m, p: tile_v(sz, m, p, 96, 160))
    small = []
    for j in range(5):
        x, y, w, h = 500, 90 + j * 77, 500, 68
        small.append(dict(rect=(x, y, w, h), label=(96, (h - 44) // 2, w - 120, 44), align=ALIGN_LEFT, draw=tile_h))
    # order CarPlay, Radio, Auto(big), BT, Apps, Setup
    return [small[0], small[1], big, small[2], small[3], small[4]]


def layout_list():
    """a list of the six functions on the right half, the left half free for the wallpaper"""
    out = []
    for i in range(6):
        x, y, w, h = 500, 84 + i * 64, 500, 64
        out.append(dict(rect=(x, y, w, h), label=(80, (h - 44) // 2, w - 140, 44), align=ALIGN_LEFT, draw=list_row))
    return out


LAYOUTS = {'grid': layout_grid, 'dock': layout_dock, 'hero': layout_hero, 'list': layout_list}



STYLE_CONFIG = {
    'split':   (card_split,   (0, 296, CARD_W, 40), ALIGN_CENTRE, 32),
    'deck':    (card_deck,   (38, 36, CARD_W - 50, 40), ALIGN_LEFT, 30),
    'capsule': (card_capsule,  (0, 298, CARD_W, 40), ALIGN_CENTRE, 30),
    'dial':    (card_dial, (0, 282, CARD_W, 40), ALIGN_CENTRE, 32),
    'glass':  (card_glass,  (0, 292, CARD_W, 44), ALIGN_CENTRE, 32),
    'tile':   (card_tile,   (52, 312, CARD_W - 70, 44), ALIGN_LEFT, 32),
    'disc':   (card_disc,   (0, 292, CARD_W, 44), ALIGN_CENTRE, 32),
    'float':  (card_float,  (0, 292, CARD_W, 44), ALIGN_CENTRE, 32),
    'orb':    (card_orb,    (0, 328, CARD_W, 44), ALIGN_CENTRE, 32),
    'squircle': (card_squircle, (0, 328, CARD_W, 44), ALIGN_CENTRE, 32),
    'compact': (card_compact, (0, 296, CARD_W, 44), ALIGN_CENTRE, 32),
    'ring':   (card_ring,   (0, 328, CARD_W, 44), ALIGN_CENTRE, 32),
}
NO_DOCK = {'grid', 'dock', 'hero', 'list', 'glass', 'tile', 'disc', 'float', 'orb', 'squircle', 'compact', 'ring'}    # no page-dot capsule: the firmware draws no dots in it


def card(size, k_idx, pressed):
    fn = STYLE_CONFIG[HOME_STYLE][0]
    if fn in (card_float, card_orb, card_squircle, card_ring):
        return fn(size, CARD_INFO[k_idx], pressed, first=k_idx in (0, 1, 6, 7, 8))   # first slot of a page
    return fn(size, CARD_INFO[k_idx], pressed)


def page_dock_pill(size):
    """Image 15 (1024x94 at screen y=506..600): subtle frosted pill around the firmware's two page indicator dots."""
    w, h = size
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((476, 41, 548, 69), radius=14,
                        fill=(12, 18, 22, 110), outline=GLASS + (42,), width=1)
    return im


def app_card(size, symbol, pressed):
    w, h = size
    f = 4
    im = Image.new('RGBA', (w * f, h * f), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle(
        (APP_INSET_X * f, APP_TOP * f, (w - APP_INSET_X) * f - 1, APP_BOTTOM * f - 1), radius=APP_RADIUS * f,
        fill=GLASS + ((GLASS_PRESSED_ALPHA if pressed else GLASS_CARD_ALPHA),),
        outline=GLASS_PRESSED_LINE if pressed else (GLASS + (GLASS_LINE_ALPHA,)), width=(2 if pressed else 1) * f)
    im = im.resize((w, h), Image.LANCZOS)
    sym = material(symbol, SYMBOL_COLOUR, APP_SYMBOL_PX)
    im.alpha_composite(sym, ((w - sym.width) // 2, APP_SYMBOL_CY - sym.height // 2))
    return im


def apps(src, out):
    u = UiData(open(src, 'rb').read())
    pressed_of = {}
    for k, symbol in APPS.items():
        size = (APP_W, struct.unpack_from('<II', u.images[k], 4)[1])
        u.images[k] = image_blob(app_card(size, symbol, False))
        pressed_of[k] = len(u.images)
        u.images.append(image_blob(app_card(size, symbol, True)))
    for k in APPS_REMOVE:
        u.images[k] = image_blob(Image.new('RGBA', struct.unpack_from('<II', u.images[k], 4), (0, 0, 0, 0)))
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    for i, rel in enumerate(rel for t, rel in w.children(base) if t == 1):   # in order; all on page 1
        row, col = divmod(i, 4)
        struct.pack_into('<iiI', raw, rel + 0xd4, APP_COLS[col], APP_ROWS[row], APP_W)
        struct.pack_into('<iiII', raw, rel + APP_LABEL, 0, 150, APP_W, 30)
        normal = struct.unpack_from('<i', raw, rel + 0xe4)[0]
        struct.pack_into('<ii', raw, rel + 0xe8, pressed_of[normal], pressed_of[normal])
        col_at = raw.find(APP_TEXT_STOCK, rel, rel + struct.unpack_from('<I', raw, rel)[0])
        assert col_at > 0, 'app button text colours not found'
        struct.pack_into('<III', raw, col_at, bgr(TEXT), bgr(TEXT), bgr(TEXT))
    u.windows[0] = (Window(bytes(raw), base), base)
    open(out, 'wb').write(u.build())


def picker_frames(src, out):
    """Setup > WallPaper: the thumbnail frames (1 normal: glass, 2 chosen: the accent red) instead of grey / gold"""
    u = UiData(open(src, 'rb').read())
    for k, (rgba_col, width) in {1: (GLASS + (GLASS_LINE_ALPHA,), 1), 2: (LINE_RED + (255,), 2)}.items():
        w, h = struct.unpack_from('<II', u.images[k], 4)
        f = 4
        im = Image.new('RGBA', (w * f, h * f), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, w * f - 1, h * f - 1), radius=10 * f, outline=rgba_col,
                                             width=width * f)
        u.images[k] = image_blob(im.resize((w, h), Image.LANCZOS))
    open(out, 'wb').write(u.build())


def main(src, out, wall_dir=None):
    data = os.path.dirname(src)
    picker_frames(os.path.join(data, 'SetupWallPaper.data'), os.path.join(os.path.dirname(out), 'SetupWallPaper.data'))
    apps(os.path.join(data, 'MainApp.data'), os.path.join(os.path.dirname(out), 'MainApp.data'))
    if wall_dir:
        wallpapers.generate(wall_dir, wallpapers.COMBINED)
    u = UiData(open(src, 'rb').read())
    if HOME_STYLE in LAYOUTS:
        return main_layout(u, out)
    for k in CARD_INFO:
        h = struct.unpack_from('<II', u.images[k], 4)[1]
        u.images[k] = image_blob_argb(card((CARD_W, h), k, k in PRESSED_IMAGES))
    for k in REMOVE:
        size = struct.unpack_from('<II', u.images[k], 4)
        u.images[k] = image_blob_argb(Image.new('RGBA', size, (0, 0, 0, 0)))
    # Image 15: bottom page-dot frosted capsule
    size15 = struct.unpack_from('<II', u.images[15], 4)
    u.images[15] = image_blob_argb(Image.new('RGBA', size15, (0, 0, 0, 0)) if HOME_STYLE in NO_DOCK
                                   else page_dock_pill(size15))

    _, (tx, ty, tw, th), align, font_px = STYLE_CONFIG[HOME_STYLE]
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    buttons = [rel for t, rel in w.children(base) if t == 1]
    for i, rel in enumerate(buttons):
        page, slot = divmod(i, 3)
        struct.pack_into('<i', raw, rel + 0xd4, page * 1024 + SLOTS_X[slot])
        struct.pack_into('<I', raw, rel + 0xdc, CARD_W)
        struct.pack_into('<iiII', raw, rel + BTN_TEXT + STR_RECT, tx, ty, tw, th)
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_FONT, font_px)
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_ALIGN, align)
        struct.pack_into('<II', raw, rel + BTN_TEXT + STR_COL, bgr(TEXT), bgr(TEXT))
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_COL + 8, bgr(TEXT))
    u.windows[0] = (Window(bytes(raw), base), base)
    symbols(u, {k: SYSTEM_BAR[v] for k, v in HOME_BAR.items()}, px=BAR_PX)
    header(u, 17)
    add_belt(u, os.path.join(os.path.dirname(__file__), '../climabar/assets/belt.png'), label='Main')
    open(out, 'wb').write(u.build())
    print(f'{out}: restyled ({HOME_STYLE})')


def main_layout(u, out, font_px=32):
    """HOME_STYLE in LAYOUTS: the six buttons on one page, each drawn at its own size"""
    lay = LAYOUTS[HOME_STYLE]()
    for k in REMOVE | {15}:
        u.images[k] = image_blob_argb(Image.new('RGBA', struct.unpack_from('<II', u.images[k], 4), (0, 0, 0, 0)))
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    for t, rel in w.children(base):             # the page-2 decorations (transparent) onto page 1: one page only
        x = struct.unpack_from('<i', raw, rel + 0xd4)[0]
        if t == 4 and x >= 1023:
            struct.pack_into('<i', raw, rel + 0xd4, x - 1024 if x >= 1024 else 0)
    buttons = [rel for t, rel in w.children(base) if t == 1]
    for i, rel in enumerate(buttons):
        L = lay[i]
        x, y, bw, bh = L['rect']
        for k in BUTTON_IMAGES[i]:
            u.images[k] = image_blob_argb(L['draw']((bw, bh), CARD_INFO[k], k in PRESSED_IMAGES))
        struct.pack_into('<iiII', raw, rel + 0xd4, x, y, bw, bh)
        struct.pack_into('<iiII', raw, rel + BTN_TEXT + STR_RECT, *L['label'])
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_FONT, font_px)
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_ALIGN, L['align'])
        struct.pack_into('<II', raw, rel + BTN_TEXT + STR_COL, bgr(TEXT), bgr(TEXT))
        struct.pack_into('<I', raw, rel + BTN_TEXT + STR_COL + 8, bgr(TEXT))
    u.windows[0] = (Window(bytes(raw), base), base)
    symbols(u, {k: SYSTEM_BAR[v] for k, v in HOME_BAR.items()}, px=BAR_PX)
    header(u, 17)
    add_belt(u, os.path.join(os.path.dirname(__file__), '../climabar/assets/belt.png'), label='Main')
    open(out, 'wb').write(u.build())
    print(f'{out}: restyled ({HOME_STYLE}, one page)')


if __name__ == '__main__':
    main(*sys.argv[1:4])
