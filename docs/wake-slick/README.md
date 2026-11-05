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

## Follow-up: shorter and softer (sailing-feedback #9, Nov 2026)

Testers saw the lane as a long, dark, flat ribbon with hard edges running out of frame (Ultra, J/22 at 5.3 kn: the
grid there is 128 m, and the 40 s lane held its full strength for most of it). Now:

- **Life 12 s, not 40; spreading 0.3 m²/s, not 0.15.** About 0.3 of its start 20 m astern at 6 kn and close to nothing
  by 40 m, a few boat lengths, with soft edges.
- **Set by her speed** (full from 2.5 m/s, about 5 kn), so a boat drifting or tied up leaves no lane round her.
- **The shader** follows the lane instead of saturating it: `0.45 * slick^1.5`, not `0.8 * saturate(1.5 slick)`.
- **A pale trail just astern:** water a moving hull has just left gets bubbles (foam 0.7 at full speed, fading over
  the foam's 4 s life), a broken white trail two or three lengths behind her, thickest down her middle and fading to nothing at her sides (0.35 across her whole beam at first: too faint, Bean Nov 5; then 0.7 across her beam drew a hard-edged band, QA). Only where she has been, never ahead or round a
  stopped boat.
- **The test** `SailingSim.Visual.WakeGrid` now checks the lane is plain 5 m astern and a little wider than her beam
  there, fading 20 m astern (0.05-0.4, under 0.6 of its 5 m value), gone 40 s after she stops, and that there is foam
  2 m astern and none 6 m ahead of the bow. An offline model of the slick step (calibrated on the old 0.47) gives 0.63
  at 5 m, 0.27 at 20 m and 0.05 at 40 m.

### Stills (feedback #9, Mac, High, uncooked; main 0cf4f6bc before, this branch after)

From the reported spot (J/22, 12 kn, TWA 106), chase camera astern and above:

| | before | after |
| --- | --- | --- |
| Sailing at 5.5 kn, 45 s in, no HUD | [before](fb9-sailing-5kn-before.jpg) | [after](fb9-sailing-5kn-after.jpg) |
| The start, 14 s in, 2.3 kn | [before](fb9-start-before.jpg) | [after](fb9-start-after.jpg) |
| Mid-tack (bow checked for stray foam) | [before](fb9-mid-tack-before.jpg) | [after](fb9-mid-tack-after.jpg) |

The lane is still there, as it should be, a little narrower near the stern and fainter at its far end; from this camera
it mirrors the bright sky, so it reads light here, where the reported view read it dark. No foam at the bow mid-tack.

The reported view (Ultra, a low chase camera off the quarter about 8 m up: pitch -12, 38 m, 45 s in at 5.5 kn, no HUD),
main and fix at camera yaw 150, 200 and 230: [150 main](fb9-quarter-150-main.jpg) / [fix](fb9-quarter-150-fix.jpg),
[200 main](fb9-quarter-200-main.jpg) / [fix](fb9-quarter-200-fix.jpg), [230 main](fb9-quarter-230-main.jpg) /
[fix](fb9-quarter-230-fix.jpg). At 200 and 230 main's long pale lane astern is gone on the fix, fading within a few
lengths; at 150, into the sun's glitter, the two look alike. (The dark shape beside her is her shadow, not the wake.)
