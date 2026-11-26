# White streaks on the lake: windrows and the wind map (Nov 25 2026)

Bean, Nov 25: "white streaks pass across the surface of the lake ... too repetitive and obvious, and they stutter a bit
(the water still seems to stutter, or maybe it all stutters)."

## What they were

- **Windrows** (W2, `M_WaterV4`): from about 6-9 kn of slow wind, thin lines along the wind about 14 m apart, out to
  260 m. Each smooths the ripples (`smoothing` 0.5), so it mirrors the sky: a white line. They were sines (fixed spacing,
  sine bends, sine dashes) with three rows in four drawn: a ruled field.
- **Why they moved:** they were laid along `WindSlow` measured from the map origin (the club). `WindSlow` is the readable
  wind at the boat smoothed over 120 s, so each small turn swung the whole pattern about the club: a tenth of a degree
  moves a row 1 km out by 1.7 m. The slicks did the same (same family as #805's foam fix).
- **Why they stuttered:** `WindSlow` was set at 10 Hz (`UpdateGustMap`), so the swing came in steps. Separately, the wind
  maps (cat's paws, glassy lulls, the ripples' local direction, the windrows' on/off) are rebuilt a strip at a time, a whole
  pass every 0.8 s (1.6 s on Ultra), and the water drew each strip as it was written: everything the maps drive ticked.

Not this: feedback #26 (the world clock's 120 Hz steps, fixed by #787's render clock).

## The change

1. **Two fixed frames** (`AWaterSurface::StepRowFrames`): the slicks and windrows lie along `WindSlow.xy` (older) and
   `.zw` (newer) and cross-fade over `kRowFadeSeconds` (45 s) once the smoothed direction has turned `kRowTurnDegrees` (3)
   from the newer. Nothing slides across the water. `WindRowFade.y` carries the dashes downwind at 2% of the wind on the
   render clock. The gale streaks (24 kn+) turn with the blend of the two frames, smoothly.
2. **Windrows less regular and fainter:** spacing bent by value noise, under half the rows drawn and each in stretches of
   one or two hundred metres, value-noise dashes, fade-out by 150 m (was 260), smoothing 0.3 (was 0.5).
3. **Wind maps blended in time:** each level keeps its last whole pass (`FWindLevel::Shown`) and the one before
   (`GustPrevMap`, `WindFarPrevMap`); the water blends between them over the time a pass takes (`WindBlend`, render clock).
   Uploads drop from one per 0.1 s to two per pass. It adds one pass of latency (0.8 s; the roughness already rises over 2 s).
   Both water materials read the previous maps through their maps' own samplers (no new sampler slots).
4. Args: `-SailingNoWindrows` (none drawn), `-SailingClassicWindMap` (strips drawn as written, no blend).

Test: `SailingSim.Visual.WindrowFrames` (an hour of shifting wind: frames change only by starting a cross-fade, never
during one, the newer frame keeps up).

## Proof (to do)

- Mac: `MATERIALS_ONLY=build_water,build_water_v4`, build, tests, `gate.sh --scope water`.
- PC: before/after stills and 10 s clips at 8 and 12 kn, helm eye and 30 m up, at the club and 3 km out.
