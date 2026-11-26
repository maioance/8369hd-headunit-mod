"""Vehicle alerts artwork from the stock "Vehicle information" screen (apps/Data/CarComputer.data):
the car seen from above with one red overlay per open door / boot, and the seat-belt symbol.

  door_card.png               semi-transparent rounded card with the car, DOOR_SCALE of the stock size
  door_fl/fr/rl/rr/boot.png   the matching red overlay, cropped; door_offsets.json = its place on the card
  belt.png                    seat-belt warning symbol for the status bar

usage: import_vehicle_assets.py <CarComputer.data> <assets dir>
"""
import json
import os
import sys
from PIL import Image, ImageDraw

from extract_images import decode, UiData

DOOR_SCALE = 0.62
CARD_PAD = 14
CARD_BG = (10, 16, 18, 205)            # see-through, like the climate strip
BELT_PX = 30
BELT_COLOUR = (220, 226, 228)          # white-grey, like the climate symbols
OVERLAYS = {6: 'door_fl', 7: 'door_fr', 8: 'door_rl', 9: 'door_rr', 10: 'door_boot'}


def main(src, assets):
    u = UiData(open(src, 'rb').read())
    car = decode(u.images[4])
    cw, ch = round(car.width * DOOR_SCALE), round(car.height * DOOR_SCALE)
    w, h = cw + 2 * CARD_PAD, ch + 2 * CARD_PAD

    k = 4
    card = Image.new('RGBA', (w * k, h * k), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=16 * k, fill=CARD_BG)
    card = card.resize((w, h), Image.LANCZOS)
    card.alpha_composite(car.resize((cw, ch), Image.LANCZOS), (CARD_PAD, CARD_PAD))
    card.save(os.path.join(assets, 'door_card.png'))
    offsets = {}
    for idx, name in OVERLAYS.items():
        ov = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ov.alpha_composite(decode(u.images[idx]).resize((cw, ch), Image.LANCZOS), (CARD_PAD, CARD_PAD))
        box = ov.getbbox()
        ov.crop(box).save(os.path.join(assets, name + '.png'))
        offsets[name] = box[:2]
    json.dump(offsets, open(os.path.join(assets, 'door_offsets.json'), 'w'))

    # belt: the stock icon is a light glyph on a dark disc; keep the glyph only and recolour it
    src_belt = decode(u.images[2])
    px = src_belt.load()
    glyph = Image.new('RGBA', src_belt.size, (0, 0, 0, 0))
    gp = glyph.load()
    for y in range(src_belt.height):
        for x in range(src_belt.width):
            r, g, b, a = px[x, y]
            lum = max(r, g, b)
            if lum > 90:                                       # glyph pixels; the disc is dark
                gp[x, y] = BELT_COLOUR[:3] + (min(255, a * (lum - 90) // 110),)
    glyph = glyph.crop(glyph.getbbox())
    s = BELT_PX / max(glyph.size)
    glyph = glyph.resize((max(1, round(glyph.width * s)), max(1, round(glyph.height * s))), Image.LANCZOS)
    # one colour (the resize shifts it a little): stored as alpha only in climabar.mod (gen_assets.py)
    Image.merge('RGBA', Image.new('RGB', glyph.size, BELT_COLOUR[:3]).split() + (glyph.getchannel('A'),)).save(
        os.path.join(assets, 'belt.png'))
    print(f'vehicle assets -> {assets} (card {w}x{h})')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
