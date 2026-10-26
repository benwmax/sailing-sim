# Fair cumulus as tall as they are wide (Oct 26 2026)

The Ultra re-audit's gap 1 remainder: the fair-weather cumulus still read as cotton. Matched against the Commons
photos of Lake Tawakoni (`docs/graphics-5/blind`: still06 for `g5-lakeopen`, still01 for `g5-bridge`, 13:00,
AfternoonBreeze), the biggest remaining difference is the clouds' shape. The photos' clouds are heaped, about as tall as
they are wide. The game's were low, wide puffs.

## Measured (`scratchpad` metrics: cloud pixels above the horizon; clouds clear of the horizon band)

| Frame | Height / width (median, max) | Cloud median / p99 | Cover |
|---|---|---|---|
| Photo, still06 (lakeopen) | 0.83, 1.15 | 0.75 | 0.37 |
| Photo, still01 (bridge) | 0.63, 0.63 | 0.76 | 0.11 |
| main, g5-lakeopen High | 0.42, 0.73 | 0.58 | 0.55 |
| main, g5-bridge High | 0.56, 0.80 | 0.82 | 0.21 |
| main, u5-bridge Ultra | 0.55, 0.78 | 0.80 | 0.22 |
| **this, g5-lakeopen High** | **0.64, 0.69** | 0.54 | 0.60 |
| **this, g5-bridge High** | **0.86, 1.03** | 0.83 | 0.28 |
| **this, u5-bridge Ultra** | **0.77, 1.00** | 0.80 | 0.29 |

Brightness within the clouds is close to the photos in the sunlit bridge view (median/p99 0.80-0.83 against 0.76). The
lakeopen view is now shaded at the camera (`sun_through_cloud` 0.76, against 0.96 on main) by a taller cloud, so its
frame is darker.

## Cause and fix

A cell stands its size's share of the cumulus layer's depth (`CumulusTop`). On a fair day the depth was 0.4 + 0.7 x
Afternoon km, written when the cells were about 1 km across. Since W5a's size classes, the largest fair-day cells are 2.4 km
across (`FWeatherMap`: 2 km radius x `CuCellScale` 0.6), so every cell came out about half as tall as wide. The
afternoon now deepens the layer by 1.5 km instead of 0.7 (`Weather.cpp`): 1.3 km at 13:00, 1.9 by mid-afternoon (0.8 of
the largest cells' width: cumulus mediocris). The morning keeps its 0.4 km humilis. `SailingSim.Visual.CumulusDepth`
holds both.

## Stills (left to right: photo, main, this)

- `lakeopen.jpg`, `bridge.jpg`: the photo, then main and this change.
- `chase-ultra.jpg`, `chase-high.jpg`: main, then this change.

## Gate (clouds scope, main bd7a3fbd + this): pass

Tests 239/239, including the heavy physics tests.

| View | Tier | fps |
|---|---|---|
| beam8 | High | 56.9 |
| beat15 | High | 55.5 |
| storm | High | 47.9 |
| gulf-sea | High | 60.5 |
| helm-eye | High | 53.5 |
| bridge | High | 58.3 |
| storm | Medium | 68.5 |

That matches the day's sweep on main, so no measurable cost.
