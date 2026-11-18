# The demo autopilot's lookout (sailing-feedback #31)

## The bug

`-SailingDemo` sails close-hauled and tacks every 12 s (or holds `-SailingHoldTWA`). Short tacks make good straight
upwind, so the demo beat to windward until it met the shore and stayed there aground:

- **Galveston, launch 1** (Kemah channel), 6 kn southerly: aground at about -1,403 N 1,190 E from minute 11 of a one-hour
  soak (PC, main `8a768667`).
- **Ray Hubbard, launch 1**, 10 kn southerly: aground on the south shore at about -2,518 N 75 E from minute 50 of the
  two-hour 4K soak. Game-thread hitches grew while she sat there (frames over 30 ms: 1-10 per ten minutes sailing,
  88-490 aground).

Every soak and long showcase run from those spots measured a boat sitting still.

## The fix

`FDemoShoalGuard` (`Source/SailingPhysics/Public/DemoHelm.h`, plain C++) reads the chart ahead once a second:

- **Look-ahead:** 90 s at her speed, 150 m at least and 400 m at most.
  - Beating, it looks along her mean course (straight upwind) and 40 m along each tack's heading.
  - Holding an angle, it looks along her heading.
- **What counts as blocked:** water shallower than her draft plus 0.6 m (the depth alarm's 2 ft), or within 12 m of a dock,
  pier or bridge (`FLakeData::Obstacles`, on a 100 m grid).
  - A dock she starts beside does not block her way out.
  - Starting in thinner water than that, she keeps to water no shallower than where she is.
- **While the water is clear:** the demo's own course is returned unchanged, so open-water views are untouched.
- **When it is not clear:** she bears away to the wind angle with the longest clear water, from 60, 90, 120 and 150 on
  either tack. Open water (950 m clear) counts the same in any direction; among those she picks the angle furthest from the
  wind, on the tack she is on.
- **Holding the bear-away:** she holds it for 120 s and until the water upwind is open for twice the look-ahead, then beats
  again. If the bear-away's own course runs into shallows, she picks again.

The pawn (`ASailboatPawn::Tick`, demo block) feeds it:
- the lake's terrain and obstacles;
- the wind a sailor reads (`FWindField::ReadableAt`);
- the tack schedule's angle.

Each bear-away is logged: `Demo: shallow water ahead at <N> N <E> E (t <s> s), bearing away to TWA <deg>`.

- `-SailingNoDemoGuard` sails without the guard, for comparison.
- With `-SailingHoldTWA` (every gate bench view and still) the guard starts after 60 s, so the views keep their framing.
- `HoldForTests` turns the guard off.

## Checks

Standalone (scratch harness on the physics, clang, the real `.height` bakes), a J/22 in W1 gusts (factor 1.3):

| Run | Without the guard | With it |
|---|---|---|
| Galveston launch 1, 6 kn from 180, 1 h | aground at 1,209 s near -1,320 N 1,130 E, then still for 40 min | 6 bear-aways, never aground, least water under the keel 0.83 m |
| Ray Hubbard launch 1, 10 kn from 180, 1 h | aground at 2,028 s on the south shore, then shuffling along it | 6 bear-aways, never aground, least water under the keel 8.9 m |

`SailingSim.Physics.DemoShoalGuard.*`:
- **`Logic`:** a synthetic lake.
  - In open water the course is untouched.
  - With a shore upwind she bears away short of the margin.
  - A dock alongside does not block; a pier across her course does.
- **`Charts`:** every launch spot of Ray Hubbard, Galveston Bay and Marseille, in eight winds, two hours of the demo's course
  sailed as a point. With the guard none touch the bottom; without it most do (the check bites). In the scratch runs:
  - Ray Hubbard: 40 of 40 without the guard ended aground, none with it.
  - Galveston: 46 of 56 without, none with it.
  - Marseille: 72 of 80 without, none with it.
- **`Galveston`:** the real boat (physics, trimmer, autopilot) from 300 m short of the soak's grounding, 360 s. With the
  guard she bears away and keeps sailing. The same run without the guard was aground at 258 s.

## Not changed

- The hitches while aground (#31's second comment: `Sailing_BoatPhysics` and the learning coach's aground tip) still
  happen to a player who runs aground. The demo no longer goes there.
- Traffic boats keep their own shoal check (`FTrafficSim`).
