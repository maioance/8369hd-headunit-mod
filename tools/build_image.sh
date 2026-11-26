#!/bin/bash
# Builds the firmware update image: the stock firmware + the files of the overlay (tools/build_overlay.sh).
#
#   1. extracts the stock image (firmware/8369HD.img), clean
#   2. copies the overlay files (emulator/emu/overlay, hidden files .* excepted) over the ROOTFS partition (data_udisk)
#   3. repacks the partition, then brings it to the stock geometry: the MinFS header with the partition size and
#      zero padding up to 31391744 bytes (as in the stock image)
#   4. repacks the image (img_tool recomputes the Vdata_udisk.fex checksum)
#   5. verifies: the new image is extracted again; every item except data_udisk must be identical to the stock one,
#      and every file of the partition identical to the stock file or to the overlay file
#
# Boot loader and kernel are never touched (the stock bytes are used as they are).
# usage: tools/build_image.sh [out.img]      (default: build/8369HD.img)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG_TOOL="$ROOT/tools/melis-tools/bin/img_tool"
ORIG="$ROOT/firmware/8369HD.img"
OVERLAY="${OVERLAY:-$ROOT/emulator/emu/overlay}"     # OVERLAY=<dir> to build from another overlay (an empty one: repack test)
OUT="${1:-$ROOT/build/8369HD.img}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== 1. extracting the stock image"
[ "$(sha1sum "$ORIG" | cut -d' ' -f1)" = 50183b1126a1525a4eaaac980e5e381137635285 ] || { echo "firmware/8369HD.img is not the stock image!"; exit 1; }
"$IMG_TOOL" extract "$ORIG" "$WORK/orig" >/dev/null
cp -a "$WORK/orig" "$WORK/mod"
rm -rf "$WORK/mod/boot_pkg_uboot_nor.fex.out" "$WORK/mod/melis_pkg_nor.fex.out"   # boot + kernel: untouched

echo "== 2. copying the overlay"
(cd "$OVERLAY" && find . -type f ! -name '.*' -printf '%P\n') | sort | while read -r f; do
	mkdir -p "$WORK/mod/data_udisk.fex.out/$(dirname "$f")"
	cp "$OVERLAY/$f" "$WORK/mod/data_udisk.fex.out/$f"
	echo "   $f"
done

echo "== 3. repacking the partition"
"$IMG_TOOL" pack "$WORK/mod" "$WORK/pass1.img" >/dev/null
python3 - "$WORK/mod/data_udisk.fex" "$WORK/orig/data_udisk.fex" "$WORK/mod/Vdata_udisk.fex" <<'EOF'
import struct, sys
new, orig, verify = sys.argv[1], sys.argv[2], sys.argv[3]
b = bytearray(open(new, 'rb').read())
size = len(open(orig, 'rb').read())                 # the ROOTFS partition (61312 sectors)
assert b[:6] == b'MINFS\0', 'not MinFS'
assert len(b) <= size, f'partition full: {len(b)} > {size} bytes'
struct.pack_into('<I', b, 0x1c, size)               # total size field, as in the original
b += bytes(size - len(b))
open(new, 'wb').write(b)
# the item checksum update.mod compares (sum of the 32-bit words), recomputed for the final bytes
total = sum(struct.unpack('<%dI' % (len(b) // 4), b)) & 0xffffffff
open(verify, 'wb').write(struct.pack('<I', total))
print(f'   Vdata_udisk.fex = {total:#010x}')
print(f'   MinFS: {struct.unpack_from("<I", b, 0x18)[0]} bytes used of {size} ({size - struct.unpack_from("<I", b, 0x18)[0]} free)')
EOF
rm -rf "$WORK/mod/data_udisk.fex.out"

echo "== 4. repacking the image"
mkdir -p "$(dirname "$OUT")"
"$IMG_TOOL" pack "$WORK/mod" "$OUT" >/dev/null
python3 - "$ORIG" "$OUT" <<'EOF'
# img_tool writes zeros where the original has filler bytes (header, item table, gaps between items); every item
# keeps its name, type, size and position, so the image is the original with only the two new items put in: it
# differs from the original only inside data_udisk.fex and Vdata_udisk.fex.
import struct, sys
orig, out = sys.argv[1], sys.argv[2]
a, b = bytearray(open(orig, 'rb').read()), bytearray(open(out, 'rb').read())
assert len(a) == len(b), 'image size changed'
def table(d, n=25):
    rows = []
    for i in range(n):
        e = d[0x400 + i * 0x400:0x800 + i * 0x400]
        rows.append((bytes(e[8:32]), bytes(e[32:36]), bytes(e[36:292]).split(b'\0')[0], struct.unpack_from('<IIIIII', e, 292)))
    return rows
ta, tb = table(a), table(b)
assert ta == tb, 'item table changed'
assert a[8:0x60] == b[8:0x60], 'image header fields changed'
# start from the original image byte for byte and put in only the two new items (same offsets and sizes)
res = bytearray(a)
for r in ta:
    if r[2] in (b'data_udisk.fex', b'Vdata_udisk.fex'):
        off, length = r[3][4], r[3][2]
        res[off:off + length] = b[off:off + length]
open(out, 'wb').write(res)
changed = sum(1 for i in range(0, len(a), 4096) if a[i:i + 4096] != res[i:i + 4096])
print(f'   image = the stock one with only data_udisk.fex + Vdata_udisk.fex replaced ({changed} blocks of 4 KiB)')
EOF

echo "== 5. verifying"
"$IMG_TOOL" extract "$OUT" "$WORK/check" >/dev/null
for f in "$WORK/orig"/*.fex "$WORK/orig/image.cfg"; do
	b=$(basename "$f")
	case "$b" in data_udisk.fex|Vdata_udisk.fex) continue ;; esac
	cmp -s "$f" "$WORK/check/$b" || { echo "DIFFERENT: $b"; exit 1; }
done
echo "   boot / kernel / configuration items: identical to the stock image"
python3 - "$WORK/check" <<'EOF'
# every item that has a V<item>.fex: its checksum must match (what update.mod checks before flashing)
import glob, os, struct, sys
d = sys.argv[1]
for v in sorted(glob.glob(os.path.join(d, 'V*.fex'))):
    item = os.path.join(d, os.path.basename(v)[1:])
    b = open(item, 'rb').read()
    b += bytes(-len(b) % 4)
    total = sum(struct.unpack('<%dI' % (len(b) // 4), b)) & 0xffffffff
    want = struct.unpack('<I', open(v, 'rb').read()[:4])[0]
    assert total == want, f'{os.path.basename(item)}: checksum {total:#x} != {os.path.basename(v)} {want:#x}'
    print(f'   checksum {os.path.basename(item)}: {total:#010x} = {os.path.basename(v)}  OK')
EOF
python3 - "$WORK/orig/data_udisk.fex.out" "$WORK/check/data_udisk.fex.out" "$OVERLAY" <<'EOF'
import os, sys, filecmp
orig, check, overlay = sys.argv[1:4]
def files(d):
    return {os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs}
o, c = files(orig), files(check)
ov = {f for f in files(overlay) if not os.path.basename(f).startswith('.')}
expected = o | ov
assert c == expected, f'missing: {sorted(expected - c)}  extra: {sorted(c - expected)}'
import struct
def sections(p):
    # modules are stored as sections in MinFS and come back as a rebuilt ELF (other section names, no entry):
    # compare type / address / size / flags / content of every section, in order
    d = open(p, 'rb').read()
    shoff = struct.unpack_from('<I', d, 0x20)[0]
    size, num, stri = struct.unpack_from('<HHH', d, 0x2e)
    sh = [struct.unpack_from('<IIIIIIIIII', d, shoff + i * size) for i in range(num)]
    so = sh[stri][4]
    out = []
    for s in sh[1:]:
        if d[so + s[0]:d.index(b'\0', so + s[0])] == b'.shstrtab':
            continue
        out.append((s[1], s[2], s[3], s[5], d[s[4]:s[4] + s[5]] if s[1] != 8 else b''))
    return out
def same(f):
    a, b = os.path.join(check, f), os.path.join(overlay if f in ov else orig, f)
    if f.endswith('.mod') and f in ov:
        return sections(a) == sections(b)
    return filecmp.cmp(a, b, shallow=False)
bad = [f for f in c if not same(f)]
assert not bad, f'wrong content: {bad}'
print(f'   {len(c)} files in the partition: {len(c) - len(ov)} stock unchanged, {len(ov)} from the overlay - all correct')
EOF
sha256sum "$OUT" | tee "$OUT.sha256"
echo "Done: $OUT"
