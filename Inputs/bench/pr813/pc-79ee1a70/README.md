# PR #813 at 79ee1a70 (weedy-patch noise on a bent lattice) on the PC

**Build:**

- Head `79ee1a70`, confirmed with `gh pr view 813`. It contains main `91c8c80d`, so it was used as is. Fresh worktree, `git lfs pull`.
- MSVC build: Succeeded.

**Ground material:** `import_ground.py` with `GROUND_MATERIAL_ONLY=1` rebuilt M_Ground with no "Failed to compile Material". Not committed; the worktree was removed.

## Views

Same uncooked Ultra 1080p args (`args.csv`). `crops/compare-*.png` set 556aa91a beside 79ee1a70 at 1:1. Bean's Saved was held aside and restored.

| Crop | Verdict |
|---|---|
| diamond (`compare-diamond.png`, x 1060-1300, y 350-530) | **still there:** a faint lighter patch with diagonal, diamond-like edges, about as strong as at 556aa91a |
| old rectangle area (`compare-rect-area.png`) | **unchanged:** no straight-edged rectangles, the same soft patches |
| beach (`compare-beach.png`) | **unchanged:** no step |

Nothing else in the ground look changed. The diamond isn't removed by this head on the PC.
