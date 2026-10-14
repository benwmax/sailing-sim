# Boats and models 9 (PC)

The boat-model items left open by Graphics G8 (both halves), rebuilt on the PC with the new
`scripts\windows\make-boat-models.ps1`. It is the Windows twin of `make-boat-models.sh`: Tools/BoatExport built with
MSVC, then Blender 4.2 headless, then `import_boats.py`.

| Item | Fix |
|---|---|
| Two tiller extensions on the fleet's tillered boats (the Mac's G8 note) | `build_fleet.py` no longer bakes an extension along the tiller. It puts a `TillerEnd` socket on the rudder at the tiller's end, and `ASailboatPawn::TillerEndCm` (unchanged) draws the live one from it. The Hobie 16 keeps its baked extension: it hangs from the middle of the crossbar, which the game doesn't draw. |
| The crew's caps read as domes | `build_crew_gear.py`: the crown is a superellipse (exponent 2.6). It has fuller shoulders and a flatter top at the same height, so the skull still can't come through, and the two front panels stand taller. |
| Keelboats "read flat" | `build_fleet.py` `keelboat_deck_detail` (Catalina 22 and 30) adds an aluminium toe rail along the sheer, horn cleats on the foredeck and both quarters, bow chocks, and three halyards a side from turning blocks at the mast step aft along the cabin top to clutches by the hatch, with their tails coiled beside it (new `Rope` slot, `MI_Boat_Rope`). |
| The helm's foot through the topsides (cockpit stance, crew close-up at 15:00) | Not reproduced on the PC: in the bench's crew close-up and in light air (4 kn) the crew sat where they should. Left open with the stance code (`CrewPose.cpp`, the Mac's), for a capture that shows it. |

Rebuilt and reimported: Sunfish, ILCA 7, Catalina 22, Catalina 30, Corsair 880 (hull, mast, boom, rudder) and the crew
gear (`SM_CrewCap`, `SM_CrewPFD`). Each still matches its physics: LOA and beam to the centimetre, canoe volume within 1%,
centre of buoyancy within 2 mm. The J/22, the Hobie, the Lagoon and the berthed dresses were not rebuilt. The berthed
Catalinas pick up the new deck detail at their next `build_berthed.py` run.

Tests: `test.ps1 -Filter SailingSim.Visual` 18 passed, 0 failed (`FleetMesh`, `J22Mesh`, `MetaHumanCrew` among them).
The Mac gate (build, tests, Medium 60, High 45) runs before the merge.

Windows notes: the editor crashes at shutdown after a big import (the scripts end with `os._exit(0)`), and Windows can
leave that `UnrealEditor-Cmd` as a process that holds its files open and can't be killed until a reboot. Close the crash
reporter first. `run-python.ps1` no longer reads that crash's callstack as a Python error.
