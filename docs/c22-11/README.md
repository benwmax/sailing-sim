# Catalina 22 rebuild, slice 10: she sails on the new model

Slice 10 gives the game's Catalina 22 the rebuilt boat's own hull, swing keel, kick-up rudder and sail plan, so the
boat the player sails is the boat the player sees. Plan: <https://claude.ai/artifact/3oMiRWywPhitATHvGxs51a>. The
model itself is slices 0 to 9 (`docs/c22-1` to `docs/c22-10`); the PC imports it in slice 11 (`docs/c22-12`).

## Words used here

- **Polar:** a table of how fast a boat sails at each wind speed and angle. The game holds each boat to a reference
  polar within a tolerance (here 15%, because the Catalina 22's reference is an estimate from her handicap).
- **Board:** the game's control for a centreboard, daggerboard or swing keel: 1 fully down, 0 fully up.
- **Leeway:** how far the boat slides sideways while sailing upwind. A keel stops most of it.
- **Righting moment:** how hard the boat pushes back upright when heeled. More is a stiffer boat.

## What changed

| | Before | Now |
|---|---|---|
| Hull | a formula fitted to her sizes | the model's 31 sections (`hull_c22.section`), canoe depth 0.237 m |
| Floats | 0.56 deg by the stern | level on her drawn waterline (her hull and rig's weight placed over the model's centre of buoyancy) |
| Wetted area | the J/22's coefficient (7.4 m^2) | the sections' own girth (8.8 m^2) |
| Keel | a 0.60 m^2 board that slid straight up | the 0.63 m^2 cast-iron plate turning 60 deg aft about its pin; its foot, area and its 249 kg of iron follow it |
| Keel up | no keel at all, grounding still at 5 ft | 0.16 m^2 still below the stub, grounding at 2 ft (plus the crew's sink), the iron 0.58 m higher |
| Rudder | 0.25 m^2, fixed | the 0.29 m^2 kick-up blade: the bottom pushes it up instead of grounding her, it drops back over 2 s in deep water |
| Boom | 1.45 m | 1.565 m, 11.5 cm higher (Bean, Nov 16: "the boom does sit too low") |
| Main | tack 0.82 | tack at the gooseneck, 0.78; luff P and foot E as before, 9.42 m^2 |
| Genoa | 135%, tack 0.85 m up, 12.9 m^2 | Bean's high-cut 140% on its pennant, tack 1.55 m up, 12.54 m^2 as drawn |
| Masthead | 8.84 m | 8.864 m (the 25 ft mast on its step) |
| Draft | 1.52 m | 1.552 m (5 ft plus the crew's 2.8 cm sink) |

The genoa takes the drawn sail's 12.54 m^2, not the old physics' 12.9: the cloth the player sees is what drives her.

## How it's made

`Tools/shipkit/catalina22/export_physics_c22.py` reads the rebuild's own scripts (`hull_c22`, `keel_c22`, `rig_c22`,
`sails_c22`) and writes `Source/SailingPhysics/Private/Catalina22HullData.inl`: the sections, the hull's particulars,
the swing keel's table (11 positions, up to down), the rudder's kick table (11 positions) and the rig's numbers.
`Fleet.cpp`'s `Catalina22()` builds her from it, the way the maxi and the J-Class are built. Edit the slice's JSON or
the script, never the `.inl`; `export_physics_c22.py --check` says whether the `.inl` is current.

In the physics (`BoatModel.h`, `FFoilDef`): a foil with a `Swing` table turns with the Board control instead of
sliding, its iron (`SwingMass`) adding the moment of its weight moved up and aft; a foil with a `KickUp` table kicks up
on the bottom (`FBoatTelemetry::RudderKick`, 0 down to 1 up, for the model's blade in slice 11). Every other boat is
unchanged: none has either table.

## Measured (standalone, `scripts/polar.sh --boat "Catalina 22"`)

All 15 polar points stay inside 15%. Before and after (model speed in knots, error against the reference):

| TWS | TWA | reference | before | now |
|---|---|---|---|---|
| 6 | 52 | 4.03 | 3.70 (-8.1%) | 3.59 (-10.9%) |
| 6 | 60 | 4.26 | 3.84 (-9.9%) | 3.82 (-10.3%) |
| 6 | 90 | 4.32 | 4.22 (-2.3%) | 4.14 (-4.2%) |
| 10 | 52 | 5.19 | 5.08 (-2.2%) | 5.03 (-3.0%) |
| 10 | 90 | 5.52 | 5.50 (-0.4%) | 5.47 (-1.0%) |
| 10 | 150 | 4.81 | 5.26 (+9.5%) | 5.09 (+5.9%) |
| 16 | 52 | 5.56 | 5.19 (-6.6%) | 5.19 (-6.6%) |
| 16 | 90 | 5.99 | 6.24 (+4.2%) | 6.24 (+4.1%) |
| 16 | 120 | 6.25 | 6.93 (+10.9%) | 7.13 (+14.1%) |
| 16 | 150 | 5.89 | 6.55 (+11.2%) | 6.50 (+10.3%) |

- She is stiffer: righting moment at 10 deg 2,200 N m against 1,470 (the drawn hull's flat, firm bilge), so she heels
  less (16 kn close-hauled 16 deg against 23) and carries the genoa harder on a breezy reach: the 16 kn reach at 120 deg
  is now +14.1%, near the 15% line. Nothing was retuned to pull it back: the reference there is a handicap estimate.
- Light air upwind she is 1 to 3% slower than before: the sections' wetted area is 19% more than the old coefficient gave.
- Reference checks (`scripts/reference-checks.sh --quick`): her Portsmouth ratios are unchanged (1.07 and 1.15); her
  knockdown recovery is 1.0 deg 30 s later (2.2 before). The one check out (the Sunfish 20 s after a capsize, 145.2 deg
  against 145) is out on main too, in the cloud without `Wind.mann`.
- Swing keel at 12 kn, 50 deg: keel down 5.36 kn with 6.3 deg of leeway, keel up 5.50 kn through the water with 14.6
  deg (worse made good). Becalmed with her crew on one side she lists 3.7 deg keel down, 4.2 up.
- In 1 m of water she grounds keel down and sails on keel up; in 0.8 m the rudder kicks up about a third and drops back
  down in deep water.

## Tests

`Source/SailingSimTests/Private/C22PhysicsTests.cpp`: `SailingSim.Physics.C22Hull` (sizes, volume, centre of
buoyancy, level trim, the rig), `SailingSim.Physics.C22SwingKeel` (the table, leeway, list, the shoal),
`SailingSim.Physics.C22KickUpRudder`. `SailingSim.Fleet.PolarCatalina22` holds the polar as before.

## For the Mac and the PC

- The fleet model `SM_Catalina22_*` (`build_fleet.py` from BoatExport) is built from the physics hull, so
  `scripts/make-boat-models.sh` must be rerun for `SailingSim.Visual.FleetMesh` (its volume moves 2.2%, its draft 3 cm).
  `build_fleet.py` now builds a hull that has sections (`hull_stations`, only the Catalina 22 in the fleet) on them, as
  `build_j22.py` does: on the formula's stand-in fit its canoe was 1.008 m^3 against 1.220 and its CB 12 cm aft. Built
  with the `bpy` module in the cloud: canoe 1.225 m^3, CB (-0.097, -0.088), LOA 6.550, beam 2.338, as the physics.
  Slice 11's hero (`SailingSim.Visual.C22HeroMesh`, PR #762) is held to these same numbers.
- The physics' `Board` toggle (1 or 0.25 in the pawn today) now swings the keel: slice 11 can draw it and the rudder
  from `FFoilDef::SwingAt` and `FBoatTelemetry::RudderKick`.
- `RudderStockToCP` stays the old 0.09 m (the helm's feel); the blade's quarter chord is 0.18 m behind its pintles.
