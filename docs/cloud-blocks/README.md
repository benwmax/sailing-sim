# Cloud blocks through a narrow lens

Found by the film mode work (PR #817, PC runs on the inputs branch under `Inputs/bench/pr817/`): at Ultra 3840x2160 through
the film tripod's 26 deg lens, the far clouds showed a regular grid of soft square tiles along their edges and through
their thin parts. It was the same with `r.VolumetricRenderTarget.Mode` 3 (full resolution, 512 samples) and 1, and with
motion blur off, so it was not the volumetric render target or the blur.

## Cause: the sky cache's knots, magnified

Past 5 km (`kSkyCacheSplitM`) the clouds are not drawn by the live volumetric march but by the sky cache (C2): a panorama
marched a strip at a time and read by `M_SkyDome` through a cubic B-spline (docs/far-cloud-rims/, docs/cache-march/).
Ultra's panorama is 8192 x 1024 over 360 x 36 deg, and from 3 deg up the spline's knots are coarsened to 4096 x 512, so a
knot is 0.088 deg across and 0.070 deg tall (High's 4096 x 512 has the same knots).

| View | Pixel (deg) | Knot on screen |
| --- | --- | --- |
| 90 deg on 2560 px (playing) | 0.035 | 2.5 px |
| 90 deg on 3840 px | 0.023 | 3.8 px |
| 60 deg (Settings' narrowest) on 3840 px | 0.016 | 5.6 px |
| Film tripod, 26 deg on 3840 px | 0.0068 | **13.0 x 10.4 px** |

Each knot is one jittered march through the cloud, so the spline, smooth as it is, draws the knots' differences as a
lattice of soft squares once a knot is many pixels wide. The pr817 crop (`4acec367/clouds-1to1-mode3-vs-mode1.png`) has
its edge autocorrelation peaks at 13, 26 and 39 px across: the knot exactly. A finer panorama only halves the squares
(16384 wide costs four times the march); through a long lens the cache has nothing finer to give.

Not a regression of feedback #22 (the live clouds' grain, docs/cloud-shimmer/): that is the near march, this the far
panorama.

## Fix: a narrow lens takes the whole sky live

`ASailingEnvironment::UpdateSkyCache` works out how many pixels a knot spans in the player's view
(`SkyCacheKnotPixels`: the camera manager's FOV over the game viewport's width). Past 8 px (`kSkyCacheMaxKnotPx`) the
cache is set aside as it is under a storm or a closed deck: the live clouds draw the whole sky to their full tracing
distance. Under 7 px again it comes back (a band, `SkyCacheTooCoarse`, so a zoom held at the edge doesn't toggle it).
The log says each change ("Sky cache: set aside for a narrow lens ..."). A panorama cut short by the switch (or a storm)
starts again from its first column when the cache returns.

Where it switches on (knot px = 0.0879 x width / FOV):

| View | 1920 | 2560 | 3456 (Mac Retina) | 3840 | 5120 |
| --- | --- | --- | --- | --- | --- |
| Chase, Settings FOV 60-120 | 1.4-2.8 | 1.9-3.8 | 2.5-5.1 | 2.8-5.6 | 3.8-7.5 |
| Cockpit / ship walk (FOV - 10, from 50) | 3.4 | 4.5 | 6.1 | 6.8 | 9.0 (on) |
| Mount zoomed to its 30 deg | 5.6 | 7.5 | 10.1 (on) | 11.3 (on) | 15 (on) |
| Capture Chase 50 / HelmEye 70 / Drone 80 | under 8 | | | 6.8 / 4.8 / 4.2 | |
| Capture ShoreTele 15 | 11.3 (on) | 15 (on) | | 22.5 (on) | |
| Film tripod 26 | 6.5 | 8.7 (on) | | **13.0 (on)** | |
| Photo lens 10-110 | on under 21 deg | under 28 | under 38 | under 42 | under 56 |

- Gate and bench views run the 90 deg chase or HelmEye at 70 deg: never on, no cost.
- Playing views (the chase at any Settings FOV) stay under 7 px on screens up to 3840 wide (the Mac's Retina 3456 too), so
  after a zoom the cache always comes back. On 5120 the chase at a Settings FOV of 60-64 sits inside the band (7.0-7.5
  px): after a zoom the live sky stays until the FOV is 65 or more, and the cockpit at a narrow Settings FOV (9.0 px at 50)
  switches it on.
- Where it is on, the far clouds cost what they did before the cache (+0.6 to 1.8 ms on the 4090 at Ultra,
  docs/ultra-cloud-tops/); film mode renders offline.
- Coming back, the cache's first panorama is marched at the fast rate (1 s) and handed over in play: one visible change
  in the far clouds a second or so after zooming back out (docs/cloud-popin/'s pop, which the loading screen hides at
  the start). Accepted: it happens only after a long lens.
- The view's width is the game viewport's, not an offline render's: a film frame larger than its window (HighResShot
  multipliers, a render queue) would read the window's knot size. The film tripod renders at the window's size
  (`-ResX=3840 -ForceRes`); its log should show the "set aside" line.
- Measuring: `-SailingSkyCacheMaxKnotPx=<px>` (0: never set aside; the old behaviour). `-SailingNoSkyCache` still turns
  the cache off everywhere.

Test: `SailingSim.Visual.SkyCacheLens`.
