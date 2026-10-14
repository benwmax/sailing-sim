# Graphics G6: the tells (working notes)

Round 7 of the blind test (10 real photos, 10 game stills): Bean scored 19 of 20 and caught 9 of 10 game frames. His
reasons, plus my own read, give the fix list below. Branch `graphics-6-fixes` (from `graphics-5-blind`). No PRs beyond
the one-at-a-time queue (V7, then G1 to G5, each against main).

## Fixes, in priority order

- [x] 1. Cloud grain in storm skies (game-04, game-08: "clouds have a lot of noise").
- [ ] 2. Shoreline and buildings (game-09, game-03): houses from the G2 footprints, roofs and colours (full detail
      within 400 m of the water).
- [ ] 3. Boat and crew detail in close-ups (game-06 action cam): fittings, lines, clothing creases, PFDs, sail creases.
- [ ] 4. Distant water reflections from a high camera (game-03 drone).
- [ ] 5. The slip (game-07): a berthed boat with the boom down and sails stowed.
- [ ] 6. Lesser: race-start water (game-01) and the Gulf under overcast.

## Gate

Tests green (92+); Medium 60 and High 45 on every bench-visual view; README with before/after per fix; round 8 pack:
the ten round 7 scenes recaptured with the same arguments (`docs/graphics-5/game/final.csv`) to
`docs/graphics-6/game/game-01..10.png` (1440x1080).

## Log

- Fix 1 (14 Oct): the grain was optical depth per march step. Near the horizon a view ray crosses tens of km of the
  slab in 80 samples (600 m steps), and the shadow rays take 10 samples over 4 km (400 m); at 0.1 /m the cloud went
  opaque inside one step, so each pixel was lit at whatever depth its jittered sample landed. The material now knows its
  step (`Tracer`, `TracerShadow` from the component and cvars), caps the optical depth per step (storm, stratus and rain
  at 1 by the longer of view and shadow step; fair cumulus at 2 by the view step) and filters its noise at the step.
  The rain streak noise had no mip (vertical scratches). Editor runs now finish shader compiling before the measured
  window (a still once came out with no clouds).
