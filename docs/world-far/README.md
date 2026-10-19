# The far coast ring (Wide World Rendering, PR 1)

## In plain English

Past 8 km from the camera the coast is now drawn from a separate, cheap "far ring" of land: low-detail terrain built
from a free satellite elevation model (Copernicus GLO-90, about 90 m between points) out to 40 km on Galveston Bay and
the Gulf, 60 km at Marseille. Before, the detailed terrain was drawn out to 20 km and then simply stopped, and outside each
world's map there was no land at all. Now the near terrain stops at 8 km and the far ring takes over seamlessly, so from
a height you see Houston's plain behind Texas City, and the ranges behind Marseille's hills.

What it costs: under a third of a millisecond of GPU time on High, about a tenth on Medium (the budget was 1.0 and 0.6
ms). Every world view still passes the gate (High 45 fps, Medium 60). Sailing at deck level on the flat Texas coast, the
far land mostly sits below the horizon (the earth's curvature hides land a few metres high past about 10 km), so the
Bolivar Roads views look the same as before; that is the right answer, and the hand-over is invisible. In Marseille,
where the land is high, the difference is easy to see.

## How it works

- **Bake** (`scripts/make-far-ring.sh [World ...]`, about 30 s a world): `Tools/terrain/fetch_far_dem.sh` downloads
  the GLO-90 tiles (`Data/Far/raw`, git-ignored; Marseille's come from its own `Data/Marseille/raw/far`),
  `Tools/terrain/build_far_ring.py` writes `Content/TerrainData/<World>.far` (2 s), and the editor builds one Nanite mesh per
  8 km tile in `/Game/World/Far` (`UWorldKitLibrary::BakeFarRing`). Tiles within 20 km of the world's grid are meshed every
  90.9 m, farther ones every 181.8 m (a fine tile's edge follows its coarse neighbour's line, so they meet without cracks).
  Tiles with no land above -1 m are left out.
- **Heights**: inside the world's grid the ring samples the grid itself (so it meets the near terrain); outside, GLO-90
  (EGM2008, taken as NAVD88 on the Texas coast, then the world's NAVD88-to-MLLW; as NGF-IGN69 at Marseille), blended over
  the first kilometre past the grid. GLO-90 is a surface model (buildings and trees in it) with flat water. Land never sits
  below mean high water + 0.25 m, as in the grids. Heights are stored in 1 cm steps, or 5 cm where land rises past 320 m.
- **Material** (`M_FarLand`, `build_far_land` in `make_materials.py`): the near terrain's palette by height above the
  water and slope, kilometre-scale mottling, the baked sky visibility (eight 2 km horizons per vertex) as ambient
  occlusion. Its world position offset is the water's curvature drop (d^2/2R, R = 7/6 earth radius, `CURVATURE_CODE`),
  plus: inside 7.8 km (the hand-over less 200 m) the land is buried 60 m under the water, and out to where a near chunk
  can reach (8 km plus a chunk's diagonal) it sits 2 m lower so the near terrain wins wherever both are drawn.
  `FarRing::OffsetZ` mirrors it and the test holds them together.
- **Game** (`ALakeTerrainActor`, `FarRing.h`): the `.far` index is read on a worker and each tile's package is loaded
  asynchronously (`FFarRingLoader`); the game thread adds at most 8 components a frame (Static, no shadow, not in the
  Lumen scene, the distance fields or ray tracing). Only when every tile is in do the near chunks stop at 8 km (before,
  they draw to 20 km as they did, so nothing goes missing while loading). Chunks past the cap are made invisible, which
  takes them out of the scene, not just out of view. Whole tiles inside the burial or past the outer edge are hidden.
  `-SailingNoFarRing` turns all of it off. Ray Hubbard has no ring and is unchanged.

## Numbers (Mac, M5 Pro, packaged Development, 12 s per view)

GPU ms by slice, ring on / off (`-SailingNoFarRing`), from `scripts/bench-visual.sh` (`Artifacts/visual-bench-far-on.csv`,
`-far-off.csv`). The ring lands in the base pass.

| view | tier | fps on / off | GPU total on / off | base on / off | lumen on / off | render thread on / off |
|---|---|---|---|---|---|---|
| far-coast | Low | 118.7 / 118.8 | 8.62 / 8.36 | 3.29 / 3.26 | 1.16 / 1.16 | 8.31 / 8.31 |
| far-coast | Medium | 95.5 / 96.5 | 10.07 / 9.94 | 3.99 / 4.01 | 1.44 / 1.43 | 10.33 / 10.22 |
| far-coast | High | 64.2 / 64.6 | 14.26 / 13.95 | 5.96 / 5.73 | 1.81 / 1.83 | 15.33 / 15.23 |
| far-coast-night | Low | 118.4 / 118.5 | 7.94 / 8.01 | 2.20 / 2.20 | 1.18 / 1.18 | 8.36 / 8.35 |
| far-coast-night | Medium | 112.6 / 112.3 | 8.41 / 8.43 | 1.99 / 2.00 | 1.42 / 1.43 | 8.77 / 8.80 |
| far-coast-night | High | 78.7 / 79.2 | 11.14 / 11.39 | 2.75 / 2.97 | 1.87 / 1.84 | 12.54 / 12.46 |
| coast-day | Low | 102.8 / 102.6 | 9.57 / 9.63 | 3.78 / 3.86 | 1.21 / 1.21 | 9.60 / 9.62 |
| coast-day | Medium | 82.3 / 82.1 | 11.66 / 11.79 | 5.04 / 5.00 | 1.65 / 1.69 | 11.97 / 12.00 |
| coast-day | High | 54.5 / 54.4 | 17.19 / 17.09 | 8.31 / 8.21 | 2.46 / 2.45 | 18.04 / 18.07 |
| marseille-port | Low | 102.6 / 103.4 | 9.32 / 9.36 | 2.24 / 2.34 | 3.09 / 3.11 | 9.62 / 9.55 |
| marseille-port | Medium | 96.0 / 95.6 | 9.70 / 9.61 | 3.83 / 3.69 | 1.61 / 1.62 | 10.27 / 10.31 |
| marseille-port | High | 62.6 / 63.3 | 13.96 / 13.65 | 5.93 / 5.66 | 2.37 / 2.39 | 15.71 / 15.53 |

The ring's cost is at most 0.31 ms on High and 0.13 ms on Medium in these views (some are within the run-to-run noise
of about 0.2 ms). From 300 m up over Bolivar Roads, where the most ring is on screen, four alternating uncooked runs on
High gave 12.94 and 12.99 ms with the ring and 13.10 and 13.06 without. The render thread did not get measurably cheaper
from capping the near chunks at 8 km in these views (they were already culled past 20 km; most chunks out to 20 km are
open water here), so the saving the plan expected from the cap is small on this Mac.

**World gate** (`scripts/gate.sh --scope world`, High, with the ring on): 195 tests passed; marina 61.4, coast-day 54.5,
coast-night 63.6, helm-eye 60.4, slip 53.6, bridge 65.7, marina-night 59.7, far-coast 64.0, far-coast-night 79.5,
marseille-port 61.8 fps: pass. Medium (the bench above): every view 82 fps or more.

**Bake and pack size per world**

| world | outer edge | tiles (fine) | .far | Nanite tiles (editor assets) | bake |
|---|---|---|---|---|---|
| Galveston Bay | 40 km | 188 (97) | 2.9 MB | 20.5 MB | about 27 s |
| Gulf passage | 40 km | 181 (102) | 2.9 MB | 18.7 MB | about 25 s |
| Marseille | 60 km | 191 (53) | 2.1 MB | 20.2 MB (1.09 M triangles) | 33 s |

The `.far` heights take 2 s per world in Python; the rest is the editor building the Nanite meshes.

## Test: `SailingSim.World.FarRing`

- Coverage: 4,000 points in the band around random cameras in each grid: every point on the grid's land lies in a tile,
  and every point's tile is drawn for that camera (0 misses on all three worlds).
- Seams at the 8 km hand-over: the ring's nodes are the grid's heights (5 mm; 25 mm at Marseille's 5 cm steps). Between
  nodes, against the 10 m grid, 95% within 0.74 m on Galveston Bay and 0.19 m in the Gulf (held to 1 m). Marseille's hills
  can't be followed by a 90 m mesh (95% within 10.9 m of the 10 m grid, 8.4 m of the near terrain's own 80 m mesh at 8
  km); there the test holds the ring to what the near terrain draws (12 m) and the 2 m under-band hides most of it.
- Curvature: `M_FarLand`'s offset is the water's (`7.433e8` cm in both), and `FarRing::OffsetZ` matches `CurvatureDrop`.
- Nothing inside 8 km: any far vertex inside 7.8 km ends at or below -60 m; a tile wholly inside is hidden; near chunks
  stop at 8 km.
- Loading: starting the loader takes 0.02 ms; the longest game-thread call while the 188 Galveston tiles stream in is
  0.4 ms; every mesh arrives, all Nanite.

## Stills (`*-before.jpg` ring off, `*-after.jpg` ring on; High)

- `far-coast-*`, `far-coast-night-*`, `marseille-port-*`: the bench views, packaged build. At deck level they barely
  change (see above), which is the point of the hand-over.
- `bolivar-drone-*`: 300 m over Bolivar Roads looking west-northwest (capture mode, uncooked). With the ring, the
  mainland behind Texas City carries on past 20 km and beyond the bay grid's west edge.
- `marseille-drone-*`: 120 m off the coast looking east: the ring adds the ranges behind Marseille's hills.
- `ring-maps.jpg`: the three rings from above (Galveston Bay, the Gulf passage, Marseille; land shaded by height and
  sky visibility).

## Known gaps

- The Gulf passage's grid has no DEM (its land is flat at MHW + 1.8 m), and inside the grid the ring follows the grid,
  so that land stays flat in the ring too (the dark square in `ring-maps.jpg`). Rebaking the Gulf with a DEM fixes both.
- No land-cover tint yet: the material takes one (vertex green times `Tint`), the bake writes none.
- GLO-90 is a surface model: refinery tanks, tall buildings and tree lines are in its heights as bumps, not models.
- The 90 m mesh can't follow Marseille's ridges at the hand-over (above); a finer inner band (45 m inside the grid)
  would, at about four times those tiles' size.
- Untested on Windows (MSVC-clean by the usual rules; the bake runs in the editor there the same way).
