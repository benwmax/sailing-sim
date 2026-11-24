# PR #820 (film mode clouds: Mode 0, not 3) on the PC at 3edc27ea

- **Head:** branch `claude/project-thread-q73bv9` at **3edc27ea**, on main e0a1125d (#817 merged).
- **Build and test:** a fresh worktree `D:\dev\ss-fix-wt\pr820`, removed afterwards. MSVC build (`build.ps1`) Succeeded,
  0 errors. `SailingSim.Smoke.FilmMode` 4/4 (FrameClock, ShotMoves, ShotParse, Switches).
- **Package:** Development `Packaged\Windows-pr820-3edc27ea` (kept), 3 min; cook 0 errors, 1 warning.
- **Still:** one 2 s tripod run, Ultra 4K, `-SailingFilm -SailingMotionBlur=0`, the same shot as the cloud-blocks runs.
  120 of 120 frames, 1.28 s/frame. Its log: "Film quality: r.VolumetricRenderTarget=1 r.VolumetricRenderTarget.Mode=0
  ...", so the change is live.
- **Cloud bases:** `Inputs/bench/pr820/clouds-1to1-3edc27ea.png` shows frame 60 at 1:1 from (400,450), left to right:
  4acec367 film (Mode 3), this head (Mode 0), and the follow-up's (4) (no sky cache, Mode 0).
  - **The ~8 px blocks are still there at 3edc27ea.** They look just like 4acec367's, because this branch still renders
    the far sky from the 8192x1024 sky cache. The blocks are the cache's texels, which Mode 0 doesn't touch.
  - Only the follow-up's (4), with the cache off, is clean.
  - So the reel needs Mode 0 together with #818's sky-cache lens switch (or `-SailingNoSkyCache`) to lose both the
    blocks and the stipple.
- Nothing was pushed to the PR. Bean's Saved was held aside and restored (7B5CA7BE). Crew link unlinked only, 541 files.
