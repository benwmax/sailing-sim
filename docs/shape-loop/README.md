# Boat shape loop

Raises the boats' big shapes and features (hull and deck fairing, cabin, cockpit, companionway, rails, drains, transom,
keel and rudder), one section per PR, measured against class drawings and specs. Plan and Bean's decisions:
<https://claude.ai/artifact/LUQJog4e1veru9wwaQsxpn> (Nov 10 2026). It sits beside the part detail loop
(`docs/part-detail-loop`) and the texture loop (`docs/texture-loop`).

Bean's decisions (Nov 10 2026): J/22 hero and Sunfish only for now; hatches always closed (separate closed parts, no
open state, no Mac code); the underwater shape stays matched to the physics; club photos later; Ultra is measured at
4K on BEN-PC.

## Quality rule

Every boat is authored once at full quality; the lower tiers are derived from it (coarser Nanite error and texture
mips for High and Medium, a baked LOD mesh for Low, the quarter-size light copy for AI boats). The master is never cut
to rescue a lower tier: tune that tier's derivation instead.

| Gate | Where | Target | Floor (blocks a merge) |
| --- | --- | --- | --- |
| Ultra, average over the bench views | BEN-PC, 4K | 60 fps | 50 fps |
| Ultra, worst boats view | BEN-PC, 4K | 50 fps | 45 fps |
| Ultra, 1% lows in the worst view | BEN-PC, 4K | 40 fps | 35 fps |
| High | Mac gate | | 45 fps |
| Medium | Mac gate | | 60 fps |
| Any boats view vs main | Mac gate | | no more than 2 fps slower |

The 3M triangles per boat line is a checkpoint where we measure, not a ceiling.

## Sections

Sections follow the boat's real mouldings: `Tools/shapeloop/sections_j22.json` lists each section's objects (by name
prefix), the build functions it owns, its borders and the joins the seam check measures.

1. The hull is never sliced lengthwise; it is faired as one surface.
2. Every PR also gets a whole-boat pass: the fixed camera set, the outline check and the blind A/B always run on the
   whole boat, with close-ups of every join the section touches.
3. Joins overlap, they don't just meet: separate meshes simplify separately on the derived tiers, so edges that only
   touch can open at distance. Check joins at Medium in game, not just Ultra.
4. Only the hull section changes the shared curves (`sheer_z`, `half_beam`, `section`, `deck_z`); a PR that does re-runs
   every section's checks. The `moved` check lists every object centre that moved (the bake's sockets come from them).

`build_j22_hero.py` stays one file: the deck mould, cockpit and cabin share one baked atlas (`bake_j22_hero.py`
DeckMould), and the interior is built from the script's whole namespace, so splitting it would add hidden links for
little gain. Hero shape PRs go one at a time.

## The loop, per section

1. **Card**: `Tools/shapeloop/cards/<boat>-<section>.json`: targets with tier and source, outline views, feature list,
   moves allowed outside the section, triangle line, Mac wiring (none while hatches stay closed).
2. **References**: links and numbers in the card; drawings, manuals and photos in git-ignored
   `Data/Reference/raw/boats/<Boat>/shape/`. Tiers: A class rules and ORC, B builder and owner-manual drawings, C our
   measured reference models (Sunfish), D free-licence photos, E generic practice for the boat type (marked on the
   card), F Bean's photos only when a top-half feature's sources disagree by more than 10% or don't show it and a wrong
   guess would read as a different boat; those go on one shot list per club visit.
3. **Baseline**: build main, then run the four tools below into `<work>/base`.
4. **Rebuild** the section in the build script.
5. **Round**: build again and run the tools into `<work>/rN`; `score.py` against the baseline.
6. **Blind A/B**: 3 fresh reviewer agents see the reference and the two renders (unlabelled), pick the closer one; the
   round must win at least 2 of 3 with no "wrong boat". A round that loses is reverted.
7. **Sheet** for Bean: reference, before, after.
8. **QA review** by a separate critical agent: the diff, the card and `score.md` only.
9. **PR**, then PC: `--clean-bake`, import, in-game stills from the same views, 4K Ultra bench; Mac: `scripts/gate.sh
   --scope boats` (and `--scope crew` when seats or handholds moved) and the material rebuild on the branch.

## Tools

All in `Tools/shapeloop`, run with Blender's Python (pip `bpy`) except `score.py`.

```
B=<work>/base
python build_j22_hero.py -- $B                       # (via a wrapper that imports bpy first; J22H_FONT=<a .ttf>)
python Tools/shapeloop/measure.py   $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python Tools/shapeloop/fairness.py  $B/j22_hero.blend $B
python Tools/shapeloop/seams.py     $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python Tools/shapeloop/render_set.py $B/j22_hero.blend Tools/shapeloop/sections_j22.json $B
python3 Tools/shapeloop/score.py Tools/shapeloop/cards/j22-hull_shell.json $B <work>/r1 --refs <traced masks>
```

| Tool | Writes | Check |
| --- | --- | --- |
| `measure.py` | `stats.json`: objects with section, triangles, bounds, centre; triangles per section; hull LOA, beam, freeboards and 21 station cuts; the build's canoe volume and CB | size, budget, moved, physics |
| `fairness.py` | `fairness.json`: 10 waterline and 10 station cuts of the hull, inflections and kinks per line | fairness (no line may get worse) |
| `seams.py` | `seams.json`: per join, vertices near it, how many sit 0.5-15 mm off the neighbour, widest gap | seams (no join may get worse) |
| `render_set.py` | silhouettes (profile, plan, bow, stern), clay renders (those plus 3/4, bow and stern 3/4, helm eye), zebra stripes | outline, fairness by eye, blind A/B, sheet |
| `score.py` | `score.json`, `score.md` (goes in the PR) | all of the above; exits 1 on a hard fail |

Hard checks: fairness, seams, physics (canoe volume within 1% and CB within 2 cm of the baseline) and moved (nothing
outside the card's sections moves unless the card lists it).

## Baseline

`baseline/` holds the tools' output for main at the time of wave 0, so later rounds can see what the boat measured
before the loop began.

Main at `46d23774` (Nov 10 2026), built in the cloud with pip bpy 5.2:

| Measure | Value |
| --- | --- |
| Triangles in the build (all objects, sails off) | 1,080,328 |
| Shape sections | hull 61,164; joint and rails 43,184; deck 20,226; cabin 43,494; cockpit 20,216; transom and bow 19,434; keel and rudder 19,908 |
| Hull LOA, beam | 6.860 m, 2.448 m (class 6.858, 2.438) |
| Freeboard at bow, stern | 0.782 m, 0.569 m (ORC 0.774 at its point, 0.568) |
| Canoe body volume, CB | 1.088 m³ at (-0.226, -0.074); the physics floats 1.052 m³ at (-0.195, -0.080): the hero already displaces 3.4% more than the physics. The physics check holds every round to this baseline so the loop never widens the gap; closing it is a physics calibration job (frozen), not a shape PR. |
| Fairness | 19 lines, 13 inflections (stem and transom corners), 59 kinks (mostly the lowest waterlines near the keel root) |

Self-test: a copy of the baseline with a 12 mm bump on the port topside and the cabin raised 10 mm fails three hard
checks: fairness (waterline 5 gains 4 inflections), seams (deck to cabin opens 29 more bins) and moved (the cabin
moved outside the hull card's section). The physics check reads the build's own report, so it only sees real builds.

## Sunfish

The fleet build (`Tools/blender/build_fleet.py`) joins each boat into one hull mesh before exporting the fbx, so the
section split by object name doesn't apply to it yet. Wave 5 adds an option to save the pre-join scene as a .blend
(no change to the fbx), then a `sections_sunfish.json` (hull and deck, cockpit well, board and trunk, rudder, small
fittings). The Sunfish's underwater hull is the physics hull exactly, so its physics check is exact.
