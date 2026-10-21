# Rain on the Sky row

The Conditions screen's Sky row (and the in-game Change conditions screen, which builds the same panel) offers **Rain**:
steady rain from the start of the session, the `Rain` weather preset (0.6 rain, a low grey deck, 4 km visibility, 14 kn
NE). Before, the row had no rain: Storms runs the thunderstorm, whose rain only comes with its front, and the Rain preset
could only be picked from the in-game Settings panel.

- `ESailSky::Rain` is appended last, so saves (string ids) and the int uses of the others (`SailCatalog::Expect`) keep
  their meaning. The row shows Clear, Fair, Overcast, Rain, Storms, Fog (`SkyRowOrder` in `SailFrontEnd.cpp`).
- `USailSessionSubsystem::WeatherPresetFor(Rain)` is the Rain preset, the same path every Sky choice takes to the game
  mode (`ApplyToSettings`, `SailingGameMode` on the cast-off reload).
- "What to expect" says so. Tests: `SailingSim.UI.SessionFlow` (Rain runs the Rain preset, its name) and
  `SailingSim.Save.*` (the sky sweep covers all six by name).

| Before | After |
| --- | --- |
| ![](conditions-before.jpg) | ![](conditions-after.jpg) |

The row's six chips overflowed into the next column at 1440x1080 (Mac UI gate). `SSailChoice` now lays its chips out in a right-aligned `SWrapBox` that takes the row's width (a row too narrow wraps inside its panel) and sits rows of six or more a little tighter: one line at 1920x1080 (`conditions-1920.jpg`), two at 1440x1080 (`conditions-1440.jpg`, `conditionsingame-1440.jpg`).
