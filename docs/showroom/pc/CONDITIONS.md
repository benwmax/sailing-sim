# Showroom, PC PR 3: the Conditions screen

`Inputs/ui-showroom/brief.md` section 6 (artboard 3), on the Mac's live preview (`PreviewConditions`, docs/showroom-wiring/)
and the Boat screen's stage input (PR 2).

## The screen (`SailFrontEnd.cpp` `BuildConditions`)

- **One translucent column on the left (540 px).** It holds the eyebrow and "SET THE CONDITIONS" at 40 px, the presets in
  two columns, the real days in two columns, then wind speed, gusts, wind from, sky, time of day, date, air temp and lake
  level (or the tide note on Galveston), all scrolling. Next (or Apply in game) sits at the bottom.
- **Wind from is a slider** (5 degree steps, with the compass point beside it). The wind dial didn't fit one column.
- **Over the world:**
  - top right, a "Live preview" badge with the clock the world shows;
  - near the boat, the wind ("↓ 20 kn from N, gusts to 28", or the real day's);
  - bottom right, "What to expect" as a caption.
- **The backdrop:** the Boat screen's vignettes, and the left fade ends at the column's edge (600 px of 1440, Bean's note),
  so the world to its right stays clear.
- **View mode:** V or View hides the column and the caption. Drag, the right stick and the wheel look around the boat (PR 2's
  orbit input, on this screen too).

## Keys and the pad

- **Down and Up go through every row**: presets, real days, each slider and choice, then Next. Focus stops on Next going down
  and on the first preset going up.
- **The column scrolls to keep the focused row in view** (`ScrollWhenFocusChanges`). Before, rows under the fold were out of
  the hit-test grid that navigation searches, so Down stopped at the sky row.
- **Each row is its own scroll-box slot.** An `SScrollBox` navigates slot to slot, so rows that shared one slot were skipped
  going up (lake level jumped straight to the real days).
- Checked with `-SailingUIScript` (12 Downs, 12 Ups, then Right ten times on wind speed): every step lands on the next row,
  and the world goes from 10 to 20 kn (whitecaps, heel, the caption's advice). The UI script's log names each focused widget
  with its source line (`SWidget::ToString`).
- Testing note: benches run `ProfileGPU` for their GPU slices. Its GPU Visualizer window takes keyboard focus partway through a
  run, so UI-script runs need `-SailingNoGpuSlices`.

## The blends

The world behind eases toward the choice instead of popping:
- **Wind speed and gusts** close on the new value over about 2 s (time constant 0.67 s), so the waves and the heel build
  with them.
- **Time of day** sweeps at up to 3 hours a second while the slider moves.
- While either moves, the world is re-previewed five times a second (`PreviewConditions`).

**Still snapping** (the Mac's debounced preview, 200 ms after a change stands): wind direction, the sky preset (cloud
cover, rain and fog jump rather than cross-fading over about 1.5 s), the date, the real day and the lake level. Each
re-preview also restarts the weather timeline at the chosen hour, as a cast off would. Easing the sky needs a blend in the
weather system itself; that's the next step for this screen.

## Stills (Ultra, `-SailingFrontEnd=Conditions -SailingPreviewPreset=<id>`)

- `cond-default-1440.jpg`, `cond-default-1920.jpg`: the ASA 101 lesson day.
- `cond-glassy-1920.jpg`: glassy morning, 07:30, 2 kn.
- `cond-norther-1920.jpg`: blue norther, 11:00, 20 kn, overcast.
- `cond-storms-1920.jpg`: typical July afternoon, the storm building.
- `cond-viewmode-1920.jpg`: the norther with the column hidden (V).
