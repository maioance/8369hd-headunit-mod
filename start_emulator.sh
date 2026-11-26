#!/bin/bash
# Starts the emulator on the stock firmware with this repository's overlay; then open http://localhost:8133
#   ./start_emulator.sh            factory settings (a clean start)
#   ./start_emulator.sh --keep     keeps the settings saved last time (e.g. the chosen wallpaper), like the head unit
#                                  restarting in the car
# Extra options go to the emulator (emulator/emu/src/server.ts), e.g. --usb <dir> mounts <dir> as a USB stick on F:\.
# --overlay: the files of emulator/emu/overlay (tools/build_overlay.sh) replace / add to the firmware, in the emulator
# only. --udisk: the device settings (E:\Config.ini) from udisk_config/ instead of the factory ones.
# --stub-hw-checks: the stock app checks the MCU and the flash chip, which the emulator does not have; this answers
# those checks in the emulator's memory only (nothing is changed in the firmware or on the unit).
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/emulator/emu" || exit 1
FRESH=--fresh
[ "${1:-}" = --keep ] && { FRESH=; shift; }
UDISK=()
[ -f "$ROOT/udisk_config/Config.ini" ] && UDISK=(--udisk "$ROOT/udisk_config")
exec node --experimental-strip-types --no-warnings src/server.ts --stub --stub-hw-checks $FRESH \
  --dump "$ROOT/firmware/8369HD_unpacked" --overlay "$ROOT/emulator/emu/overlay" \
  "${UDISK[@]}" --port 8133 "$@"
