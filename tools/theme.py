"""The colours of all restyled screens (Home, Radio, Bluetooth, vehicle, Setup, climate strip, volume popup).

Design rules followed everywhere (docs/design.md):
- dark neutral backgrounds; the wallpaper shows through glass panels; text near-white on near-black;
- one accent, red (LINE_RED), used sparingly: states (selected / pressed marker, slider fill, the line under the
  status bar), never large areas - a big bright area at night dazzles;
- symbols white-grey (TEXT) when lit, dim grey (OFF) when off; warnings (open doors, seat belt) red, as on the
  instrument cluster.
"""

# screen background, cards, text
BG = (10, 16, 18)
CARD, CARD_LINE = (20, 27, 30), (35, 48, 47)   # opaque cards (pop-ups that must stay readable over anything)
TEXT = (220, 226, 228)                          # text, lit symbols
DIM = (138, 149, 153)                           # secondary text
OFF = (78, 88, 94)                              # symbols that are off
WARN = (240, 96, 64)                            # warnings
# ACCENT and PRESSED: the original teal accent, still used by a few stock-art recolourings; the drawn teal ends up
# white (tools/teal_to_white.py), so it does not appear on screen
ACCENT, PRESSED = (53, 200, 200), (16, 52, 54)

# the accent red (as on the car's factory head units: the line above the bottom bar, the active page dot): the line
# under the status bar, selected / pressed markers, slider fills
LINE_RED = (240, 74, 56)
# BT Music's placeholder cover: a gradient of that red, dark at the bottom right
COVER = (tuple(round(c * 0.5) for c in LINE_RED), tuple(round(c * 0.17) for c in LINE_RED))

# Glass: the wallpapers are nearly black, so a dark see-through panel would look just like an opaque one. Glass panels
# are a light tint at low opacity instead (frosted glass): the wallpaper's colours show through, a bit lighter.
GLASS = (200, 225, 228)        # the tint (cool white)
GLASS_PANEL_ALPHA = 14         # bars (radio bottom bar, frequency ruler)
GLASS_CARD_ALPHA = 26          # cards and buttons
GLASS_LINE_ALPHA = 46          # their outline
GLASS_PRESSED_ALPHA = 60       # a card while pressed: the glass a step lighter ...
GLASS_PRESSED_LINE = (255, 255, 255, 200)   # ... with a white outline


def hex_(c):
    return '#%02x%02x%02x' % c


def header_line(size):
    """the line under the status bar: a thin red line with a soft glow, brightest in the middle and fading towards
    the sides, like a strip of ambient light"""
    import math
    from PIL import Image
    w, h = size
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    px = im.load()
    mid = (h - 1) / 2
    for x in range(w):
        fade = math.exp(-((x - w / 2) / (w * 0.36)) ** 2)
        for y in range(h):
            d = abs(y - mid)
            a = 230 if d < 0.6 else 70 * math.exp(-d * d / 2.5)          # core row(s), then glow
            px[x, y] = LINE_RED + (round(a * fade),)
    return im
