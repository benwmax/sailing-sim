# Lagoon 42: the raised helm station (pc/lagoon-helm)

The Mac's fleet sweep found this: on the Lagoon 42, the helm-eye and cockpit views showed only the wheel and the
saloon's opaque aft bulkhead half a metre ahead (`helmeye-before.jpg`, `cockpit-before.jpg`). The wheel stood on that
bulkhead 1 m above the bridgedeck, and the seat was 0.45 m up, 0.5 m aft of it.

On a real Lagoon 42, the helm station is raised on the starboard side at the aft end of the coachroof, so the helmsman
looks forward over the roof. `build_fleet.py` `lagoon_detail()` now builds it that way. Heights are over the bridgedeck
(`dz`). Fore and aft, the seat and the wheel stay where they were:

| | Before | Now |
| --- | --- | --- |
| Helm deck | none | x -3.60 to -2.42, the helm's y ± 0.40, top 0.40, non-skid |
| Step up from the cockpit | none | x -3.90 to -3.60, top 0.20 |
| Seat cushion top | 0.49 | 0.86 |
| Wheel hub (rim 0.36) | 1.00 | 1.19, so the rim's top (1.55) stays under the eye |
| Pod and instruments | at the old hub | raised with the hub |

The bulkhead is not glazed.

A seated eye is about 1.66 m up. The roof at the helm's y is about 1.44, so the view clears it (`new-eye-after.jpg`: a
free camera at the new eye point). `station-after.jpg` shows the station from aft.

The crew: the helm's seat and pelvis come from `CrewMotion.cpp` (the Lagoon's helm pelvis) and `CrewPose.cpp`
(`CrewSeatSurfaceZ`, its seat box: Between + 0.47). Those files are the Mac's. Until the seat box reads Between + 0.84
and the helm's feet stand on the helm deck (Between + 0.38), the helm sits at the old height inside the new seat. The
game's helm-eye and cockpit cameras follow the helm's head, so they look out from there
(`helmeye-after-crew-not-moved.jpg`).

`SailingSim.Visual.FleetMesh` and `SailingSim.Visual.BoatBudget` pass. Only `SM_Lagoon42_Hull` changed.
