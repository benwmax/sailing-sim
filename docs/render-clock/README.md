# Drawing the world between physics steps (feedback #26)

A tester saw a slight stutter in the water at 60 fps on an Afternoon Breeze day (sailing-feedback #26: build 40226d1c,
RTX 4090, Ultra at 3840x2160, Ray Hubbard, J/22, 20 kn, frame rate 47 to 68 in the report's telemetry). The build
already had the storm-stutter fixes (#687, #688, #690), and nothing in its log shows a hitch.

## Cause

The world clock (`FWorldClock`, online readiness rule 3) moves in whole 120 Hz physics steps. The water's `WaveTime`,
the short waves' blend, the ocean's blend and the player's boat were all drawn at that clock. A frame of about 16.7 ms
is two steps, but when the frame times scatter a millisecond or two about 16.7 ms the leftover time sits near a step
boundary, and the frame steps one or three times instead: the drawn world moves 8.3 or 25 ms of time in a 16.7 ms
frame. Fine, fast water (a 20 kn breeze, the boat at 7 kn) shows it as a stutter; a calm day hardly does.

Simulated with the game's stepper (`FFixedStepper`):

| Frame rate | Frame time scatter | Frames moved 4+ ms off the frame |
| --- | --- | --- |
| 60 fps | +-0.3 ms | 3% |
| 60 fps | +-1.5 ms | 14% |
| 59 fps | +-2.5 ms | 24% |
| 68 fps | +-1.5 ms | 26% |
| 50 fps | +-2 ms | 34% |

## Fix

- `FWorldClock::GetRenderTime()`: the clock less the part of a step not yet stepped (`GetTime() - (1 - alpha) x dt`).
  It moves by each frame's own length and is never more than one step (8.3 ms) behind the clock.
- `ASailingGameMode::GetRenderTime()` hands it out; `-SailingClassicClock` draws at `GetSimTime()` again to compare.
- `AWaterSurface` draws at it: `WaveTime` (the long waves in both water materials), the short-wave detail frames and
  their blend, the ocean's 30 Hz blend and the foam grid. The wake grid, spray, wind maps and far caps still step on the
  sim clock (they are stepped simulations or planned every half second).
- The player's boat is drawn between the pose before her last step (`FBoatPose`, written by `FBoatStepJob`) and her
  pose now, at the render time (`ASailboatPawn::ApplyStateToTransform(true)`), so she and the camera move as smoothly as
  the water and stay on the drawn waves. Not in the showroom (she is put back on her spot between steps), a
  `-SailingRun` slide, after a re-place or reset, or across a move of 2 m or a turn of 30 degrees in one step (set there by hand).
- The water's hull clip, her bow wave and the drips off her sheer follow where and when she is drawn
  (`GetDrawnOrigin`/`GetDrawnOrientation`, `DrawnBodyToWorld`, `DrawnTime`), and so do the helm view's heading and pitch
  and the capture presets' framing (`DrawnRotationOffset`): placed from the telemetry they turned up to a step ahead of
  the hull they sit in.
- AI sailboats are stepped to the clock by the traffic simulation, which keeps no pose before: they are drawn back along
  their velocity and turn by the clock's lag (at most a step; straight lines are exact enough over 8 ms). Power vessels
  are drawn back along their course the same way. Buoys and the camera's floor over the waves read the sea at the
  render time.
- Left on the physics on purpose: the wake grid's hull patches and the spray's emission (stepped simulations whose
  sources are a few centimetres ahead at most, inside a wake cell or a spray burst) and the far caps (planned every half
  second). The ghost is a traffic-mode pawn, so it is drawn back like an AI boat along the velocity its replay frame
  carries.

The physics, the boats' steps and everything they read are unchanged; only what is drawn moves, by up to one step. What
you see is on average about 4 ms later than before (half a step); the controls act on the next step as before.

Tests: `SailingSim.Physics.WorldClockRenderTime` (the stepped clock is uneven at these frame times; the render time moves
by every frame's length and stays within one step behind, never before the start) and `SailingSim.Physics.DrawBetweenSteps`
(the step job's pose before her last step, `FBoatPose::BlendTo`: drawn between steps she moves by her speed times each
frame's length, never back in time, and is not blended across a 5 m jump, a 40 degree turn set by hand or a stale pose).

Reviewed by an independent QA pass before merge (PR #787): it found the helm view, AI boats, power vessels, buoys, the
camera floor, drips and capture framing still on the stepped clock; all moved above.

## Checking it

On the repro (`-SailingWorld=ray-hubbard -SailingBoat=J22 "-SailingStartAt=8825,-367,163" -SailingWind=20
-SailingTWA=-160`, Ultra, vsync off) with `-SailingBenchTrace`, with and without `-SailingClassicClock`: frame times
should match, and the water should look smooth by eye only in the run without the flag.
