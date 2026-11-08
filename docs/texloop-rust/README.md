# Texture loop: rust weeps and streaks (L0-L4)

Rust lane of the boat texture and wear loop (plan: https://claude.ai/artifact/Bq6JXirCL49khtgLL76h3q). Card
`Tools/texloop/cards/rust.json`, references and targets `Tools/texloop/refs/rust.json`, code: the "Rust weeps" block in
`scripts/make_materials.py` (BOAT_CODE). Cost $0; CC0 references only; no new textures.

## What changed

The old block drew thin grey-brown lanes from the livery's rust channel alone, so with `-SailingBoatAge` (or a berthed
boat's Age and Care) a brand-new boat and a neglected 20-year-old one carried the same streaks, and they never reached
rust colour (darkest Lab 68, 4, 10 on white). The new block:

- **Driven by Age and Care.** Count and length (rwN) grow with the years the steel has had, `saturate((Age - 1.5) / 12)`;
  strength (rwA) with how little the boat is cleaned, `1 - 0.85 Care`. L0 and L1: none. L2: a couple of short weeps per
  2 m. L3: faint ghosts of cleaned stains. L4: many long dark ones with a crust at each bolt. Unset Age: 0.5 and 0.8 x the
  livery's rust channel, so a club livery reads like L2. Salt water: more and stronger.
- **Shaped like a weep.** A bolt slot every 25 cm along the hull, sources 50-78 cm above the waterline (the hull-deck
  joint), a dark head about a washer wide, a run that wanders slightly, pales and narrows (CC0 leak decals), blotches
  along its length, and sometimes a thin finger splitting off.
- **Rust colour.** Part dye (multiplies the gelcoat, so thin stain is tan, not grey) and part deposit, toward Lab 26, 17, 23
  with a 0.6 cm crust mottle; matt (roughness 0.8, clear coat cut 70%).
- **Filtered.** Marks widen to a pixel with distance and fade to match, so far boats don't shimmer.
- **Cost.** No texture reads (Medium included). Everything past the slot hash sits behind a dynamic branch that only a
  weeping slot's side faces take.

## Scores (round 8, `scores.json`)

Rendered with a numpy port of the block (`scripts/rustport.py`, `render_round.py`) on a white J/22 topside, not in
engine: the PC is paused.

| Check | Result |
|---|---|
| Colour | L4 crust Lab 29.0, 16.1, 21.3 vs 30.8, 18.4, 25.0: dE 4.7 (pass); spread sdL 5.3 vs 5.3 (pass). L4 stain 66.4, 5.2, 9.3 vs 62.9, 6.3, 10.0: dE 3.8 (pass). Main today: no rust-coloured pixels at all. |
| Size | Head FWHM 0.7-1.6 cm (target 1.0-1.1 cm for a 19 mm washer, varied per weep); L4 runs 26-34 cm (target 18-42); L2 14-17 cm (8-20); L4 2.5 weeps a metre (1.5-3). Procedural, so pixel density is unlimited. |
| Tiling | Procedural, no tile. Weep-profile autocorrelation along a 10 m hull: 0.18 at most beyond 30 cm (no repeat). |
| Wear ladder | 3 fresh reviewers, L1-L4 shuffled: all three ordered them exactly (rank match 1.0) and told every neighbour pair apart. L0 = L1 by design (nothing bleeds in months). |
| Blind A/B | 3 of 3 picked the new block over main; none called it the wrong material (main's read as "a faint grey line"). |
| Budget | No maps. Frame time not measured here: Mac boats gate (`scripts/gate.sh --scope boats`) still to run. |

## Next round's to-do (reviewers' "still different")

- Weeps still read a little clean and uniform: wider fans on some, more orange/brown variation, side bleed at the head.
- Heads are dots: no washer shape or orange halo round the bolt.
- The swatches show the rust alone on flat gelcoat; the chalk, grime and black streaks of a real L4 boat come from the
  other lanes (gelcoat thread) and show only in engine.
- Counts and lengths are stand-ins: Bean's close-ups of an old boat at Rush Creek would set them. Wikimedia photos were
  wanted for measuring only, but the cloud network blocks upload.wikimedia.org.

## Rust on the hardware itself (Bean's follow-up)

A new surface kind, **12 galvanised or plain steel**. The hero J/22's `Galvanised` (anchor) and `KeelBoltSteel` (keel
plates, nuts and studs) slots map to it in `scripts/import_j22_hero.py`; before this they rendered as stainless (kind 3)
and never rusted. The steel:

- **Dulls** from spangled zinc to flat grey in its first three years, kept or not.
- **Blooms white** (zinc oxide) on a boat that's left.
- **Rusts through** in patches. Coverage stands in for the CC0 rusty-steel scans (ambientCG Metal020-026): 0 at L0/L1,
  about 1% at L2, 2% at L3, 20% at L4. The rust is orange at a patch's edges and a dark crust at its heart, with a brown
  bleed round each patch and ragged edges from a fine octave. Pits rust first close up (detail map cavities).
- **Is not metal where it's rusted**: `metalOut` drops under the rust and the bloom, and AlbedoOut and F0Out use it.

Patches are projected on the two boat axes across each face (the grime's slanted projection streaked on small upright
parts) with a rotated second octave (no lattice blocks). Stainless (kind 3) and aluminium (kind 4) belong to the metals
thread and are unchanged here.

| Check (`hardware_scores.json`, round 4) | Result |
|---|---|
| Colour | L4 rust Lab 29.4, 17.8, 23.7 vs 30.8, 18.4, 25.0: dE 2.0 (pass); spread sdL 4.4 vs 5.3 (pass, within 25%) |
| Coverage | L2 1.2%, L3 2.1%, L4 20.2% (targets 0.5-3, 1-4, 15-30) |
| Wear ladder | Round 2, 3 reviewers: all ordered L1 < L3 < L2 < L4. They read the kept classic as cleaner than the club boat (its white bloom reads as neglect). That is a 0.8 rank match, which passes the 0.8 bar, and it is arguably right for a kept boat. One reviewer of three called L3 vs L2 marginal. |
| Blind A/B | Round 2 beat main 3/3 ("main reads as plain flat grey"), but all three called the rust "cartoon blobs with dark outlines". Round 3 (no rims) lost to round 2, 1-2. Round 4 adds the zinc mottle, darker crust cores and flecks, and beat round 2 3/3. |

Still different (round 4 reviewers): the grey base is still too even (no spangle, scratches or grime); the rust sits in a few
large soft clumps where real rust also has fine speckle and streaks.

## Not done here

- In-game import and stills (`-SailingBoatAge=0,1`, `0.3,0.9`, `6,0.5`, `30,0.9`, `20,0.1`) wait for the PC; then the Mac
  boats gate. The HLSL has not been through a shader compiler yet.
- Docks, trailers, dock chain and ships use `M_WorldSurface` (a later world pass). The hero J/22's baked deck stains are unchanged.

## Reproduce

The measure scripts expect the CC0 downloads under `/home/user/refs/` (ambientCG `<id>_1K-JPG.zip` unzipped per asset,
Poly Haven 1k diffuse jpgs); keep them in git-ignored `Data/Reference/raw/textures/Rust/` instead.
`python3 scripts/render_round.py <out>` then `python3 scripts/score.py <out> scripts/targets.json`.
