# Track B blind round 1 (16 Nov 2026)

Three fresh reviewers, one pair each, sides shuffled, asked only about the shore's ground and grass: which side looks
more like a real grassy Texas lake bank, a 1 to 5 "could pass for a photo" score each, and the biggest fake left on the
side they preferred.

**Before:** the PC's still of the natural bank north of the club (`Inputs/bench/env-before-nov16/07-natural-bank.jpg` on
the inputs branch, Ultra, main 8f5331f4). **New:** `render_grass.py` stills (Cycles, outside the game) with Track A's
ground colour as a flat stand-in for its texture. Not a like-for-like engine comparison: it judges the plants, not the
game's lighting.

| Pair | New shot | Picked | New score | Before score |
| --- | --- | --- | --- | --- |
| 1 | `shore_15m_noon_summer` (right) | new | 2.5 | 1 |
| 2 | `shore_15m_low_dormant` (left) | new | 3 | 1 |
| 3 | `shore_3m_low_summer` (left) | new | 3 | 1 |

**New beats old 3 to 0.** "Photo or game" is not met yet (no side above 3).

What the reviewers still saw as fake on the new side, and who owns it:

- The tall clumps read as evenly spaced, the same height and colour, ending in a hard top line (Track B: next round
  varies height by patch and thins the stand toward the top of the bank).
- Thin, see-through bunches with sky between blades at 15 m (Track B: fuller bases on the Light copies).
- The bare ground under the clumps is one flat colour, and the bank is a perfectly straight, level strip with a clean
  waterline (the render's stand-ins: Track A's ground texture and Track C's shoreline types replace both in the game).

# Track B blind round 2 (16 Nov 2026)

Same question and scoring, fresh reviewers each pair, sides shuffled. Round 2 against round 1 (both `render_grass.py`
stills, same camera, light and seed), so it judges only this round's changes: the stand rules (vigour patches, height by
patch, shorter toward the bank top), fuller Light copies and the far cards.

First try (stand with wide bare gaps and small bunches in weak patches):

| Pair | Shot | Round 2 side | Picked | Round 2 score | Round 1 score |
| --- | --- | --- | --- | --- | --- |
| 1 | `shore_15m_noon_summer` | left | round 1 | 2 | 2.5 |
| 2 | `shore_15m_low_dormant` | left | round 1 | 2 | 3 |
| 3 | `shore_60m_noon_summer` (High) | right | round 2 | 2 | 1 |

The far cards won (the 60 m bank on High is no longer bare), but the stand lost at 15 m: the gaps showed the low rough
tufts in an even, tiled-looking scatter, and the copper bluestem clumps read as "stamped copies" too saturated against
the tan. Tuned: fewer and smaller gaps (`density_low` 0.9, `gap_below` 0.03), a milder top shrink (0.15), bunches and
rough tiles jittered across their whole 0.5 m cell with more size spread (no grid), and a duller rust for dormant
bluestem. Second try, new reviewers:

| Pair | Shot | Round 2 side | Picked | Round 2 score | Round 1 score |
| --- | --- | --- | --- | --- | --- |
| 4 | `shore_15m_noon_summer` | right | round 2 | 2.5 | 2 |
| 5 | `shore_15m_low_dormant` | left | round 1 (narrowly) | 2 | 2.5 |

**Round 2 (tuned) against round 1: 2 to 1** counting pairs 3, 4 and 5. At 15 m it is close to a draw (both reviewers
called the two sides nearly identical); at 60 m on High it is a clear win. Still no side above 3 of 5.

What the reviewers now name as the biggest fake is mostly not the grass:

- The ground: a flat, even mat between clumps, no bare mud or wet soil at the waterline, no slope (Track A's ground
  textures and Track C's shoreline types; the renders use flat stand-ins).
- The flat green land behind the bank with a ruler-straight skyline (a render stand-in; the game has terrain and trees).
- The far cards read as a uniform fence of thin upright spikes at 60 m (Track B: next round softens the far atlas into
  rounded tussock outlines and varies their heights).
