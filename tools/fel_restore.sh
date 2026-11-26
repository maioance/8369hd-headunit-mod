#!/bin/bash
# Recovery over FEL: writes back ONLY the stock application partition (ROOTFS) into the head unit's flash.
#
# The head unit must be in FEL mode (the flash chip's middle pins to ground at power-on) and connected to the PC with a
# USB A-A cable. Boot loader and kernel are never touched.
#
#   1. checks the link: the CPU in FEL + the flash chip (MX25L25645G, 32 MiB)
#   2. full copy of the flash on the PC, read twice and compared (the safety net)
#   3. checks in the copy that the ROOTFS partition (MINFS signature) starts at 0x190000 and that the boot loader in
#      the flash is the stock one - otherwise it stops without writing anything
#   4. after your confirmation: writes the stock data_udisk.fex at 0x190000
#   5. reads the region back and compares it with the stock partition
#
# usage: tools/fel_restore.sh        (asks for the administrator password for USB access, unless a udev rule allows it)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XFEL="$ROOT/tools/melis-tools/bin/xfel_spi_nor"
UNP="$ROOT/firmware/8369HD_unpacked"
ORIG_ROOTFS="$UNP/data_udisk.fex"
ROOTFS_OFF=0x190000
ROOTFS_SIZE=31391744
NOR_SIZE=0x2000000
OUT="$ROOT/backup_flash"
mkdir -p "$OUT"
# without sudo when a udev rule gives access to the FEL device (1f3a:efe8), with sudo otherwise
if "$XFEL" version >/dev/null 2>&1; then x() { "$XFEL" "$@"; }; else x() { sudo "$XFEL" "$@"; }; fi

echo "== 1. link"
x version
x spinor

echo "== 2. full copy of the flash (32 MiB, twice)"
STAMP=$(date +%Y%m%d_%H%M%S)
A="$OUT/flash_$STAMP.bin"; B="$OUT/flash_${STAMP}_verify.bin"
x read 0 $NOR_SIZE "$A"
x read 0 $NOR_SIZE "$B"
[ -O "$A" ] || sudo chown "$USER" "$A" "$B"
cmp -s "$A" "$B" || { echo "The two reads differ - unstable USB link. Do NOT go on; try again."; exit 1; }
rm -f "$B"
sha256sum "$A" | tee "$A.sha256"
echo "   copy: $A"

echo "== 3. checking the contents"
python3 - "$A" "$UNP" $ROOTFS_OFF <<'EOF'
import sys
flash, unp, off = open(sys.argv[1], 'rb').read(), sys.argv[2], int(sys.argv[3], 0)
assert flash[off:off + 6] == b'MINFS\0', f'ROOTFS does not start at {off:#x} (found {flash[off:off+6]!r}) - writing nothing'
boot0 = open(f'{unp}/boot0_nor.fex', 'rb').read()
assert flash[:len(boot0)] == boot0, 'boot0 in the flash differs from the stock one - writing nothing; keep the copy for analysis'
kernel = open(f'{unp}/melis_pkg_nor.fex', 'rb').read()
k = flash.find(kernel[:4096])
assert k >= 0 and flash[k:k + len(kernel)] == kernel, 'the kernel is not found intact in the flash - writing nothing'
print(f'   ROOTFS at {off:#x}: ok;  boot0: stock;  kernel at {k:#x}: stock')
EOF

echo
read -r -p "== 4. Write the STOCK ROOTFS ($ROOTFS_SIZE bytes) at $ROOTFS_OFF? Type 'yes': " ans
[ "$ans" = "yes" ] || { echo "Stopped, nothing written."; exit 1; }
x write $ROOTFS_OFF "$ORIG_ROOTFS"

echo "== 5. reading back and comparing"
C="$OUT/rootfs_written_$STAMP.bin"
x read $ROOTFS_OFF $ROOTFS_SIZE "$C"
[ -O "$C" ] || sudo chown "$USER" "$C"
if cmp -s "$C" "$ORIG_ROOTFS"; then
	echo "   ROOTFS written and verified: identical to the stock partition."
	echo "Done. Remove the FEL wire from the flash if still there, power off and start the head unit normally."
else
	echo "WARNING: the region read back differs from the stock partition. Do not power off; check before going on."
	exit 1
fi
