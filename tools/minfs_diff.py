"""Compare two MinFS partitions (ROOTFS) entry by entry: header, directory order, attributes, sizes, module
section extents (compression), and the decompressed content.

usage: minfs_diff.py <a data_udisk.fex> <b data_udisk.fex>
"""
import lzma
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../emulator/tools'))
from build_firmware import walk, lzma_unpack     # noqa: E402


def header(fs):
    return struct.unpack_from('<6sH6I', fs, 0)


def entries(fs):
    """every entry (files and directories) in directory order: path -> entry dict (+ order index)"""
    magic, version, root, root_size = struct.unpack_from('<6sHII', fs, 0)
    out, stack = [], [(root, root_size, '')]
    while stack:
        off, ln, parent = stack.pop(0)
        for e in walk(fs, off, ln, parent):
            out.append(e)
            if e['attr'] & 1:
                stack.append((e['data'], e['size'], e['path']))
    return out


def extents(fs, e):
    nl = struct.unpack_from('<H', fs, e['entry'] + 16)[0]
    rec = struct.unpack_from('<H', fs, e['entry'] + 12)[0]
    p, end, out = e['entry'] + 20 + ((nl + 3) & ~3), e['entry'] + rec, []
    while p + 32 <= end:
        out.append(struct.unpack_from('<8I', fs, p))
        p += 32
    return out


def content(fs, e):
    """decompressed bytes: plain file body, or the module's sections in order"""
    if not e['attr'] & 2:
        return bytes(fs[e['data']:e['data'] + e['size']])
    out = []
    for off, stored, unp, mem, va, typ, flags, attr in extents(fs, e):
        raw = fs[e['data'] + off:e['data'] + off + stored]
        out.append(lzma_unpack(raw, unp) if attr & 2 else bytes(raw[:unp]))
    return b''.join(out)


def main(a_path, b_path):
    A, B = open(a_path, 'rb').read(), open(b_path, 'rb').read()
    ha, hb = header(A), header(B)
    names = ['magic', 'version', 'root', 'root_len', 'entries', 'dentry_len', 'data_len', 'fs_size']
    print('header:')
    for n, x, y in zip(names, ha, hb):
        print(f'  {n:10s} {x!s:>14} {y!s:>14}{"" if x == y else "   <-- diferit"}')
    ea, eb = entries(A), entries(B)
    da, db = {e['path']: e for e in ea}, {e['path']: e for e in eb}
    print(f'entries: {len(ea)} / {len(eb)};  only in A: {sorted(set(da) - set(db))[:10]}  only in B: {sorted(set(db) - set(da))[:10]}')
    same_order = [e['path'] for e in ea] == [e['path'] for e in eb]
    print(f'same directory order: {same_order}')
    attr_diff, ext_diff, content_diff = [], [], []
    for p in sorted(set(da) & set(db)):
        x, y = da[p], db[p]
        if x['attr'] != y['attr']:
            attr_diff.append((p, x['attr'], y['attr']))
        if x['attr'] & 1:
            continue
        if x['attr'] & 2:
            ex, ey = extents(A, x), extents(B, y)
            sig = lambda es: [(u, m, va, t, f, at & ~0) for _, _, u, m, va, t, f, at in es]
            if sig(ex) != sig(ey):
                ext_diff.append((p, len(ex), len(ey)))
        if content(A, x) != content(B, y):
            content_diff.append(p)
    print(f'attribute differences ({len(attr_diff)}):', attr_diff[:20])
    print(f'module section-table differences ({len(ext_diff)}):', ext_diff[:20])
    print(f'content differences ({len(content_diff)}):', content_diff)


if __name__ == '__main__':
    main(*sys.argv[1:3])
