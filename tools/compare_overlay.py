"""Compares two overlays (tools/build_overlay.sh outputs): which files differ and how.

.data screens are compared by content - window records byte for byte, images by their pixels (two encodings of the
same picture count as equal); every other file byte for byte. Hidden files (.*) are skipped, as tools/build_image.sh
does. Exit status 1 when anything differs.

usage: compare_overlay.py <overlay A> <overlay B>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../climabar/tools'))
from uidata import UiData                    # noqa: E402
from extract_images import decode            # noqa: E402


def files(root):
    out = set()
    for d, _, names in os.walk(root):
        for n in names:
            if not n.startswith('.'):
                out.add(os.path.relpath(os.path.join(d, n), root))
    return out


def data_diff(a, b):
    ua, ub = UiData(open(a, 'rb').read()), UiData(open(b, 'rb').read())
    if len(ua.images) != len(ub.images) or len(ua.windows) != len(ub.windows):
        return 'different number of images / windows'
    win = [i for i in range(len(ua.windows)) if ua.windows[i][0].raw != ub.windows[i][0].raw]
    img = [k for k in range(len(ua.images)) if ua.images[k] != ub.images[k]
           and decode(ua.images[k]).convert('RGBA').tobytes() != decode(ub.images[k]).convert('RGBA').tobytes()]
    return (f'windows {win} ' if win else '') + (f'images {img}' if img else '')


def main(a, b):
    fa, fb = files(a), files(b)
    bad = 0
    for f in sorted(fa | fb):
        if f not in fa or f not in fb:
            print(f'{f}: only in {a if f in fa else b}')
            bad += 1
            continue
        pa, pb = os.path.join(a, f), os.path.join(b, f)
        if open(pa, 'rb').read() == open(pb, 'rb').read():
            continue
        why = data_diff(pa, pb) if f.endswith('.data') else 'bytes differ'
        if why:
            print(f'{f}: {why}')
            bad += 1
    print(f'{len(fa | fb)} files, {bad} different')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
