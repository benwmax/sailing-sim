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
(`SkyCacheKnotPixels`: the camera manager's FOV over the viewport's width). Past 6 px (`kSkyCacheMaxKnotPx`) the cache is
set aside as it is under a storm or a closed deck: the live clouds draw the whole sky to their full tracing distance.
Under 5 px again it comes back (a band, `SkyCacheTooCoarse`, so a zoom held at the edge doesn't toggle it). The log
says each change ("Sky cache: set aside for a narrow lens ...").

- Playing views (60-120 deg on any screen up to 3840) stay under 6 px: no change, no cost. Gate and bench views run at
  90 deg.
- It switches on for the film tripod and path shots with long lenses, a zoomed photo mode lens, and a zoomed view mount
  at 4K. There the far clouds cost what they did before the cache (+0.6 to 1.8 ms on the 4090 at Ultra,
  docs/ultra-cloud-tops/); film mode renders offline.
- Measuring: `-SailingSkyCacheMaxKnotPx=<px>` (0: never set aside; the old behaviour). `-SailingNoSkyCache` still turns
  the cache off everywhere.

Test: `SailingSim.Visual.SkyCacheLens`.
