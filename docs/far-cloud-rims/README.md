# Far cloud rims at low sun (Oct 24 2026)

In the dusk stills the far clouds, drawn from the sky cache (C2: a 4096 × 512 panorama, -3 to 33°), had jagged bright
rims with stair-steps along their outlines and single bright texels along the sunlit edges.

## Cause

Two things, both at the cache's texel (about 0.09 × 0.07°, about 1.6 px at 80° across 1440 px):

- **The stair-steps:** M_SkyDome read the panorama bilinearly. A low sun's rim is a texel or two wide and far brighter
  than the cloud behind it, and bilinear interpolation of such an edge draws the texel grid.
- **The speckle:** the cache's march jitters each texel. The comment there says the refreshes are blended so the grain
  averages out, but `CacheShadow.z` is 1: each refresh replaces the last, deliberately, because blended a third at a time
  the clouds' drift between refreshes stacked into ghosts. So each refresh's grain stays in the panorama.

## Fix

M_SkyDome reads the cache through a cubic B-spline: four bilinear fetches for each of the two panoramas, in place of
one (Sigg and Hadwiger 2005).

- The spline is smooth to its second derivative, so the outlines lose their steps.
- It averages each texel with its neighbours, so the grain is softened.
- The cache is unchanged, so its refresh, cost and ghosting are as before.

High-frequency energy in the cloud band (luminance less a 3 × 3 box blur), High, capture mode:

| View | Before | After |
| --- | --- | --- |
| Galveston dusk (sun 4°) | 1.60 | 1.28 |
| Lake sunset (sun 2.6°) | 1.70 | 1.26 |

`dusk.jpg`, `sunset.jpg`: before above, after below, enlarged 2× (nearest neighbour).

The cache comment's "blended" is now wrong, so it gets corrected (`make_materials.py` `CACHE_HEAD`).
