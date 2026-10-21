# The white polygon off the J/22's quarter

The PC's Ultra audit (`docs/clipping-audit-2/water-rectangle.jpg` on `audit-fixes`) found it on a 15 kn beat: a flat,
hard-edged white polygon about a metre off the J/22's low side, aft, following the boat. The Mac reproduces it on
High and Ultra:

```
-SailingBoat=J22 -SailingWind=15 -SailingTWA=42 -SailingHoldTWA=42 -SailingCamTarget=-2.5,-1.8,0.1
-SailingCamYaw=180 -SailingCamPitch=-25 -SailingCamDist=4
```

It is not the hull clip, a shadow, the wind map or the wake grid. It is `M_WaterV4`'s own white water, `hullFoam` in
`V4_SHADE`, and it went away with that term off.

## The cause

The hull clip map (`FHullClipMap`) covers the hulls plus two texels of padding, a few centimetres. Further out the GPU
clamps to the edge texel, so the side margin it reads stops at about -4 cm, however far from the boat the pixel is:

- **The waterline band** fades out at 10 cm outside the deck edge. With the margin stuck at -4 cm it never faded. On
  the low side of a heeled boat, the water rises in her frame with distance, so the band (the water within a few cm of
  the bottom, which past the deck edge is the sheer) drew a strip out on the water, shaped by the sheer.
- **The transom churn** spreads at 0.3 m per metre aft of the transom's half-width. With the margin stuck it ran
  sideways right out to the branch's reach.

## The fix

Past the map, the shader adds the distance beyond the map's edge to both margins, as the churn already did aft.

## Before and after

High, 15 kn:

- `rect-before`, `rect-after`: 42° TWA, the repro view. The polygon is gone. The dark band along her side is her
  shadow.
- `churn-before`, `churn-after`: 90° TWA, looking aft over the transom. The churn now stays near her wake instead of
  spreading wide across the water.
