# PR #813 at 1795eead (M_Ground.hlsl regenerated) on the PC

**Build:**

- Head `1795eead`, confirmed with `gh pr view 813`. It contains main `91c8c80d`, so it was used as is.
- Fresh worktree, `git lfs pull`, crew linked. MSVC build: **Succeeded, 0 errors**.

**Test:** `SailingSim.Lake` passed 18 of 18, 0 failed (1 with the standing warning).

**Ground material:**

- `run-python.ps1 import_ground.py` with `GROUND_MATERIAL_ONLY=1` rebuilt `M_Ground` locally (`Content/Materials/M_Ground.uasset` modified).
- **No "Failed to compile Material" and no "missing usage flag"** (`import_ground-excerpt.txt`).
- The asset was NOT committed; the worktree, with it, was removed afterwards.

## Views

Uncooked Ultra 1080p, the same args as main 91c8c80d's lawn-step stills (`args.csv`). Bean's Saved was held aside and restored. `crops/compare-*.png` set main 91c8c80d beside 1795eead at 1:1; `crops/full-*.png` are half size.

| View | Verdict |
|---|---|
| `env-club-beach-05m` | **step gone:** the lawn is continuous across about x 1400 |
| backyards top-down (map N 240.3 E 1.4, 60 m) | **the straight-edged 8 x 12 m rectangles are gone.** Softer, round-edged lighter patches remain in about the same areas (e.g. lower middle of the crop), and one faint lighter patch with diagonal, diamond-like edges now shows at about x 1140-1220, y 410-470 of the full frame |

Nothing else changed in the ground look: the mowing stripes, grass texture, colour and sand edge read the same.
