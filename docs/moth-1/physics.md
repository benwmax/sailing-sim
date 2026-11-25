# Hydrofoil moth: what the physics needs (Mac, after Dec 11)

The moth is the first boat in the game that sails **above** the water. Every boat so far floats on her hull and
uses her fins (keel, boards, rudders) only to stop her sliding sideways. The moth's hull leaves the water at about
7 knots and from then on two small underwater wings carry her whole weight. This page is the spec the Mac's physics
slice (slice 8) works from. Nothing here is code yet; nothing lands before the Dec 11 release, and the Lagoon 42 and
the Hobie 16 get the Mac first.

## Words used here

- **Foil:** an underwater wing. **Main foil:** the wing at the foot of the daggerboard (the **strut**), under the
  middle of the boat. **Elevator:** the smaller wing at the foot of the rudder, like a plane's tailplane.
- **Flap:** the hinged back part of the main foil. Flap down = more lift, flap up = less.
- **Wand:** a light stick hinged at the bow, its tip dragging on the water. When she flies higher the wand swings
  back, and a pushrod down the strut lifts the flap, so she settles back down. That loop is how a moth holds her
  height by itself. **Gearing:** how far the flap moves per degree of wand.
- **Ride height:** how high the hull flies above the water. **Twist grip:** a grip on the tiller extension that
  tilts the elevator, to trim her nose up or down.
- **Low-riding:** sailing on the hull like a normal dinghy, before take-off. **Ventilation:** air sucked down onto
  a foil that comes too near the surface; the foil loses its lift at once.
- **Lift coefficient (CL):** how hard a wing is working; about 1.2 is the most a small flapped foil gives before it
  stalls.

## What the game can't do today

`Source/SailingPhysics/Public/Foil.h`: `FFoilParams` is "a keel or rudder as a finite wing, **standing vertically**",
and `ComputeFoil` uses only the X and Y parts of the flow. Every `EFoilRole` (Keel, Board, Rudder, HullLateral) pushes
sideways. There is no foil that lifts up, no flap, no ride height, no wand and no way for a foil to break the surface.

## The numbers that drive everything

`python3 -I Tools/shipkit/moth/moth_check.py --card` prints this: the lift coefficient each foil needs to hold up
115 kg (35 kg boat + 80 kg sailor), with the main foil taking 85% of it.

| Boat speed (knots) | CL main foil (0.12 m²) | CL elevator (0.065 m²) |
| ---: | ---: | ---: |
| 6 | 1.68 | 0.55 |
| 7 | 1.23 | 0.40 |
| 8 | 0.94 | 0.31 |
| 10 | 0.60 | 0.20 |
| 15 | 0.27 | 0.09 |
| 20 | 0.15 | 0.05 |
| 30 | 0.07 | 0.02 |

What it says:

- **Take-off sits at 7 to 8 knots**, where the main foil needs CL 0.9 to 1.2: nearly all it has, flap fully down.
  Below that she can't fly; that matches the published 6 to 8 knots.
- **Between take-off and top speed the lift she needs falls 15 to 20 times.** Something must take the lift away as
  she speeds up, or she would leap out of the water. That is the wand's whole job, and why the flap and the wand
  loop must be in the physics, not faked.
- At 20 knots and up the foils barely work, so **drag** (the struts' and foils' skin friction and the spray off the
  struts) decides her top speed, not lift.

## What the physics slice adds (proposal for the Mac)

1. **Lifting foils.** A foil with a span direction (`FFoilDef` gets a span axis, or a new role `LiftingFoil`), so a
   foil can lie flat and push up. The main foil and the elevator each also keep some sideways grip from their
   vertical strut and rudder, which stay ordinary vertical foils.
2. **Flap.** The main foil's lift slope stays; the flap shifts its zero-lift angle (about 0.6 degrees of zero-lift
   shift per degree of flap for a 30% chord flap, to be checked against a published flapped-section table). Flap range
   about -5 to +15 degrees.
3. **Wand loop.** Ride height at the bow read from the wave height under the wand's tip (`FWaveField::Height`), wand
   angle from that, flap = gearing x (wand angle - its set point). Wand length and gearing are settings (ashore in real
   life; in the game, presets). The existing lift lag (`FoilLiftLagScale`, Wagner) stays on: it is real and it damps
   the loop.
4. **Elevator trim.** The twist grip sets the elevator's angle; the helm (player or autopilot) trims it.
5. **Depth effects.** A foil near the surface loses lift (free-surface effect), and one that breaks the surface
   ventilates: lift drops to near nothing in a few hundredths of a second and comes back only once it is deep again.
   The existing `LiftFactor` (ventilation by heel) is the hook. This is where crashes start.
6. **Crash states.** (a) The main foil ventilates or the bow drops: she falls onto the hull from 0.5 m at 15+ knots
   and stops hard (a "nosedive", the crew thrown forward: `FCrewFalls`). (b) Heeled too far to leeward with the foil
   near the surface: she slides sideways and capsizes to leeward. (c) Too far to windward (she flies heeled to windward
   on purpose): capsize to windward, the classic moth crash. Capsize state is by `Quat::Tilt()`, as for every boat.
7. **Hull in the air.** Hull buoyancy and drag fade to zero as the hull clears the water; the bow wave, spray, wake
   and hull clip (`FHullClipMap`) must follow her height, not assume she floats.
8. **The sailor is 70% of her weight.** At 80 kg against a 35 kg boat, where he sits (fore and aft as well as out on
   the wing) trims her as much as the foils do. `CrewAftRange` and the dinghy trimmer (`DinghyEasePerHeelDeg`) are the
   start; the sailor also leans the rig to windward, which turns some sail force into lift.
9. **Reference polar.** A new `FleetReferencePolar` from published figures only: take-off about 7 knots in 8 knots
   of wind; upwind 15 to 20 knots of boat speed in 12 to 16 knots of wind; downwind 25 to 30 knots. The Southampton
   moth VPP (Findlay and Turnock) and the Strathclyde T-foil tank tests (Day et al. 2019) are the papers to read
   first; their links are in `specs_moth.json`.
10. **Tests.** `SailingSim.Physics.MothTakeoff` (flies by 8 knots, not by 6), `MothRideHeight` (holds 0.4 to 0.6 m
   in flat water and in the lake's 12-knot chop without leaving the water for 5 minutes on the autopilot),
   `MothCrash` (each crash state reached and recovered), the polar gate for her points, and the J/22's `PolarGate`
   unchanged.

## Is 120 Hz enough?

Yes, by a rough sum: with a wand gearing that changes lift by about 1,000 N per 10 cm of height at 15 knots, the
boat (115 kg plus some added mass) bobs at about 1.5 times a second, and at 30 knots about 3 times. At 120 physics
steps a second that is 40 to 80 steps a bob: plenty. The risk is not the step size but a loop that is too stiff or not
damped enough, which makes her porpoise (bob in and out of the water). The tuning must be checked in chop, not only
in flat water.

## Risks, in order

1. The lifting foil, flap and wand are new code in `SailingPhysics` and touch the foil code every boat uses: the
   J/22's polar gate and every other boat's must not move.
2. Ride height tuning: too stiff porpoises, too soft crashes. The Mac tunes it standalone (`scripts/polar.sh --boat
   moth`, a new `--sea` case for her) before anything is drawn.
3. Take-off: the change from a dragging hull to flying is where drag peaks (the "hump"). Published numbers are scarce
   and come from forum and coaching sources; the reference polar's tolerance must say so.
4. Crashes at 25 knots need the crew-fall and capsize code to cope with a boat that stops in a boat length.
5. Depth: the foils reach about 1.1 m below the hull at rest. Ray Hubbard's shallows and the club's ramp need a "foils
   up" state for launching (in real life the sailor launches with the rudder up and pushes the boat off by hand).
6. Feel: how twitchy she is, how much Easy mode flies her for you (an automatic ride height and anti-crash, like the
   maxi's `FSceneLimits`) and what the controls are (twist grip on a key?) are Bean's calls once she sails.

## Not in this slice

- The model itself (slices 1 to 7, cloud) and the PC's import (slice 9).
- Foil gybes and tacks for the autopilot and AI boats: the first version can drop off the foils to tack, as beginners
  do; flying through a tack is a later step.
- Racing her against other moths (traffic and race AI) waits until she flies well alone.
