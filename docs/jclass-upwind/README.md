# Bluebonnet upwind in a breeze, and her gooseneck

J-Class 14 left her 12% under her estimated polar close-hauled in 16 knots (10.59 against 12.09 at 52 degrees), and the
physics' gooseneck 0.227 m ahead of her model's boom pin (`docs/jclass-14/`, "Known gaps"). This page is the fix for
both, in `Fleet.cpp`'s `Bluebonnet()` and two new `FBoatConfig` fields. Every other boat is unchanged (the J/22's quick
polar: 0 of 39 outside, worst 8.0%, as before).

## Why she was slow

`scripts/polar.sh --boat blue --point 16 52` showed her held at 18 degrees of heel with the main luffing (angle of attack
0): she had all the power her righting moment could carry, and the polar search found heeling further slower. Sail and
keel aspect ratios, camber and the trimmer's heel limit each moved her under 1%. Two things did move her:

- **Wave-making read at her length at rest.** The physics reads the residuary table at her 26.0 m waterline whatever she
  does; slice 13 cut the whole table to 0.6 for her overhangs. Her own sections say how much longer she gets as her bow
  and stern waves climb her overhangs: a crest 0.25 m up wets 28.2 m (+9%), 0.5 m 30.4 m (+17%), 0.75 m 32.4 m (+25%).
  Heeled in still water she gains almost nothing (18 deg: +1.5%), so it is the waves, and they climb higher the faster
  she goes.
- **Heeled drag fitted to the J/22.** The fleet charges friction `1 + 0.4 sin heel` and wave-making `1 + 2 sin^2 heel`
  (12% and 19% more at 18 degrees). Her sections, heeled and sunk to the same volume, wet 0.6% more area and 1.5% more
  length at 18 degrees (1.0% and 1.8% at 22). Those terms were what made 18 degrees her best heel; a J went best at 20
  to 25.

## What changed

| | Before | Now |
|---|---|---|
| Wave-making | the sheet's table x 0.6 at every speed | the sheet's table on her sailing length: at each speed her crest is 0.25 x V^2/2g up her overhangs, her length L from her sections, and the table is read at Fn sqrt(L0/L) times (L0/L)^3 (`BluebonnetSailingLength`) |
| Heeled drag | 0.4 sin, 2.0 sin^2 (the fleet's) | 0.02 sin, 0 (her lines: `HeelFrictionCoef`, `HeelResiduaryCoef`) |
| Gooseneck (`MainLuffX` at `BoomZ`) | 2.578, the sail's tack on the mast's track | 2.3508, the boom's pin (slice 4's `boom_frame.origin`); the main's foot 0.227 m shorter so the clew stays put; area kept |
| `TrimRollSeconds` | 8.0 | 10.0 (below) |

Against the sheet's table her wave-making is now 0.96 of it at Fn 0.10, 0.83 at 0.20, 0.64 at 0.30, 0.53 at 0.35, 0.40
at 0.40 and 0.29 at 0.45 (slice 13's flat factor: 0.6 everywhere). The crest share 0.25 is the one knob: at 0.20 she was
7% under close-hauled in 16 knots; at 0.35 and 0.40 her run in 16 knots went 15 and 18% over.

## Results

`scripts/polar.sh --boat blue`: 0 of 15 points outside 20%, worst 10.5% (was 12.4%).

| TWS | 52 | 60 | 90 | 120 | 150 |
|---|---|---|---|---|---|
| 6 kn | -6.2% (was -3.6) | -6.8% (-4.2) | -6.4% (-3.4) | +2.0% (+4.6) | -0.2% (+2.3) |
| 10 kn | -4.6% (-6.3) | -4.1% (-6.3) | +1.6% (-1.1) | +2.7% (-0.5) | +4.3% (+5.6) |
| 16 kn | -4.6% (-12.4) | -3.8% (-11.9) | +3.2% (-8.5) | +3.5% (-7.3) | +10.5% (+3.7) |

- Close-hauled in 16 knots she heels 25 degrees (was 18) at 11.54 knots.
- Best beat in 12 knots: VMG 7.11 at 34 degrees (was 7.01), 0.98 of *Ranger*'s 1937 record (7.26).
- The light-air points are 2 to 3% slower: the flat 0.6 also cut her wave-making at 6 knots, where her crest is small.
- The run in 16 knots is now 10.5% over the estimate, the largest error left: wave-making is most of her drag there.
- `--scenarios` (tacks and irons): unchanged.

**Her roll.** A knot faster upwind in a breeze, she swung 19 to 27 degrees every 13 s in 20 to 22 knots with the game's
hands at `TrimRollSeconds` 8 (her free roll period). Putting the fleet's heeled drag back does not cure it (20 to 25
degrees), nor does the old gooseneck; trimming over 10 s does: within 1.5 degrees from 12 to 24 knots with
the game's hands and the ideal ones (`SailingSim.Physics.BluebonnetRoll`, now with 22 knots too).

## The gooseneck and her model

The physics' gooseneck is `MainLuffX` at `BoomZ` (the pawn's `BoomPivot`, the main's cloth, the crew's boom checks). It
is now her boom's pin. Her model's export (`Tools/shipkit/jclass/export_game.py`, J-Class 14 step 2) places
`SM_Bluebonnet_Boom`'s origin on the same pin (the build's boom frame origin, #770), so the boom turns about its own jaw.

## Tests

- `SailingSim.Physics.BluebonnetUpwind` (new): the gooseneck on the pin, clew and area as the sheet; her heeled drag and
  the J/22's unchanged; her wave-making by Froude number against the sheet's; 16 knots at 52 degrees within 7% of the
  estimate at 20 to 27 degrees of heel; her 12-knot beat 0.95 to 1.0 of *Ranger*'s.
- `SailingSim.Physics.BluebonnetRoll`: `TrimRollSeconds` 10, and 22 knots added.
- `SailingSim.Fleet.Polar.Bluebonnet`: unchanged (20% everywhere).

Checked standalone with clang (`scripts/polar.sh`, and the roll test's loop in a scratch harness); the Unreal tests need
the Mac and the PC.
