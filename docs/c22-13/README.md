# Catalina 22 rebuild: the keel swings and the rudder kicks up

Slice 12 of the rebuild (the game wiring's second half, after `docs/c22-12/`). Her swing keel and the rudder's blade are
now parts of their own, and the game turns them as the physics does (`docs/c22-11/`).

## What you see

- **The keel.** The Board key (1 down, 0.25 up in the pawn today) swings the cast-iron plate aft about its pin. Fully up
  (Board 0) it turns 59.9 degrees; at the pawn's 0.25 it turns 44.9 degrees. The game winds the drawn plate toward the
  physics' at 0.25 rad/s (about 4 s from down to up), as her winch would. This easing changes only the look: the physics
  sails on the new Board at once, as it did before.
- **The rudder.** When the bottom comes up under her, the physics kicks the blade up just as far as it must, then drops it
  back over 2 s in deep water (`FBoatTelemetry::RudderKick`). The drawn blade turns about its bolt in the rudder's head by
  the same amount, up to 86 degrees, and steers with the head and tiller.

## How

- **Export** (`Tools/shipkit/catalina22/game_c22.json`, `export_game_c22.py`):
  - `SM_C22Hero_Keel` is the build's `C22_Keel` about its pin, the new hull socket `KeelPin` (`keel_c22.json`
    `keel.pivot`: x 0.8, z -0.37). It is no longer in the hull part.
  - `SM_C22Hero_RudderBlade` is the build's `C22_Rudder` faces in Topsides (the blade), cut out by material
    (`split_material`). It sits about the rudder part's new `RudderBolt` socket (`rudder.pivot_x` + `head.bolt`).
  - The printed draft is measured over the hull and the keel together.
- **Import** (`scripts/import_boats.py c22hero`): imports both parts with their sockets when the export made them.
- **Game** (`BoatModelVisuals.cpp`, `SailboatPawn.cpp`):
  - `ModelMeshesFor` loads the two parts when both exist. An import from before this slice still draws them fixed,
    inside the hull and rudder parts.
  - `KeelPivot` sits on the hull's `KeelPin`. `BladePivot` sits on the rudder part's `RudderBolt`, so it steers with the
    rudder.
  - The tick turns them by `ASailboatPawn::KeelSwingTurn` and `BladeKickTurn`:
    - `KeelSwingTurn` is the turn of the iron's centroid about the pin, from `FFoilDef::SwingAt`'s `MassX`/`MassZ`. The
      centroid is a fixed point of the plate; the table's lowest point slides round the outline as the plate turns, so
      using it would read 57.4 degrees instead of 59.9.
    - `BladeKickTurn` is the physics' kick times the new `FFoilDef::KickUpAngle`. That is 86 degrees for the C22: the
      kick table is even in angle.
- **Physics**: one new field, `FFoilDef::KickUpAngle`, set only on the Catalina 22's rudder. Nothing in the physics reads
  it, so the polars are unchanged.

## Test

`SailingSim.Visual.C22HeroMesh` adds these checks.

These always run:
- The keel is drawn up 59.86 degrees at Board 0, within 0.5 degrees.
- At Board 0.5 it is drawn half that.
- The blade is drawn up 86 degrees at Kick 1.

Once the parts are imported:
- The draft is measured with the keel part on its pin.
- `KeelPin` is the physics' pin: the iron is the same distance from it with the keel up and down, within 1 cm.
- The blade's foot under its bolt is at the physics' tip, within 2 cm.

The export on the slice 9 build (cloud, bpy 5.3) reads:

| Part | Triangles |
|---|---|
| Hull | 243,784 |
| Keel | 3,820 |
| Mast | 30,420 |
| Boom | 1,052 |
| Rudder head | 12,972 |
| Blade | 4,400 |
| Interior | 71,891 |

It also reads a draft of 1.552 m, a canoe body of 1.2382 m^3 and 80 sockets.

## AI boats (Nov 18)

Bean chose the full rebuilt model for AI Catalinas too: `UseC22Hero` no longer leaves AI boats and the ghost on the
fleet model (`-SailingClassicC22` still does, everywhere). Their keels and blades turn as the player's do; the cabin
below stays the player's. The hull, keel, boom, rudder and blade are Nanite; the mast is not (M_BoatMast bends it) and
has no LOD chain, so each AI Catalina adds its 30k mast triangles. A boats-scope gate after the import measures it; if
it costs too much, the fix is a lighter mast for AI boats from the build's light copy (`light_c22.py`, about 12% of the
triangles).
