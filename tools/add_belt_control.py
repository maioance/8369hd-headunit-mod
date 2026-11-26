"""Seat-belt symbol as a control of the stock status bar (SystemBar.data and the screens with their own copy).

init.axf binds the image control name "ViewShowImageDashSeatBelt" to a handler that reads one int (0xe931e874):
non-zero -> state 'n', 0 -> state 'c'. The VW CAN parser never writes it; climabar.mod sets it from the belt bits.
The control maps state 'n' to the belt picture and has no picture for 'c', so the firmware itself draws the symbol
in the bar - under the volume popup like every other status symbol.

The record is a copy of the window's ViewShowImageBtConnect control (renamed, moved, one state pair) appended as
the window's last child.

usage: add_belt_control.py <in.data> <out.data> <belt.png> [dx]
  dx: left edge of the symbol relative to the Bluetooth control's left edge (default -70: left of the USB symbol)
"""
import os
import struct
import sys
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
from uidata import UiData, Window, U, rec_name, set_name   # noqa: E402
from build_volume_bar import image_blob                     # noqa: E402

NAME = 'ViewShowImageDashSeatBelt'
STATE_ON = ord('n')                    # handler: belt variable != 0
STATE_OFF = ord('c')                   # handler: belt variable == 0


def add_child(w: Window, base: int, rec: bytes, typ: int) -> Window:
    """the window with rec appended as its last child (records stay contiguous after the (type, offset) pairs)"""
    raw = w.raw
    hdr, n = U(raw, 4), U(raw, 0xf4)
    kids = w.children(base)
    assert all(t != 1 or U(raw, o) == 0x108 for t, o in kids), 'nested buttons not supported'
    head = bytearray(raw[:hdr + 8])
    recs = [(t, bytes(raw[o:o + U(raw, o)])) for t, o in kids] + [(typ, rec)]
    pos = len(head) + 8 * len(recs)
    assert sum(len(r) for _, r in recs[:-1]) + hdr + 8 + 8 * n == len(raw), 'unexpected window layout'
    pairs, body = bytearray(), bytearray()
    for t, r in recs:
        pairs += struct.pack('<II', t, base + pos)
        body += r
        pos += len(r)
    out = head + pairs + body
    struct.pack_into('<I', out, 0xf4, len(recs))
    struct.pack_into('<I', out, 0, len(out))
    return Window(bytes(out), base)


def add_belt(u: UiData, png, dx=-70, label=''):
    """add the control to every window of u that has a ViewShowImageBtConnect control"""
    ico = Image.open(png).convert('RGBA')
    done = 0
    for k, (w, base) in enumerate(u.windows):
        kids = w.children(base)
        names = [rec_name(w.raw, o) for _, o in kids]
        if 'ViewShowImageBtConnect' not in names or NAME in names:
            continue
        t, o = kids[names.index('ViewShowImageBtConnect')]
        rec = bytearray(w.raw[o:o + 0x110])
        assert t == 4 and U(rec, 0) == 0x110, 'BtConnect is not a one-picture image control'
        set_name(rec, 0, NAME)
        bx, by, bw, bh = struct.unpack_from('<iiII', rec, 0xd4)
        x = bx + dx
        struct.pack_into('<iiII', rec, 0xd4, x, by + (bh - ico.height) // 2, ico.width, ico.height)
        struct.pack_into('<I', rec, 0xe4, STATE_OFF)            # initial state: no picture
        struct.pack_into('<II', rec, 0x100, STATE_ON, len(u.images))
        u.images.append(image_blob(ico))
        u.windows[k] = (add_child(w, base, bytes(rec), 4), base)
        done += 1
        print(f'{label}: {NAME} in {rec_name(w.raw, 0) or "window " + str(k)} at x={x}')
    return done


def main(src, out, png, dx=-70):
    u = UiData(open(src, 'rb').read())
    assert add_belt(u, png, dx, os.path.basename(src)), f'{src}: no window with ViewShowImageBtConnect (or done)'
    data = u.build()
    UiData(data)                                                # parses back
    open(out, 'wb').write(data)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[2], *(int(v) for v in a[3:4]))
