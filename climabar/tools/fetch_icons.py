"""Material Symbols (Android Automotive climate icons, Apache 2.0) -> assets/*.png in the climabar colours.

SVGs are downloaded once into icons_src/ (with the licence) and rendered with ImageMagick. To use another
icon, change its name below (browse https://fonts.google.com/icons) and run: make icons && make

usage: fetch_icons.py <assets dir> <svg cache dir>
"""
import os
import subprocess
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFont

ON, OFF = '#dce2e4', '#4e585e'   # on: the text colour (white-grey), off: dim grey
URL = 'https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsrounded/{}/default/48px.svg'
LICENSE_URL = 'https://raw.githubusercontent.com/google/material-design-icons/master/LICENSE'

ICON_SCALE = 1.4                          # the strip's status icons and airflow, relative to the first design

# status icons: (asset name, symbol, canvas w x h) -> <name>_on.png / <name>_off.png
STATUS = []
# symbol + label, like the buttons on the Climatronic: (asset name, symbol, label, canvas w x h)
COMPOSITE = [
    ('ac', 'ac_unit', 'A/C', (70, 34)),
    ('auto', 'mode_fan', 'AUTO', (70, 34)),
    ('sync', 'sync', 'SYNC', (70, 34)),
    ('recirc', 'car_fan_recirculate_2', 'REC', (76, 34)),          # air intake: one of these three
    ('recirc_auto', 'car_fan_recirculate_2', 'REC A', (76, 34)),
    ('fresh', 'air', 'FRESH', (76, 34)),
    ('max_front', 'windshield_defrost_front', 'MAX', (70, 34)),
    ('rear_defrost', 'windshield_defrost_rear', 'REAR', (70, 34)),
]
COMPOSITE = [(n, sym, label, (round(w * ICON_SCALE), round(h * ICON_SCALE))) for n, sym, label, (w, h) in COMPOSITE]
COMPOSITE_ICON = round(24 * ICON_SCALE)   # symbol height inside a composite
FONT = '/usr/share/fonts/google-noto/NotoSans-SemiBold.ttf'
FONT_PX = round(15 * ICON_SCALE)

# airflow pictogram, one icon per combination of windshield / face / feet (lit)
AIRFLOW_SIZE = round(72 * ICON_SCALE)
AIRFLOW = {
    'airflow_none': ('car_fan_mid_left', OFF),
    'airflow_feet': ('car_fan_low_left', ON),
    'airflow_face': ('car_fan_mid_left', ON),
    'airflow_face_feet': ('car_fan_low_mid_left', ON),
    'airflow_ws': ('car_defrost_left', ON),
    'airflow_ws_feet': ('car_defrost_low_left', ON),
    'airflow_ws_face': ('car_defrost_mid_left', ON),
    'airflow_ws_face_feet': ('car_defrost_mid_low_left', ON),
}


def svg(cache, symbol):
    path = os.path.join(cache, symbol + '.svg')
    if not os.path.exists(path):
        urllib.request.urlretrieve(URL.format(symbol), path)
    return path


def render(src, colour, size, out):
    """tint the symbol, fit it into the canvas height and centre it horizontally"""
    w, h = size
    tinted = out + '.svg'
    with open(src) as f:
        open(tinted, 'w').write(f.read().replace('<svg ', f'<svg fill="{colour}" ', 1))
    subprocess.run(['magick', '-background', 'none', '-density', '384', tinted, '-resize', f'{h}x{h}',
                    '-gravity', 'center', '-extent', f'{w}x{h}', 'PNG32:' + out], check=True)
    os.remove(tinted)


def composite(src, label, colour, size, out):
    """symbol on the left, label on the right, centred as a group"""
    w, h = size
    render(src, colour, (COMPOSITE_ICON, COMPOSITE_ICON), out)
    sym = Image.open(out).convert('RGBA')
    font = ImageFont.truetype(FONT, FONT_PX)
    tw = ImageDraw.Draw(sym).textlength(label, font=font)
    gap = round(3 * ICON_SCALE)
    x = round((w - (COMPOSITE_ICON + gap + tw)) / 2)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    im.alpha_composite(sym, (x, (h - COMPOSITE_ICON) // 2))
    ImageDraw.Draw(im).text((x + COMPOSITE_ICON + gap, h / 2), label, font=font, fill=colour, anchor='lm')
    im.save(out)


# fan speed panel: thin white outline (stock shape), mode_fan_2 at both ends, 7 rising bars
PANEL = (484, 88)                          # design size (stock panel); scaled by PANEL_SCALE
PANEL_SCALE = 1.0
PANEL_LINE = (235, 240, 242, 230)
BAR_W = 11
BAR_H = [15, 17, 19, 21, 23, 26, 28]      # same heights as the stock bars (positions: layout.json fan_bars)
FAN_ICONS = [(96, 46, 22), (358, 38, 32)]  # (x, y, size) of the small / large fan symbol; 20 px from the bars


def fan_panel(cache, assets):
    k = 4
    w, h = PANEL
    im = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # one continuous line: sloped sides, rounded corners (quadratic Bezier), straight top; open at the bottom
    def bez(p0, p1, p2, n=24):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]
    top, lw = 10, 2
    pts = [(4, h), (40, 30)] + bez((40, 30), (52, top), (78, top))[1:] + [(w - 78, top)] \
        + bez((w - 78, top), (w - 52, top), (w - 40, 30))[1:] + [(w - 4, h)]
    d.line([(x * k, y * k) for x, y in pts], fill=PANEL_LINE, width=lw * k, joint='curve')
    im = im.resize(PANEL, Image.LANCZOS)
    for x, y, size in FAN_ICONS:
        tmp = os.path.join(assets, '.fan_tmp.png')
        render(svg(cache, 'mode_fan_2'), '#ebf0f2', (size, size), tmp)
        im.alpha_composite(Image.open(tmp).convert('RGBA'), (x, y))
        os.remove(tmp)
    sc = lambda v: max(1, round(v * PANEL_SCALE))
    im.resize((sc(w), sc(h)), Image.LANCZOS).save(os.path.join(assets, 'fan_panel.png'))
    for n, bh in enumerate(BAR_H, 1):
        bw, bh = sc(BAR_W), sc(bh)
        for state, colour in (('on', ON), ('off', OFF)):
            bar = Image.new('RGBA', (bw * k, bh * k), (0, 0, 0, 0))
            ImageDraw.Draw(bar).rounded_rectangle((0, 0, bw * k - 1, bh * k - 1), radius=3 * k, fill=colour)
            a = bar.resize((bw, bh), Image.LANCZOS).getchannel('A')
            bar = Image.new('RGBA', (bw, bh), colour)        # one colour (the resize shifts it a little): stored as
            bar.putalpha(a)                                  # alpha only in climabar.mod (gen_assets.py)
            bar.save(os.path.join(assets, f'fan_bar{n}_{state}.png'))


NOTE_PX = 36                               # music note on the "now playing" cover
# Home widgets (vehicle data from the CAN box): one symbol per chip, white-grey
WIDGET_ICONS = [('w_temp', 'device_thermostat'), ('w_fuel', 'local_gas_station'), ('w_battery', 'battery_full')]
WIDGET_ICON_PX = 30

# temperature in Noto Sans (same family as the labels): one image per glyph, all the same height
DIGIT_FONT = '/usr/share/fonts/google-noto/NotoSans-Regular.ttf'
DIGIT_H = 46                               # digit height
DIGIT_PAD = 3                              # transparent rows above and below (round glyphs overshoot)
TEMP_COLOUR = (220, 226, 228, 255)


def digits(assets):
    font = ImageFont.truetype(DIGIT_FONT, round(DIGIT_H / 0.72))   # Noto digit height is ~0.72 em
    asc = font.getbbox('0')[1]
    glyphs = {f'digit_{n}': str(n) for n in range(10)}
    glyphs.update({'dot': '.', 'celsius': '°C', 'temp_lo': 'LO', 'temp_hi': 'HI'})
    for name, text in glyphs.items():
        w = round(font.getlength(text)) + 1
        im = Image.new('RGBA', (w, DIGIT_H + 2 * DIGIT_PAD), (0, 0, 0, 0))   # round glyphs overshoot the digit height
        ImageDraw.Draw(im).text((0, DIGIT_PAD - asc), text, font=font, fill=TEMP_COLOUR)
        im.save(os.path.join(assets, name + '.png'))


def main(assets, cache):
    os.makedirs(assets, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    lic = os.path.join(cache, 'LICENSE')
    if not os.path.exists(lic):
        urllib.request.urlretrieve(LICENSE_URL, lic)
    for name, symbol, size in STATUS:
        for state, colour in (('on', ON), ('off', OFF)):
            render(svg(cache, symbol), colour, size, os.path.join(assets, f'{name}_{state}.png'))
    for name, symbol, label, size in COMPOSITE:
        for state, colour in (('on', ON), ('off', OFF)):
            composite(svg(cache, symbol), label, colour, size, os.path.join(assets, f'{name}_{state}.png'))
    fan_panel(cache, assets)
    digits(assets)
    # now playing card: note on the generated cover
    render(svg(cache, 'music_note'), '#ffffff', (NOTE_PX, NOTE_PX), os.path.join(assets, 'np_note.png'))
    for name, symbol in WIDGET_ICONS:
        render(svg(cache, symbol), '#dce2e4', (WIDGET_ICON_PX, WIDGET_ICON_PX), os.path.join(assets, name + '.png'))
    for name, (symbol, colour) in AIRFLOW.items():
        render(svg(cache, symbol), colour, (AIRFLOW_SIZE, AIRFLOW_SIZE), os.path.join(assets, name + '.png'))
    print(f'Material Symbols -> {assets}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
