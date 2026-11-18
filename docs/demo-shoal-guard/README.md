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
  pier or bridge (`FLakeData::Obstacles`, on a 100 m grid, each one a closed-form ray and capsule test).
  - Bridge decks higher than her masthead plus 2 m are not in her way.
  - Already within 12 m of a dock (leaving the marina), she keeps 1.5 m from it instead: she can get out, not into it.
  - In thinner water than that already (a shallow start, or blown onto a shoal), she keeps to water no shallower than where
    she is, and a bear-away heads for the deepest water 25 to 50 m away.
- **While the water is clear:** the demo's own course is returned unchanged, so open-water views are untouched.
- **When it is not clear:** she bears away to the wind angle with the longest clear water, from 60, 90, 120 and 150 on
  either tack. Open water (950 m clear) counts the same in any direction; among those she picks the angle furthest from the
  wind, on the tack she is on.
- **Holding the bear-away:** she holds it for 120 s and until the water upwind is open for twice the look-ahead (after
  8 minutes, for the look-ahead alone), then beats again.
- **Choosing again:** when the bear-away's own course has less than 60 m of clear water, she picks again, at most every
  10 s unless the way is shut right ahead. The way back along the course she is giving up scores lowest, and a new course
  no better than the old one is not taken: in a small lake or a crowded harbour that only turned her back and forth.

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

The same harness from both soak spots in eight winds (every 45 deg; Galveston 8 kn, Ray Hubbard 12 kn), one hour each
with the guard: none of the 16 touched the bottom. The least water under the keel was 0.65 m at Galveston and 0.95 m on
the lake, with 0 to 12 bear-aways an hour.

`SailingSim.Physics.DemoShoalGuard.*`:
- **`Logic`:** a synthetic lake.
  - In open water the course is untouched.
  - With a shore upwind she bears away short of the margin.
  - A dock alongside does not block; a pier across her course does.
  - Aground on the shelving shore, she heads for the deep water in three winds.
- **`Charts`:** every launch spot of Ray Hubbard, Galveston Bay and Marseille, in eight winds, an hour of the demo's course
  sailed as a point. With the guard none touch the bottom; without it most do (the check bites). Steps inside a dock's
  capsule are listed as info. In the scratch runs (with an obstacle list rebuilt from the bakes' json):
  - Ray Hubbard: 37 of 40 without the guard ended aground, none with it.
  - Galveston: 38 of 56 without, none with it.
  - Marseille: 61 of 80 without, none with it.
  - The slowest single guard update was 7.6 ms (the first, which indexes Galveston's ~100k pier segments); the rest stay
    under 3 ms, about 0.3 ms on average.
- **`Galveston`:** the real boat (physics, trimmer, autopilot) from where the soak's boat was at minute 10, 600 s. With
  the guard she bears away (once; least water under the keel 0.71 m) and keeps sailing. The same run without the guard was
  aground at 436 s.

## Known limits

- **Crowded starts:** from Marseille's launch 0 (the Vieux-Port quay, among moored boats) every course is a few metres
  long; the guard cannot find a way out and the point-boat runs touch the boats beside her, as the demo did before.
  Galveston's launch 0 (Clear Lake) is a small lake: she sails about in it, never aground, 120-400 m from the start.
- **Streamed worlds:** tiles that are not resident read as land, so a far look can see a shore that is not there.

## Not changed

- The hitches while aground (#31's second comment: `Sailing_BoatPhysics` and the learning coach's aground tip) still
  happen to a player who runs aground. The demo no longer goes there.
- Traffic boats keep their own shoal check (`FTrafficSim`).
