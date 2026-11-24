# PC clean-up, Nov 24 2026 (Bean's "yes" at 19:08 UTC)

**D: free went from 172.8 GB to 642.1 GB, freeing 469.3 GB.** Nothing was skipped: no SailingSim process was running,
and every listed path was gone afterwards.

`packaged.csv` lists every item that was in `D:\dev\ss-fix\Packaged` before the clean-up, with its size, last-write
date and action.

## Deleted (by exact path, each checked as gone)

- 77 package folders, 377 GB: the older `Windows-*`, msvcfix, merge, pr817/820/823/824, frigate, canary and soak
  builds, and the Shipping candidates other than 76a41ea4 and 40226d1c.
- 12 old `ReadyAbout-*-Win64.zip` files, 48 GB.
- The worktrees `D:\dev\ss-fix-wt\pr764`, `main` and `frigate`, removed with `git worktree remove`, then
  `git worktree prune`. Their crew junctions were unlinked first, and none had changes. The crew still has 541 files.

## Kept

| Item | Why |
|---|---|
| `Shipping-76a41ea4` + zip | tester build Bean cleared |
| `Shipping-40226d1c` + zip | Bean's play build |
| `Windows-9291fbf6` | current main |
| `Windows-906c9034` | Nov 20 main, a baseline in reports |
| `Windows-frigate-3946b08c` | the frigate's performance baseline |
| `Windows-pr823-d7188785`, `Windows-pr824-fdaa4352`, `Windows-pr825-bcb91c2b` | newest package of each open PR |
| `ReadyAbout-*-TESTERS.md` (5 small files) | not on the delete list |
| worktree `D:\dev\ss-fix-wt\fw` | holds the local `pc/allow-firewall` branch |

## Not touched

- Saves and Bean's Saved folder.
- Bench results.
- `D:\dev\reel-test` and `D:\dev\frigate`.
- The checkouts ss2/3/5/6, sailing-sim and sailing-sim-w6.
- `C:\dev`.
- The firewall rules and the Sentry folder.
