# Round 12: the towers at Kemah

Round 12 found too many towers clustered at Kemah, all drawn as water towers. Three changes:

- **Merge.** `LandmarkPlacements` (`LandmarksActor.h`) now draws one landmark of a kind within 100 m. Platforms keep the old
  5 m merge, because a gas field's wells stand closer together than 100 m. The chart places six towers within 600 m of
  the origin: two exact duplicates, and two pairs 62 m and 81 m apart. Three are now drawn. Across the bay 195 landmarks
  were drawn before and 186 now, including the new water tower.
- **Slim towers.** A generic charted tower (`CATLMK` 17, "Tower", no name) is drawn as the slim lattice tower
  (`SM_Landmark_Mast`) at 45 m when the chart gives no height, not as the 41.6 m Texas spheroid. The Gulf world's generic
  towers change in the same way.
- **The real water tower.** Kemah's water tower is in OpenStreetMap (`man_made=water_tower`, 29.5386 N, 95.0280 W) but not
  on the chart. `build_galveston.py` now adds it as a "Water tower" landmark at sim (-665, -843), about 1.1 km south-west
  of the origin. `GalvestonBay.json` gets the same entry, in the place the bake would put it: after the charted
  landmarks, before the platforms. Adding it shifts the platforms' list indices, so their seeded yaws change too.

`SailingSim.Coast.Landmarks` checks the following:
- No two landmarks of a kind are drawn within 100 m.
- Kemah's generic towers come out as 1-3 drawn towers.
- Every generic tower is the slim tower, 45 m tall when the chart gives no height.
- There is exactly one water tower from OpenStreetMap, where it should be.

The test result on the PC was 152/152, with this test passing.

Stills are from the packaged game on the PC (Ultra). The camera is fixed in the world at the "Kemah channel, outbound"
launch spot, looking west-south-west:

- `kemah-from-channel-60m.jpg`: from 60 m up. From the water the shore's trees hide the tower, as they would in reality
  at 2 km.
- `kemah-water-tower-crop.jpg`: the water tower over Kemah's trees, enlarged.
- `kemah-slim-tower-crop.jpg`: a merged generic tower at water level, now a thin lattice tower behind the shore houses.
