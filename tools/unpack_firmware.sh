#!/bin/bash
# Unpacks the stock firmware update image into firmware/8369HD_unpacked, the layout every other script uses:
#   firmware/8369HD_unpacked/<item>.fex, data_udisk.fex.out/ (the ROOTFS = D:\), melis_pkg_nor.fex.out/, image.cfg ...
#   firmware/8369HD_unpacked/gpt.bin.out/  what the emulator expects (--dump): links to the above, and the stock
#                                          Config.ini as the settings partition (E:\)
#
#   tools/unpack_firmware.sh [firmware/8369HD.img]
# Needs img_tool in tools/melis-tools/bin (docs/building.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="${1:-$ROOT/firmware/8369HD.img}"
OUT="$ROOT/firmware/8369HD_unpacked"
IMG_TOOL="$ROOT/tools/melis-tools/bin/img_tool"
STOCK_SHA1=50183b1126a1525a4eaaac980e5e381137635285     # the image this repository was made for

[ -f "$IMG" ] || { echo "missing $IMG"; exit 1; }
[ -x "$IMG_TOOL" ] || { echo "missing $IMG_TOOL (docs/building.md)"; exit 1; }
[ "$(sha1sum "$IMG" | cut -d' ' -f1)" = $STOCK_SHA1 ] ||
	echo "warning: $IMG is not the image this repository was made for (sha1 $STOCK_SHA1); the init.axf patches will refuse it"
[ -e "$OUT" ] && { echo "$OUT exists; remove it first"; exit 1; }

"$IMG_TOOL" extract "$IMG" "$OUT"
mkdir -p "$OUT/gpt.bin.out/1_bootA.bin.out" "$OUT/gpt.bin.out/3_UDISK.bin.out"
ln -s ../data_udisk.fex.out "$OUT/gpt.bin.out/2_ROOTFS.bin.out"
ln -s ../../melis_pkg_nor.fex.out/sys_config.fex "$OUT/gpt.bin.out/1_bootA.bin.out/sys_config.fex"
cp "$OUT/data_udisk.fex.out/apps/Config.ini" "$OUT/gpt.bin.out/3_UDISK.bin.out/Config.ini"
echo "unpacked: $OUT"
