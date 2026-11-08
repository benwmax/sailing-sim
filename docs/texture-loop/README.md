# Texture loop (Nov 8 2026)

Bean's ask: a repeatable way to find reference images for the boats' textures and wear (rust, wear and tear, waterline
growth, wood, gelcoat, non-skid, sailcloth, rope, metals) and to match them at different amounts of wear. The plan with
the research behind it is the Claude Doc "Boat texture and wear loop" (https://claude.ai/artifact/Bq6JXirCL49khtgLL76h3q).
It mirrors the part detail loop (`docs/part-detail-loop`). Each texture runs in its own thread and PR; this page is
the shared method, and the hull gelcoat is its first run.

## Wear levels

Five fixed points on E1's Age (years) and Care (0 neglected .. 1 kept), in `Tools/texloop/levels.json`:

| Level | Age, Care | What you see | ageK (before) | timeK | dirtK |
| --- | --- | --- | --- | --- | --- |
| L0 Brand new | 0, 1.0 | mirror gelcoat, crisp non-skid, white rope, clean waterline | 0.00 | 0.00 | 0.00 |
| L1 A few months | 0.3, 0.9 | faint scum line, scuffs where people step aboard, dust in the non-skid | 0.01 | 0.10 | 0.06 |
| L2 Years in use (club boat) | 6, 0.5 | chalky topsides, grime trails, grey rope, tea stains, silver teak | 0.21 | 0.46 | 0.57 |
| L3 Decades old, maintained | 30, 0.9 | polished but faded, slightly yellow gelcoat, crazing, repairs | 0.46 | 0.86 | 0.24 |
| L4 Neglected | 20, 0.1 | heavy chalk, black streaks, slime, mildew, oxide, peeling varnish | 0.94 | 0.75 | 0.92 |

## The time/dirt split (Bean, Nov 8)

One number couldn't tell L1 from L0, and gave L3 a half-neglected boat's chalk and stains. The materials now work out
two numbers from the same Age and Care (no new data slots):

- `timeK = saturate(0.25 (1 - e^(-age/0.75)) + 0.75 (1 - e^(-age/18)))`: what the years do and care can't undo
  (yellowing, fade, dock rash). A quarter of it in the first year or two.
- `dirtK = saturate((1 - e^(-age)) (0.15 + 0.85 (1 - care)))`: what care removes (chalk, grime, stains, slime, mildew).
  Quick in the first months, as heavy as the boat is left.

Unset (Age -1: the player's and the AI boats), both are the livery's oxidation channel, as `ageK` was, so those
boats look as before (`test_wear.py` checks it). In this PR, M_BoatSurface's gelcoat chalk (`max(dirtK, 0.3 timeK)`),
gelcoat yellowing (new: timeK, white gelcoat only), deck grime, black streaks, dock rash and the E1 stain band read
them, and so does the hero J/22's material. The other surfaces keep `ageK` until their own loop moves them over.
`Tools/texloop/wear.py` carries the same formulas in Python for the swatch renders; `test_wear.py` fails if the HLSL
and the Python drift apart.

## The loop

Once per surface, steps 1-3; then rounds of 4-7 until every check passes (at most five rounds, then report what's
left); then 8-9.

1. **Texture card** (`Tools/texloop/cards/<surface>.json`): kind, boats and slots, closest camera, pattern size in
   real cm, the levels it needs, what it replaces.
2. **Reference pack** (`Tools/texloop/refs/<surface>.json`): 5-10 photos per level, overcast, square-on, with a scale
   object where size matters. `fetch_refs.py` saves them to the git-ignored `Data/Reference/raw/textures/<Surface>/<L>/`.
   The repo keeps links, licences and numbers only. Licences: CC0, public domain or our own photos may become texture
   data (`use: ship`); CC BY, CC BY-SA and FAL are measure-only. Nothing NC or ND, no AI-generated images, no people or
   real logos.
3. **Targets** (`measure.py <surface>` -> `Tools/texloop/targets/<surface>.json`): white-balanced on a neutral box,
   then per level: a* and b* (colour, independent of exposure), mottle (blotchiness after the shading is taken off),
   gloss (how far the sky's reflection stands above the body colour), exposure-normalised L*.
4. **Build**: procedural numpy first (`Tools/boats/make_detail_textures.py`), CC0 scans only where procedural looks
   fake; weathering in the material's HLSL, mirrored in `wear.py`.
5. **Render** (`render_swatch.py <surface> [--before]`): a numpy image-based-lighting renderer with the engine's
   split-sum shading under Poly Haven's CC0 `kloofendal_overcast` sky, with an 18% grey card in frame. Same view every
   round. (No Blender needed: the bpy wheel crawled through the proxy, and this matches the engine's shading model.)
6. **Score** (`score.py <surface>`), six checks: colour, size, tiling, wear ladder, blind A/B, budget (below).
7. **Fix and log**; 8. **sheet for Bean** (`make_sheet.py`); 9. **in game**: PC import, `-SailingBoatAge` stills,
   the Mac boats gate.

| Check | Pass |
| --- | --- |
| Colour | each level's a*, b* within 6 (Lab) of its photo target |
| Size | pattern repeat within 10% of the measured real size; at least 4 texture pixels per mm at the closest camera |
| Tiling | wrapped edges no rougher than the interior; no strong repeat in a 3x3 tiling |
| Wear ladder | three fresh reviewers match the five shuffled levels to their descriptions, 4 of 5 or better each |
| Blind A/B | three fresh reviewers, photos beside this round and the last: this round wins 2 of 3, nobody calls it the wrong material |
| Budget | Medium: no new maps (the hero J/22 is at 22.4 of 24 MB); High up to +8 MB of shared maps; Mac gate Medium 60, High 45, boats views no more than 2 fps down |

## Files

| Path | What |
| --- | --- |
| `Tools/texloop/levels.json` | the five levels |
| `Tools/texloop/wear.py`, `test_wear.py` | the wear formulas in Python, and the check that the HLSL matches |
| `Tools/texloop/fetch_refs.py` | downloads a surface's references (licence check, Wikimedia pacing) |
| `Tools/texloop/measure.py` | the colour and finish numbers, for photos and renders alike |
| `Tools/texloop/render_swatch.py` | the swatch renderer |
| `Tools/texloop/cards/`, `refs/`, `targets/` | one file per surface; each texture thread owns its own |

Gelcoat's first run (card, references, targets, before/after renders and scores) follows in this PR.
