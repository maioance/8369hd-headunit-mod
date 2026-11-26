# Safety: keeping the unit booting

The module and the init.axf patches run inside the unit's only application. A crash there, or anything that stops
`startup.sh`, leaves the unit at the boot logo (with the CAN box powered: a reboot loop). The stock USB update still
works only as long as the application starts far enough to run it, so a broken image can need the flash programmer.
Every rule below comes from a real failure.

## Rules

1. **New module code: first a minimal image.** Before a feature that uses a new kind of call (a new syscall, a new
   ioctl, a new firmware function or address), build and install an image whose module does only that, with nothing
   else (`make -C climabar minimal` gives the bare module: same name, type and address, no display work;
   `THREAD=1` adds the thread). Only then the full feature.
2. **Never patch code at run time.** init.axf's code is write-protected (also through its physical address); a write
   resets or hangs the unit. Code changes are made only in the file, by `climabar/tools/patch_initaxf.py`, each patch
   checking the original bytes first.
3. **Keep the module's escape hatches:** the start delay (`start_delay_seconds`), stopping when a stick holds
   `Update/8369HD.img`, and `firmware_ok()` refusing any other init.axf. They make a stock update always possible.
4. **Syscall stub saves `ra`.** On the real kernel `ecall` returns by jumping into the handler with
   `ra = address of ecall + 4`; the stub must keep `ra` on the stack (`climabar/src/start.S`). A stub without it made
   `ret` jump to itself on the first syscall (creating the thread from `MInit`, during `startup.sh`) and hung the boot.
5. **Display buffers by physical address.** `DISP_LAYER_SET_CONFIG` takes the buffer's physical address:
   `esMEMS_VA2PA(fb)`.
6. **Write back the cache after drawing:** `esMEMS_CleanDCacheRegion`. On the C906, `esMEMS_FlushDCacheRegion` only
   *invalidates* - it throws away what was just drawn.
7. **Pointer checks accept both address ranges:** the heap (malloc, `esMEMS_Palloc`, the application's objects) is at
   `0x4xxxxxxx` (virtual = physical), modules and init.axf at `0xe9xxxxxx` (`in_ram()`).
8. **Module size:** the image must end before `0xe90f0000` (its heap follows, then init.axf); the linker script checks
   it. The hook table must stay the first code (`0xe9000000`), also checked.
9. **Always install verified images** (`tools/build_image.sh` ends with `Done` only when every check passed), keep the
   last image confirmed in the car, and change one thing at a time.

## What not to do (and why)

| Don't | Why |
|---|---|
| hook or patch code in memory at run time | write-protected: the unit resets / hangs (rule 2) |
| patch Android Auto's session start (the removed `aa_stay` patch) | it bypassed the stock start of a wireless session (type 900 flag): projection worked but Android Auto had **no sound** |
| change `uiType` in Config.ini to switch screen sets | it is read in 39 places; ~20 of them change behaviour and layouts, not only the screen folder |
| draw features on overlay layers when a firmware handler can draw them | same-channel layers replace, not blend: the module has to copy GUI pixels, which lags the GUI's own redraws (black flashes, leftovers after leaving a screen). Repointing a control's handler (`preset_names`, `belt_binding`) makes the firmware draw it in step |
| make the climate strip see-through | the GUI under it keeps redrawing and the blend visibly re-renders; it stays nearly opaque (`layout.json` opacity 230) |
| `objcopy --gap-fill` when making the module | it filled over `.bss` |
| `esMEMS_FlushDCacheRegion` after drawing | invalidates the drawing (rule 6) |
| trust the emulator alone | see below |
| leave `Update/` on a stick after updating | the module stays off while any stick holds an update file (on purpose) |

## The emulator is not the unit

Each of these caused a real bug that the emulator did not show at first:

- the kernel overwrites `ra` on `ecall` (now imitated);
- physical addresses for display buffers (the emulator now warns);
- heap at `0x4xxxxxxx` (now imitated at `0x4a000000`);
- no blending between layers of the same channel (now imitated);
- **not imitated:** write protection of init.axf's code; real wireless Android Auto / CarPlay, Wi-Fi, video
  decoding; real timing (the emulator is 10-100 times slower).

So: emulator first, then a minimal image when the change is risky, then the unit.

## Recovery

If the unit no longer starts (stuck at the logo):

1. **Try a USB update first** with the last good image (or the stock one): if the application starts far enough, the
   updater runs. The module never runs while the stick is in.
2. **CH341A programmer + SOIC-8 clip** (`tools/ch341_restore.sh`): the unit **unpowered** (no 12 V, no CAN, no USB),
   clip on the flash chip with the red wire on pin 1. The script finds the chip three times, reads the whole flash
   twice and compares the reads, checks that boot0 and the kernel are stock and ROOTFS starts at `0x190000`, and only
   after you type `yes` writes the stock ROOTFS back (`0x190000`-`0x1F7FFFF` only), then reads everything back and
   compares. Boot loader, kernel and settings are never written. Keep the full dump it makes.
3. **FEL over USB** (`tools/fel_restore.sh`), if the board is reachable in FEL mode: the same checks and the same
   region, written with `xfel_spi_nor`.

Before experimenting at all, make a full flash dump with the programmer (read twice, compared) and keep it safe.
