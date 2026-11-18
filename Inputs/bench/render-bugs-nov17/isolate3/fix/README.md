# #804 (M_Terrain wet band) before/after on the PC: tip 8369ebda

**Build:**

- Tip `8369ebda` lacks main `df3bca26`, so it was merged locally as `780cd4a6` (not pushed). Fresh worktree, `git lfs pull` after the merge.
- MSVC build: Succeeded, 0 errors.
- **Shots:** the four #29 stills uncooked at Ultra 1920x1080 with the render-bugs-nov17 args, before (the branch's committed M_Terrain) and after `run-python.ps1 make_materials.py -Only build_terrain`.
- **Rebuild:** compiled clean. "Materials built", with no "Failed to compile Material" in the editor log or the last game log.
- **Saved:** Bean's Saved was held aside and restored.

**Contents:**

- `crops/compare-<scene>.png` stack three crops at the #29 boxes: the Nov 17 ecd4ed1c package, before and after.
- `crops/glow-*.png` are the single 1:1 crops.

## Result: #804 removes the glow at all four stations

Mean luma inside the #29 glow rectangles:

| Station | Nov 17 package | before | after |
|---|---|---|---|
| bridge-05m | 151.8 | 147.7 | **104.7** |
| bridge-15m | 151.1 | 149.8 | **94.3** |
| wooded-05m | 125.6 | 138.2 | **92.2** |
| wooded-15m | 128.1 | 130.8 | **80.1** |

- **Before:** the cream glow is there at all four, uncooked as in the package. So main df3bca26 alone does not remove it.
- **After:** it is gone. The bank under it reads as shaded soil (`compare-bridge-05m.png`).
- **Isolate3:** consistent with its finding that the glow is specular from the wet band (`../README.md`: ShowFlag.Specular 0 removes it).
- **#797 Track A stills:** the glow was missing there too, so either change alone appears to remove it.

## The asset commit was NOT made

The brief asked for the rebuilt `Content/Materials/M_Terrain.uasset` to be committed to `claude/project-thread-ei98g7` and pushed.

- **What I did:** checked out the branch tip 8369ebda cleanly, without the local main merge, and staged only that file. Main's make_materials.py changes since the branch point are boat and sail code only, so the terrain material is the same either way.
- **Why not:** this PC's permission check denied the commit and push to the PR branch, so nothing was committed or pushed.
- **The asset:** the rebuilt asset is kept on the PC: `Artifacts\bench\matfix-804\M_Terrain.uasset`, 22,790 B, sha256 A6F5A9B465B8...
- **To land it:** Bean's go-ahead in the thread, or the Mac rebuilding it with `make_materials.py` (MATERIALS_ONLY=build_terrain).
