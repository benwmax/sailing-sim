# Galveston water edge: confirmed on the Mac (main c371418e)

The PC's report (inputs a7435e24): at Galveston from Launch 3, the drawn water ends 1 to 2 km out and a flat brown band
shows before the far shore. The Mac reproduces it on main at High with the same args (`galveston-launch3-high.jpg`):

`-SailingWorld=1 -SailingLaunch=3 -SailingTraffic=2 -SailingTrafficNear -SailingHour=11 -SailingCamYaw=120
-SailingCamPitch=-8 -SailingCamDist=90 -SailingNoHud -SailingQuality=High` (`scripts/run-game.sh 12`).

## Separating the suspects (`galveston-launch3-rings-hidebelow.jpg`, the horizon band of each still)

| run | band |
|---|---|
| default (5 rings: the outer ring reaches 512 m) | from about 1 km out to the shore |
| `-SailingWaterRings=3` (128 m) | starts just past the boat |
| `-SailingWaterRings=6` (1 km) | a thin strip near the shore |
| `-SailingWaterRings=7` (2 km) | almost gone (`galveston-launch3-high-rings7.jpg`) |
| HideBelow -0.5 m (temporary local override, not committed) | gone; the water runs to the horizon |
| HideBelow -30 m | the whole bay bed past the rings |

The band recedes as the rings grow, and it goes away when the bed isn't meshed. So it is the bay bed, showing past the
ring mesh. Both suspects take part, but the fault lies with the water.

## Why: the far plane is sunk tens of metres past the rings

Beyond the rings the water is `AWaterSurface::FarPlane`: the engine's Plane mesh scaled to 40 km, one quad with four
vertices. Its material adds the earth's curvature as a world position offset, d^2 / 2R (`CURVATURE_CODE`), and that is
evaluated per vertex. At the corners, 20 to 28 km from the camera, the drop is 27 to 53 m, and it is interpolated across
the whole quad. Past the rings the drawn water therefore lies some 25 to 50 m down, instead of the few centimetres it
should drop 1 to 2 km out. The terrain is meshed at real resolution and gets the true curvature, so any bed above the far
plane shows through. `ALakeTerrainActor::HideBelow` hides only the bed deeper than 3.5 m on the lake and the bay (15 m on
the Gulf). Nearly all of Galveston Bay is shallower than that, so the band runs from the ring's edge to the shore.

## The lake and the Gulf (`lake-gulf-default-vs-rings3.jpg`, wide views from Launch 2)

- **Lake:** at the default rings there's no band from mid-lake (the bed there is deeper than 3.5 m). At 3 rings, dark
  shoal patches show past the ring edge, so the cause is the same and it shows wherever the shallows lie beyond the rings.
- **Gulf:** none at either setting (the bed is below 15 m).

## Owner and proposed fix

Owner: the water (`AWaterSurface`'s far plane), not the terrain. **Proposed fix:** build the far plane as a grid that
continues the rings' geometric spacing out to 20 km (a few more cheap rings, or a radial mesh). The per-vertex curvature
then stays within centimetres of the true drop everywhere, and the shallow bed stays under the water. Raising HideBelow
would only hide the symptom on the bay and would cut the visible shallows.

# The fix (branch water-edge-fix)

`AWaterSurface::FarPlane` is now a procedural grid (`BuildFarGrid`), built with the rings:

- It is made of concentric squares, 44 cells a side. Each square is about one cell larger than the last, evenly spaced
  in log distance. The cells stay about square and grow with the distance, as the rings' do. The grid runs from one
  outer-ring cell inside the outer ring (the rings overlap each other the same way) out to 20 km. Each quad is split
  along its shorter diagonal.
- It sits on the outer ring's snap, 10 cm below the rings, so the rings draw where they overlap it. It used to sit 6 m
  down: bed shallower than that would also have shown above it.
- `HideBelow` is unchanged.

The per-vertex curvature error goes as the cell's size squared over 4R: 2.5 cm at 20 km and at the 28 km corners, on
any ring count. The old quad was 27 m out at the camera. `SailingSim.Visual.FarWaterCurvature` holds it under 3 cm at
3, 5 and 7 rings. The same test checks that the grid starts inside the outer ring, reaches 20 km and is wound like the
rings.

## Stills (High)

- `fix-galveston-launch3-high.jpg`: main against the fix, same args as above. The brown band is gone, and the water
  runs to the horizon.
- `fix-lake-rings3.jpg`: the lake at `-SailingWaterRings=3`, wide from Launch 2. No shoal patches show past the rings.
  The pale streak is a W2 slick, and it is in main's still too.
- `fix-gulf-unchanged.jpg`: the Gulf, main against the fix. The view is the same, including the wake line at lower
  left. The one difference is the horizon, about 12 px higher. It is now the true horizon (about 14 km at this camera
  height); the sunk plane used to drop the far water below it.

## Cost

The first version, 64 cells a side (31k vertices), cost 0.35 ms in the water slice and about 3 fps on every Medium
view. `-SailingFarGrid=<n>` (measuring) showed the cost follows the vertex count (Medium, back to back):

| cells a side | beat15 fps | gulf-sea fps |
|---|---|---|
| 4 (almost no grid) | 83.8 | 103.4 |
| 32 | 83.1 | 102.1 |
| 64 | 80.7 | 99.0 |

At 44 cells a side (14.8k vertices; the five rings have 83k), the curvature error is 2.5 cm. In an A/B against main,
benched back to back, the water slice is 0.2 to 0.3 ms higher, and views are 0.2 to 2.8 fps lower (beam8 High read
4.0 lower once but 60.1 in the gate run). The fastest way to win this back is to skip the waves' vertex work past
their fade (900 m) in M_WaterV4. I left that for after W4, which is rebuilding that material.

`scripts/gate.sh --scope water`: 148/148 tests, pass. Lowest per tier: Medium storm 70.0 fps, High storm 50.8 (slip 51.9).
