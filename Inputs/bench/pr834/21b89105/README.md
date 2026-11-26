# #834 at 21b89105 (cook line for /Game/Wildlife; only drawn instances sent): PC recheck (Nov 26 2026)

**Checkout:** a clean 21b89105 in `D:\dev\ss-fix-wt\pr834`, with no local edits. The branch's own `DefaultGame.ini` has
`+DirectoriesToAlwaysCook=(Path="/Game/Wildlife")`.

**Build and tests:**
- MSVC succeeded, 0 project warnings.
- **`SailingSim.Wildlife`: 9 of 9 pass**, including `SailingSim.Wildlife.Passes`.
- **`SailingSim.Smoke`: 36 tests, 0 failed.** The only warnings are the usual 13 on `AsyncPhysicsMatchesSync`.

**Package:** Development, full cook, `Packaged\Windows-pr834-21b89105`, 3 min. It's complete: `SailingSim-Windows.ucas`
is in, with no copy errors.

**Birds in the packaged game: yes.**
- The warm-up lake run draws them (197 in view, 540 quads and 3 bodies). There's no `not built yet` line in any run's
  log, so the cook-line fix works.
- **Galveston:** 154 in view, with brown pelicans at 93 m drawn as bodies (`p834-galveston.webp`).

**Ultra 4K lake beam8 against main 8ae5a0b1:** 3 alternating pairs, 20 s each after an 8 s warm-up, demo, crew off.

| Run | main fps | #834 fps | main game ms | #834 game ms | main GPU ms | #834 GPU ms |
|---|---|---|---|---|---|---|
| 1 | 50.7 | 49.6 | 10.60 | 12.09 | 19.14 | 19.57 |
| 2 | 51.6 | 50.0 | 10.67 | 11.44 | 18.80 | 19.42 |
| 3 | 50.2 | 50.0 | 10.84 | 11.48 | 19.31 | 19.40 |
| **Mean** | **50.8** | **49.9 (-1.0)** | **10.70** | **11.67 (+0.97)** | **19.08** | **19.46 (+0.38)** |

**The game thread is not lower than at 50cc95bc.**
- **Cost:** +0.97 ms here against +0.85 ms there, with the same 540 quads and 3 bodies drawn and 236-237 birds in view.
  Sending only the drawn instances hasn't moved it on this view, where all 540 quads are drawn anyway.
- **The plan's budget** is 0.3 ms game thread (High). At Ultra's 500 / 100 / 20, the lake is about three times over.
- **GPU:** +0.38 ms, inside the 0.5 ms budget.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
