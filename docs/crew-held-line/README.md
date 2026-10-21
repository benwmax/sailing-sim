# The jib-winch hand and the light-air crew

The PC reproduced this on Ultra on main 2d46177e: J/22, 4 kn, 50° TWA, the leeward trimmer at the self-tailer. Two
symptoms:

- the fingers folded into a mitten through the sheet;
- the wrist bent about 90°.

The Mac stills turned up a third problem in the same light-air setup: the J/22's trimmer and bow sat inside each other on
the leeward seat.

## Fixes

- **Fingers on a held line** (`CrewSolver::CurlFingers`, a hand in Reach): the curl stops at the line's radius, at
  proximal 55, middle 70 and distal 45 degrees at full grip (the full fist was 72, 95 and 62). A relaxed or bracing hand
  is unchanged.
- **The wrist** (`CrewSolver::ClampWrist`, after the palm turns to the line): flexion within ±60° and deviation within
  ±25° of the rest pose. The turn about the forearm is left alone, so the forearm takes the rest.
- **The light-air seat** (`CrewPlacement`): the keelboats' seated crew are now each 0.45 m further aft than the one
  forward of them. Before, all of them were clamped to the same spot, 0.3 m aft of the well's forward end. On the J/22 the
  trimmer takes the forward place, beside the jib winch, and the bow sits next aft.
- **The jib sheet's tail** (`UpdateModelRig`): it goes only into a hand that holds it. Otherwise it lies where the model
  lays it. Before, it went to the nearer hand resting on a knee, through the thigh.

`SailingSim.Visual.CrewHeldLine` holds all of this. Main fails it with wrists bent 76–83°, a middle-finger curl of 123°,
and the J/22's crew 0.28 m apart.

- **Hands:** each MetaHuman rig closes a hand on a line in five directions. The checks:
  - the wrist bends at most 66° from rest;
  - no finger bone passes within 0.6 cm of the line;
  - the middle finger curls at most 110° over its first two joints.
- **Spacing:** every boat's crew sit 0.4 m apart or more, in CrewHullClearance's cases.

The stills are before (main) and after, High, 4 kn, 50° TWA:

- `winch-hand-side`: the trimmer and bow apart;
- `hands-close`: the hands, and the tail no longer through the thigh.

## Not done

- **The winch hold itself:** on the Mac, the trimmer doesn't take the tail into a hand in this setup, on main either. So
  the fixed winch hand can't be shown here; the test checks the hand directly. Please re-shoot it on the PC with the same
  args.
- **The vest at the armpit:** the vest poking through the polo at the armpit isn't touched. It needs the vest's weights
  near the armpit checked in `build_vest.py`, with the MetaHuman clothes rebuilt.
