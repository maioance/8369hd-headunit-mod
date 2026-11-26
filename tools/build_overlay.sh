#!/bin/bash
# Builds every modified file of the head unit (the "overlay") from the stock firmware and this repository's sources.
#
#   tools/build_overlay.sh [<out dir>]        default out dir: emulator/emu/overlay
#
# The overlay mirrors the rootfs (D:\): apps/Data/*.data, apps/init.axf, apps/Language/*.txt, apps/WallPaper/,
# mod/climabar.mod, startup.sh (and res/stalogo1.jpg if local/stalogo1.jpg exists). tools/build_image.sh packs it into
# a firmware update image; the emulator loads it with --overlay.
#
# Needs: the unpacked stock firmware in firmware/8369HD_unpacked (see docs/building.md), Python 3 + Pillow,
# ImageMagick (magick), the RISC-V toolchain and the Melis SDK (for climabar.mod), Noto Sans fonts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$ROOT/firmware/8369HD_unpacked/data_udisk.fex.out"
OUT="$(mkdir -p "${1:-$ROOT/emulator/emu/overlay}" && cd "${1:-$ROOT/emulator/emu/overlay}" && pwd)"
ICONS="$ROOT/climabar/icons_src"
[ -f "$FW/apps/init.axf" ] || { echo "missing $FW/apps/init.axf: unpack the stock firmware first (docs/building.md)"; exit 1; }

A="$OUT/apps"
mkdir -p "$A/Data" "$A/Language" "$A/WallPaper" "$OUT/mod"
step() { echo "== $*"; }

step "init.axf: static patches"
python3 "$ROOT/climabar/tools/patch_initaxf.py" "$FW/apps/init.axf" "$A/init.axf" >/dev/null

step "climabar.mod"
make -C "$ROOT/climabar" assets FW="$FW" >/dev/null
make -C "$ROOT/climabar" >/dev/null
cp "$ROOT/climabar/build/climabar.mod" "$OUT/mod/climabar.mod"

step "startup.sh: load climabar.mod before the desktop"
sed -e 's/\r$//' -e 's#^insmod d:\\apps\\desktop.mod#insmod d:\\mod\\climabar.mod\ninsmod d:\\apps\\desktop.mod#' \
	"$FW/startup.sh" > "$OUT/startup.sh"

step "Home, Apps, wallpapers"
python3 "$ROOT/home/build_home.py" "$FW/apps/Data/Main.data" "$A/Data/Main.data" "$A/WallPaper" >/dev/null

step "Radio"
python3 "$ROOT/radio/build_radio.py" "$FW/apps/Data/RadioRds.data" "$A/Data/RadioRds.data" "$ICONS" >/dev/null

step "Bluetooth screens and the status bar"
python3 "$ROOT/bt/build_bt.py" "$FW/apps/Data" "$A/Data" >/dev/null

step "Trip computer, climate page"
python3 "$ROOT/vehicle/build_carcomputer.py" "$FW/apps/Data/CarComputer.data" "$A/Data/CarComputer.data" >/dev/null
python3 "$ROOT/vehicle/build_aircondition.py" "$FW/apps/Data/AirCondition.data" "$A/Data/AirCondition.data" >/dev/null

step "Setup"
python3 "$ROOT/setup/build_setup.py" "$FW/apps/Data" "$A/Data" >/dev/null

step "Volume popup"
python3 "$ROOT/vehicle/build_volume_popup.py" "$FW/apps" "$A" "$ICONS" >/dev/null

step "Titles, status bar text"
python3 "$ROOT/vehicle/fix_titles.py" "$FW/apps/Language" "$A/Language" >/dev/null
python3 "$ROOT/tools/tip_icons.py" "$FW/apps" "$A" "$ICONS" >/dev/null

if [ -f "$ROOT/local/stalogo1.jpg" ]; then
	step "boot logo (local/stalogo1.jpg)"
	mkdir -p "$OUT/res"
	cp "$ROOT/local/stalogo1.jpg" "$OUT/res/stalogo1.jpg"
fi
echo "overlay: $OUT"
