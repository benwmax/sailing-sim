# ILCA seat: feet under the hiking strap (Oct 23 2026)

pc/ilca-fidelity (#286) gave the ILCA's well a webbing hiking strap. Hiked, the sailor's feet stood beside it and a shin
went through the webbing. Now the feet go under it, as on the Sunfish (`docs/sunfish-seat/`).

## Change

`CrewCockpitWell` (`CrewPose.cpp`), the ILCA's well, from #286's model numbers (boat frame, m):

- the sole at 0.12 (not the sheer less the well's depth);
- the strap's ends at x -1.616 and -0.224;
- its top at 0.24 at the ends and 0.22 midway (x -0.92), which is 0.12 and 0.10 over the sole, the Sunfish's shape;
- 25 mm either side of the centreline, 3 mm of webbing.

Nothing else changes: `CrewMotionPose`'s strap code (feet 0.12 and 0.30 m ahead of the hips, clamped 6 cm off the aft
end and 10 cm off the forward end, the ball turned under the webbing) works as it is. The ILCA's `CrewAftRange` slides
the sailor up to 0.5 m aft on the plane, and the feet follow the hips.

## Test

`SailingSim.Visual.SunfishStrap` is now `SailingSim.Visual.DinghyStrap`. It checks the Sunfish and the ILCA, sitting up
and hiked, on both tacks; on the ILCA also 0, 0.25 and 0.5 m aft. For each foot it checks three things:

- the ankle is beside the strap, within its length;
- the instep passes under the webbing;
- the shin stays clear of it.

SK_Sailor's ankles on the ILCA:

| Slid aft | Hips at x | Ankles at x |
| --- | --- | --- |
| 0 | -0.90 | -0.78, -0.60 |
| 0.25 m | -1.15 | -1.03, -0.85 |
| 0.50 m | -1.40 | -1.28, -1.10 |

All of them are 7 cm over the sole (z 0.19), inside the strap's -1.616 to -0.224.

## Stills

`before-after.jpg`: High, uncooked. Before is #286 alone (left); after is with this change (right). From the top:
hiked on starboard, port, and planing on a reach.
