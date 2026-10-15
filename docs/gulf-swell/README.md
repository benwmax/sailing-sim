# Gulf swell in the Galveston world

The gap noted in #42 was that the Galveston world's Gulf front (the Seawall, the jetties and the piers) showed bay chop
only. The Gulf world had `FOcean` swell, but Galveston had no ocean at all. This branch gives the Galveston world the
same ocean, with a mask that keeps the swell on the Gulf side, lets part of it in through Bolivar Roads, and keeps it
out of the bay and Clear Lake.

It does not touch `M_WaterV4`, `scripts/make_materials.py` or `WaterSurface.cpp`. `AWaterSurface::UpdateOcean` already
uploads the ocean grids and the mask for any world whose wave field has an ocean, so the Galveston world draws through
that path as it stands. A few follow-ups for the PC's W2 are listed at the end.

## What changed

- **Galveston is an ocean area.** `GalvestonBay.json` has `"ocean": true`, and so does `Tools/coast/build_galveston.py`
  for the next rebake. `ASailingGameMode::InitGame` therefore builds an `FOcean` for it. `UpdateOcean` is unchanged: the
  Gulf climatology picks the swell by weather preset (0.5 to 1.4 m, 8 to 9 s, from 135°), and `-SailingSwell` still
  overrides it. `-SailingNoOcean` turns the ocean off, for comparison runs on the same build.
- **A new mask** (`FOcean::BuildMask`). The old exposure counted open water toward the swell up to the first land,
  SmoothStep from 3 to 12 km. Inside Galveston Bay that reads the bay itself as open sea: from Kemah there are 25 to
  30 km of water toward the southeast. The new exposure is the share of the swell's directional spread that reaches a
  point from the open Gulf in straight lines:
  - **Land grid.** Land is marked on the 100 m mask grid if any 10 m terrain node in the cell is above the water, so a
    seawall or jetty one or two nodes wide still blocks the swell.
  - **Rays.** 19 rays run toward where the swell comes from, over ±45° with cos² weights. That is the narrow swell
    widened by refraction and diffraction at a gap.
  - **Open or shut.** A ray is open only if it leaves the chart over water at least 4 m deep. The Gulf qualifies; East
    Bay and West Bay, where the chart's edge cuts them, are about 2 m deep and do not. Any land on the way shuts the ray.
  - **What that gives.** Behind the barrier every ray is shut. In Bolivar Roads only the rays through the jetties' gap
    are open, and that share falls with distance from the gap. Height follows the square root of the energy share.
  - **Grid.** Exposure is computed on a 200 m grid. Coarse nodes that land on land take the mean of the water nodes
    around them, so the sea reaches the beach instead of fading out a cell short of it. The existing depth limit
    (breaking at about 0.6 × depth) takes the sea down across the shoals.
  - **Build time.** About 40 ms on the Galveston grid and 0.3 s on the Gulf world's. It runs on the game thread at
    start and again when Hs changes by more than 15%.
- **The boat feels the ocean only where the mask lets it in.** Two things ignored the mask before. They didn't matter
  in the Gulf world, but in Galveston a boat in Clear Lake would have felt the Gulf swell:
  - **Added resistance.** `FWaveField::Bands()` added the ocean's bins wherever the boat was. `FBoatModel` now scales
    them by `OceanShareAt` (mask²) at the boat's position.
  - **Sea height.** `FWaveField::SignificantHeight()` included the full swell. The HUD, the logbook's sea and the
    hull's splash band now use `SignificantHeightAt`. Heave and pitch were already masked, because `Height`/`Sample`
    multiply by the mask.
- **Tools.** `scripts/ocean-mask.sh [GalvestonBay|GulfPassage] [Hs]` builds the physics standalone (`Tools/OceanMask`).
  It prints the mask at named points and the build time, and writes `Artifacts/ocean-mask-<World>.pgm`.
  `bench-phase5.sh` takes `EXTRA_ARGS` (for example `-SailingNoOcean`).

## The mask

Light is open sea and mid-grey is water with no swell; land is dark. The Galveston grid is on the left and the Gulf
world's on the right.

![Galveston mask](mask-GalvestonBay.png) ![Gulf mask](mask-GulfPassage.png)

| Point (Galveston world) | Mask | Depth |
|---|---|---|
| 1 km off the Seawall at 25th St | 1.00 | 5.9 m |
| Pleasure Pier end | 1.00 | 2.9 m |
| Off 61st St | 1.00 | 4.0 m |
| Between the jetty heads | 1.00 | 9.0 m |
| Bolivar Roads (launch 5) | 0.29 | 6.0 m |
| Galveston Channel, Texas City Dike, Red Fish Bar, West Bay | 0.00 | |
| Clear Lake | 0.00 | 2.0 m |

In the Gulf world, the point the old test called "inside Bolivar Roads" goes from under 0.1 to 0.37. Offshore and West
Bay are unchanged at 1.00 and 0.00. `SailingSim.Physics.OceanSpectrum` now expects a reduced swell there (under 0.6)
instead of none.

## Tests

`SailingSim.Coast.GalvestonSwell` is new. It checks the mask, the sea height and the boat:
- **Mask.** Above 0.95 off the Seawall, above 0.9 at the Pleasure Pier and between the jetty heads, between 0.05 and
  0.6 in Bolivar Roads, under 0.1 at the Texas City Dike, and exactly 0 in Clear Lake. The build takes under 0.5 s.
- **Sea height.** Clear Lake's `SignificantHeightAt` is the chop alone. Off the Seawall it carries the swell.
- **The boat.** A J/22 close-hauled in 12 kn sails 5.94 kn in Clear Lake with or without the ocean (identical). Off the
  Seawall she sails 5.94 kn without it and 5.55 kn in the swell.

`scripts/test.sh` passed all 128 SailingSim tests.

## Stills (before | after)

These are the round-10 views, captured in the capture mode on the uncooked game at High (`scenes.csv`). Before is the
same build with the ocean off. The telemetry beside each shot has the boat's motion.

| View | Pitch max, before → after | Water height σ at the boat, before → after |
|---|---|---|
| Pleasure Pier, 11:00, 12 kn (swell 0.9 m) | 0.7° → 5.5° | 0.02 → 0.28 m |
| 61st St at dusk, 6 kn (swell 0.5 m) | 1.1° → 4.9° | 0.01 → 0.06 m |
| Bolivar Roads, outbound, 14 kn | 1.9° → 4.5° | 0.03 → 0.08 m |

![Pleasure Pier](compare-gs-pier.jpg)
![61st St at dusk](compare-gs-dusk.jpg)
![Bolivar Roads](compare-gs-jetties.jpg)

Full-size shots are in `before/` and `after/`.

## Performance (packaged, Development)

**bench-phase5 (Galveston, Medium).** Each figure is the mean of two runs; ocean off is the same build with
`-SailingNoOcean`. Raw runs are in `phase5-bench.csv`. Every view is within 2 fps. The water's GPU slice rises 0.0 to
0.17 ms, because the ocean term is drawn everywhere and masked in the shader.

| View | Ocean off | Ocean on | Δ fps | p99 off / on | Water GPU off / on |
|---|---|---|---|---|---|
| coast-day | 88.7 | 87.0 | -1.8 | 11.95 / 12.14 ms | 1.50 / 1.67 ms |
| coast-bay | 80.0 | 79.5 | -0.5 | 13.48 / 13.53 ms | 1.57 / 1.64 ms |
| coast-night | 103.6 | 102.2 | -1.4 | 10.61 / 10.76 ms | 1.34 / 1.48 ms |
| coast-dusk | 110.9 | 113.1 | +2.1 | 9.88 / 9.74 ms | 1.48 / 1.50 ms |
| chart | 119.7 | 119.6 | -0.1 | 9.31 / 9.53 ms | |
| chart-bay | 119.7 | 119.7 | 0.0 | 8.79 / 8.73 ms | |

**At the Gulf front itself** (the Pleasure Pier view, two runs each, `front-bench.csv`):

| Tier | Ocean on | Ocean off |
|---|---|---|
| Medium | 89.1 and 89.0 fps | 90.0 and 89.7 fps |
| High | 49.9 and 50.2 fps | 49.6 and 49.6 fps |

**Gates (bench-visual, `bench-visual.csv`).** Both hold:
- Medium: lowest is 68.8 fps (storm), against a gate of 60.
- High: lowest is 46.7 fps (slip), against a gate of 45.
- Coast-day High is 49.5 fps (mac-polish: 49.9) and coast-night High is 51.3 (52.4). Gulf-sea is unchanged at 61.0
  (61.1).

## Handoff for the PC's W2 (the three files this branch doesn't touch)

From reading the code (not measured):
1. **Low tier tint.** `AWaterSurface::UpdateOcean` sets M_Water's `WaterColor` to the Gulf's blue-green the first time
   an ocean exists. That was right for the Gulf world, but in the Galveston world it now tints the whole bay on Low.
   Fix: set it only for World 2, or blend toward it by `OceanMask`.
2. **Water body on the Gulf front.** On Medium and High the Galveston world uses one water body everywhere
   (`WaterBodyFor(1)`, the silty bay). The Gulf front could blend toward `WaterBodyFor(2)` by the ocean mask, which the
   material already has (`OceanMask`, `OceanMaskRect`).
3. **Cost in the bay.** The ocean term is evaluated over the whole water ring even where the mask is 0 (the 0.1 to 0.17
   ms above). A branch on the mask, or skipping the ocean grid samples when the mask is 0, would win that back in the
   bay.
