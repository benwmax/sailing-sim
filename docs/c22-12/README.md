# Catalina 22 rebuild, slice 11 (cloud half): game wiring

The rebuilt Catalina 22 (`Tools/shipkit/catalina22`, slices 0 to 10) goes into the game as the player's Catalina 22. Until
it is imported, the fleet model (`/Game/Boats/Catalina22`, `Tools/blender/build_fleet.py`) stands in, so nothing changes
in the game when this lands; it changes the day the Mac or the PC runs `scripts/make-c22-hero.sh` (or
`scripts\windows\make-c22-hero.ps1`).

## The path

1. `build_c22.py <dir>` builds `c22.blend`, `c22_sockets.json` and `c22_report.json` (about 2 minutes in Blender or the
   `bpy` module).
2. `export_game_c22.py <build dir> <out dir>` cuts it into the game's parts as `game_c22.json` says and writes
   `SM_C22Hero_{Hull,Mast,Boom,Rudder}.fbx` (and `SM_C22Hero_Interior.fbx` once the build has slice 7's cabin) and
   `C22Hero_sockets.json` in `import_boats.py`'s form:
   - **Hull** (Nanite): shell, deck, cabin with the pop-top down, ports, keel down and its stub, gudgeons, the outboard,
     deck hardware, lifelines and the rig fittings off the mast. The shell's one gelcoat is cut at the fleet's paint lines
     (bottom under 5 cm, boot stripe to 11 cm, topsides above), so the livery colours her until slice 8's textures.
   - **Mast** (not Nanite: `M_BoatMast` bends it; checked under 40k triangles): mast, its hardware, the halyards at rest
     and the rig fittings on the mast (the loose parts of `C22_RigFittings` whose centre is over 1.2 m and within
     0.85 m of the mast).
   - **Boom** about the build's gooseneck; **Rudder** (blade down, head, tiller) about the pintles' axis at the waterline.
   - **Interior** (optional): the `C22_Interior*` objects, the table up and the galley in.
   - Left out: the standing rigging and running rigging (the game draws them live from the sockets), every sail state
     and the cover (the game's sails are cloth from the physics), the raised pop-top, the keel up and the rudder kicked
     up (states for a later switch).
   - Sockets: the build's (rig and hardware) with their parts renamed, plus `RudderPivot`, `RudderStock`, `TillerEnd`
     (from `keel_c22.json`) and `Gooseneck` (the build's boom origin). The export stops if one the pawn reads is missing.
3. `scripts/import_boats.py c22hero` imports them to `/Game/Boats/C22Hero` (Nanite with a 6% fallback, no berthed dress).

`scripts/make-c22-hero.sh [--no-import]` runs all three (the build only when a source is newer than the `.blend`;
`C22_REBUILD=1` forces it). `BLENDER=<a python with bpy>` works too.

## In the game

`ASailboatPawn::UseC22Hero`: every Catalina 22 under sail (the player's, the gallery's, AI boats and the ghost; AI boats
since Nov 18, Bean's choice) draws `/Game/Boats/C22Hero` once it exists. The cabin below stays on the player's boat only.
Marina neighbours tied up in their slips keep their berthed dress (`SM_Catalina22_Berthed_*`, on her new hull since
slice 10). `-SailingClassicC22` keeps the fleet model everywhere, for compared stills and benches. The showroom's async load (`ModelAssetPaths`) follows
the same choice. The hull carries its own outboard and traveller (`bOwnOutboard`, no traveller bridge).

She is already on the Boat screen in a slice build (`SailCatalog::InSliceBoat`) and in the career (Coastal Cruiser's
boat, opened by Day Sailor's certificate; the tier's lessons are still to come).

## The test

`SailingSim.Visual.C22HeroMesh` holds the imported model to `FBoatConfig::Make(Catalina22)`, as `J22Mesh` holds the J/22:
the canoe body's length and beam to the physics hull (2 cm), the draft keel down to `Draft` (2 cm), its volume (2%) and
centre of buoyancy (2 cm) to the hydrostatics, `MastStep` on `MastX` (1 cm), the build's `Gooseneck` on
(`MainLuffX`, `BoomZ`) (2 cm), the hounds over the genoa's head, every socket the pawn reads, the hull Nanite and the mast
not, and a boat material on every slot. Without the import it is skipped with a warning.

## Today's build against today's physics (Nov 17)

From `export_game_c22.py` on main's slices 0 to 6 (cloud, `bpy` 5.3):

| | model | physics today |
|---|---|---|
| length (canoe) | 6.550 m | 6.55 |
| beam | 2.338 m | 2.34 |
| draft, keel down | 1.552 m | 1.52 |
| canoe volume | 1.238 m³ (hull 1.220 + keel stub) | the formula hull's |
| gooseneck (x, z) | (0.78, 1.565) | (0.82, 1.45) |
| triangles | hull 249k, mast 30k, boom 1k, rudder 17k | |

The draft (the model floats with the crew aboard: `specs_c22.json` `crew_sink_m`), the gooseneck (Bean's boom +11.5 cm)
and the hull's volume and centre are what slice 10 (the physics hull) brings into line; the test fails until it lands, so
import after it.
