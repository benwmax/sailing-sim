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
