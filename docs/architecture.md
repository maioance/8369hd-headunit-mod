# How it works

## The unit

| | |
|---|---|
| SoC | Allwinner F133 (D1s): one RISC-V C906 core, 64 MiB DDR2 |
| OS | Melis RTOS (Allwinner), modules (`*.mod`) loaded at fixed addresses |
| Screen | 1024 x 600, touch |
| Flash | Macronix MX25L25645G, 32 MiB SPI NOR |
| Around it | an MCU (keys, radio tuner, power, the Bluetooth module behind it), a CAN box (Raise protocol: climate, doors, trip data, steering wheel keys), a Wi-Fi module for wireless CarPlay / Android Auto |

Flash layout (from a programmer read):

| Offset | Content |
|---|---|
| `0x0` | boot0 |
| `0x10000` | kernel (`melis_pkg_nor.fex`) |
| `0x17e400` | configuration |
| `0x190000` - `0x1F7FFFF` | **ROOTFS** (MinFS, 31 391 744 bytes) = drive `D:\` - the only part this mod changes |
| `0x1F80000` | settings (UDISK) = drive `E:\`: `Config.ini`, `Save\SetupSave.bin`, ... |

USB sticks mount as `F:\` onwards. The stock updater installs `Update/8369HD.img` from a stick (an Allwinner
IMAGEWTY image; each item has a `V<item>.fex` checksum the updater checks).

## The application

The ROOTFS holds the whole user interface:

- `startup.sh`: loads the modules, then the desktop (`apps/desktop.mod`), which runs `apps/init.axf`;
- `apps/init.axf`: the application (RISC-V ELF, loaded at `0xe9100000`). Apps inside it ("Main" = Home, "Radio",
  "Bt", "Can" = vehicle / climate, "Link" = CarPlay / Android Auto, ...) are switched by name;
- `apps/Data/*.data`: one UI file per screen (format DATAV1.0, see the emulator's `docs/data-format.md`): windows,
  controls (buttons, texts, images, lists, sliders) with positions and colours, and the images (RGB565 + 5-bit alpha,
  ARGB8888 or RGB888, zlib). Each control has a name (e.g. `ViewShowStrSubFreq1`); every app binds names to handler
  functions through a (name, handler) table in init.axf;
- `apps/Language/*.txt`: the texts (UTF-16, tab-separated, Chinese key first);
- `apps/WallPaper/0..3.jpg`: the wallpapers (shown behind screens without their own background);
- `mod/*.mod`: drivers and services, e.g. `wireless.mod` (wireless CarPlay / Android Auto, type 0x8c).

## What the mod changes

All changes are files of the ROOTFS; nothing runs that the stock firmware would not load.

### 1. Screens (`*.data`, languages, wallpapers)

Each builder (`home/`, `radio/`, `bt/`, `vehicle/`, `setup/`) reads a stock `.data` file and writes a restyled one: new
images (same index, same or new size), moved / resized controls, text colours and fonts. Control names, handlers and
touch behaviour stay the stock ones, so the firmware drives everything as before. A few controls are added (the
seat-belt symbol in the status bars, `tools/add_belt_control.py`). Home's buttons are all moved to page 1, so the
screen does not scroll.

### 2. init.axf: static patches (`climabar/tools/patch_initaxf.py`)

Small byte patches, each checking the stock bytes first (another firmware version is refused):

| Patch | Effect |
|---|---|
| `door_popup` | a door / boot / seat-belt change no longer opens the full-screen trip computer |
| `climate_no_popup` | a climate change no longer opens the full-screen climate page (the strip shows it) |
| `bt_music_first` | Bluetooth opens on BT Music |
| `no_startup_link` | a wireless link the phone offers starts only while the Auto / CarPlay screen is open |
| `preset_names` | the radio preset texts are produced by hooks in climabar.mod (learned station names) |
| `belt_binding` | the status bar's seat-belt control works on every screen |

The patch descriptions in the script give the addresses and the reasoning.

### 3. climabar.mod (`climabar/`)

A Melis module loaded by `startup.sh` before the desktop (type 0x90, at `0xe9000000`, up to `0xe90f0000`; its heap
follows, then init.axf). It never patches code: it reads the application's state from memory, draws on its own
display layers, and offers functions that the patched init.axf calls.

- **Start:** waits `start_delay_seconds` (`layout.json`), then stops at once if a USB stick holds
  `Update/8369HD.img` (checked again every 2 s for 3 minutes, as sticks mount late) or if init.axf is not the expected
  version (`firmware_ok()`); then creates its thread.
- **Loop** (every 50 ms): compares the climate block init.axf decodes from the CAN box (`*(0xe932b210)`) with the last
  one; on a change it draws the strip and slides it in (display channel 1, layer 1, above the GUI and above Android
  Auto video) and hides it after `show_seconds`. It also: sets the seat-belt flag the firmware's own belt control
  shows; learns station names from the RDS text (a name counts once it has been on air 3 s, stored in
  `E:\climabar_ps.bin`); draws the overlay layer (channel 1, layer 2: the big station name on the radio screen, the
  door card, the now-playing card); manages Android Auto (below).
- **Overlay layer:** layers of the same display channel do not blend, so where it draws, the module copies the GUI's
  pixels (channel 1, layer 0) under its drawing and blends itself, and only when the GUI is not mid-redraw. Wherever
  possible the firmware draws instead (handler hooks, like the preset names), which needs no copying.
- **Preset names:** `climabar_hooks` (the first code of the module, `0xe9000000 + 8 * i`) are called by init.axf as
  the handlers of the preset texts; they call the stock handler and replace the text with the learned name.
- **Android Auto:** the phone offers wireless Android Auto when its Bluetooth connects; with `no_startup_link` the
  firmware takes it only on the Auto screen. When the Auto screen is open and no session starts within 3 s, the module
  renews the Bluetooth connection (`AT#CD`, then `AT#CC` = reconnect the last phone) so the phone offers it again; when
  a session ended and the Auto screen is left, it renews it once more so the phone gives its media back to Bluetooth.
- **Log:** only when a stick holds `climabar_log.txt`; kept in RAM and written at most once a second.

Artwork: `climabar/assets/*.png` (generated, `make assets`) and `layout.json` become C arrays (`build/assets.h`,
`tools/gen_assets.py`); single-colour images are stored as alpha only to keep the module small (it must end before
`0xe90f0000`, checked by the linker script).

## The build chain

```
firmware/8369HD.img --unpack_firmware.sh--> firmware/8369HD_unpacked
        |                                          |
        |                         build_overlay.sh (builders, make, patches)
        |                                          v
        +---------------- build_image.sh <-- emulator/emu/overlay  --> emulator (--overlay)
                               |
                               v
                     build/vN.img (verified) --> USB stick Update/8369HD.img --> unit
```
