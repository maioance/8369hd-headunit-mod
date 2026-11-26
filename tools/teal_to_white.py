"""Teal accents -> white, in place: the volume popup (VolumeBar.data), the climate popup (AirCondition.data) and the
climate strip's art (climabar/assets/*.png, built into climabar.mod).

A teal pixel (blue and green well above red) becomes theme.TEXT at the same brightness (its strongest channel against
the accent's), alpha kept: bright teal -> white, dark teal shades -> grey, so outlines and soft edges stay. Other
colours (the orange seat heating, greys, whites) are left alone.

usage: teal_to_white.py <file.data | file.png> ...
"""
import os
import sys
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
sys.path.insert(0, os.path.dirname(__file__))
from uidata import UiData                    # noqa: E402
from extract_images import decode            # noqa: E402
from build_volume_bar import image_blob      # noqa: E402
from theme import TEXT                       # noqa: E402

ACCENT_LEVEL = 200                            # the teal accent's strongest channel (53, 200, 200)


def is_teal(r, g, b):
    return b > r + 25 and g > r + 20


def recolour(im):
    """the image with its teal pixels white; None when it has none"""
    im = im.convert('RGBA')
    px = im.load()
    changed = False
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and is_teal(r, g, b):
                f = min(1.0, max(g, b) / ACCENT_LEVEL)
                px[x, y] = tuple(round(c * f) for c in TEXT) + (a,)
                changed = True
    return im if changed else None


def main(paths):
    for p in paths:
        if p.endswith('.png'):
            im = recolour(Image.open(p))
            if im:
                im.save(p)
                print(f'{p}: white')
            continue
        u = UiData(open(p, 'rb').read())
        done = []
        for k, blob in enumerate(u.images):
            im = recolour(decode(blob))
            if im:
                u.images[k] = image_blob(im)
                done.append(k)
        if done:
            open(p, 'wb').write(u.build())
        print(f'{p}: images {done}')


if __name__ == '__main__':
    main(sys.argv[1:])
