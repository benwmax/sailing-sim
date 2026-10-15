# Boats 10: the hero J/22 in the game

The script-built hero J/22 from the "Detailed J/22 model proof of concept" thread (branch `j22-hero-poc`, review page
https://claude.ai/artifact/6r4id7HUep25Sk379bZ2hf), imported beside the game's J/22, which is left as it is.

## What was done

- `Inputs/j22-hero/` copied from `j22-hero-poc`: the four game parts as FBX, `J22H_sockets.json`, the baked textures,
  `materials.json`, the build scripts and renders.
- `scripts/import_j22_hero.py` imports them to `/Game/Boats/J22Hero`. Run it with
  `scripts\windows\run-python.ps1 import_j22_hero.py`, or the editor directly (see Windows below).
  - `SM_J22H_Hull`, `_Mast`, `_Boom` and `_Rudder` are imported as `import_boats.py` imports a boat. Nanite is on for
    the hull, boom and rudder. The sockets were measured off the hero's fittings and are relative to each part's
    pivot: 35 on the hull, including `RudderPivot` (see below).
  - The textured parts (hull, deck mould, rudder, teak) are `MI_J22H_<group>` on a new `M_J22HeroSurface`: baked base
    colour, roughness and normal, with the OpenGL normals flipped on import. Each texture parameter has a default of
    its own sampler type. Without one the material fails to compile and draws the engine's grey grid.
  - The hardware, ropes and gelcoat are `MI_J22H_<name>` instances of `M_BoatSurface`, with the values in
    `materials.json`.
  - The mast's aluminium keeps `MI_Boat_MastAluminium`, so the game's mast bend still drives it.
- `-SailingJ22Hero` draws the hero in the J/22's place. It is a guarded branch at the top of
  `ASailboatPawn::ModelMeshesFor`; nothing else in `BoatModelVisuals.cpp` changed. The rig lines, sails (cloth), crew,
  rudder and boom hang off the same socket names as on the game's J/22.
- **Fixed on the way:** the hero's sockets JSON puts `RudderPivot` on the rudder, but the game hangs the rudder from
  the hull's `RudderPivot`, so the first import had no rudder in the game. The importer now also puts it on the hull,
  at the same point.

## Side by side

Same camera and conditions for both: Ray Hubbard, 15:00, 10 kn at 60 deg, High, uncooked run, main merged with C1
crew motion (#39). The current J/22 is on the left, the hero on the right. Full-size stills are `<view>-current.png`
and `<view>-hero.png`.

| View | Compare |
|---|---|
| Chase | ![chase](chase-compare.jpg) |
| Helm's eye | ![helm-eye](helm-eye-compare.jpg) |
| Crew close-up (the bench's `crew` view) | ![crew](crew-compare.jpg) |

- **Chase:**
  - The hero has the lesson boat's look: no lifelines (TX 7295 EC has none), a proper outboard on its bracket with
    the rudder beside it on the transom, a lower sheer line and a fuller transom.
  - Its cabin trunk is the known gap, narrow and boxy beside the current one.
- **Helm's eye:**
  - The hero's deck reads as a real moulding: textured cross-hatch non-skid with a smooth margin, teak grab rails on
    the cabin top, a solid hatch board, fine fittings at the mast step and a varnished toe rail.
  - The current deck is flatter and plainer, though its cabin-top edge and hatch garage are better modelled.
- **Crew close-up:**
  - The crew sit in the same place on both hulls, with C1's AnimInstance posing: hiked on the rail, the helm aft, heads
    turned to their gaze.
  - Their stances come from the physics, not the mesh, and the hero's sheer and rail are where the crew expect them.

## The physics check against the hero hull

`SailingSim.Visual.J22HeroMesh` (new) measures the hero hull the way `SailingSim.Visual.J22Mesh` measures the game's.
It cuts the canoe body at the design waterline and checks length, beam, draft, displaced volume and centre of buoyancy
against the J/22's physics, with the same tolerances (2 cm, 2%). The hero is a candidate, so a miss is a warning with
the numbers. The check fails only on what would break the boat in the game: the rig sockets the pawn reads, Nanite on
the hull, and a material on every slot. `J22Mesh`'s measuring is now shared as `MeasureCanoe`.

Results (`test.ps1 -Filter SailingSim.Visual`: 23 passed, 0 failed):

| Check | Hero | Physics |
|---|---|---|
| Length overall | 6.860 m | 6.860 m |
| Beam | 2.448 m | 2.440 m |
| Draft | 1.160 m | 1.160 m |
| Canoe body volume | 0.151 m^3 (warning) | 1.052 m^3 |
| Centre of buoyancy | (0.007, 0, -0.240) m (warning) | (-0.195, 0, -0.080) m |

Length, beam and draft agree to a centimetre. The volume and centre of buoyancy can't be measured this way on the hero.
Its `J22H_Hull` slot is the whole shell from the keel bottom (-1.16 m) to the sheer, keel included, and it has
thickness (an inner skin facing the other way). The tetrahedron sum that measures the game's single-surface canoe body
largely cancels on it.

The proof of concept measured its own canoe body in Blender at 1.08 m^3 against the physics' 1.052 m^3 (+3%), with
the centre of buoyancy at x -0.22, z -0.07 m against -0.195, -0.080 m (2.7 cm off). So even measured properly it is a
little outside J22Mesh's 2% and 2 cm. To hold it to the physics like the game's boat, the hero needs two things:
- the canoe body in a slot of its own (the outer surface only, like the game's `Topsides`/`Antifouling`);
- its lines eased aft.

## Crew attach points (for the Mac's crew code)

`J22H_sockets.json` carries the crew points C1 reads by name:

`TillerExtTip`, `TillerExtUJ`, `MainsheetCam`, `JibCam0_S/P`, `JibCam1_S/P`, `HandholdCabin_S/P`,
`HandholdCoaming_S/P`, `Seat_S/P`, `FootBrace_S/P`, `SideDeck_S/P`, `CockpitSole`, `Boom_LowOverCockpit`.

They are imported as hull and rudder sockets, so with `-SailingJ22Hero` the crew take them from the mesh rather than
from `CrewDerivedAttachPoints`. The crew code is the Mac's, and nothing here changed it.

## Known gaps

- From the proof of concept: the cabin trunk is narrow and boxy, and the rudder head is a plain box.
- From the import: the game's livery (`SampleBoatLivery`) doesn't recolour the hero, whose look is baked from its
  style JSON (TX 7295 EC, club). A fleet of hero J/22s needs the style generator's output baked per boat, or the
  livery wired into `M_J22HeroSurface` as tint parameters.
- The canoe body isn't in a slot of its own (see above).

## Windows

- An editor Python script that ends with `os._exit(0)` crashes the editor on exit. An editor killed in that state
  lingers, holding its files (the module DLLs too) until a reboot.
- Without `os._exit`, and with `-NoCrashReporter`, `import_j22_hero.py` exited cleanly (code 0, 45 s).
  `docs/windows/README.md` has the details.
- This branch was finished in a second worktree (`C:\dev\ss2`), which has its own `Binaries` that the stuck processes
  don't hold.
