#!/bin/bash
# Recovery with a CH341A programmer + SOIC-8 clip: writes back ONLY the stock application partition (ROOTFS) straight
# into the head unit's flash chip (MX25L25645G, 32 MiB). The head unit's CPU takes no part.
#
# The head unit must be UNPOWERED (no 12 V, no CAN, no USB), the clip on the chip with the red wire on pin 1 (the dot).
# Boot loader and kernel are never touched.
#
#   1. the programmer finds the chip (3 times in a row, so we know the clip makes good contact)
#   2. full copy of the flash on the PC, read twice and compared (the safety net)
#   3. checks in the copy that ROOTFS (MINFS) starts at 0x190000 and that boot0 and the kernel are the stock ones, and
#      says what ROOTFS holds now (stock, our image or something else) - otherwise it stops without writing anything
#   4. after your confirmation: writes the stock data_udisk.fex at 0x190000 (the ROOTFS region only, verified)
#   5. reads everything back and compares: ROOTFS = stock, the rest of the flash unchanged against the copy
#
# Flash layout (found in a programmer read): boot0 0x0, kernel 0x10000, config 0x17e400, ROOTFS 0x190000
# (up to 0x1F80000), settings (E:) 0x1F80000.
#
# usage: tools/ch341_restore.sh [copy.bin]
#   with a copy made before (by this script): reads the flash once and compares it with the copy, instead of two reads
#   ROOTFS_FILE=<data_udisk.fex> writes another partition than the stock one (a test), with the same checks
#   FAST=1: no copy at the start and no read-back at the end (flashrom verifies the written region anyway); the
#           step 3 checks use the newest copy in backup_flash/ (boot loader and kernel are never written)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNP="$ROOT/firmware/8369HD_unpacked"
ORIG_ROOTFS="$UNP/data_udisk.fex"
ROOTFS_FILE="${ROOTFS_FILE:-$ORIG_ROOTFS}"
[ "$ROOTFS_FILE" = "$ORIG_ROOTFS" ] && WHAT="STOCK" || WHAT="TEST ($ROOTFS_FILE)"
ROOTFS_OFF=$((0x190000))
ROOTFS_SIZE=31391744
OUT="$ROOT/backup_flash"
FR=(flashrom -p ch341a_spi -c "MX25L25635F/MX25L25645G")
mkdir -p "$OUT"
STAMP=$(date +%Y%m%d_%H%M%S)

echo "== 1. looking for the chip"
for i in 1 2 3; do
	probe=$(flashrom -p ch341a_spi 2>&1 || true)
	grep -q "MX25L25635F/MX25L25645G" <<< "$probe" ||
		{ echo "   chip not found (attempt $i). Check the clip (red wire on pin 1) and that the head unit is unpowered."; exit 1; }
done
echo "   found: Macronix MX25L25645G (3 times)"

if [ "${FAST:-0}" = 1 ]; then
	A="${1:-$(ls -t "$OUT"/flash_2*.bin | grep -v -e _verify -e _to_write -e _after -e _verificare -e _de_scris -e _dupa | head -1)}"
	echo "== 2. (fast) no new copy; checking the newest copy: $A"
elif [ -n "${1:-}" ]; then
	echo "== 2. reading the flash once and comparing it with the copy $1 (a few minutes)"
	A="$1"; B="$OUT/flash_${STAMP}_verify.bin"
	[ "$(stat -c %s "$A")" = 33554432 ] || { echo "the copy is not 32 MiB"; exit 1; }
	"${FR[@]}" -r "$B" >/dev/null
	cmp -s "$A" "$B" || { echo "The flash read differs from the copy - poor contact or another copy. Do NOT go on."; exit 1; }
	rm -f "$B"
	echo "   identical to the copy: $A"
else
	echo "== 2. full copy of the flash (32 MiB, twice; a few minutes each)"
	A="$OUT/flash_$STAMP.bin"; B="$OUT/flash_${STAMP}_verify.bin"
	"${FR[@]}" -r "$A" >/dev/null
	"${FR[@]}" -r "$B" >/dev/null
	cmp -s "$A" "$B" || { echo "The two reads differ - poor clip contact. Do NOT go on; reseat the clip and try again."; exit 1; }
	rm -f "$B"
	sha256sum "$A" | tee "$A.sha256"
	echo "   copy: $A"
fi

echo "== 3. checking the contents"
python3 - "$A" "$UNP" "$ROOT/build/8369HD.img" $ROOTFS_OFF $ROOTFS_SIZE <<'EOF'
import os, sys, hashlib
flash, unp, built, off, size = open(sys.argv[1], 'rb').read(), sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
assert len(flash) == 32 << 20, f'the copy has {len(flash)} bytes'
assert flash[off:off + 6] == b'MINFS\0', f'ROOTFS does not start at {off:#x} (found {flash[off:off+6]!r}) - writing nothing'
boot0 = open(f'{unp}/boot0_nor.fex', 'rb').read()
assert flash[:len(boot0)] == boot0, 'boot0 in the flash differs from the stock one - writing nothing; keep the copy for analysis'
kernel = open(f'{unp}/melis_pkg_nor.fex', 'rb').read()
k = flash.find(kernel[:4096])
assert k >= 0 and flash[k:k + len(kernel)] == kernel, 'the kernel is not found intact in the flash - writing nothing'
print(f'   ROOTFS at {off:#x}: ok;  boot0: stock;  kernel at {k:#x}: stock')
cur = flash[off:off + size]
orig = open(f'{unp}/data_udisk.fex', 'rb').read()
what = 'the STOCK partition' if cur == orig else None
if what is None and os.path.exists(built):
    img = open(built, 'rb').read()
    i = img.find(cur[:4096])
    if i >= 0 and img[i:i + size] == cur:
        what = 'OUR image (build/8369HD.img), written completely'
    elif i >= 0:
        same = sum(1 for p in range(0, size, 4096) if img[i + p:i + p + 4096] == cur[p:p + 4096])
        what = f'our image, but INCOMPLETE/different ({same}/{size // 4096} 4 KiB blocks identical)'
print(f'   ROOTFS now holds: {what or "something else (neither stock nor our image)"}')
print(f'   sha256 of the current ROOTFS: {hashlib.sha256(cur).hexdigest()[:16]}...')
EOF

echo
[ "$(stat -c %s "$ROOTFS_FILE")" = $ROOTFS_SIZE ] || { echo "$ROOTFS_FILE is not $ROOTFS_SIZE bytes"; exit 1; }
head -c 6 "$ROOTFS_FILE" | grep -q MINFS || { echo "$ROOTFS_FILE is not a MinFS partition"; exit 1; }
read -r -p "== 4. Write the $WHAT ROOTFS ($ROOTFS_SIZE bytes) at $(printf 0x%x $ROOTFS_OFF)? Type 'yes': " ans
[ "$ans" = "yes" ] || { echo "Stopped, nothing written."; exit 1; }
NEW="$OUT/flash_${STAMP}_to_write.bin"
LAYOUT="$OUT/layout_$STAMP.txt"
cp "$A" "$NEW"
dd if="$ROOTFS_FILE" of="$NEW" bs=4096 seek=$((ROOTFS_OFF / 4096)) conv=notrunc status=none
printf '%08x:%08x rootfs\n' $ROOTFS_OFF $((ROOTFS_OFF + ROOTFS_SIZE - 1)) > "$LAYOUT"
"${FR[@]}" -l "$LAYOUT" -i rootfs -N -w "$NEW"
if [ "${FAST:-0}" = 1 ]; then
	echo "Done (fast; flashrom verified the written region). Remove the clip and start the head unit."
	rm -f "$NEW"
	exit 0
fi

echo "== 5. reading everything back and comparing"
C="$OUT/flash_${STAMP}_after.bin"
"${FR[@]}" -r "$C" >/dev/null
if cmp -s "$C" "$NEW"; then
	echo "   ROOTFS = $WHAT; the rest of the flash (boot, kernel, settings) unchanged."
	echo "Done. Remove the clip, refit and start the head unit normally."
else
	echo "WARNING: the flash read back differs from what was to be written. Disconnect nothing; check before going on."
	exit 1
fi
