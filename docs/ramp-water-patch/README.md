# The square patch of water by the club ramp

The PC's in-game still `docs/texture-loop/ingame/dock-ramp-high.jpg` (branch `pc/content-import-nov8`, Nov 9 2026)
shows a hard-edged, lighter square of water beside the launch ramp at Rush Creek.

## Cause

It is the water's shore map, not the ramp's material (#552) or the marina rebake.

`AWaterSurface` keeps a 512 m map of water depth round the boat (`ShoreMap`, 1 m cells). `M_WaterV4` reads it for
the shore's look: under 0.35 m it draws the lapping foam line (`swash`), under 0.4 m it calms the short waves (flatter,
more mirror-like water), under 2 m the waves shoal. Every dock, pier, breakwater and berthed boat is stamped into the map
as shallow water (0.05 m at its edge, 0.6 m deeper per metre out), so the waves lap against it.

The stamp only filled a box 2 m past each obstacle's two end points. The launch ramp's dry part is an obstacle with a
2.65 m half width (club docks pass 3, #454), wider than the box. Where the ramp meets the water the box cut straight
through the ramp's own footprint: inside it, 0.05 m deep (full lapping foam, flat water); one cell outside, the lake's
real depth. That gives an axis-aligned square of foamy, flat water with hard edges right off the ramp's waterline.
The breakwater (3 m half width) had the same cut, mostly hidden under its rocks.

## Fix

`AWaterSurface::BuildShoreDepth` (the shore map, moved out of the worker lambda so it can be tested):

- Each stamp now reaches `ShoreReachM` (3.25 m) past the obstacle's half width, where it is 2 m deep. `M_WaterV4` stops
  reading the depth at 2 m, so the stamp meets the lake's depth with no step.
- The ramp is stamped as its slab (the water over the slab, 0.05 m where it is out of the water) rather than as a
  structure standing in the water. The capsule's round end would otherwise put a disc of lapping foam 2.65 m past the
  waterline, over the submerged slab. The waves now lap across the ramp at its waterline, and the water over the slab
  gets deeper with it.

`shore-map-before-after.png` is the shore map round the ramp worked out from the committed Ray Hubbard terrain (1 m
shore detail), 0.25 m cells. Blue is shallow, pink is where the lapping foam is drawn, green is land. Left is main: the
pier's lapping band, and the square off the ramp's waterline. Right is this change: lapping along the ramp's waterline,
the slab's shallows fading out down the ramp. The largest step between neighbouring cells drops from 0.62 m to 0.15 m
(the terrain's own steepest step there is 0.14 m).

`SailingSim.Lake.ShoreMapAtRamp` builds the game's map round the ramp. It checks for a step the bed doesn't have, for
lapping at the ramp's waterline, and for the water over the slab 10 m down it.

Side effect: around every dock the stamp now fades out over 3.25 m instead of stopping at its box. Inside that ring the
water shoals a little more than before (the short waves up to 1.2x steeper where the old box ended). This is meant to be
continuous, not stronger. The Mac world gate's marina views are the check.

## Also: -SailingHoldTWA on port

The same stills run asked for port tack with `-SailingTWA=-60 -SailingHoldTWA=-60` and got starboard. `-SailingTWA`
pointed the boat on port, but the demo autopilot multiplied the hold angle by the starting tack's sign (-1), so -60
became +60 and it tacked. A negative `-SailingHoldTWA` is now port, as `-SailingTWA`'s sign is. A positive one still
holds whichever tack she starts on, so every existing script behaves as before.
