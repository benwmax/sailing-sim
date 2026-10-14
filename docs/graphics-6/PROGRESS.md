# Graphics G6: the tells (working notes)

Round 7 of the blind test (10 real photos, 10 game stills): Bean scored 19 of 20 and caught 9 of 10 game frames. Across
all four packs he caught 34 of 35 game frames; only the marina masts from the shore passed. His reasons, plus my own read,
give the fix list below. Branch `graphics-6-fixes` (from `graphics-5-blind`). No PRs beyond the one-at-a-time queue (V7,
then G1 to G5, each against main).

References: Bean's eight lesson photos in `Data/Reference/raw/j22-lessons` (git-ignored, faces: never committed). They
show the club's royal blue Type III vests (grey webbing, three buckles; the instructor in a black inflatable), caps and
sunglasses, beige grimy non-skid and grey teak toe rails, a Mercury outboard on a stern bracket, the drive-on lifts with
blue floats, grey-blue townhouses behind the Rush Creek docks, olive-grey water with foam streaks at 10 to 12 kn, and
off-white sails with creases and seams.

## Fixes, in priority order

- [x] 1. Cloud noise and grain in storm and cumulus skies (dbf2f7f): optical depth capped per march step, noise filtered
      at the step; overcast stratus capped by the view step (0354ba2) so it stays grey; overcast coverage 1.0.
- [x] 2. Shore: houses from the G2 footprints (0354ba2: `build_houses.py`, `HouseKit.cpp`, 553 baked Nanite tiles; lidar
      eaves and ridges, NAIP roof colours, full detail within 400 m of the water); trees from the G2 lidar crowns
      (44478f7: `build_crowns.py`, `PlaceCrownTrees`: real positions, heights and crown widths, all within 400 m, one in
      three beyond; species by crown shape); the tree models' opaque cores smaller, smooth and shaded.
- [x] 3. Boats and crew: J/22 fittings (winches, cam cleats, blocks, coiled tails; 0354ba2), lines in the crew's hands;
      six berthed dresses per keelboat in the marina (44478f7: cover colours, flaked mains, covers, dodgers, fenders,
      gear, outboards, burgees); the club vests tailored over each polo and skinned (eaef74c: `build_vest.py`); beige
      non-skid and teak toe rails.
- [x] 4. Sails: off-white Dacron, yellowing toward the leech and head, a grey foot, mildew specks, fold lines and seam
      pucker in the normal, resin sheen (0354ba2, 44478f7).
- [x] 5. The container ship (4a3d223): stepped house with windows and rails, bridge wings, radar mast, funnel band, three
      cranes, lashing bridges, bulwark rails, mooring gear, lifeboats, corrugated containers, rust weeping down the hull.
- [x] 6. Far water from a high camera: unresolved slope as roughness (Cox and Munk) so a breeze never mirrors like a calm;
      the bare clay and wet band only within 14 m of the water (0354ba2).
- [x] 7. The slip: a keelboat tied up in her slip wears her berthed dress (sails stowed, cover on, boom on the
      centreline) until she casts off (0354ba2).

## Gate

Tests green (92+); Medium 60 and High 45 on every bench-visual view; README with before/after per fix; round 8 pack:
the ten round 7 scenes recaptured with the same arguments (`docs/graphics-5/game/captures.csv`) to
`docs/graphics-6/game/game-01..10.png` (1440x1080).

## Log

- Fix 1 (14 Oct): the grain was optical depth per march step. Near the horizon a view ray crosses tens of km of the
  slab in 80 samples (600 m steps), and the shadow rays take 10 samples over 4 km (400 m); at 0.1 /m the cloud went
  opaque inside one step, so each pixel was lit at whatever depth its jittered sample landed. The material now knows its
  step (`Tracer`, `TracerShadow` from the component and cvars), caps the optical depth per step (storm, stratus and rain
  at 1 by the longer of view and shadow step; fair cumulus at 2 by the view step) and filters its noise at the step.
  The rain streak noise had no mip (vertical scratches). Editor runs now finish shader compiling before the measured
  window (a still once came out with no clouds).
- 14 Oct, after the restart: the previous session's work committed as found (0354ba2). Tests 93 run, 0 failed on it.
- Trees: 279k lidar crowns placed on the lake plus 19k canopy-map trees outside the band (was 99k canopy-map trees).
  The near trees showed their opaque cores as faceted green balls; cores now at 50% of the far blobs, smooth-shaded and
  darker, and only cards deep inside them dropped.
- Gotchas: a new BMesh face's normal is zero until `normal_update()` (every vessel's box UVs were projected along X);
  Unreal's FBX import flips V (a material reading height from UV.y must use 1 - y); `env.sh` sets `-e`, so a `grep`
  that matches nothing ends a script that sources it.
