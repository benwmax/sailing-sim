# Water edge: skipping the far vertices' wave work (not shipped)

The #91 far grid (`AWaterSurface::BuildFarGrid`, 44 cells a side, 14.8k vertices from 504 m to 20 km) cost 0.2 to
0.3 ms of the water slice (docs/water-8/edge-mac). The freeze notes proposed winning it back by skipping the long
waves' vertex work past their 900 m fade (`WaveFadeMeters`) in M_WaterV4. I tried that and measured it. It doesn't win,
so it isn't shipped.

## Where the work is

The five rings (0.5 to 8 m spacing, 128 quads, half-widths 32 to 512 m) all lie inside the fade: the outer ring's
corners are 724 m out. Past 900 m there are only the far grid's vertices, about 12k of its 14.8k. There `V4_WPO` still
did the whole sum: seven sea-atlas samples and 24 sincos with Gerstner, slopes and Jacobian, all multiplied by
`fade = 0`.

## The change tried

Option (a): `[branch] if (fade > 0.0) { sea atlas; 24 long components; the fade multiplies }` around the long waves,
with the short-wave scale carried out in a local (the short waves fade by 300 m, inside the branch). The branch
switches exactly where the fade reaches zero, so the output is unchanged everywhere (past the fade h, d and the slopes
were already 0 and the Jacobian 1). Built with `MATERIALS_ONLY=build_water_v4`, packaged, then benched against the
main package, interleaved (before, after, before, after), 12 s per view, Mac (M5 Pro), `scripts/bench-visual.sh`.

## Results

Water slice (`gpu.water`, ms), two runs each:

| view | tier | main | branch |
|---|---|---|---|
| helm-eye | Medium | 1.86, 1.88 | 1.90, 1.96 |
| helm-eye | High | 2.18, 2.18 | 2.26, 2.36 |
| coast-day | Medium | 2.15, 2.20 | 2.26, 2.27 |
| coast-day | High | 2.61, 2.60 | 2.66, 2.67 |
| gulf-sea | Medium | 2.21, 2.21 | 2.26, 2.28 |
| gulf-sea | High | 2.85, 2.84 | 2.87, 2.93 |
| beat15 | Medium | 2.20, 2.53 | 2.33, 2.33 |
| beat15 | High | 2.53, 2.54 | 2.64, 2.72 |

The branch is 0.02 to 0.15 ms slower on every view, and 0.2 to 1.2 fps slower. `water_cpu_ms` doesn't change (the
material isn't on the CPU path).

To check that the far grid itself still costs what #91 measured, I benched main with `-SailingFarGrid=4` (almost no
grid) against the shipped 44 (water slice, ms, two runs each):

| view | tier | grid 4 | grid 44 |
|---|---|---|---|
| helm-eye | Medium | 1.66, 1.45 | 1.87, 1.91 |
| helm-eye | High | 2.03, 2.07 | 2.21, 2.23 |
| coast-day | Medium | 1.99, 1.99 | 2.19, 2.19 |
| coast-day | High | 2.44, 2.48 | 2.67, 2.62 |
| gulf-sea | Medium | 2.00, 1.99 | 2.20, 2.22 |
| gulf-sea | High | 2.62, 2.64 | 2.88, 2.87 |

The grid still costs 0.2 to 0.3 ms. Skipping the wave sum on its vertices recovers none of it. So the cost follows the
vertex count but not the arithmetic of the long waves. The likely cause is the size of M_WaterV4's vertex shader, which
the branch leaves unchanged and arguably makes worse: the registers it reserves cut occupancy for every vertex, whether
or not the sum runs. Other possibilities are the per-vertex work the branch doesn't touch (curvature, ocean to 6 km,
shore and wake lookups, the interpolators SLW carries) and the extra passes that run the vertex shader.

## What might work instead

- Option (c), a separate small vertex shader for the far grid: a material instance of M_WaterV4 with a static switch
  that compiles the long waves, detail and wake out of the WPO (curvature, ocean and shore stay; `LongN` = (0, 0, 1)),
  set on `FarPlane` only. That tests the occupancy explanation directly. The grid starts at 504 m, inside the 900 m
  fade, so to keep the seam invisible either the grid starts at the fade (the outer ring grows or a sixth ring is
  added), or the far grid splits into a near band with the full material and the rest with the small one.
- Option (b), fewer components far out, doesn't help: the branch already skipped all 24 and gained nothing.
- Fewer far-grid vertices (`FarGridPerSide`) trades the curvature error (2.5 cm at 44) against the measured cost. The
  table in docs/water-8/edge-mac still holds.
