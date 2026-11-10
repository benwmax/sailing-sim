# Hardware fit, wave 1: the kit's deck hardware on the hero J/22 (Nov 8 2026)

Bean's hardware sheet (Nov 8) sent each fitting through the part detail loop (docs/part-detail-loop). This is the first
step of putting the rebuilt parts on a boat: the plan is the Claude Doc "Fitting the new hardware to the boats"
(https://claude.ai/artifact/LjJQXzXbXhbt869TrrxuDz). The hero J/22 (Inputs/j22-hero) drew its own simple copy of
almost every part; wave 1 swaps those for the kit parts at the same spots, so nothing on the boat moves.

| Where | Before (the hero's own) | Now (the kit's) | How many |
|---|---|---|---|
| Jib sheet cams on the cockpit walls (`Cam_*_0`) | `j22_details.cam_cleat` | `CamCleat` | 2 |
| Halyard cams on the cabin top (`HalCam_*`) | the same | `CamCleat` | 4 |
| Spinnaker sheet cams beside the cockpit (`SpinCam_*`) | the same | `CamCleat` | 2 |
| Turning blocks beside the mast step (`Turn_*`), spinnaker quarter blocks (`SpinAft_*`), twinger blocks (`SpinTwing_*`), pole downhaul (`PoleDownhaul`) | `j22_mastgear.cheek_block` on `j22_details.padeye` | `Block40` (scaled to 35 or 29 mm where the hero had those) standing on a `Padeye`, its shackle pin through the eye | 7 blocks, 7 pad eyes |
| Spinnaker lead blocks on their spring stands (`SpinLead_*`) | `cheek_block` | `Block40` on the stand | 2 |
| Backstay cascade block (`BS_cascade`) | `j22_details.block` | `Block40` | 1 |
| Backstay bridle ends (`BS_eye_*`, `BS_sh_*`) | `j22_details.padeye` | `Padeye` and a `ShackleBow` through it; the bridle ties to the shackle | 2 + 2 |
| Rudder (`Pintle_*`, `Gudgeon_*`) | `j22_steering.build_pintles`, `build_gudgeons` | `Pintle` on the blade, two strap `Gudgeon`s either side of each (as `partloop/render_rudder_assembly.py`) | 2 + 4 |

Two old misplacements the renders showed, fixed in kit mode only:

- The lower pintle was at z 0.05, below the transom (flat down to z 0.225 on the centreline; below that the bottom
  curves forward), so its gudgeons hung in open water. The kit's lower pintle sits at z 0.27, so both of its gudgeons
  bear on the flat transom at its bottom edge, as on the real J/22 (`j22_kitfit.LOWER_PINTLE_Z`). The blade is unchanged.
- Each transom corner had both a stainless plate (`BS_plate_*`, build_hardware) and the bridle's pad eye inside it. The
  kit's pad eye and bow shackle are that fitting, so the plate is left out.

The cabin-top winches were already the kit's `WinchPlain` (docs/part-detail-loop/winch.md). Not in this wave: the
mainsheet and traveller cams, the cunningham and the tiller's cam (`j22_mainsheet.py`, `j22_mastgear.py`,
`j22_steering.py`, where the gooseneck and vang thread is working), the vang fiddles, the turnbuckles (the J/22 keeps its
own booted ones: docs/part-detail-loop/turnbuckle.md) and anything that rides the live jib or halyards (wave 2).

The code is `Inputs/j22-hero/j22_kitfit.py`: one function per old call, with the same arguments where it can
(`cam_cleat`), and the kit sockets kept as `sock_<Name>` properties like `kit_part`. `build_j22_hero.py -- out --sails
--old-hardware` builds the boat exactly as before: the same triangles and sockets as main's own build.

## Checks (cloud, bpy 5.1.2)

| | Before | After |
|---|---|---|
| Whole boat, sails included (main 4d9350d, with the cabin top, bow fittings and outboard) | 841,508 triangles, 1,522 objects | 1,171,568 triangles, 1,068 objects |
| Materials per group (Hardware, Rig, Rudder) | 12, 12, 8 | the same 12, 12, 8: no new slot (the kit's `Graphics` slot takes the hero's `RedPlastic`) |
| Canoe volume and centre of buoyancy | 1.0879 m³, (-0.226, -0.074) | unchanged |

Sockets that moved (`J22H_sockets.json`, cm, body frame):

| Socket | Before | After | Why |
|---|---|---|---|
| `JibWinch_S/P` | (-102.45, ±91.82, 56.64) | (-102.79, ±92.17, 56.64) | the kit cam's fairlead (`Lead`) |
| `JibTailer_S/P` | (-105.6, ±91.74, 56.64) | (-105.0, ±92.17, 56.64) | the kit cam's jaws (`Line`) |
| `BackstayPlate` | (-335.0, 0, 58.26) | (-334.43, 0, 62.17) | the bridle now ends on the shackle's bow, 4 cm above the pad eye |

The hero is now about 1.17 million triangles against the plan's cap of 1.2 million (the hull, deck and hardware are
Nanite): wave 2 needs lighter copies of the repeated small parts, or a higher cap, before it adds more. Whether the frame rate holds is the PC's and the Mac's gate (below).

## In the game (waits for the PC)

Nothing changes in the game until the hero is rebuilt and imported on BEN-PC, after Bean's "resume":

1. `scripts\windows\make-boatkit.ps1 -Import` (the whole kit, so the gallery and `kit.json` match).
2. Rebuild the hero and bake it (Inputs/j22-hero/README.md, "Rebuild"): `build_j22_hero.py -- out --sails`, then
   `bake_j22_hero.py -- out/j22_hero.blend out --res 2048`. The hardware is flat-material and outside the baked groups,
   so keep the committed texture maps (as docs/j22-rebuild did) and take the new `fbx/` and `J22H_sockets.json`.
3. Import with `scripts/import_j22_hero.py`, run `SailingSim.Visual.BoatBudget` and `HardwareKit`, take close-up stills
   of the four views below in the game, and gate `-Scope boats` on Windows and the Mac (Medium 60, High 45; no boats view
   more than 2 fps slower). If one misses, the plan's fallback is lighter copies of the repeated small parts.

## Renders

`render_j22_hero.py` has four new close-ups, `cu_jibcam`, `cu_quarter`, `cu_mastbase` and `cu_rudder`. Build both
boats (with and without `--old-hardware`) and render each:

    blender -b -P Inputs/j22-hero/render_j22_hero.py -- out/j22_hero.blend out/renders cu_jibcam cu_quarter cu_mastbase cu_rudder

## In the game (Nov 9, BEN-PC, main 170323cb with #569's rebake)

The hero imported clean: 773,010 triangles over `SM_J22H_*` (Nanite source; 33,689 in the fallback meshes), far under
the J/22's 3 million cap (raised Nov 9; Bean wants high quality). Blender's 1.17 million counts the still sails, lines
and coils, which the game draws live. Ultra close-ups, uncooked (`ingame/`): the port quarter (quarter block on its pad
eye, cam cleats), the mast base (turning blocks on their pad eyes) and the rudder from forward. The jib cam shot was
blocked by the crew; there is no argument to hide them yet. Counts: `ingame/hero-tris.txt`.
