# The ILCA's tiller with the rudder out of the water

Gap #5 from the Oct 28 list. On a steady 22 kn broad reach the ILCA crash-gybed at a couple of angles between 110 and 120
deg (`SailingSim.Physics.LaserPlaningDrag` allows three). On main c2cb055c it was one angle, 116 deg, out of the sixteen
from 100 to 130.

## What happened at 116 deg

A trace every 0.1 s, with the rudders' immersion now in the telemetry (`FBoatTelemetry::RudderImmersion`, the wet share
of their span):

- **46.1-46.6 s:** over a crest the rudder comes clear (immersion 0.00) and she rounds up at 36 deg/s. The autopilot
  feels nothing and winds the tiller from -0.2 to its stop, -0.46.
- **46.7 s:** the rudder lands at -0.46 and throws her into a bear-away (yaw -14 deg/s).
- **47.5-48.3 s:** the rudder comes clear again while she bears away. She spins up to -132 deg/s with the tiller at +0.46,
  gybes at 48.5 s and goes over.

A sailor with the rudder out of the water holds the tiller about where it was. Nothing comes back through it to steer by.

## The fix (`FAutopilot`, `AutoTrim.h/.cpp`)

On a boat under `AirborneTillerMassKg` (500 kg: the dinghies and beach cats, where the helm's hand is on the tiller), the
tiller moves at most `AirborneTillerRate` (0.3 of its travel a second) while the rudder is clear. It moves faster as the
rudder goes back in (the rate over one minus the immersion) and is free once it is under.

**The most immersed rudder.** The first gate failed `SailingSim.Physics.HobieRunGuard` (seed 3, TWA 170: by the lee and
over). `RudderImmersion` was the mean over the rudders, and a cat flying a hull has her windward rudder in the air, so the
Hobie read as half clear for long stretches and her run guard steered slowly. The helm steers with whichever rudder is in
the water, so the telemetry is now the most immersed rudder's.

**Why only light boats.** I first applied it to every boat. A keelboat's rudder never comes clear, but it is never quite
fully under either, so the limit nibbled at the J/22: her 6 and 15 kn tack scenarios moved by 0.1 s, and three polar
points moved. Freeing the tiller from 30, 45 or 60% immersed left the J/22 byte-identical but brought the ILCA's 116 deg
capsize back, because her rudder half-lifts on those faces. A limit by the boat's weight keeps the J/22 exactly as she was.

## Before and after: ILCA, steady 22 kn, 180 s per angle

| | Main c2cb055c | Fix |
|---|---|---|
| Capsized (tilt 70 deg+) of 16 angles | 1 (116 deg) | 0 |
| Peak, 1 s mean | 14.1-16.3 kn | 14.1-16.5 kn |
| Mean at 116 deg | 1.89 kn (over) | 13.83 kn |
| Most tilt, upright angles | 9-29 deg | 9-50 deg |

The tilt at a few angles (110, 116, 118) now reaches 38-50 deg: she still rounds up and heels on those faces, but comes
back.

## Unchanged

- The J/22: `scripts/polar.sh` and `--scenarios` are byte-identical to main.
- The ILCA's, Sunfish's and Hobie 16's polars (`--boat`) are byte-identical too.
- `scripts/reference-checks.sh --quick`: all 48 in range, as on main. The ILCA's 22 kn reach check heels to 41.7 deg
  (21.6 on main; its band is 0-70). The dinghies' capsize and righting checks move by under 0.2 s or 0.2 deg. The Hobie's
  tacking angle and laps are unchanged.

## Tests

`SailingSim.Physics.AirborneTiller` (new) checks that the ILCA is a light boat and the J/22 isn't, and that the ILCA stays
up at all 16 angles from 100 to 130 deg in a steady 22 kn, with a mean over 11 kn. `LaserPlaningDrag`'s band (three
capsizes allowed) is unchanged; its comment now records the counts.

## Gate (`scripts/gate.sh --scope boats`, packaged, the Mac)

Pass: 278 tests, every view over its floor on High: beam8 56.7, beat15 52.4, marina 55.6, helm-eye 58.8, slip 48.8,
crew 46.7.
