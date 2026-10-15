# Boats 10: the hero J/22 in the game

The script-built hero J/22 from the "Detailed J/22 model proof of concept" thread (branch `j22-hero-poc`, review page
https://claude.ai/artifact/6r4id7HUep25Sk379bZ2hf) imported beside the game's J/22, which stays as it is.

## What was done

- `Inputs/j22-hero/` copied from `j22-hero-poc`: the four game parts as FBX, `J22H_sockets.json`, the baked textures,
  `materials.json`, the build scripts and renders.
- `scripts/import_j22_hero.py` (run with `scripts\windows\run-python.ps1 import_j22_hero.py`) imports them to
  `/Game/Boats/J22Hero`:
  - `SM_J22H_Hull`, `_Mast`, `_Boom`, `_Rudder`, imported as `import_boats.py` imports a boat: Nanite on the hull, boom
    and rudder, and the 49 sockets (34 on the hull) measured off the hero's fittings, relative to each part's pivot.
  - The textured parts (hull, deck mould, rudder, teak) are `MI_J22H_<group>` on a new `M_J22HeroSurface` (baked base
    colour, roughness and normal; the OpenGL normals are flipped on import).
  - The hardware, ropes and gelcoat are `MI_J22H_<name>` instances of `M_BoatSurface` with `materials.json`'s values.
  - The mast's aluminium keeps `MI_Boat_MastAluminium`, so the game's mast bend still drives it.
- `-SailingJ22Hero` draws the hero in the J/22's place (`ASailboatPawn::ModelMeshesFor`, a guarded branch at its top;
  nothing else in `BoatModelVisuals.cpp` changed). The rig lines, sails (cloth), crew, rudder and boom all hang off the
  same socket names, and they all worked on the first run.

## Side by side

Same camera, same conditions (Ray Hubbard, 15:00, 10 kn at 60 deg, High, uncooked run): the current J/22 on the left
and the hero on the right. Full-size stills are `<view>-current.png` and `<view>-hero.png`.

| View | Compare |
|---|---|
| Chase | ![chase](chase-compare.jpg) |
| Helm's eye | ![helm-eye](helm-eye-compare.jpg) |
| Crew close-up (the bench's `crew` view) | ![crew](crew-compare.jpg) |

- **Chase:** the hero has the lesson boat's look. It has no lifelines (TX 7295 EC has none), a proper outboard on its
  bracket, a lower sheer line and a fuller transom. Its cabin trunk is the known gap: narrow and boxy beside the
  current one's.
- **Helm's eye:** the hero's deck reads as a real moulding. It has textured cross-hatch non-skid with a smooth margin,
  teak grab rails on the cabin top, a solid hatch board, fine fittings at the mast step and a varnished toe rail. The
  current deck is flatter and plainer; its cabin-top edge and hatch garage are better modelled.
- **Crew close-up:** the crew sit in the same place on both hulls. Their stances come from the physics, not the mesh,
  and the hero's sheer and rail are where the crew expect them. These stills predate C1 crew motion (#39, the crew
  posed in an AnimInstance node). The same check with #39 merged is pending (see below).

## The physics check against the hero hull

`SailingSim.Visual.J22HeroMesh` (new) measures the hero hull exactly as `SailingSim.Visual.J22Mesh` measures the game's.
It cuts the canoe body (the `J22H_Hull` slot) at the design waterline and checks length, beam, draft, displaced volume
and centre of buoyancy against the J/22's physics, within the same tolerances (2 cm, 2%). Because the hero is a
candidate, a miss is a warning with the numbers rather than a failure. It fails only on what would break the boat in
the game: the rig sockets the pawn reads, Nanite on the hull, and a material on every slot.

The proof of concept's own measurement (`Inputs/j22-hero/README.md`, Blender): canoe volume 1.08 m^3 against the
physics' 1.052 m^3 (+3%), and centre of buoyancy x -0.22, z -0.07 m against -0.195, -0.080 m (2.7 cm off). So the hero
is outside J22Mesh's 2% and 2 cm on volume and CB, by a little. The physics stays the source of truth. The hero's hull
lines would need easing aft to match before it replaces the game's boat.

**Pending (the PC must restart first).** Two Unreal commandlets crashed on exit during the imports and Windows left
them holding the editor's module DLLs, so nothing can be linked until a restart. After it: build, run
`SailingSim.Visual` (J22HeroMesh's numbers go here), merge main (C1 crew motion), and recapture the crew close-up with
the AnimInstance posing.

## Crew attach points (for the Mac's crew code)

`J22H_sockets.json` carries crew points the current J/22 lacks. They are imported as hull and rudder sockets and are
not used yet. The crew posing (CrewPose, the C1 AnimInstance) is the Mac's, so nothing here reads them:

`TillerExtTip`, `TillerExtUJ` (the extension's tip and universal joint), `MainsheetCam`, `JibCam0_S/P`, `JibCam1_S/P`,
`HandholdCabin_S/P`, `HandholdCoaming_S/P`, `Seat_S/P`, `FootBrace_S/P`, `SideDeck_S/P`, `CockpitSole`,
`Boom_LowOverCockpit`.

## Known gaps

From the proof of concept: the cabin trunk is narrow and boxy, and the rudder head is a plain box. From the import: the
game's livery (`SampleBoatLivery`) doesn't recolour the hero, whose look is baked from its style JSON (TX 7295 EC,
club). A fleet of hero J/22s needs the style generator's output baked per boat, or the livery wired into
`M_J22HeroSurface` as tint parameters. A stale `M_BoatHero.uasset` (a first try, held by a stuck process) is in
`Content/Boats/J22Hero` on the PC and is not committed. It goes after the restart.

## Windows note

On Windows an editor Python script that ends with `os._exit(0)` crashes the editor on exit. If that editor is then
killed while the crash reporter is up, it can linger holding its files (including the module DLLs) until a reboot. So
`import_j22_hero.py` lets the commandlet exit by itself. Close the crash reporter before anything else when a script
does crash on exit.
