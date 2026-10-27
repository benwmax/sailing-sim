# Near-shore audit, phase 2: the wooded shore's understory

Follow-up to the near-shore audit's item 4 ("the wooded shore is a strip": lidar crowns standing alone in grass, no
shrubs, saplings, dead wood or brush between them). Procedural only; no downloaded assets.

## What changed

- `Tools/blender/build_understory.py` builds nine models from the trees' own skeleton and leaf cards
  (`build_trees.py`'s `Builder`, the shared leaf atlas, `M_TreeBark`/`M_TreeLeaves`):
  - yaupon holly (`SM_Shrub_0`, `_1`): evergreen clumps of thin stems, 2 to 3.5 m;
  - roughleaf dogwood and coralberry (`SM_Shrub_2`, `_3`): lower, spreading, deciduous;
  - a cedar elm sapling and a young red cedar (`SM_Sapling_0`, `_1`);
  - a fallen trunk with its limbs and root plate, and a brush pile (`SM_Deadfall_0`, `_1`);
  - a standing snag (`SM_Snag_0`).
  `make-world-models.sh` runs it and `import_world.py` files them under `Trees` and `Props`. `build_trees.py` gained
  `LIMB_FLOOR`, `stem_r` and `leader_r` for the small plants and only runs `main()` as a script.
- `ALakeTerrainActor::PlaceUnderstory` (High and Ultra; `-SailingNoUnderstory` compares). Around every full-detail lidar
  crown with open water within 80 m, outside the houses' yards and the club's marina:
  - shrubs under and around the crown, about one per 12 m² of crown, a third on the water side: yaupon under the
    canopy, dogwood and coralberry at the drip line;
  - up to three thickets or saplings 3 to 15 m past the drip line, filling the gaps between spaced crowns;
  - a sapling toward the light on one crown in four, dead wood under one in eight, a snag at the water on one in thirty.
  On Ray Hubbard that is 17,994 crowns, about 117k shrubs, 8.8k saplings, 1.2k logs, 1k brush piles and 214 snags. They
  are hierarchical instanced Nanite meshes, out of Lumen's scene and ray tracing, with static-cached shadows, as the
  reeds are. They carry the trees' per-instance look (tint, autumn), so the dogwood turns with the season and the
  yaupon stays green. Culling: shrubs and saplings at 600 m, dead wood at 300 m, snags at 1 km.

## Cost

Understory off (`-SailingNoUnderstory`, as main) against on, alternating, two rounds, with the new meshes' derived data
warmed first. RTX 4090, 1920x1080, uncooked. Each cell is main → branch:

| View | Tier | fps | game ms | render ms | GPU ms | base pass ms |
|---|---|---|---|---|---|---|
| Wooded shore, raised | Ultra | 74.7 → 73.2 | 11.03 → 11.23 | 5.55 → 5.67 | 6.16 → 6.31 | 2.26 → 2.39 |
| Wooded shore, raised | High | 77.8 → 72.9 | 10.45 → 10.79 | 5.34 → 5.65 | 4.30 → 4.29 | 1.65 → 1.70 |
| Helm eye | Ultra | 57.4 → 56.5 | 15.42 → 15.36 | 7.34 → 7.46 | 7.66 → 7.62 | 3.40 → 3.33 |
| Helm eye | High | 59.0 → 59.2 | 14.29 → 14.75 | 7.12 → 7.10 | 5.07 → 5.16 | 2.31 → 2.37 |

The wooded view's High fps comes from one slow branch run (69.7 fps); its second run matched main (76.1 against
77.6). The GPU costs about 0.15 ms where the understory fills the frame and nothing at the helm. On High the shadows
didn't move: the "other" slice, where the virtual shadow maps land, was 1.20 ms → 1.16 ms. The CPU difference is within
run-to-run noise.

## Stills (Ultra, 15:00, the audit's wooded-shore spot)

- `wooded-raised-15h.jpg`: the raised camera, before and after.
- `wooded-eye-15h.jpg`: eye height.
- `wooded-shore-band.jpg`: the spit at full resolution, before above, after below.
