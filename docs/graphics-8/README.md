# Graphics G8 (PC): boats, piers, clouds, trees and houses

Round 8 of the blind test scored 20 of 20 again. This round splits the work by machine. The Mac took the people
(`docs/graphics-8-crew`, PR #27). The PC (Bean's RTX 4090, this branch) took the rest of Bean's round 8 notes, in his words:

| Tell | Bean's notes (round 8 pack) | Scenes |
|---|---|---|
| 1 Boats | "the boat is not detailed enough/looks flat", "not enough details on the boats", "drab colors, boats not detailed enough" | game-01, 07, 05 |
| 2 Clouds | "the clouds have noise", "clouds look fake almost cartoonish", "clouds look like a cartoon" | game-04, 05, 08, 10 |
| 3 Trees | "trees do not look real", "trees are too round/lack detail" | game-03, 09, 10 |
| 4 Buildings | "buildings and shoreline not detailed" | game-02, 09, 10 |
| 6 Piers | "the pier elements lack textures and details" | game-07, 02 |

The PC's captures are all in `before/` and `game/`:

- `before/game-01..10.png`: the ten round 8 scenes (`docs/graphics-5/game/final.csv`), captured on the PC before any
  change: High, capture mode, 1440x1080, Blender crew.
- `game/game-01..10.png`: the same scenes after the round, with the MetaHuman crew from the Mac's zip (strand hair,
  which only Windows High and Ultra draw). This is the round 9 pack.
- `compare/<scene>.jpg`: before beside after. `compare/<scene>-<part>.jpg` crops the part a fix changed.
  `Tools/blindtest/make_g8_pc_compare.py` rebuilds them.

The PC frames differ a little from the Mac's for the same arguments, for example game-07's slip. Compare `before/`
with `game/`, not with `docs/graphics-6/game/`.

## What looked fake, and the fix

Everything is in the generated materials (`scripts/make_materials.py`). Nothing changed in the models, so no assets
were rebaked; the instances update in place.

| What showed | Cause | Fix | Before / after |
|---|---|---|---|
| Round, dark balls inside the trees (game-09, 03) | Each near tree's crown has opaque icosphere cores, which save the overdraw of the leaf cards inside it. `M_TreeCrown` lit them as the smooth spheres they are: bright on top, shading round to dark underneath. The far crowns are the same blobs. | **Clumped crowns.** The crown's normal is the facet's normal (from position derivatives, since `VertexNormalWS` isn't world space on Nanite here), bent hard toward a two-scale clump field, and the clumps' hollows are darker. The near cores are a third as bright and lit mostly by the clump field. They read as the shade between leaf clumps, not as a ball behind them. | [game-09](compare/game-09-trees.jpg) |
| Bare, flat dock decking, concrete-looking pilings, plain white boxes (game-07) | Deck pattern 1 was only grey per board. The pilings used the concrete pattern (4). The dock boxes were plain. | **Weathered wood** (`WORLD_SURFACE_CODE`, which now also outputs a normal). The decking is cut to 2.4-3.6 m boards with staggered butt joints, silver to brown, wandering grain, drying checks, knots, screw pairs over the joists, and dirt in the gaps and ends, with relief at the gaps. **Pilings** (new pattern 9) have vertical grain and cracks, grey-weathered over brown, a dark wet band above the water and algae below it. **Dock boxes and pedestals** (pattern 10) are chalky and yellowed, with grime low down and runs from the lid. `KitLook()` in `WorldKit.cpp` matches. | [game-07](compare/game-07-dock.jpg) |
| The race fleet all white (game-01) | Every AI keelboat carried the default Dacron. | **Laminate sails** (`SailboatPawn.cpp`). Traffic keelboats with the race wear profile, and a third of the rest, carry smoky grey, grey Mylar or tan aramid sails. These are light enough that the dark numbers still read. The player's boat keeps the club's Dacron. | [game-01](compare/game-01-fleet.jpg) |
| Flat hulls (game-07, 01) | Uniform gelcoat with nothing on it | **Hull wear** (`BOAT_CODE`). Black streaks run down the topsides from the toe rail, each its own width and length. Tone varies by plus or minus 3% across a hull or deck. The fairness of a laid-up hull bends the clear coat's reflections. These are subtle. The J/22 already has its deck hardware (winches, cam cleats, tracks, blocks), so the flat look is mostly lighting and shading, not missing parts. | [game-07](compare/game-07.jpg) |
| Painted cumulus: one evenly white shape, feathered edges (game-05, 10) | AO on fair cumulus only went down to 0.75. The edges were eroded by the detail noise's fine octaves. | **Cumulus** (`CLOUD_CODE`). It sits on flat grey bases (AO 0.5, cumulus share only, so stratus decks keep their tone). The edges are eroded by the detail's coarse octaves, and a crisper ramp runs from edge to body. The detail noise is one mip coarser. The per-step optical-depth cap is 1.5 times the storm's (it was 2), so the skin isn't frosted. | [game-05](compare/game-05-cumulus.jpg) |
| Speckled storm cloud (game-04, 08) | Optical depth per march step: storm cloud closed within a step, so each pixel was lit at whatever depth its jittered sample landed. | **Storm step cap** at 0.6 of `MaxStepDepth` for storm and rain. Measured on game-08 with the measuring arguments: 0.6 smoothed the grain and kept the dark mass, 0.4 washed it grey, and 160 view samples (`-SailingCloudSamples`), half-resolution tracing (`-SailingCloudMode=1`) and 4x shadow samples didn't help. Less speckle, not none: see Open. | [game-08](compare/game-08-storm.jpg), [game-04](compare/game-04-storm.jpg) |
| Houses as plain boxes (game-09, 02, 10) | Glass was a flat dark panel. Walls had no eave detail. | **House kit materials.** Glass has white sash frames and a meeting rail, blinds half drawn in some windows, and the sky's brighter reflection in the upper panes. Painted windows have frames and a muntin. A soffit shadow, a fascia and downspouts run along each wall. Roofs have granule speckle, black algae streaks from the ridge, a darker drip edge and patched shingles. | [game-09](compare/game-09.jpg) |

## The crew on the PC

The Mac's G8 crew (zip `MetaHumanCrew-20261014-f2d6f8f`) is unzipped in `Content/Crew/MetaHumans` (git-ignored). With
it, `SailingSim.Visual.MetaHumanCrew` runs instead of skipping, and High and Ultra draw the crew's hair as strands. In
game-06 at 2-4 m the strands draw on all three sailors (single stills: flicker in motion wasn't checked). In game-05
at 10 m the dinghy sailor's hair is on the card LOD the Mac set (`UpdateCrewGroomLOD`). See [game-06](compare/game-06.jpg).

## Windows scripts

These are new in `scripts/windows/` and mirror the Mac loop:

- `run-python.ps1 <script.py> [-ScriptArgs ...] [-Only fn,...]` runs an editor Python script headless. This is how
  `make_materials.py` (`-Only` sets `MATERIALS_ONLY`), `bake_shore.py` and the rest run on the PC.
- `run-game.ps1 -Seconds N -Shot name -GameArgs "..."` runs the game uncooked from the editor, for quick looks.
- `capture-scenes-win.ps1 [-Scenes csv] [-Out dir]` captures a scene list on the packaged game, like `capture-scenes.sh`.
- `test.ps1` no longer fails a passing run when a shader worker still holds the editor's stderr file as it exits.
- `build_trees_materials` keeps the imported `T_LeafAtlas` when there is no freshly drawn PNG (the PC has no venv to
  draw it; the atlas script isn't seeded).

## Gate (PC)

- `scripts\windows\build.ps1`: succeeded (MSVC 14.51).
- `scripts\windows\test.ps1`: **98 passed, 0 failed** (13 with warnings, the usual: detail files absent for the coast,
  the editor's network probe, `S_Wind`).
- `scripts\windows\package-win.ps1`: succeeded.

**bench-visual on the PC** (`bench-visual-win.ps1 -Tiers High,Ultra`, packaged, 1920x1080, 12 s per view, MetaHuman
crew; `bench-visual-pc.csv`, screenshots in `bench/`). The PC is CPU-bound (an i9-9900K). The 4090 uses 4.3 to 5.9 ms
per frame on High and 6.2 to 8.9 ms on Ultra, so the fps here say little about the Mac.

| View | High fps | High GPU ms (clouds) | Ultra fps | Ultra GPU ms (clouds) |
|---|---|---|---|---|
| beam8 | 72.4 | 5.09 (0.45) | 72.9 | 6.84 (1.48) |
| beat15 | 71.3 | 4.82 (0.46) | 71.4 | 6.58 (1.55) |
| storm | 73.8 | 4.72 (0.62) | 72.5 | 8.85 (3.52) |
| marina | 76.5 | 5.02 (0.43) | 73.6 | 6.90 (1.53) |
| coast-day | 69.1 | 5.58 (0.39) | 67.6 | 7.53 (1.26) |
| coast-night | 76.7 | 4.27 (0.49) | 79.5 | 6.18 (1.00) |
| gulf-sea | 70.1 | 4.74 (0.44) | 70.5 | 7.03 (1.37) |
| helm-eye | 70.0 | 5.92 (0.40) | 64.1 | 7.27 (1.36) |
| slip | 77.7 | 5.81 (0.39) | 74.0 | 7.67 (1.25) |
| bridge | 76.0 | 4.78 (0.42) | 71.9 | 6.96 (1.45) |
| crew | 69.2 | 5.74 (0.40) | 66.6 | 8.32 (1.52) |
| marina-night | 84.5 | 4.55 (0.42) | 79.8 | 6.72 (1.02) |

**The round 9 scenes**, before and after (packaged, High, 1440x1080):

| Scene | fps before | fps after | GPU ms before | GPU ms after | clouds ms before | clouds ms after |
|---|---|---|---|---|---|---|
| game-01 | 48.9 | 41.6 | 4.72 | 6.55 | 0.25 | 0.36 |
| game-02 | 91.5 | 81.5 | 4.33 | 4.32 | 0.25 | 0.25 |
| game-03 | 82.4 | 80.7 | 4.24 | 4.72 | 0.37 | 0.38 |
| game-04 | 87.6 | 72.3 | 3.93 | 4.55 | 0.51 | 0.60 |
| game-05 | 80.3 | 74.8 | 3.55 | 4.25 | 0.36 | 0.38 |
| game-06 | 76.4 | 66.5 | 3.82 | 4.52 | 0.27 | 0.26 |
| game-07 | 87.1 | 77.1 | 4.38 | 5.25 | 0.34 | 0.36 |
| game-08 | 82.7 | 81.0 | 4.15 | 4.62 | 0.49 | 0.61 |
| game-09 | 91.2 | 83.5 | 4.46 | 4.99 | 0.34 | 0.36 |
| game-10 | 90.2 | 79.8 | 4.61 | 6.72 | 0.42 | 1.02 |

"After" also has the MetaHuman crew and its strand hair, and most of the drop is the crew's CPU cost. Rerun with
`-SailingBlenderCrew` on the same G8 build, game-06 ran at 73.7 fps (66.5 with the MetaHumans, 76.4 before G8),
game-10 at 82.5 and game-04 at 85.9. So G8's own cost on the PC is 2 to 8%: the storm cap's clouds slice is about
0.1-0.2 ms more on the 4090, and the materials' extra ALU is the rest.

**For the Mac gate** (Medium 60, High 45; the Mac reruns it): every change runs on every tier, and none is gated behind
Ultra. The one that costs real GPU is the storm cap (storm and rain only). The Mac's G8 crew bench has storm High at 47.6
and helm-eye at 45.1. If the storm view drops under 45 there, the fallback is to keep the storm cap at 1.0 on High (a
`QualityCVars`-style switch through a material parameter) and use 0.6 on Ultra only.

## Open

- Storm speckle is reduced, not gone. The frosted texture on bright cumulus inside a storm is the same from run to
  run, so it is in the density field and the shading, not only in the sampling. The next thing to try is the
  Perlin-Worley remap's sharpness (`* 1.9 - 0.75`) for cloud inside the storm's extent.
- Boats still read flat up close. The next step is geometry, not texture: the nonskid panels' smooth margins, cockpit
  cushions, coiled lines on the berthed boats, and dodgers on the bigger keelboats (`build_fleet.py`, `build_berthed.py`).
- The Mac's note: the fleet's rudder models bake a tiller extension along the tiller, and the live one is drawn too.
  A `TillerEnd` socket without the baked extension (`build_fleet.py`) needs Blender and the import on the PC. Not done.
- The Sunfish in game-05 shows a broken, ghostly reflection of its daggerboard and rudder under the hull (the water's
  screen-space reflection of the submerged foils). It is in the water material, not yet looked into.
- The near tree cores are now dark. From close up a few read as dark blotches between the cards. The core brightness
  (0.32) is the knob.
