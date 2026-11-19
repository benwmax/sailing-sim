# Lawn rectangles and beach step: lighting or material? (main 91c8c80d, PC)

**Setup:**

- Uncooked Ultra 1080p in the kept main 91c8c80d worktree (`args.csv`).
- Views: the backyards top-down (`"-SailingCamWorld=128,40,60,0,-89"`, landing at map N 240.3 E 1.4, 60 m) and `env-club-beach-05m`.
- New runs: `-ExecCmds="viewmode unlit"` and `-ExecCmds="r.Lumen.DiffuseIndirect.Allow 0"` (the game took it; no fallback needed).
- The `-SailingClassicGround` stills are the ones already taken for `main-91c8c80d/lawn-step/`.
- Bean's Saved was held aside and restored.

**Compare sheets:** `crops/compare-topdown.png` (1:1 at x 1000-1700, y 0-600) and `crops/compare-beach.png` (1:1 at x 1050-1750, y 330-620). Each stacks #813 d887d809, main lit, unlit, ClassicGround and Lumen indirect off.

| Run | Top-down rectangles | Beach step |
|---|---|---|
| main, lit | present | present |
| #813 d887d809 | present | present |
| `viewmode unlit` | **present**, fainter (the lighter blocks at lower middle and upper left still show in the unlit base colour) | not clearly visible: the unlit grass is too noisy to judge |
| `-SailingClassicGround` | **none** | **none** |
| `r.Lumen.DiffuseIndirect.Allow 0` | **present** | **present** |

**Verdict: material, not lighting.**

- The rectangles survive unlit (they're in M_Ground's base colour) and survive with Lumen's diffuse GI off.
- They vanish only with the classic ground.
