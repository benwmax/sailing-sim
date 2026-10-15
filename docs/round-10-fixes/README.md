# Round 10 fixes: the Laser sailor and the Gulf front's buildings

Blind round 10 caught all ten game frames. On the Mac's side of the split, Bean's tells were still 03
(`r10-lake-laser`, "clouds, person") and still 16 (`r10-gulf-pier`, "clouds, odd buildings on shoreline"). The clouds
are the PC's (W5a). This round fixes the person and the buildings. Both stills were retaken with the same
`scenes.csv` rows (`scripts/capture-scenes.sh 18`, `SCENES=docs/round-10-fixes/scenes.csv`).

## The ILCA sailor (r10-lake-laser)

![before / after](laser-before-after.png)

*Left: round 10. Right: now. Same scene row, 18 s in.*

What read as fake:

- **He slid in and out across the cockpit.** On a 16 kn reach the auto-trim holds the ILCA flat by moving the
  sailor at up to 2.5 m/s with every roll. Run standalone, it moved him 47 m a minute, and a third of the time he was
  inboard of the deck edge, sometimes all the way to leeward (hike −0.4 to +0.4 every second in the telemetry). Every
  fast move inboard also tripped the tack's crossing crouch. I tried changing the physics so he stays on the windward
  deck (a hike floor in a breeze, with a quick move in on a windward roll). It halved the crossing, but both ILCA
  speed checks then capsized (`ILCA 7 broad reach, 22 kn` and `16 kn gusting 22`: heel 113 and 180 deg). So the
  physics is unchanged, and the fix is in the figure:
  - The figure follows the crew model's offset through a critically damped spring (about 0.6 s; dinghies only).
  - Hiking moves no longer count as a crossing unless he passes within 0.2 m of the centreline.
  - His seat slides along the side deck (cockpit edge + 0.14 m to the deck edge) instead of staying pinned at the
    edge with an upright body.
  - The hike is measured from the deck edge to fully hiked (sit-out plus hike-out). Before, it was measured from
    80 % of the sit-out, so he sat bolt upright at the edge.
  - He moves aft with `CrewOffsetX` as she gets on the plane, as the physics already does.
- **His hands floated in the air.** The extension grip was at hip height beside the aft shoulder, and the sheet came
  off the transom traveler. Both were out of reach, so the round-10 frame shows both arms held out to the sides.
  Now, in the dinghy stance, the aft hand holds the extension across the body at the waist (the dagger grip) and the
  forward hand holds the sheet just ahead of it, a hand's width apart along the boat (closer together, they read as
  folded arms). The stance's elbows hang nearer the sides (65 deg down, not 40). The ILCA's sheet now leads from
  the boom-end block forward under the boom to a mid-boom block, down to a ratchet block on the cockpit floor, and up
  to his hand. The extension runs a hand's width past the grip.
- **He sat like he was in a chair.** Sitting out, the legs now reach across the well to the strap on the centreline
  (knees bent half as much, the feet planted on the floor by the existing IK), and the body leans back from the start
  (−20 deg, −70 hiked).

On this reach the physics really only asks him to sit out: the crew offset is 0.55–0.75 m, against 1.1 m fully hiked.
Upwind in 16 kn he hikes flat out, legs nearly straight, the extension in hand:

| reach, abeam (round-10 framing) | upwind, 16 kn, from windward |
|---|---|
| ![](ilca-reach-abeam.png) | ![](ilca-upwind-hiking.png) |

## The Gulf front (r10-gulf-pier)

![before / after](pier-before-after.png)

*Left: round 10. Right: now. Same scene row and drone camera.*

What read as odd:

- **The Pleasure Pier's buildings stood in the Gulf.** Its restaurant and shops (OSM footprints, lidar roofs 4–6 m
  above the 10 m deck) were measured from the ground under them, which is the water. The house kit built them from
  the sea bed up as 14 m blocks with suburban hip roofs, inside the pier's piles. Now, at bake time
  (`BuildHouseGeometry`), any footprint over a lidar deck on piles (`Lake.Decks`, the same outlines the shore bake
  draws) stands on the deck. Its eave and roof are measured from the deck: a storey at least, 12 m at most.
- **The pier's deck was mostly missing.** The ear clipping gave up partway round its 235-point lidar outline. Where
  the triangulation covers less than 97 % of an outline, the deck is now filled in 2 m cells. Decks over 2.5 m above
  the water also get an underside and a pile bent every 6 m under them, not only round the edge.
- **Tall blocks were suburban houses.** For buildings of 10 m and up, the lidar eave fit often took a podium, an
  annex or a parapet's shadow (a 32 m block had a 5.9 m eave, so it became a 5.9 m box under a huge roof). Now
  `build_houses.py` takes the block's height from the median of its lidar roof grid (or the top less a metre when the
  grid saturates at 25.5 m), with OSM's levels at 3 m a floor as a floor under it. From four storeys up a block gets a
  flat roof with a parapet and rooftop units, unless the lidar fitted a real pitched roof (Hotel Galvez). That's 1,670
  blocks on the Galveston side and 91 at the lake. The house kit had drawn full-detail windows on the first three
  storeys only. Tall blocks now get the material's painted windows on every storey, and seven in ten get balconies on
  the side facing the water: a slab per storey, glazed doors, a glass balustrade on a rail, and a fin between units.
- **Flat colours.** On the coast, tall blocks and pier buildings are mostly stucco in a paler Gulf palette (whites,
  sand, cream, pale coral, aqua, yellow, grey-blue), not North Texas brick and greys.

Up close, from a boat off the pier and the Seawall:

| Pleasure Pier | the Seawall east of it |
|---|---|
| ![](pleasure-pier-close.png) | ![](seawall-close.png) |

From 4 m up and 200 m off, the 10 m deck's underside is a sliver and you see under the pier between its piles, as
you would for real.

Rebaked: `Tools/terrain/build_houses.py RayHubbard GalvestonBay` and `scripts/make-houses.sh` (553 + 1,202 Nanite
tiles), then `scripts/bake-shore.sh GalvestonBay` (509 tiles). `M_WaterV4`, `make_materials.py` and
`WaterSurface.cpp` are untouched (the PC's W2).

## Checks

- `scripts/test.sh`: 131 passed, 0 failed (`SailingSim.Visual.MetaHumanCrew`, `CrewFeet`, `CrewMotionFeet` and
  `CrewPose` among them).
- `scripts/reference-checks.sh --quick`: unchanged from main (the physics is untouched; the only check outside its
  range is the known Hobie 16 Portsmouth ratio).
- bench-visual (packaged, 12 s, `bench-visual.csv`) against the bench-fix baseline:

  Lowest per tier: **Medium, storm 67.9 fps** (gate 60), **High, slip 46.8 fps** (gate 45). Views are 0–2.5 fps
  under bench-fix's run, including the lake and open-sea views this round doesn't touch (gulf-sea −2.5, beam8 −1.3),
  so most of that is run-to-run drift; storm on High reads +2.6.

| view | tier | fps | p99 ms | GPU ms | bench-fix fps | Δ |
|---|---|---|---|---|---|---|
| beam8 | Medium | 89.6 | 12.32 | 10.59 | 90.9 | -1.3 |
| beam8 | High | 54.8 | 20.31 | 17.07 | 56.3 | -1.5 |
| beat15 | Medium | 88.3 | 12.59 | 10.8 | 89.5 | -1.2 |
| beat15 | High | 53.3 | 23.06 | 17.72 | 55.1 | -1.8 |
| storm | Medium | 67.9 | 16.41 | 15.1 | 69.2 | -1.3 |
| storm | High | 50.1 | 23.28 | 19.67 | 47.5 | +2.6 |
| marina | Medium | 88.2 | 12.68 | 11.38 | 90.7 | -2.5 |
| marina | High | 49.2 | 22.75 | 18.39 | 51.7 | -2.5 |
| coast-day | Medium | 80.7 | 13.04 | 12.16 | 82.6 | -1.9 |
| coast-day | High | 47.3 | 22.31 | 16.24 | 48.9 | -1.6 |
| coast-night | Medium | 102.7 | 10.55 | 9.43 | 103.2 | -0.5 |
| coast-night | High | 51.9 | 20.55 | 13.22 | 52.3 | -0.4 |
| gulf-sea | Medium | 107.6 | 9.82 | 8.93 | 110.1 | -2.5 |
| gulf-sea | High | 60.8 | 17.64 | 13.52 | 62.4 | -1.6 |
| helm-eye | Medium | 81.4 | 13.43 | 11.62 | 83.7 | -2.3 |
| helm-eye | High | 47.3 | 23.2 | 20.74 | 49.0 | -1.7 |
| slip | Medium | 74.7 | 15.51 | 13.33 | 75.8 | -1.1 |
| slip | High | 46.8 | 23.55 | 19.61 | 46.8 | +0.0 |
| bridge | Medium | 96.7 | 11.05 | 9.53 | 99.0 | -2.3 |
| bridge | High | 54.4 | 20.32 | 14.88 | 55.7 | -1.3 |
| crew | Medium | 72.8 | 14.54 | 13.02 | 74.1 | -1.3 |
| crew | High | 47.1 | 23.4 | 20.02 | 47.6 | -0.5 |
| marina-night | Medium | 79.1 | 14.34 | 12.9 | 81.9 | -2.8 |
| marina-night | High | 52.1 | 21.3 | 18.31 | 53.0 | -0.9 |

- bench-phase5 (Medium, packaged, 12 s), A/B in this checkout with main's baked tiles and this branch's
  (`phase5-bench-main.csv`, `phase5-bench.csv`):

  Every view is within 1.1 fps of main. (gulf-swell's earlier numbers, 87.0 coast-day and 113.1 coast-dusk, were
  taken before the bench fix, when phase 5 still sailed the saved Lagoon 42 with no MetaHuman crew.)

| view | main tiles, run 1 / 2 | this branch | Δ (mean of main) | p99 main / branch |
|---|---|---|---|---|
| coast-day | 80.6 / 81.5 | 80.8 | -0.2 | 13.03 / 12.89 ms |
| coast-bay | 76.8 / 76.4 | 77.5 | +0.9 | 14.0 / 13.9 ms |
| coast-night | 100.7 / 101.1 | 100.4 | -0.5 | 10.72 / 10.83 ms |
| coast-dusk | 104.2 / 105.3 | 104.4 | -0.3 | 10.38 / 10.36 ms |
| chart | 119.7 / 119.7 | 119.7 | +0.0 | 9.25 / 9.07 ms |
| chart-bay | 119.7 / 119.7 | 119.6 | -0.1 | 8.94 / 8.82 ms |
