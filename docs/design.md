# Design

One look for every screen, inspired by factory head units of current cars, with the rules that matter in a car.

## Rules

- **Glanceable.** One large symbol and a label of 32 px per control; no small secondary text (below ~18 px it cannot be
  read at a glance while driving).
- **No fake data.** Screen art is static: never draw values that look live (a frequency, a progress bar, "live
  traffic") into an image. Live content comes from the firmware's own texts or from the module.
- **Dark, calm, readable at night.** Dark backgrounds, near-white text (`TEXT` on near-black is well above the 4.5:1
  contrast minimum), no large bright areas.
- **One accent, used sparingly:** red (`LINE_RED`, like the car's own illumination) marks states only - the pressed /
  selected marker, slider fills, the line under the status bar. Symbols are white-grey when lit, dim grey when off.
  Warnings (doors, seat belt) are red, as on the instrument cluster; seat heating is orange, as its lights.
- **Glass.** Panels and cards are a light tint at low opacity over the wallpaper (frosted glass); a dark see-through
  panel would look opaque over the near-black wallpapers. Pop-ups that must stay readable over anything (dialogs) are
  opaque.
- **Consistent states.** Pressed: the glass a step lighter with a white outline (every card and button). Selected list
  row: discreet glass with a red bar on the left; its text stays white.
- **Touch targets** of at least 64 px; on Home a whole column / tile is the target, larger than what is drawn.
- **Nothing under the climate strip:** Home keeps its content above y 468, where the strip slides in.

## Palette (`tools/theme.py`)

| Name | RGB | Use |
|---|---|---|
| `BG` | 10, 16, 18 | screen background, volume popup |
| `TEXT` | 220, 226, 228 | text, lit symbols |
| `DIM` | 138, 149, 153 | secondary text, chevrons |
| `OFF` | 78, 88, 94 | symbols that are off |
| `LINE_RED` | 240, 74, 56 | the accent |
| `WARN` | 240, 96, 64 | warnings |
| `CARD`, `CARD_LINE` | 20, 27, 30 / 35, 48, 47 | opaque cards (dialogs) |
| `GLASS` | 200, 225, 228 | the glass tint: panels alpha 14, cards 26, outline 46, pressed 60 |

The stock firmware's accent was teal; stock art that keeps it is turned white-grey by `tools/teal_to_white.py`.

## Components

- **Wallpapers** (`home/wallpapers.py`): generated in floating point with sub-pixel dithering (no banding on dark
  gradients); dark at the top (status bar) and bottom, light only as low glows. Four are installed (the picker shows
  four): carbon & crimson, honeycomb vignette, pure night, ambient horizon. Baseline JPEG, 4:4:4.
- **Home** (`home/build_home.py`, `HOME_STYLE=grid`): six glass tiles on one page (2 x 3), each a thin ring with the
  symbol and a short red arc on top, label below.
- **Status bar:** the red line with a soft glow, brightest in the middle.
- **Lists** (Setup, Language, Radio PTY): see-through rows with a hairline; selected / pressed: glass + red bar.
- **Sliders:** grey track, red fill. **Switches:** grey / red track, white knob.
- **Icons:** Material Symbols Rounded (`climabar/icons_src/`), white-grey.
- **Climate strip** (`climabar/layout.json`): A/C, AUTO, SYNC, air intake, MAX, REAR as symbol + label; temperatures in
  Noto Sans; the fan panel with 7 bars, or the airflow pictogram right after an airflow change.

## Fonts

The firmware draws its texts with its own font (`apps/Font30_8Bit.vft`, 8-bit glyphs); only some sizes exist (32 px
works for Home labels, 34 px falls back to a smaller one). The module draws with Noto Sans glyphs built into it
(`tools/gen_assets.py`, printable ASCII plus Central European letters).
