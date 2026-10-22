# Whitecaps in the middle distance: why they go soft, and a plan

**The symptom:** at 12–20 kn, whitecaps are discrete white flecks out to about 150–250 m. Beyond that there are none,
only dark chop (`wide20-before`). From the helm's 2 m eye there are none past a couple of hundred metres.

## Why

Past the first few texels of the short-wave grid, `M_WaterV4` reads each pixel's cap cover from the fold table
(`DetailC`, W8). Its mips average the cover over the pixel's footprint, so the cover is right on average: it is what
`SailingSim.Visual.Whitecaps` holds to Monahan. But it is an average:

1. **The power.** The averaged cover was drawn to the power 1.5. That suits a near cap, where a pixel's cover is how
   much of one cap it holds and the power thins its edge. Far out, a pixel's cover is the share of a patch of sea under
   foam. On the lake that is 0.2% at 16 kn and 0.4% at 20 kn (Monahan's 0.5% and 1.1%, times fresh water's 0.4). To the
   power 1.5 it drew about a twentieth of the foam. **Fixed here:** linear in cover where the table is used, and the
   bubble cells' factor fades to its mean (0.6), not to the factor at the cells' mean (0.44).
2. **The averaging itself.** A 0.4% cover spread evenly over a pixel is a 0.4% brightening, which nobody can see.
   Distant caps are visible because each is a bright fleck on dark water. This needs new work: see below.
3. **The eye height.** From 2 m, a flat cap 1 km away is a few millimetres tall on screen. Real caps at that range read
   as flecks because they stand up (crest, spray), about 0.3–0.5 m, or half a pixel to a pixel at 1440×1080. No shading
   of the flat surface can show them.

The far band's mean brightness changes by under 0.2 levels in 255 with fix 1 (`wide*-before`/`-after`, `helm20-*`). That
is the expected size: fix 1 makes the energy right, but not visible. The cap thresholds (`CapCal`, `FoamThresholdAt`)
and the cover mask (`caps`) are untouched, so `SailingSim.Visual.Whitecaps` still holds the cover to Monahan.

## Options for points 2 and 3

GPU costs are estimates for the Mac's High tier at 1440×1080, to be measured with the bench's `water` slice. That slice
is now about 2.7 ms of a 15–16 ms frame on the lake views.

**A. Fleck cells on the far water (shader only).**
- **How:** where the table is used, split the sea into world-fixed cells about one cap across. Each cell holds a cap
  with probability cover ÷ (the fleck's area share), by a hash of the cell and a 3–5 s epoch, fading in and out over a
  cap's life. The mean stays the table's cover.
- **Cell sizes:** they step up by factors of two with the footprint, two levels cross-faded, so the flecks don't swim
  as the camera moves.
- **What it fixes:** point 2, for views from above about 10 m (drone, chase, chart). At grazing views a cell must be at
  least a pixel tall, so it gets wide: there the flecks become short horizontal dashes, a fair likeness of far caps.
- **Cost:** about 40–60 ALU per far pixel, under 0.1 ms. Risk: shimmer if the cell levels aren't tied to fixed
  distances.

**B. Cap sprites with height, for the horizon.**
- **How:** the CPU places cap sprites from the same Monahan cover. The game has its per-tile statistics already, in
  `FWaveDetail`'s `JCap` and `CapThreshold`. They're placed in a ring from about 150 m to 2 km around the camera, each
  living 2–5 s. Each is a small billboard 0.3–0.5 m tall, lit as the near foam, in an ISM like the spray's.
- **Count:** cover × ring area ÷ cap area gives about 15,000 at 20 kn. Culled to those at least half a pixel tall,
  roughly 2,000–5,000.
- **What it fixes:** point 3, the helm's eye.
- **Cost:** the ISM's draw and translucency, about 0.2–0.5 ms, plus about 0.2 ms of game-thread placement (the spray
  pool is the model).

**C. The long waves' fold per pixel in the far rings.** The fold is now computed per vertex (`V4_WPO`) and
interpolated across the far rings' large triangles. Carrying it per pixel would sharpen where caps sit on the long
waves at 200–600 m. It doesn't make caps visible on its own: they would still be averaged cover. About 0.5–1 ms (24
sine terms a pixel over the far band).

## Recommendation

A first: cheap, and it fixes the wide and aerial views. Then B, for the helm's horizon, which nothing else can fix. C
only if A and B leave the 200–600 m placement visibly wrong. Each should be held by a cover check against Monahan on the
drawn result, with `-SailingDebugFoam` counting the flecks.
