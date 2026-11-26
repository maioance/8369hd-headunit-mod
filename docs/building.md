# Building and installing

## What you need

Not in this repository (vendor or third-party material), each in its git-ignored place:

| Where | What |
|---|---|
| `firmware/8369HD.img` | the stock firmware update image of the unit (sha1 `50183b1126a1525a4eaaac980e5e381137635285`, app version 20250320). Another version: the init.axf patches and the module refuse it, on purpose - every address is version specific |
| `tools/melis-tools/bin/` | the F133/D1s Melis firmware toolkit: `img_tool` (update images), `dump_tool` (full flash dumps), `xfel_spi_nor` (FEL recovery) |
| `sdk/d1s-melis/` | the Melis SDK ([gitee.com/grantho/d1s-melis](https://gitee.com/grantho/d1s-melis)); only its linker scripts (`scripts/`) are used |
| `udisk_config/Config.ini` | optional: a copy of your unit's settings partition `E:\Config.ini`, for the emulator to start with your settings |
| `local/stalogo1.jpg` | optional: a boot logo (1920 x 720 baseline JPEG, like the stock one), installed as `res/stalogo1.jpg` |

Tools (versions used): Python 3 with Pillow 12, ImageMagick 7 (`magick`), the Noto Sans fonts
(`/usr/share/fonts/google-noto/`), a RISC-V cross toolchain (`riscv64-linux-gnu-gcc` 16, e.g. Fedora
`gcc-riscv64-linux-gnu`), Node.js 22.6+ for the emulator, `flashrom` 1.6 for recovery with a CH341A programmer.

## Build

```sh
tools/unpack_firmware.sh          # once: firmware/8369HD.img -> firmware/8369HD_unpacked
tools/build_overlay.sh            # all modified files -> emulator/emu/overlay (about 25 s)
tools/build_image.sh build/vN.img # the update image
```

`tools/build_overlay.sh` runs every builder from the stock files: the init.axf patches, the module (artwork, then
`make`), `startup.sh`, every screen, the volume popup, titles. The overlay mirrors the ROOTFS partition (`D:\`); the
emulator loads it on top of the stock firmware, and `tools/build_image.sh` packs it into an update image.

`tools/build_image.sh` starts from the stock image byte for byte, replaces only the ROOTFS partition and its checksum,
then extracts the result again and verifies it: boot loader, kernel and configuration identical to stock, checksums
correct, every file of the partition identical either to the stock file or to the overlay file. Do not install an
image whose build did not end with `Done`.

The builds are reproducible: `python3 tools/compare_overlay.py <overlay A> <overlay B>` compares two overlays (screens
by window records and pixels, everything else byte for byte), e.g. a fresh build against the one installed.

### Changing one part

- a screen: edit its builder (colours at the top, `tools/theme.py` for the shared palette), run `tools/build_overlay.sh`
- the module: `climabar/src/`, `climabar/layout.json` (positions, sizes, fonts, timings); `make -C climabar`
- the module's artwork: `climabar/tools/fetch_icons.py` (Material Symbols, digits), `import_vehicle_assets.py`
  (car, doors, seat belt from the stock trip computer); `make -C climabar assets`
- the Home layout: `HOME_STYLE` in `home/build_home.py` (`grid` is the installed one; the others are kept as options)

## Emulator

```sh
./start_emulator.sh          # http://localhost:8133, factory settings
./start_emulator.sh --keep   # keeps the settings of the last run (chosen wallpaper etc.)
./start_emulator_image.sh build/vN.img   # a built image, without the overlay, on port 8134
```

It runs the real `init.axf` with the overlay, mouse = touch. The scripts pass `--stub-hw-checks`: the stock app checks
the MCU and the flash chip before opening its apps, and the emulator has neither, so those checks are answered in the
emulator's memory (nothing changes in the firmware or on the unit). The panel on the right sends CAN frames (steering
wheel keys, doors, trip computer data, climate), RDS names, and drives a simulated Bluetooth phone. HTTP endpoints for
scripts: `GET /frame.png`, `POST /touch {a: down|move|up, x, y}`, `POST /can {type, data}`, `POST /mcu {cmd, data}`,
`POST /bt {action: connect|disconnect|play|pause|track|incoming...}`, `POST /link {link, status}` (projection state),
`GET /status`. `--usb <dir>` mounts a folder as a USB stick on `F:\` (e.g. with an empty `climabar_log.txt`).

It is not the unit: wireless Android Auto / CarPlay, Wi-Fi and real video are not emulated (`wireless.mod` is
stubbed), it runs at ~10-40 MIPS, and it does not reproduce every hardware rule - see
[safety.md](safety.md#the-emulator-is-not-the-unit). Everything new is tried in the emulator first, then on the unit.

## Installing on the unit

1. Copy the image to a FAT32 USB stick as `Update/8369HD.img` and check it (`sha256sum`, the build prints it).
2. Put the stick in the unit with the engine running (stable power) and let the stock updater run. Do not cut power.
3. When the unit is back, **remove `Update/` from the stick** (the module stays switched off while an update file is
   on any stick, so that an update always runs exactly as stock).

Settings, radio presets and Bluetooth pairing survive an update; the learned station names are kept in
`E:\climabar_ps.bin`.

**Diagnostic log:** an empty `climabar_log.txt` in the root of a stick makes the module write its log there (start-up,
errors). Without that file the module writes nothing.

## Releases

Keep every image that went into the car together with its `.sha256` and the overlay it was built from, and tag the
commit; the last image confirmed in the car is the one to go back to. An image is identified by its sha256; two builds
of the same commit give the same image.
