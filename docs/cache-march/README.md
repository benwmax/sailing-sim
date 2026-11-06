# The far cumulus's blocks and pillars (Oct 26 2026)

The Ultra re-audit found blocks, pillars and blade-like ridges in the cumulus 3–10 km out. They go away with
`-SailingNoSkyCache`, and High showed them softly. Stills: the chase view (AfternoonBreeze, 14:00, 14 kn), with main on top
and this change below.

- `chase-ultra.jpg`, `chase-high.jpg`: the chase view on each tier.
- `ultra-zoom.jpg`: Ultra close up.
  - Top left: main. Top right: this change.
  - Bottom left: main's cache with only its sun term (`-SailingSkyCacheLight=1.7,0`).
  - Bottom right: main's cache with only its sky term (`-SailingSkyCacheLight=0,1.2`).

## What it was

The coarse march's step-back refinement was the first suspect. These tests rule it out:

| Test (chase view) | Blocks |
|---|---|
| Ultra at High's 96 steps, or at 4x the steps (`-SailingSkyCacheSize`) | still there |
| A new jitter hash, the footprint from the fine step, or the weather map's frame set per strip | still there |
| Ultra with High's cache and High's cloud settings | gone |
| High with Ultra's 8192 x 1024 panorama | there |
| High with twice the rows only, or twice the columns only | a little sharper |
| The cache's light at zero (`-SailingSkyCacheLight=0,0`) | none: every cloud in the view is the cache's, and its silhouettes are smooth |
| The cache's sun term alone | there |
| The cache's sky term alone | smooth |

So the blocks are in the cache's sunlight. `CACHE_SHADOW` lights each view sample with five shadow samples toward the
sun, at the middles of steps doubling from 50 m. That puts them on shells at 25, 100, 250, 550 and 1150 m round every
cloud. Every texel's shadow samples fell on the same shells, so the sunlit term changed in terraces along them. Ultra's
finer panorama (twice the texels each way, read texel by texel through the spline) drew those terraces sharp: the
blocks, pillars and blades. On High's coarser panorama they stood as soft creases.

## The fix

- **Jittered shadow shells** (`CACHE_SHADOW`). Each shadow sample is jittered over the middle half of its step, offset
  by the golden ratio per step. Over the whole step the grain showed; over half, neither the grain nor the terraces
  do. The jitter is shared by a block of 2 x 2 texels on High's panorama. One per texel cost up to 1.2 ms of GPU on
  High, because neighbouring texels' shadow samples no longer read the same places; 8 x 8 brought the terraces partly
  back. `jitter-blocks.jpg`: per texel, 8 x 8, 4 x 4 and main. Ultra kept 4 x 4 at first, but its blocks stood as
  square patches in the cumulus's shadowed creases (feedback #8), so Ultra's 8192-wide panorama now jitters every texel
  (`CacheShadow.w`, set from the targets' width; `-SailingSkyCacheJitter=<w>` measures, 0 is the old fixed grid).
  High's 2 x 2 blocks still showed faintly; since pc/clouds-high each texel's jitter is a linear blend of the four
  nearest blocks' (by block centres, the azimuth wrapping at north), which reduces the step at the block edges to a blend.
  Cost on the PC: the same gpu total (6.44 ms), clouds_fog 0.23 to 0.29 ms (as per texel); the Mac is not measured yet
  (per texel cost it up to 1.2 ms). `-SailingSkyCacheJitter` above 2 makes bigger blocks blended the same way: their middle
  texels take a 50/50 blend (a triangular jitter).
- **The dome's spline knots** (`M_SkyDome`). The knots are never finer than two of Ultra's texels above 3 deg (nearer
  than about 23 km over a 1.2 km base, where the march's 35 m fine step spans two texels). That averages the jitter's
  grain on the near cumulus. Below 1.5 deg, where Ultra's panorama draws the small far cumulus, the spline still reads
  every texel. On High's 4096 panorama nothing changes.

Nothing is added to the march: one `frac` and a multiply-add per shadow sample, and one divide in the dome.

## Gate (clouds scope, macOS 27.0.1)

Both runs on main cab3b748. Tests 238/238, every view passes.

| View | Tier | main fps | this fps | main GPU ms | this GPU ms |
|---|---|---|---|---|---|
| beam8 | High | 57.6 | 57.9 | 16.03 | 16.04 |
| beat15 | High | 55.4 | 55.2 | 16.49 | 16.86 |
| storm | High | 47.7 | 48.0 | 19.19 | 19.06 |
| gulf-sea | High | 60.3 | 60.5 | 15.60 | 15.28 |
| helm-eye | High | 54.6 | 54.4 | 17.38 | 17.58 |
| bridge | High | 58.4 | 58.4 | 15.60 | 15.99 |
| storm | Medium | 68.3 | 68.9 | 14.03 | 14.14 |
