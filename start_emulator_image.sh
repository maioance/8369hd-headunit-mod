#!/bin/bash
# Starts the emulator from a built update image (default build/8369HD.img) WITHOUT the overlay - exactly what the head
# unit would run. Port 8134 (the usual emulator, with the overlay, stays on 8133); open http://localhost:8134
#   ./start_emulator_image.sh [image]          the image is built with tools/build_image.sh
ROOT="$(cd "$(dirname "$0")" && pwd)"
IMG="${1:-$ROOT/build/8369HD.img}"
[ $# -gt 0 ] && shift
T="$ROOT/build/imgtest"
[ -f "$IMG" ] || { echo "missing $IMG - run tools/build_image.sh first"; exit 1; }
rm -rf "$T" && mkdir -p "$T/gpt.bin.out"
"$ROOT/tools/melis-tools/bin/img_tool" extract "$IMG" "$T/img" >/dev/null || exit 1
mv "$T/img/data_udisk.fex.out" "$T/gpt.bin.out/2_ROOTFS.bin.out"         # the partition from the new image
rm -rf "$T/img"
cp -aL "$ROOT/firmware/8369HD_unpacked/gpt.bin.out/1_bootA.bin.out" "$T/gpt.bin.out/"   # boot: unchanged
cp -aL "$ROOT/firmware/8369HD_unpacked/gpt.bin.out/3_UDISK.bin.out" "$T/gpt.bin.out/"
P=$(pgrep -f "^node .*--port 8134"); [ -n "$P" ] && kill $P && sleep 1
UDISK=()
[ -f "$ROOT/udisk_config/Config.ini" ] && UDISK=(--udisk "$ROOT/udisk_config")
cd "$ROOT/emulator/emu" || exit 1
exec node --experimental-strip-types --no-warnings src/server.ts --stub --stub-hw-checks --fresh --dump "$T" \
  "${UDISK[@]}" --state "$T/state" --port 8134 "$@"
