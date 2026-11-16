# Track D: trees and shrubs up close (environment loop)

Plan: the shore, grass and buildings plan (Track D), approved by Bean on 16 Nov 2026. Results and pictures:
`docs/envloop/trees/README.md`. Cloud half only: nothing here is loaded by the game yet (integration is after the
21 Nov slice, through the main sim thread).

| File | What it does |
|---|---|
| `packs/<pack>/pack.json` | A region pack (the shore plan's rule: regions are data, not code). `north-texas-lake` lists the species, their growth knobs, the shrubs, which species stand on banks, the atlas layout and the placement rules (from map data: height above pool, distance to water, cover, slope). Every tool takes `--pack`. A new region is a new pack folder: cards, growth and placement rules, with no code change. |
| `packs/<pack>/cards/<Species>.json` | One card per species and shrub (environment loop step 1): real heights, crown shape, trunk, leaf size, the CC0 leaf and bark sets, bark tile size, distance bands, budget, USDA PLANTS link. The generator and the atlas read them. |
| `fetch_sets.py` | Downloads the CC0 sets the cards name into `Inputs/trees/{ambientcg,polyhaven}/` (Git LFS: the Mac or PC commits them). |
| `make_leaf_atlas_d.py` | `T_LeafAtlasD` (4096 x 4096, 4 x 4 tiles) and its normal map: a leafy-branch spray per species with leaves at true size, a dense "clump" per species for the crown's inside, and post oak's dried winter leaves. |
| `build_trees_d.py` | The trees (10 species x 3 models + `_Far` crowns) and the understory (`SM_Shrub_0..3`, `SM_Sapling_0..1`), from the cards. |
| `render_trees.py` | Standard renders in Cycles (3, 15, 60 m and bark at arm's length; midday, low sun, overcast) of `--gen v6` (main's `build_trees.py`, the "before") or `--gen d`, with the lump and cost measures in `metrics.csv`. |
| `make_sheet.py` | Contact sheets and before/after pairs. |

## Run

Blender 4.2+ or the `bpy` module (pip `bpy`, Python 3.11), numpy and Pillow:

```
python3 -I Tools/envloop/trees/fetch_sets.py
python3 -I Tools/envloop/trees/make_leaf_atlas_d.py Artifacts/envloop/trees/T_LeafAtlasD.png
blender -b --factory-startup -P Tools/envloop/trees/build_trees_d.py -- Artifacts/models/world-d
blender -b --factory-startup -P Tools/envloop/trees/render_trees.py -- --gen d --species PostOak --dist 0,3,15,60 --out Artifacts/envloop/trees/renders
```

`render_trees.py --gen v6` needs main's atlas first: `python Tools/blender/make_leaf_atlas.py Artifacts/models/world/T_LeafAtlas.png`.

## The measures (metrics.csv)

- `core_share`: share of the crown's pixels where the first thing a ray hits is V6's opaque inner ball. That is the
  "solid dark lump" Bean sees. Track D has no ball: 0.
- `shell_share`: the same for Track D's inner leaf patches (they are leaves in shade, meant to be seen through gaps).
- `layers`: mean leaf-card surfaces crossed per crown pixel before something opaque: the masked overdraw the game's
  depth pass pays. V6 added its ball to cut this; Track D is held to V6's number per species.
- `tris` per model against the card's `budget.near_tris_max`.

## What integration needs (after 21 Nov, one PR through the sim thread)

1. Mac or PC: `fetch_sets.py`, commit `Inputs/trees/**` (LFS).
2. Swap `make-world-models.sh` from `Tools/blender/build_trees.py` to `build_trees_d.py`, and take the shrubs and
   saplings from it too (`build_understory.py` keeps the deadfall and the snag). Same mesh names; the `_2` models and
   `SM_Pecan_*`, `SM_Mesquite_*` are new.
3. Materials, in their own script (`scripts/make_env_trees.py`, not `make_materials.py`): import `T_LeafAtlasD` and
   its normal map into `M_TreeLeaves` (the material is unchanged otherwise: vertex colours mean the same, alpha 0 marks
   the inside); `M_TreeBark` gains a `BarkTile` (UV per metre) and texture parameters, with one `MI_TreeBark_<Species>`
   per card (`bark.set`, `1 / tile_m`, `tint`); `import_world.py` maps slot `Bark_<Species>` to it. Winter: a share of
   post oak's cards (vertex B over 0.55) swap to tile 15 (dried leaves) instead of fading.
4. Game code: `ETreeSpecies` gains Pecan and Mesquite (`TreePlacement.cpp`: pecan on bottomland near creeks, mesquite on
   dry open ground away from the houses) and a third model per species (the bank form where the ground drops to the
   water within 3 m, else open-grown on lawns). `SailingSim.Visual.TreeSpecies` updated.
5. Mac High gate and PC Ultra stills at the shore stations; the Megaplants comparison on the PC (Ultra only).
