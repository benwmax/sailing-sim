# PR #813 at 556aa91a (straw lattices bent by the 11 and 31 m noises) on the PC

**Build:**

- Head `556aa91a`, confirmed with `gh pr view 813`. It contains main `91c8c80d`, so it was used as is. Fresh worktree, `git lfs pull`.
- MSVC build: Succeeded. It was needed for the uncooked runs, even though only Tools changed. Lake tests not run, as briefed.

**Ground material:** `import_ground.py` with `GROUND_MATERIAL_ONLY=1` rebuilt M_Ground with no "Failed to compile Material". Not committed; the worktree, with it, was removed.

## Views

The two lawn views uncooked at Ultra 1080p, same args as before (`args.csv`). `crops/compare-*.png` set 1795eead beside 556aa91a at 1:1. Bean's Saved was held aside and restored.

| Crop | Verdict |
|---|---|
| diamond patch (`compare-diamond.png`, x 1060-1300, y 350-530) | **fainter but still there:** a lighter patch with diagonal, diamond-like edges remains at about the same place |
| old rectangle area (`compare-rect-area.png`, x 1000-1700, y 0-600) | **unchanged** from 1795eead: no straight-edged rectangles, the same soft lighter patches |
| beach (`compare-beach.png`) | **unchanged:** no step |

Nothing else in the ground look changed.
