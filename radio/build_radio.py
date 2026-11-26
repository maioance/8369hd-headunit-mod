"""Flat restyle of the radio screen (apps/Data/RadioRds.data), in the style of the climate strip.

Redraws the artwork at the stock sizes (so touch areas stay the same) and rearranges the centre:
station name (RDS PS) on top as the title, a smaller flat frequency below it, band / unit / PTY in grey.
Colours, icons and positions are at the top; tools/build_overlay.sh rebuilds everything.

usage: build_radio.py <RadioRds.data> <out RadioRds.data> <Material Symbols cache dir>
"""
import os
import struct
import subprocess
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
from uidata import UiData, Window, U, I, rec_name   # noqa: E402
from build_volume_bar import image_blob              # noqa: E402

# --- colours (RGB) -----------------------------------------------------------------------------
# tools/theme.py: BG screen, CARD preset buttons, OFF disabled, DIM secondary text; active / pressed: white (ON),
# selected: the red marker (LINE_RED), as the selected preset
from theme import BG, CARD, CARD_LINE, OFF, TEXT, DIM   # noqa: E402
ON = TEXT
from theme import GLASS, GLASS_PANEL_ALPHA, GLASS_CARD_ALPHA, GLASS_LINE_ALPHA                  # noqa: E402
from theme import GLASS_PRESSED_ALPHA, GLASS_PRESSED_LINE    # noqa: E402  selected / pressed: as on Home
from theme import LINE_RED                                     # noqa: E402
PRESET_RED_ALPHA = 40                # the selected preset's red tint
FONT = '/usr/share/fonts/google-noto/NotoSans-Regular.ttf'
FONT_SEMI = '/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf'

# --- bottom bar: Material Symbols per button (image indices: normal, pressed) -----------------
ICON_BUTTONS = {             # label under the icon is drawn by the firmware
    (46, 47): 'radio',       # Band
    (44, 45): 'search',      # Scan
    (38, 39): 'playlist_play',  # Introduce (plays a few seconds of each station)
    (40, 41): 'location_on',    # Local (strong stations only)
    (42, 43): 'equalizer',   # Sound
}
TEXT_BUTTONS = {             # (normal, on, disabled): text
    (51, 52, 53): 'AF', (48, 49, 50): 'TA', (54, 55, 56): 'PTY', (57, 58, 59): 'RDS',
}
ICON_PX = 34

# --- centre layout (window 0 coordinates; the window starts at screen y 69) --------------------
FREQ_DIGIT_H = 44            # big frequency digits (stock: 73, metallic)
# climabar.mod draws the live RDS PS (or the frequency) where the big frequency is, in the same font and size
# (layout.json "radio_name"): the stock frequency digits, "MHz" and the small PS title are moved out of sight.
# False: stock layout (PS title above the frequency).
MODULE_STATION = True
# The preset buttons keep their stock text: climabar.mod only changes what it says (the learned station name,
# init.axf patch preset_names), the firmware draws it. True = hide it (only for a module that draws the names itself).
MODULE_PRESETS = False
PS_RECT = (112, 126, 800, 44)        # stock station name (when MODULE_STATION is False), centred
FREQ_RECT = (362, 184, 300, 50)      # frequency digits, centred (screen y 253)
BAND_RECT = (240, 194, 110, 36)      # FM-1 / AM-1, right-aligned towards the frequency
UNIT_RECT = (674, 194, 100, 36)      # MHz / KHz
PTY_RECT = (362, 240, 300, 30)       # programme type, centred

STATUS_Y = 86                        # stereo / DX / search icons: up on the row with 87.50 ... 108.00
LOC_Y = 84                           # the "DX" text on that row too
# TA / TP (traffic announcements on / station sends traffic news): stock place just above the frequency, 5 px
# from the big digits; moved to the status row, after DX
TA_RECT = (790, LOC_Y, 50, 30)       # clear of the DX rect (684..784)
TP_RECT = (840, LOC_Y, 50, 30)       # clear of 108.00 (908..)

# frequency ruler (window 1): drawn where the firmware puts the cursor (measured: centre x 63 at 87.5 MHz,
# 523 at 98.0 MHz; the stock artwork was 45 px/MHz and drifted up to ~10 px off the cursor).
# A short tick every 0.2 MHz, a long tick every 1 MHz, a label every 2 MHz
RULER_X0, RULER_PX_PER_MHZ, RULER_F0 = 63, 460 / 10.5, 87.5

ALIGN_CENTRE = 37            # text record +0x1c8: 36 left, 37 centre, 38 right
STR_RECT, STR_COL = 0x19c, 0x1b0     # text record: rect, colours (normal, focus, selected, disabled; BGR)
BTN_TEXT = 0x110                     # text record inside a button record


def bgr(c):
    return c[2] << 16 | c[1] << 8 | c[0]


def rgba(c, a=255):
    return c + (a,)


def text_img(size, text, font, colour, align='center', y_frac=0.5):
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = {'left': 0, 'center': size[0] / 2, 'right': size[0]}[align]
    d.text((x, size[1] * y_frac), text, font=font, fill=rgba(colour), anchor={'left': 'lm', 'center': 'mm', 'right': 'rm'}[align])
    return im


def symbol(cache, name, colour, px):
    path = os.path.join(cache, name + '.svg')
    if not os.path.exists(path):
        urllib.request.urlretrieve(
            f'https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsrounded/{name}/default/48px.svg', path)
    tinted, out = path + '.tmp.svg', path + '.tmp.png'
    open(tinted, 'w').write(open(path).read().replace('<svg ', f'<svg fill="#{colour[0]:02x}{colour[1]:02x}{colour[2]:02x}" ', 1))
    subprocess.run(['magick', '-background', 'none', '-density', '384', tinted, '-resize', f'{px}x{px}', 'PNG32:' + out], check=True)
    im = Image.open(out).convert('RGBA')
    os.remove(tinted), os.remove(out)
    return im


def size_of(u, k):
    return U(u.images[k], 4), U(u.images[k], 8)


def flat(size, colour=BG, top_line=None, bottom_line=None, alpha=255):
    im = Image.new('RGBA', size, rgba(colour, alpha))
    d = ImageDraw.Draw(im)
    if top_line:
        d.line([(0, 0), (size[0], 0)], fill=rgba(top_line))
    if bottom_line:
        d.line([(0, size[1] - 1), (size[0], size[1] - 1)], fill=rgba(bottom_line))
    return im


def preset(size, label, on):
    k = 4
    w, h = size
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = (4 * k, 4 * k, (w - 4) * k, (h - 4) * k)
    if on:
        # selected: red outline and a faint red tint (LINE_RED, the status bar line's red)
        d.rounded_rectangle(box, radius=10 * k, fill=rgba(LINE_RED, PRESET_RED_ALPHA), outline=rgba(LINE_RED),
                            width=2 * k)
    else:
        d.rounded_rectangle(box, radius=10 * k, fill=rgba(GLASS, GLASS_CARD_ALPHA), outline=rgba(GLASS, GLASS_LINE_ALPHA), width=1 * k)
    im = im.resize(size, Image.LANCZOS)
    # memory number small in the top-left corner, like factory radios; the name sits in the middle
    ImageDraw.Draw(im).text((16, 10), label, font=ImageFont.truetype(FONT_SEMI, 17), fill=rgba(TEXT if on else DIM))
    return im


def pressed_glass(size):
    """a pressed / switched-on bottom bar button: lighter glass with a white outline, like the Home cards"""
    k = 4
    hl = Image.new('RGBA', (size[0] * k, size[1] * k), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle((8 * k, 6 * k, (size[0] - 8) * k, (size[1] - 6) * k), radius=12 * k,
                                         fill=rgba(GLASS, GLASS_PRESSED_ALPHA), outline=GLASS_PRESSED_LINE, width=2 * k)
    return hl.resize(size, Image.LANCZOS)


def icon_button(size, icon, pressed):
    im = pressed_glass(size) if pressed else Image.new('RGBA', size, (0, 0, 0, 0))
    im.alpha_composite(icon, ((size[0] - icon.width) // 2, 14))
    return im


def text_button(size, text, state):
    """AF / TA / PTY / RDS: switched on = a short bar under the name (white, like the rest of the selected states)"""
    colour = {'normal': TEXT, 'on': TEXT, 'off': OFF}[state]
    im = text_img(size, text, ImageFont.truetype(FONT_SEMI, 24), colour, y_frac=0.45)
    if state == 'on':
        ImageDraw.Draw(im).rounded_rectangle((size[0] // 2 - 18, size[1] * 0.45 + 18, size[0] // 2 + 18,
                                              size[1] * 0.45 + 21), radius=2, fill=rgba(TEXT))
    return im


def list_card(size):
    k = 4
    w, h = size
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=12 * k, fill=rgba(CARD),
                                         outline=rgba(CARD_LINE), width=k)
    return im.resize(size, Image.LANCZOS)


def list_item(size, selected):
    k = 4
    w, h = size
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if selected:
        d.rounded_rectangle((6 * k, 4 * k, (w - 6) * k, (h - 4) * k), radius=8 * k, fill=rgba(GLASS, GLASS_PRESSED_ALPHA))
        d.rounded_rectangle((6 * k, 14 * k, 10 * k, (h - 14) * k), radius=2 * k, fill=rgba(LINE_RED))
    else:
        d.line([(16 * k, h * k - k), ((w - 16) * k, h * k - k)], fill=rgba(CARD_LINE), width=k)
    return im.resize(size, Image.LANCZOS)


def ruler(size):
    w, h = size
    im = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(FONT, 16)
    for i in range(-1, 104):                           # 0.2 MHz steps from 87.3 to 108.1
        f = RULER_F0 + i * 0.2
        x = round(RULER_X0 + (f - RULER_F0) * RULER_PX_PER_MHZ - 0.5)
        if i % 5 == 0:
            d.line([(x, 14), (x, 38)], fill=rgba(DIM), width=2)
            if i % 10 == 0:
                d.text((x, 60), f'{f:.1f}', font=font, fill=rgba(DIM), anchor='mm')
        else:
            d.line([(x, 24), (x, 34)], fill=rgba(OFF), width=1)
    return im


def ruler_cursor(size):
    w, h = size
    k = 4
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w * k / 2
    d.rounded_rectangle((cx - 1.5 * k, 8 * k, cx + 1.5 * k, 46 * k), radius=1.5 * k, fill=rgba(LINE_RED))
    d.ellipse((cx - 5 * k, 21 * k, cx + 5 * k, 31 * k), fill=rgba(LINE_RED))
    return im.resize(size, Image.LANCZOS)


def build_images(u, cache):
    img = {}
    for k, d in ((0, 'chevron_left'), (2, 'chevron_right')):                 # tune arrows
        w, h = size_of(u, k)
        for kk, col in ((k, DIM), (k + 1, ON)):
            c = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            s = symbol(cache, d, col, 56)
            c.alpha_composite(s, ((w - s.width) // 2, (h - s.height) // 2))
            img[kk] = c
    font_band = ImageFont.truetype(FONT, 24)
    for k, t in zip(range(4, 9), ('AM-1', 'FM-3', 'FM-2', 'FM-1', 'AM-2')):  # band label, right-aligned
        img[k] = text_img(size_of(u, k), t, font_band, DIM, 'right')
    img[9] = text_img(size_of(u, 9), 'KHz', font_band, DIM, 'left')
    img[10] = text_img(size_of(u, 10), 'MHz', font_band, DIM, 'left')
    t17 = Image.new('RGBA', size_of(u, 17), (0, 0, 0, 0))                    # band slider track
    ImageDraw.Draw(t17).rectangle((0, 4, size_of(u, 17)[0], 5), fill=rgba(CARD_LINE))
    img[17] = t17
    t18 = Image.new('RGBA', size_of(u, 18), (0, 0, 0, 0))                    # band slider progress
    ImageDraw.Draw(t18).rectangle((0, 4, size_of(u, 18)[0], 5), fill=rgba(LINE_RED))
    img[18] = t18
    img[21] = flat(size_of(u, 21), GLASS, alpha=GLASS_PANEL_ALPHA)            # ruler background: glass, as the bottom bar
    ImageDraw.Draw(img[21]).line([(0, img[21].height - 1), (img[21].width, img[21].height - 1)],
                                 fill=rgba(GLASS, GLASS_LINE_ALPHA))
    img[22] = ruler(size_of(u, 22))
    img[23] = ruler_cursor(size_of(u, 23))
    img[60] = list_card(size_of(u, 60))                                       # PTY / station list
    img[61] = list_item(size_of(u, 61), False)
    img[62] = list_item(size_of(u, 62), True)
    img[24] = flat(size_of(u, 24), alpha=0)                                   # presets background: none
    img[37] = flat(size_of(u, 37), GLASS, alpha=GLASS_PANEL_ALPHA)            # bottom bar background: glass
    ImageDraw.Draw(img[37]).line([(0, 0), (img[37].width, 0)], fill=rgba(GLASS, GLASS_LINE_ALPHA))
    for n in range(6):                                                        # presets P1..P6
        img[25 + 2 * n] = preset(size_of(u, 25 + 2 * n), f'{n + 1}', False)
        img[26 + 2 * n] = preset(size_of(u, 26 + 2 * n), f'{n + 1}', True)
    for (kn, kp), name in ICON_BUTTONS.items():
        img[kn] = icon_button(size_of(u, kn), symbol(cache, name, TEXT, ICON_PX), False)
        img[kp] = icon_button(size_of(u, kp), symbol(cache, name, TEXT, ICON_PX), True)
    for (kn, ko, kd), text in TEXT_BUTTONS.items():
        img[kn] = text_button(size_of(u, kn), text, 'normal')
        img[ko] = text_button(size_of(u, ko), text, 'on')
        img[kd] = text_button(size_of(u, kd), text, 'off')
    font_digit = ImageFont.truetype(FONT, round(FREQ_DIGIT_H / 0.72))       # frequency digits
    asc = font_digit.getbbox('0')[1]
    for k, ch in zip(range(63, 74), '0.98765432 1'.replace(' ', '')):
        w = round(font_digit.getlength(ch)) + 2
        g = Image.new('RGBA', (w, FREQ_DIGIT_H), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((1, -asc), ch, font=font_digit, fill=rgba(TEXT))
        img[k] = g
    for k, im in img.items():
        u.images[k] = image_blob(im)


def set_text(raw, rel, rect=None, align=None, colours=None):
    if rect:
        struct.pack_into('<iiII', raw, rel + STR_RECT, *rect)
    if align is not None:
        struct.pack_into('<I', raw, rel + 0x1c8, align)
    if colours:
        struct.pack_into('<IIII', raw, rel + STR_COL, *(bgr(c) for c in colours))


def relayout(u):
    w, base = u.windows[0]
    raw = bytearray(w.raw)
    for t, rel in w.children(base):
        n = rec_name(raw, rel)
        if n == 'ViewShowStrRdsPs':
            set_text(raw, rel, (2000, 0, 10, 10) if MODULE_STATION else PS_RECT, ALIGN_CENTRE, (TEXT, TEXT, ON, OFF))
        elif n == 'ViewShowStrPtyType':
            set_text(raw, rel, PTY_RECT, ALIGN_CENTRE, (DIM, DIM, ON, OFF))
        elif n == 'ViewShowStrMainFreqNum':
            set_text(raw, rel, (2000, 0, 10, 10) if MODULE_STATION else FREQ_RECT, ALIGN_CENTRE)
        elif n in ('ViewShowStrMinFreqNum', 'ViewShowStrMaxFreqNum', 'ViewShowStrLoc'):
            set_text(raw, rel, colours=(DIM, DIM, ON, OFF))
            if n == 'ViewShowStrLoc':
                struct.pack_into('<i', raw, rel + STR_RECT + 4, LOC_Y)
        elif n in ('ViewShowStrTaInd', 'ViewShowStrTpInd'):
            set_text(raw, rel, TA_RECT if n == 'ViewShowStrTaInd' else TP_RECT, colours=(DIM, DIM, DIM, OFF))
        elif n in ('ViewShowImageSt', 'ViewShowButtonStEn', 'ViewShowImagePS', 'ViewShowImageAS'):
            struct.pack_into('<i', raw, rel + 0xd8, STATUS_Y)
        elif n == 'ViewShowImageBand':
            struct.pack_into('<iiII', raw, rel + 0xd4, *BAND_RECT)
        elif n == 'ViewShowImageFreqUnit':
            struct.pack_into('<iiII', raw, rel + 0xd4, *((2000, 0, 10, 10) if MODULE_STATION else UNIT_RECT))
    u.windows[0] = (Window(bytes(raw), base), base)
    # every remaining text style with the stock colours (white / green focus / red selected / grey) -
    # button labels, preset frequencies, list items - gets white, also when selected (stock: red)
    stock = struct.pack('<IIII', 0xffffff, 0x00ff00, 0x0000ff, 0x3c3c3c)
    ours = struct.pack('<IIII', bgr(TEXT), bgr(TEXT), bgr(TEXT), bgr(OFF))
    for wi in range(len(u.windows)):
        w, base = u.windows[wi]
        raw = bytes(w.raw).replace(stock, ours)
        if MODULE_PRESETS and wi == 2:              # preset buttons: move their frequency text out of sight
            raw = bytearray(raw)
            for t, rel in Window(bytes(raw), base).children(base):
                if t == 1 and rec_name(raw, rel).startswith('ViewShowButtonSubFreq'):
                    struct.pack_into('<i', raw, rel + BTN_TEXT + STR_RECT, 2000)
            raw = bytes(raw)
        u.windows[wi] = (Window(raw, base), base)


def main(src, out, cache):
    os.makedirs(cache, exist_ok=True)
    u = UiData(open(src, 'rb').read())
    build_images(u, cache)
    relayout(u)
    open(out, 'wb').write(u.build())
    print(f'{out}: {len(u.images)} images restyled layout')


if __name__ == '__main__':
    main(*sys.argv[1:4])
