# Texture loop: non-skid deck (round 5)

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
- **Wear ladder (round 5, in the game).** M_BoatSurface's non-skid lines in `scripts/make_materials.py` (BOAT_CODE) now
  read the shared Time and Dirt numbers (`Tools/texloop/wear.py`): Dirt packs dust into the grooves, adds grit specks,
  grey-tan blotches with a 1.5 cm scuff mottle, and on a neglected boat black mildew specks; Time yellows the moulding a
  little and polishes the rib tops. Medium (no detail maps) draws the 2.3 mm ribs analytically, fading out by 1.8 m, in
  place of the old 8 mm diamond, and gets the groove dust as an even tint. MI_Boat_NonSkid's colour is now the clean L0
  moulding (0.75, 0.68, 0.56 linear; was 0.56, 0.52, 0.43 with grime baked into the colour).
  `Tools/texloop/nonskid/render_levels.py` mirrors those lines step for step in numpy; change both together.
- **Not changed:** the hero J/22 (`import_j22_hero.py` DETAIL_CODE) keeps its baked style presets; it already uses the
  new rib map.

## Round 5 numbers (1 m swatch, overcast, colour distance to target; pass is 6 or less)

| Level | Before (main) | After |
|---|---|---|
| L0 new | 7.8 | 0.1 |
| L1 months | 6.4 | 0.5 |
| L2 club | 4.1 | 4.7 |
| L3 old, kept | 9.3 | 1.6 |
| L4 neglected | 4.4 | 4.9 |

Spread is still short of the photo on L2 (6.3 against 10.4) and dark cover on L4 (0.27 against 0.40). "Before" is
main before the texture loop (old maps, old lines); neither side has the engine's ambient occlusion, as in the game. Before was the
same flat beige-grey at every level; the ladder now ranks in order.

`L*_close_before_after.jpg`: 20 cm at 4 px/mm under a low sun, main on the left, round 5 on the right.

Reproduce: `python3 Tools/boats/make_detail_textures.py`, then
`python3 Tools/texloop/nonskid/render_levels.py <out> --before <dir with main's two NonSkid PNGs>`.
