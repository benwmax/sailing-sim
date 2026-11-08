# Texture loop: rope (sheets and lines)

Rope now ages with the boat. The live lines (M_RigRope), rope on kit parts (BOAT_CODE `surf == 9`) and the numpy twin
used for review (`Tools/rope/rope_wear.py`) read the boat's Age and Care through the shared `time_k` / `dirt_k`
(`Tools/texloop/wear.py`), taken at the rope's own age. Before this, every boat's lines had the same fixed Fade 0.4 and
Dirt 0.5, so a new boat's sheets looked club-worn.

## How rope wears

Rope is a consumable. A kept boat replaces her lines every few seasons, so the rope's age is capped by care:
`rope age = min(Age, 3 + 12 x (1 - Care))` years (3 kept, 15 neglected). From that:

| Effect | Drives it | Look |
| --- | --- | --- |
| Dye fade | 0.35 time + 0.1 dirt | white toward ivory grey, colours slightly paler; red stays red on a club boat |
| Grime | 0.8 dirt | grey-brown in the cover, patchy along the line (cleats, hands), first in the weave |
| Fuzz | 0.45 time + 0.75 dirt | rougher, softer relief, shallower shadows, a pale veil on white carriers, more rim sheen |
| Mildew | dirt over 0.6, low care | dark specks in the weave and a grey-green film |

| Level | Age, Care | fade | grime | fuzz | mildew |
| --- | --- | --- | --- | --- | --- |
| L0 new | 0, 1.0 | 0 | 0 | 0 | 0 |
| L1 months | 0.3, 0.9 | 0.04 | 0.05 | 0.09 | 0 |
| L2 club | 6, 0.5 | 0.22 | 0.46 | 0.64 | 0 |
| L3 kept 30 yr | 30, 0.9 | 0.16 | 0.19 | 0.36 | 0 |
| L4 neglected | 20, 0.1 | 0.32 | 0.73 | 0.98 | 0.71 |

Age unset (-1, today's player and AI boats) keeps the old look exactly. `-SailingBoatAge=<years>,<care>` now ages the
player's lines with the hull (SailboatPawn.cpp makes a dynamic instance of M_RigRope).

No new textures: wear is shader maths over the existing braid maps, so Medium, High and Ultra all get it at 0 MB.

## References and targets

`Tools/texloop/cards/rope.json` (card), `Tools/texloop/refs/rope.json` (photos, measurements, scores).

- Bean's lesson photo IMG_9272 (club J/22 at Rush Creek, Oct 11 2026) is the L2 reference: the coiled white/red
  mainsheet and the jib sheets in their cam cleats. Measured against the white coaming in the same light: the rope's
  bright fibres are about as light as the gelcoat and a little warmer; the braid's pick is 0.38-0.43 d (game 0.42 d).
- ambientCG Rope001-003 (CC0) are laid natural-fibre ropes, used for the roughness range only.
- Wikimedia candidates for L0, L1 and L4 are listed in `Tools/texloop/refs/rope_commons.json`; upload.wikimedia.org
  dropped every download from the cloud on Nov 8 2026, so those levels' targets are estimates.

## Scores (round 2, kept)

| Check | Result |
| --- | --- |
| Colour | 4 of 5 levels within dE 6 of their white-crown targets; L2 (the measured one) 7.5, darker than the photo |
| Size | pass: pick 0.42 d vs 0.38-0.43 d measured; 23-36 texture px/mm at 0.3 m |
| Tiling | pass: braid maps unchanged; the new noise follows the line's UVs |
| Wear ladder | FAIL: three blind reviewers (each round) could not tell L0, L1 and L3 apart; L2 and L4 were clear every time |
| Blind A/B | pass: round 1 beat before 3 of 3; round 2 beat round 1 2 of 3; round 3 lost 1 of 3 and was reverted |
| Budget | pass: 0 MB, about 30 shader instructions |

What the reviewers still saw: real rope is softer and fuzzier with uneven grime (dark where it is cleated or handled)
and the renders are more regular. The L0/L1/L3 result is partly true to life (a kept boat's lines are nearly new) but
the check wants each level distinct; a real L0 and L4 photo would settle how far apart they should be.

## Run it

    python3 Tools/rope/rope_wear.py [out]            # level swatches and the ladder
    python3 Tools/rope/make_rope_sheet.py out.jpg <L2 crop>
    python3 Tools/rope/test_rope_wear.py              # numpy twin and both HLSL copies agree

In game: `ROPE_MATERIAL_ONLY=1` import_boat_detail.py rebuilds M_RigRope; make_materials.py rebuilds the kit surfaces.
Not done: the hero J/22 bake (`Inputs/j22-hero/j22_rope.py`) still takes fade and dirt from its style presets.
