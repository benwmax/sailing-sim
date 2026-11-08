# Texture loop: non-skid deck (round 4)

Plan: the boat texture and wear loop (https://claude.ai/artifact/Bq6JXirCL49khtgLL76h3q), surface 3 of the first five.

## What changed

- **Pattern.** Bean's lesson photo IMG_9272 (J/22 TX 7295 EC, cockpit seat, low sun) shows fine diagonal ribs, not
  pyramids: one direction strong at about 45 degrees to the boat's axis, a faint cross texture. FFT of four seat patches,
  scaled by the cam cleat's 38 mm axle spacing: 2.04, 2.10, 2.29, 2.68 mm, mean 2.3 mm. Main's map was a 45-degree grid
  of pyramids at 1.77 mm perpendicular pitch with both diagonals equal. `nonskid()` in
  `Tools/boats/make_detail_textures.py` now draws 31 ribs across the 100 mm tile's diagonal (2.28 mm), a quarter-strength
  cross texture, a slight wander, and 0.45 mm relief. The mask keeps its channels (R cavity, G top polish, B height), so
  M_BoatSurface reads it unchanged.
- **Targets.** `Tools/texloop/refs/nonskid.json`: L2 is measured on three of Bean's photos (colour against the nearby
  white gelcoat set to sRGB 215); L0, L1, L3 and L4 are derived from L2 until club close-ups exist.
- **Wear ladder.** `Tools/texloop/nonskid/render_levels.py` shades the five levels in numpy with the shader's own grime
  noise: Dirt puts dust in the grooves, grime blotches with a 1.5 cm scuff mottle, grit specks, and on a neglected boat
  black mildew specks; Time yellows the gelcoat and polishes the rib tops. Its Time and Dirt are provisional until the
  shared `Tools/texloop/wear.py` lands, and the HLSL port of these lines into BOAT_CODE follows that PR.

## Round 4 numbers (1 m swatch, overcast, colour distance to target; pass is 6 or less)

| Level | Before (main) | After |
|---|---|---|
| L0 new | 10.8 | 0.0 |
| L1 months | 9.4 | 0.5 |
| L2 club | 6.7 | 3.5 |
| L3 old, kept | 12.1 | 1.4 |
| L4 neglected | 2.0 | 4.7 |

Spread is still short of the photo on L2 (5.3 against 10.4) and dark cover on L4 (0.30 against 0.40). Before was the
same flat beige-grey at every level; the ladder now ranks in order.

`L*_close_before_after.jpg`: 20 cm at 4 px/mm under a low sun, main on the left, round 4 on the right.

Reproduce: `python3 Tools/boats/make_detail_textures.py`, then
`python3 Tools/texloop/nonskid/render_levels.py <out> --before <dir with main's two NonSkid PNGs>`.
