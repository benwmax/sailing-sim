# #834 at 50cc95bc (wildlife phase 1, distant birds): the PC half (Nov 26 2026)

**Build and tests:** worktree `D:\dev\ss-fix-wt\pr834`, moved from 02b9584d to 50cc95bc for an incremental build.
- MSVC succeeded, 0 project warnings.
- **`SailingSim.Wildlife`: 9 of 9 pass**, including `SailingSim.Wildlife.Passes`.
- **`SailingSim.Smoke`: 36 tests, 0 failed.** The only warnings are the usual 13 on `AsyncPhysicsMatchesSync`.
- The test reports are `test-wildlife.json` and `test-smoke.json`.

## Packaging problem: the branch's package draws no birds

The Development package of 50cc95bc as it is logs
`Wildlife: M_BirdFar is not built yet (scripts/make-birds.sh): no birds drawn`.
- **Why:** `AWildlifeActor` loads `/Game/Wildlife/Birds/M_BirdFar`, `M_BirdMid` and the `SM_Bird_*` bodies by path at
  runtime. `/Game/Wildlife` isn't in `Config/DefaultGame.ini`'s `DirectoriesToAlwaysCook`, while World, Boats,
  Materials and the rest are. So the cook leaves them out.
- **The fix on the branch:** one line in `DefaultGame.ini`. That's a Config change, so it needs Bean's label.
  ```
  +DirectoriesToAlwaysCook=(Path="/Game/Wildlife")
  ```
- **For the numbers below** I added that line **locally only**: never pushed, and reverted after the runs. I packaged
  `Windows-pr834-50cc95bc-cookfix` with a full cook. Its log shows the bird materials compiling and the birds drawn.
- The first 50cc95bc package was also incomplete because D: filled up. It's set aside as
  `Packaged\Windows-pr834-50cc95bc-broken-nodiskspace`.

## Ultra 4K, against main 8ae5a0b1

**Runs:** 20 s each after an 8 s warm-up, demo autopilot, crew off. Main and #834 alternate, two runs each per view; the
table gives the means. The #834 package was warmed once first.

**Views (the bench's own):**
- lake beam8 (noon);
- Galveston coast-day (11:00);
- Marseille marseille-port (14:00).

| View | fps main / #834 | GPU ms main / #834 | Game ms main / #834 | p99 ms main / #834 | Birds in view (the log's `Wildlife:` line) |
|---|---|---|---|---|---|
| Lake | 51.2 / 50.6 (**-0.6**) | 18.96 / 19.19 (+0.23) | 10.60 / 11.45 (+0.85) | 22.6 / 23.3 | 236-237 of about 920 (540 quads, 3 bodies); nearest an osprey at 234 m; update 0.25 ms |
| Galveston | 45.7 / 45.4 (**-0.3**) | 21.34 / 21.46 (+0.12) | 13.54 / 13.99 (+0.45) | 25.4 / 25.5 | 154 of about 275 (180 quads, 77 bodies); nearest a brown pelican at 94 m; update 0.11 ms |
| Marseille | 48.0 / 47.5 (**-0.6**) | 20.26 / 20.47 (+0.21) | 12.29 / 12.87 (+0.58) | 24.3 / 24.4 | 61 of 153 (152 quads, 1 body); nearest a yellow-legged gull at 466 m; update 0.04 ms |

**Cost:**
- **GPU:** +0.1 to +0.2 ms, inside the plan's 0.5 ms.
- **Game thread:** +0.45 to +0.85 ms. That's over the plan's 0.3 ms, at Ultra's budgets (500 / 100 / 20) on the busy lake.
  The logic's own update is 0.04-0.25 ms, so the rest is the drawing: placing up to 540 instances a frame.
- **fps:** 0.3-0.6 lower, within this PC's run-to-run spread.

## Do the birds read?

**Stills:**
- `p834-<world>.webp` is plain; `p834-<world>-debug.webp` is `-SailingDebugBirds` (10x size, birds pinned in view);
  `main-<world>.webp` is the same view on main.
- They're 1920 wide from the 4K frames.

**Lake: yes, as distant birds.**
- A flock reads as fine dark flecks against the cumulus up to the right of the mast, and a few low over the far shore.
- In the debug still they're clearly birds, with bent wings and gliding gull and osprey shapes.
- At noon nothing comes close in this 20 s view.

**Galveston: yes, clearly.** It's the best of the three.
- A line of **brown pelicans** flies low over the water to the right of the boat, as bodies with wings out, about 90 m off.
- There are distant flecks over the shore to the left.

**Marseille: hardly, in this view.**
- 61 birds are in the view cone, but the nearest is a gull at 466 m, so they're sub-pixel flecks near the town.
- The bench's marseille-port camera also sits partly inside the quay wall, which hides the left third of the frame. That's
  the same on main, so it's the view, not #834.
- An open-water Marseille view (Frioul or the Rade) would show them better.

**Also in both main and #834:** a virtual shadow map overflow message in the Marseille frame. It isn't new.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
