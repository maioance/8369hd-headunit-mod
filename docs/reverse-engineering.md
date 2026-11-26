# Reverse-engineering notes

Everything here is for the stock image with sha1 `50183b11...` (init.axf "APP 20250320"); addresses differ in other
versions. The emulator's `docs/` (submodule) describes the DATAV1.0 UI format, MinFS and modules in general.

## Memory map

| Range | What |
|---|---|
| `0x4xxxxxxx` | heap: malloc, `esMEMS_Palloc`, the application's objects (virtual = physical) |
| `0xe8c00000` - `0xe8e3f510` | `wireless.mod` (type 0x8c) |
| `0xe9000000` - `0xe90f0000` | `climabar.mod` (type 0x90), then its heap |
| `0xe9100000` | `init.axf` (`.text`), `.rodata` from `0xe925ba1c`, `.data` `0xe92ddbd0`, `.bss` `0xe9319578` |

init.axf file offset = virtual address - `0xe9100000` + `0x16c`.

## init.axf state (read by climabar.mod)

| Address | What |
|---|---|
| `*(0xe932b210)` | decoded climate block: `+0` rear window, `+4` MAX front, `+8` DUAL, `+12/16` auto low / high, `+20` recirculation, `+24` A/C, `+28` fan, `+36/40/44` airflow windshield / face / feet, `+48/49` temperature left / right (VW: 0 = LO, 31 = HI, else 17.5 + 0.5 v), `+68` auto recirculation, `+104/168` seat belts, `+116..132` boot, doors RR / RL / FR / FL |
| `*(0xe932ace0)` | current app: `+0` handle, `+24` descriptor, `+0` its name ("Main", "Radio", "Bt", "Can", "Link", ...) |
| `0xe93284e8` | radio: `+0` band (0..2 FM), `+4` frequency (FM 10 kHz units, AM kHz), `+8` 6 presets per band |
| `0xe93285b4` | RDS PS, 8 characters |
| `0xe931eac0` | the PTY list is open over the radio screen |
| `*(0xe9321080)` | Bluetooth object: `+12` state (2 = connected), `+0x60e` title, `+0x70e` artist, `+0x80e` album |
| `0xe92df2e4` | page of the "Bt" app (201 = BT Music); `0xe92df3c8` page of "Can" (201 = vehicle info, 101 = climate) |
| `0xe931e874` | seat-belt flag, read by the `ViewShowImageDashSeatBelt` handler |
| `*(0xe9327dd8)` | link states, 2048 bytes per link; link 6 = wireless Android Auto, `+96` session active |
| `0xe9328968` | settings; `+0xd8` the wallpaper path (`D:\apps\WallPaper\<n>.jpg`), saved in `E:\Save\SetupSave.bin` |
| `0xe91930e8` | function: send one line to the Bluetooth module, e.g. `"AT#CD"` |
| `0xe91b2e0c` | function: path of a screen file from the "UI number" (`uiType`): `<= 1` `apps\Data\X`, else `apps\UI<n>\Data\X`, falling back to `apps\Data` |

## Melis syscalls

`ecall` with the number in `a7`, arguments in `a0`..`a3`. The kernel returns into the handler with
`ra = ecall + 4`: save `ra` around it ([safety.md](safety.md)).

| Number | Call |
|---|---|
| `0x10000100` / `0x101` / `0x107` | `esKRNL_TCreate` / `TDel` / `TaskNameSet` |
| `0x1000010c` / `0x10f` | `esKRNL_TimeDly` (1 tick = 10 ms) / `TimeGet` |
| `0x10000200` / `0x201` / `0x202` | `esMEMS_Palloc` (1 KiB pages) / `Pfree` / `VA2PA` |
| `0x10000214` | `esMEMS_CleanDCacheRegion` (write back) |
| `0x10000215` | `esMEMS_CleanFlushDCacheRegion` (write back + invalidate) |
| `0x10000217` | `esMEMS_FlushDCacheRegion` (**invalidate only** on the C906) |
| `0x10000302` / `0x308` / `0x30a` / `0x315` | `esFSYS_fclose` / `fopen` / `fread` / `fwrite` |
| `0x10000905` - `0x908` | `esTIME_GetTime` / `SetTime` / `GetDate` / `SetDate` |
| `0x10001a00` / `0x1a01` / `0x1a1a` | `close` / `open` / `ioctl` |

## Display (`/dev/disp`)

`ioctl(fd, cmd, {0, &layer_config, 1})`: `DISP_LAYER_SET_CONFIG` `0x47`, `DISP_LAYER_GET_CONFIG` `0x48`; formats
ARGB8888 `0x00`, RGB888 `0x08`. Channel 0 carries video (CarPlay / Android Auto, camera), channel 1 the GUI (layer
0, RGB888, 1024 x 600). Channels blend with each other; layers of the same channel do not (transparent pixels come out
black). The buffer address in the config is physical. climabar.mod uses channel 1 layer 1 (strip) and layer 2
(overlay), z-order 255, per-pixel alpha. The firmware also draws parts of the GUI with the G2D engine straight into
RAM: invalidate before reading GUI pixels.

## Bluetooth module

Behind the MCU: lines `AT#xx` inside MCU frames with command `0xD4`; replies come back the same way, as
`<2-letter code><payload>\r\n`, fields ending in `0xFF`.

| App -> module | | Module -> app | |
|---|---|---|---|
| `AT#CC` | connect the last phone | `IS` | module ready |
| `AT#CD` | disconnect | `IA` / `IB` | phone disconnected / connected |
| `AT#CE` / `CF` / `CG` | answer / reject / hang up | `ID<n>` / `IC<n>` | incoming / outgoing call |
| `AT#CW<n>` | dial | `IG` / `IF` | call active / ended |
| `AT#MA` / `MB` | play / pause | `MA` / `MB` | paused / playing |
| `AT#MD` / `ME` | next / previous track | `MI<title>ÿ<artist>ÿ<album>ÿ` | track info |
| `AT#PA` | download the phone book | `PB<name>ÿ<number>` / `PC` | entry / end |
| `AT#PH` / `PI` / `PJ` | dialled / received / missed calls | `PD...` | call history entry |
| `AT#MM<name>` | set the module name | `MM<name>`, `SA<name>` | module name, connected phone |
| | | `PT<yyyymmddhhmmss>` | the phone's time (sets the clock when phone time sync is on) |

The phone sends its time (`PT`) only when it allows the car kit access to contacts / call history.

## MCU and CAN box frames (as the emulator sends them)

| Frame | Content |
|---|---|
| CAN `0x20` | steering wheel key: `[key, 1]` pressed, `[key, 0]` released (1 Vol+, 2 Vol-, 3 next, 4 prev, 5 phone, 6 mute) |
| CAN `0x21` | Climatronic: `d0` 0x01 rear window, 0x02 MAX windshield, 0x04 DUAL, 0x08 auto low, 0x10 AUTO, 0x20 recirculation, 0x80 A/C; `d1` bits 0-2 fan, 0x20 feet, 0x40 face, 0x80 windshield; `d2/d3` temperatures; `d4` 0x80 auto recirculation |
| CAN `0x26` | steering angle |
| CAN `0x41` sub `0x01` | doors / boot / handbrake / belt bits (0 FL, 1 FR, 2 RL, 3 RR, 4 boot, 5 handbrake, 7 belt) |
| CAN `0x41` sub `0x02` | engine speed, speed (0.01 km/h), battery (0.01 V), outside temperature (0.1 °C), odometer, fuel |
| MCU `0xB4` sub 2 | RDS: 8 characters PS + PTY |
| MCU `0xE4` | vehicle info (same fields, doors bit 5 inverted) |
| MCU `0xB2` | hardware keys `[0, code, 0]` |

## Config.ini `[LINK]` (wireless CarPlay / Android Auto)

Read by init.axf from the settings; keys and their defaults when absent: `linkVideoWidth`, `linkVideoHeight` (0 =
automatic), `autoVideoWidth` / `autoVideoHeight` (Android Auto; default: the link values), `carplayVideoWidth` /
`Height`, `linkScreenWidth` / `Height` (0), `linkFrameRate` (30), `linkZoomMode` (0), `bLinkAutoPlay` (1),
`bAirPlayBackground` (1), `wifiChannel` (stock 36, i.e. 5 GHz), `bStartUpReconnectLink` (stock 1; `no_startup_link`
makes the default 0).

## Wireless Android Auto

The phone offers Android Auto over Bluetooth when it connects, then joins the unit's Wi-Fi (5 GHz) and starts the
session; `wireless.mod` decodes H.264 into display channel 0. The session start (type 900) raises a flag that
init.axf's main loop turns into opening the Android Auto screen and switching the audio - bypassing it loses the
sound. The touch latency is mostly the video round trip (phone encoding, Wi-Fi, decoding); on the phone, the
Android Auto developer settings can lower the video resolution.

## Screen folders and `uiType`

`Config.ini` `uiType` (2 on this unit) selects `apps\UI<n>\Data` for screen files (function `0xe91b2e0c`), but init.axf
reads `uiType` in 39 places and compares it with 2 in about 20, changing behaviour and layouts; changing it to switch
screen sets is not safe. (An experiment with themes picked through the wallpaper patched the call in that function
instead; it was dropped.)
