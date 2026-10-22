# The wake's smooth lane

I checked the Oct 20 water gap list against main first:

- **Spray, the slam splash and the bow wave's sheets:** done (#197).
- **The bow wave's curl and the topsides' wet band:** done (#202, #206).
- **Waterline foam, transom churn, the grazing-angle foam:** done (#197, #215). The far caps' fold, drawn per vertex,
  is still soft in the middle distance; that is a bigger job.
- **The stern wake:** the wake grid's Kelvin waves are drawn (`V4_WPO` adds their height), but from above and astern a
  J/22 at 6 kn left almost nothing behind her within a boat length.

That last one was the most visible gap.

**The reference:** a sailboat's wake, seen from a following boat or the air, is a narrow lane of smoother, darker water
directly astern. The water her hull and keel stirred damps the wind's ripples, so the lane reflects the sky like a
glossy stripe through the chop and breaks the sun's glitter. It widens slowly and lasts tens of boat lengths, a minute or
so. The Kelvin waves spread from it at about 19.5° each side.

## What's new

- **The slick field** (`FWakeGrid`): a value per cell, 0 to 1.
  - It is set to 1 under a hull, decays over 40 s and diffuses at 0.15 m²/s, so her beam's width roughly doubles over
    its life.
  - It fades at the grid's sponge edge, so the grid's outline never shows.
  - It is the wake map's third channel (now RGBA: height, foam, slick).
- **The shader** (`M_WaterV4`, `V4_SHADE`): along the lane the water is smoother (`smoothing`, as the light-air slicks
  and windrows already are). The slopes are damped and the roughness floor is lowered.
- **Reach:** the grid covers 64 m on High and 128 m on Ultra around the boat, so the lane is drawn to about half of
  that astern.
- **The test:** `SailingSim.Visual.WakeGrid` now checks the lane on its 6 kn run. It is 1.0 under her, 0.47 20 m astern
  (3.0 m wide against her 2.4 m beam), and 0 8 m to the side.

## Stills

High, J/22 on a reach, before (main) and after:

- `astern-*` (12 kn, from a following boat): a glossy lane runs back from her, her reflection stretched along it.
- `above-*` (12 kn, from 35 m up, in the sun's glitter): a darker, smooth track behind her through the sparkle.
- `light-*` (7 kn): the lane behind her in light air.

## Gate

`scripts/gate.sh --scope water` on 134545de: pass, 221/221 tests. beam8 61.4, beat15 60.5, storm 46.7, marina 59.7,
coast-day 53.8, gulf-sea 62.9, helm-eye 59.1, bridge 63.7, storm on Medium 65.1. The slick's step adds one 3×3 pass
over the grid on its worker thread.
