# W2: wind on the water (PC graphics, Mac gates)

Plan: the Claude Doc "Water and weather realism plan", section W2. Branch `w2-wind-water`, built, tested, packaged and
benched on Bean's PC (RTX 4090, i9-9900K) on Oct 15 2026.

## What it does

- **Two-level wind map** (`AWaterSurface::UpdateWindLevel`). Near: 256² over 3.2 km (512² on Ultra); far: 128² over
  16 km. Both maps wrap around (the texel for world cell i is stored at i mod Res), so they scroll with the boat by
  refreshing strips (8 per 0.1 s tick, 16 on Ultra) and never re-upload the whole map. A jump of more than a quarter
  of the map refreshes it all. The near map samples `FWindField::VelocityAt`; the far map samples `ReadableAt` and
  `MeanSurfaceRoughnessAt`. Per texel the map carries the local direction (G, B), the surface roughness (R) and the slow
  wind (A, the 30 s mean that drives slicks). The material blends near → far → mean wind by distance.
- **Cat's paws as roughness.** Each texel's roughness rises toward the wind's over 2 s and falls over 10 s (the plan's
  1–3 s rise and 5–15 s settle). The chop doesn't change with a single puff.
- **Ripples turned to the local wind.** The ripple tile is sampled in two frames rotated in 15° bins and blended, with
  the slopes turned back, so there's no seam when the wind turns. Cap streaks run along the local wind.
- **Glassy lulls** where the local wind is under 1.5–3 m/s (`glass` in `M_WaterV4`, now from the map, not the boat).
- **Slicks** are smooth bands along the slow wind, fading out between 3.5 and 6 m/s.
  **Windrows** appear from 3 m/s: dashed lines along the wind about 14 m apart, with faint foam lace, fading by 260 m.
  Their direction is smoothed over 120 s, so they realign over minutes after a shift.
- **Whitecaps cluster in puffs.** The lake's cap threshold now scales with the wind:
  `CapSlopeAt(U) = 0.034 (U / 10 kn)^0.773` (mirrored in C++ by `AWaterSurface::CapSlopeAt` / `WhitecapThreshold`).
  `SailingSim.Visual.Whitecaps` holds the lake band at every wind again (it failed above 18 kn): 2.1× of 0.4·Monahan at
  20 kn and 1.8× at 25 kn. The sea stays 1.6–2.1× Monahan (its `FoamThreshold` is W4's).
- **Polarized sunglasses**: `sailing.Polarized 1` in the console, or `-SailingPolarized`. The material cuts the sky's
  specular near Brewster's angle (up to 80%). There is no key binding yet; the Mac's input code can add one.
- **Trees read the local wind.** `AWaterSurface::BindTreeWind` (every 3 s) swaps the `M_Tree*` materials on the
  terrain's instanced components for one dynamic instance per material, bound to the far map (`WindFar`,
  `WindFarRect`). Each tree then sways with the wind's direction and speed where it stands. Logged as "Water: trees
  read the local wind (M_TreeCrown)" (seen in the packaged game). `-SailingNoTreeWind` leaves them on the global wind.
- **Flags:** the game has no flag actors yet, so there is nothing to bind. Other boats' telltales already read each
  boat's own wind.
- **Gulf-swell handoffs:**
  1. Low's Galveston tint goes to `OceanColor`, blended by the swell mask, so it no longer tints the whole bay.
  2. Medium and High blend the Gulf's water body (`WaterAlbedoSea`, `WaterExtinctionSea`) by the mask.
  3. Both water materials skip the ocean term where the mask is 0, in the vertex and pixel shaders.
- **Boats:** `M_BoatSurface`, `M_BoatMast` and `M_J22HeroSurface` are now `used_with_nanite`.

## Stills (Ultra, packaged, lake)

| | |
|---|---|
| ![glass](glass-4kn.png) 4 kn: glassy, mirror reflections | ![puffs](puffs-16kn.png) 16 kn: rough water, caps in clusters |
| ![windrows](windrows-8kn.png) 8 kn: windrows and slicks (faint at this distance) | ![trees](trees-12kn.png) 12 kn: shore trees on the far map |
| ![glare](glare-8kn.png) 8 kn, 17:00, no glasses | ![polarized](polarized-8kn.png) same with `-SailingPolarized` |

The polarized pair barely differs from this camera. The cut is strongest looking down-sun at about 37° below the
horizon; a better pair would face the sun. The 36 bench views are in `bench/` (JPEG).

## Cost

Main `b219e6e` (after #48) re-baselined first on the same PC, then W2 merged with it (`cdce43e`, plus the measuring
argument). 1920×1080, 12 views per tier (`visual-bench-main-b219e6e.csv`, `visual-bench-w2.csv`, per view in
`compare.csv`):

| Tier | Main b219e6e fps | W2 fps | GPU ms | GPU water slice ms |
|---|---|---|---|---|
| Medium | 86.8 | 83.7 (−3.1) | 3.20 → 3.40 | 0.24 → 0.26 |
| High | 76.5 | 73.4 (−3.1) | 4.75 → 4.79 | 0.33 → 0.35 |
| Ultra | 73.1 | 69.8 (−3.2) | 6.92 → 7.13 | 0.34 → 0.36 |

On the default bench (`bench-win.ps1`, 20 s): Low 129.3 → 126.9, High 76.0 → 69.6, Ultra 72.2 → 67.7. Main's Medium
read 56.0 against 83.0 for W2, so that main run was an outlier.

The GPU cost is about 0.02 ms. The fps cost is on the CPU: the PC runs bound by the render thread (14–16 ms against a
6–9 ms GPU frame). `windmap_cpu_ms` (new in bench.json) is the wind-map fill on the game thread: 0.19 ms on Low,
0.29 on Medium, 0.38 on High and 0.62 on Ultra (the 512² near map).

The crew view loses more: Ultra 68.1 → 57.0 in the sweep, and 61–65 in four reruns (runs vary by about ±3 fps).
The tree swap isn't the cause; `-SailingNoTreeWind` measured the same. It's still open.

The obvious follow-up is moving `UpdateWindLevel` to a worker (the wind field is a pure, seeded function of place and
time) and uploading from the game thread.

## Earlier PC Ultra numbers

Before #48, measuring runs read the saved session and settings. So PC Ultra benches from Oct 14 20:34 UTC up to #48
may have sailed the Lagoon at Galveston instead of the scene asked for, and their numbers are suspect. The baseline
above was measured on main `b219e6e`, after the fix.

## Tests

`scripts\windows\test.ps1`: 131 / 131 pass on the merged branch.
