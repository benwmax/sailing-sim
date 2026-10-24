# The cumulus field: sizes, clusters and flat bases (Oct 24 2026)

Ultra audit 1 (`docs/ultra-audit-1024/`) found that every outdoor shot had a sky of similar lumpy blobs, soft all round,
much the same size and packed evenly to the horizon. Real fair-weather cumulus differ in three ways:

- their bases are flat, on a common condensation level;
- they come from towers down to scraps, many small to few large;
- they gather in clusters with clear sky between them.

## The field (FWeatherMap::Paint)

Measured on the AfternoonBreeze sky at 15:00, the CloudNoise and CumulusField tests' map:

| | main | now |
|---|---|---|
| Cloud fraction over 8 km boxes, variation | 21% of its mean | 56% |
| 8 km boxes nearly clear (under 5% cloud) | 0 of 64 | 8 of 64 |
| Clouds by area, bins x2.83 from 0.01 km^2 | 410 476 368 201 154 110 | 1550 785 453 264 123 88 |
| Largest cloud | 8.0 km^2 | 11.2 km^2 |

Three changes:

- **Presence by size, weakly.** A cell's presence goes as its size^0.3, not size^1.
  - With size^1, a small cell's presence stayed under the coverage edge, so only the big classes showed. The counts were
    flat across the middle sizes.
  - Now each bin holds about half the clouds of the one before, the D^-2.5 power law the classes were built for.
  - The renderer takes a cell's height from its size (`CumulusTop`), not its presence, so the size^1 term wasn't needed for
    height.
- **A class of scraps.** Cells of 180 m radius (cumulus humilis and fractus), 1150 m apart.
- **Clusters and gaps.**
  - Convection organises fair-weather cumulus into clusters kilometres to tens of kilometres across, with clear sky between
    them. Satellite cloud fraction varies by about half its mean over boxes of this size.
  - The convective field (cells, their noise and the streets) is scaled by an envelope 12 km across: 0.2 in a gap, 1 in a
    cluster. It is also lowered in the gaps.
  - The coverage solve keeps the sky's mean, so the clusters fill as the gaps clear.
  - Land heating still adds cloud over the land.

`weather-map.jpg` shows the cumulus channel, main on the left and now on the right, 64 km across.

## The clouds (CLOUD_CODE)

- **Flat bases.** The noise's iso-surface was the outline all round, so every cell's underside was lumpy. Over its lowest
  120 m above the layer's base, a cell's core footprint is now filled, easing into the billowed shape by 360 m. That gives
  one flat base across the field, at the day's condensation level.
- **Shallow scraps.** A cell's height grows as cuSize^1.4, which is about R^0.85, with a floor of 7% of the layer. A big
  cell still stands about as tall as it is wide. A small one is a lens about half as tall as it is wide. At cuSize itself
  the 200 m scraps stood 280 m tall: round balls.

## Stills (High, Mac; main on the left)

- `chase.jpg`: 14:00.
- `low.jpg`: 18:00, low sun.
- `up.jpg` (the sky from 25 m) and `wide.jpg` (40 m out): this change only. Main's framings were under the water.

## Not done here

- The tops' crispness is set by the march's sampling and the noise's filter floor (110 m), not the edge ramp. A steeper
  ramp on the big cells' upper half made no visible difference.
- The small clouds' cauliflower detail is finer than that floor.
- Both are for a later pass with the tracer's sampling on Ultra.

Tests:
- `SailingSim.Visual.CumulusField` (new) holds the clustering and the size distribution.
- `CumulusSize`, `CloudNoise` (the largest under 15 km^2; small outnumber mid, mid outnumber large) and `CloudLayers`
  pass.
