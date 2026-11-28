# PR #847 at 45f82f4b on the PC (Nov 28 2026)

**Head:** 45f82f4b "Merge main 8768dacc (via the tide-proxy draft) into the shore-edges draft", parents aaacbcd8 and
abbcabf9. It contains main 8768dacc and #846's d35690a0 (by design). The reused worktree (`D:\dev\ss-fix-wt\pr852-30b9ea2f`,
detached at 45f82f4b). Build and suite only, as asked. Nothing pushed to the PR branch.

- **MSVC editor build:** Succeeded, 0 project warnings, 0 errors.
- **Full `SailingSim`:** 483 tests, 443 passed, 40 with warnings, **0 failed**, 0 not run (152 min;
  `sailingsim-tests.json`).
  - Passed: `Coast.KeptKeepsProxy` (under `-nullrhi`, its proxy checks skipped with their warning),
    `Coast.KeptStaticFollowsTide`, and the shore tests (`Lake.ShoreDetail`, `Lake.ShorelineMatchesMapData`,
    `Lake.ShoreMapAtRamp`, `Lake.LeeShoreChop`, `Coast.MarseilleShoreAndSeams`, `Smoke.CameraOffShore`, `Audio.ShoreLife`).
  - The warnings are the PC's usual set:
    - 18 `LogStreaming: Failed to read file` (optional `.detail` files);
    - 17 `LogHttp` probe timeouts;
    - one each: `KeptKeepsProxy`'s `-nullrhi` note, `Geo.SaveFallback`, `AsyncPhysicsMatchesSync`'s audio samples,
      `UI.LoadingStill`'s U+2190 glyph, and `Visual.J22HeroMesh`'s canoe volume (on main too).
  - The suite's log has no "cannot attach" line. The 40 s lake count against main wasn't in this ask.
