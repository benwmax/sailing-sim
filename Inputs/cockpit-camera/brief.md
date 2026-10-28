# Cockpit camera through a tack or gybe (brief, Oct 28 2026)

For the Mac lane. Planning only; nothing here is built yet. One PR against main, `--scope crew` gate, then an
optional second PR only if Bean asks for it after a retest.

## What is wrong

PR #366 made the crew cross the cockpit on a tack or gybe (`FCrewCrossing`, `docs/crew-tack/`). The cockpit view
(`\`, `-SailingCockpit`) is the helm's own eyes, and `ASailboatPawn::UpdateCockpitCamera`
(`Source/SailingSim/Private/SailboatPawn.cpp` ~1895) puts the eye at the hidden helm's raw `head` bone, +10 cm forward
and +8 cm up, every frame, with no filtering. So during a crossing the camera inherits everything the helm's body does:

- **The crouch.** The helm drops to 0.5-0.55 m over the floor to pass under the boom, so the eye drops to the height
  of the other crew's heads and shoulders.
- **The steps.** Two 0.3 s steps on a 12 cm arc and the pelvis slide come straight through as bob and sway.
- **Nothing keeps the crew off the lens.** The trimmer crouches and crosses just ahead of the helm, so in
  `docs/crew-tack/strip-cockpit.jpg` the eye ends up a few centimetres behind their head: frames 6-7 are the inside
  of a cap, and frames 8-12 are the back of a head filling half the frame.

The look direction is fine: it is the boat's heading plus the player's own `CameraYaw`, not the helm's body.

Seeing the crew move across in front of you is real (a J/22 helm does). What is not real is your eyes dropping into
the crew's heads and bouncing with your feet. A person's head and eyes stay steady while the body moves.

## Options considered

| Option | What it does | Verdict |
|---|---|---|
| A. Hold, then cut | Eye stays on the old side until the crossing ends, then jumps | No: a jump, and wrong (the helm does move) |
| B. Steadied head | Eye follows the helm's head through damped springs: sideways fully, down only part of the crouch, step bob filtered out | **Yes, the core** |
| C. Pull back and up | Eye blends aft and up toward the transom during the crossing | No: the boom end and mainsheet are there on the J/22; a third-person look in a first-person view |
| D. Fade crew near the lens | Dither out any sailor within ~35 cm of the eye | No for now: needs a dithered opacity path in the crew and MetaHuman materials |
| E. Keep a gap | Eye eases aft (never forward) when a sailor's head is closer than 40 cm ahead of it | **Yes, with B** (camera-only, no material work) |
| F. Look into the turn | A small yaw lead toward where the boat is turning (real helms look at the new side's telltales) | **Yes, small**, off while the player is turning the camera |

## Recommendation: one PR, `cockpit-tack`

A new pure-logic struct, so tests can drive it without a world, the same way `FCrewCrossing` is:
`FCockpitEye` in `Source/SailingSim/Public/CockpitEye.h` (+ `Private/CockpitEye.cpp`). `UpdateCockpitCamera`
feeds it the raw eye (today's head bone + offset), the helm's `CrewFigures.Last().Crossing`, the other sailors'
head positions, the boom (angle and underside height over the eye) and the turn rate, and uses what it returns.

1. **Steadied eye (B).** Critically damped springs (`CrewSpring`) per boat-frame axis on the raw eye:
   - Y (across): omega 6 rad/s (settles in about 1 s), so the eye travels across smoothly with the helm.
   - X (fore and aft): omega 6.
   - Z (height): only while the helm's crossing is active, the target is the seated eye height minus 40 % of the
     head's drop below it, and never higher than 15 cm under the boom's underside where the boom is over the eye.
     omega 4 rad/s, which also filters out the step bob. Outside a crossing, Z follows the raw eye with omega 12.
   - Outside a crossing the springs are stiff enough that steady sailing looks the same as today (test 5).
2. **Keep a gap (E).** For each other sailor's head within a 60 deg cone ahead of the eye: if it is closer than 40 cm,
   move the eye aft along the boat's X by the shortfall (eased in over 0.15 s, out over 0.5 s), never past the transom
   minus 10 cm and never outside the cockpit well (`CrewCockpitWell`). If that is not enough, lift by up to 10 cm,
   still 15 cm under the boom.
3. **Look into the turn (F).** Yaw lead = clamp(turn rate x 0.5 s, +-15 deg), through a spring (omega 3), added to the
   look only while the player has not moved the camera for 2 s. Zero when the boat is not turning.
4. **The existing head lean and acceleration sway** (`CockpitHead`, `CockpitRoll`) stay as they are, applied after.
5. **Reset** the springs on `SetCockpitView(true)`, on a boat swap, and on any teleport (the start, a drill), so the eye
   never flies in from the old place.
6. **Dev arg** `-SailingCockpitRaw` turns all of it off (today's raw head eye), for before/after stills.

The reference capture's `HelmEye` (`ReferenceCapture`, `HelmSide` at ~3656) already uses its own slow interpolation
and is out of scope.

## Tests

New `SailingSim.Visual.CockpitEye` in `Source/SailingSimTests/Private/CrewMotionTests.cpp` (or a new
`CockpitEyeTests.cpp`), reusing the `SailingSim.Visual.CrewTack` harness: a J/22 tack and a gybe at 60 Hz with three
crew posed, then the same for the Catalina 22, Catalina 30 (wheel) and Hobie 16 (the helm crosses on the trampoline).

1. The eye is never closer than 35 cm to any other sailor's head (posed SK_Sailor head bone).
2. The eye stays at least 15 cm under the boom's underside wherever the boom is over it.
3. No bob: during the steps (phase C) the eye's height varies less than 3 cm peak to peak beyond the planned drop.
4. Across one way only: Y moves monotonically from the old side to the new side (2 mm noise allowed), inside the boat.
5. Unchanged at rest: in 20 s of steady sailing with no crossing, the eye is within 1 cm of today's raw head eye.
6. Settles: 1.5 s after the crossing's `EndTau`, within 2 cm of the raw head eye.
7. Look lead stays within +-15 deg and is 0 within 1 s of the turn ending.
8. Reset: turning the view on mid-tack starts at the raw eye with no jump over 1 cm.

All existing `SailingSim.Visual` tests must still pass (67 at #366).

## Stills

Redo the `docs/crew-tack/` cockpit strip (demo tack at 12 kn, every 0.25 s from 9.75 s:
`-SailingDemo -SailingCockpit -SailingShotCrew=<name> -SailingShotAtSim=<s>`), before (`-SailingCockpitRaw`) and
after, plus one gybe strip, into `docs/cockpit-tack/` with a short README. Success is that no frame is the inside of
a cap or more than a third filled by a head.

## Optional PR 2 (only if Bean asks after the retest)

A Settings > Camera choice, "Cockpit view on tacks": **Follow the helm** (PR 1, default) or **Steady**: the eye holds
on the old side until the boom passes the centreline, then glides across in 1.2 s at seated height. For players who
find any movement uncomfortable. Saved in `SailSave` like the other camera settings.

## Rules

- One PR against main, not stacked; one Unreal build on the Mac at a time (`Artifacts/mac-build.lock`).
- Online readiness: the cockpit camera is local to the player, nothing replicated; the springs run on the game thread
  only; the boom and crew inputs are read from state the pawn already has.
- Must compile with MSVC too: no shadowed names.
