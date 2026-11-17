# Cannon fire (frigate Commonwealth)

The frigate's guns in the game: the gun drill, each gun's recoil and its push on the ship, the powder smoke, the muzzle
flame, sparks and flash lights. There is no shot (Bean, Nov 17: "just the effect is enough"). Tuning knobs and bench use
are in [tuning.md](tuning.md).

## The pieces

| Piece | Where | What it does |
|---|---|---|
| Gun table | `Source/SailingPhysics/Private/FrigateGunData.inl`, from `Tools/shipkit/frigate/cannon_data.py` | 28 long 24-pounders (gun deck) and 22 32-pounder carronades (quarterdeck and forecastle): each port's frame in the ship's frame, the carriage's place housed / run in / run out, the lid, the elevations. Generated from the model build's `guns.json`; never edit the .inl. |
| Drill and recoil | `Cannons.h` / `Cannons.cpp` (`Sailing::FCannonBattery`, SailingPhysics, plain C++) | Orders (cast loose, load, run out, fire, cease fire, secure), fire modes (broadside, ripple, at will), each gun's state and timing, misfires. Recoil: impulse = muzzle velocity x (shot + 1.5 x charge), the trucks' friction and the breeching rope stop it (about 1.7 m for a long gun, 0.8 m for a carronade), the train tackle holds it in. The ship gets the reaction (`ForceOnShip`, `MomentOnShip`). |
| Smoke | `Sailing::FCannonSmoke` | Gaussian puffs: the blast's jet slows into the wind, the hot smoke rises then cools, each puff grows by eddy diffusion (Richardson's 4/3 law). Mass is conserved; over the quality's budget the oldest puff merges into its nearest. Flashes and sparks too. |
| Game side | `ACannonBattery` (`Source/SailingSim`) | Draws the guns on the ship (parts by instance, each gun's tackle swapped by pose, port lids), the smoke as lit camera-facing quads (`M_CannonSmoke`), the flame and sparks (`M_CannonFlash`), and a few pooled flash lights. `OnGunFired` for sound and camera shake. |
| Effects | `Tools/shipkit/frigate/make_cannon_textures.py`, `scripts/import_cannon_fx.py` | Textures from seeded noise (16 billowed puffs, 4 flame tongues), imported to `/Game/Materials/CannonFx`, and the two materials. Run `scripts/make-cannon-fx.sh` (Mac) or `scripts\windows\make-cannon-fx.ps1` (PC). |

Until the PC imports the gun models (`/Game/Boats/Frigate/Guns/SM_Frigate_*`) the battery draws stand-ins (the engine's
cylinder and cube). Until the effects script has run, `M_Spray` stands in for both effect materials.

## Who calls what

- The ship's pawn spawns the battery on its root: `ACannonBattery::SpawnBattery(ShipRoot)` (the root's frame is the
  model's: X forward, Y to starboard, Z up).
- The orders panel calls `Order(order, side)`, `SetFireMode(mode)` and reads `GetSideStatus(side)`.
- The camera shake and sound bind `OnGunFired` (`FCannonFiredEvent`: gun, kind, side, muzzle, bore, charge, impulse,
  misfire).
- The ship's physics adds `GetForceOnShip()` (N) and `GetMomentOnShip()` (N m), both in the ship's frame.

## Rebuilding the gun table

When the model's `guns.json` changes (a new build of the frigate):

    python3 -I Tools/shipkit/frigate/cannon_data.py <build dir or guns.json>

then `scripts/cannon-check.sh --drill` and `scripts/test.sh SailingSim.Physics.Cannons`. `lid_frame` rows (the lid's
hinge) are used when guns.json has them.

## Tests

`SailingSim.Physics.Cannons.Table`, `.Drill`, `.Recoil`, `.Smoke`, `.Params`. Standalone (no Unreal):
`scripts/cannon-check.sh --drill | --recoil | --smoke [s] [--wind m/s] [--budget n] | --params`.

## Reference numbers (standalone)

- Long 24: 10.9 kg shot, 3.6 kg charge (a third of the shot's weight, the service charge), recoil 2.6 m/s at the start,
  about 1.7 m back; ship impulse about 8,000 N s each.
- Carronade 32: 14.5 kg shot, 1.2 kg charge, 4.6 m/s, about 0.8 m on its slide; about 4,900 N s.
- Broadside from housed: about 85 s to the first shot, every gun on the side within 0.3 s of each other.
- At will: about one round a minute a gun.
- Smoke: thick for about 10 s, thin by a minute in a moderate breeze.
