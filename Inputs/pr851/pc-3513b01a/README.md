# PR #851 at 3513b01a on the PC (Nov 27-28 2026)

**Head:** 3513b01a "Object streaming: a clone of a template no longer takes the tide twice", parent 4f563bca (on main
2479e9cf). A reused worktree (`D:\dev\ss-fix-wt\pr852-30b9ea2f`, detached at 3513b01a); Development package
`Packaged\Windows-pr851-3513b01a`, warmed once. Main is `Windows-2479e9cf`. Paused 20:11 to 22:45 local on Bean's word,
then rerun from the start. Nothing pushed to the PR branch. Bean's Saved restored after every run (7B5CA7BE).

## Build and the full suite

- **MSVC editor build: Succeeded, 0 project warnings, 0 errors.** 75421c8b's C2280 (`../pc-75421c8b/`) is fixed.
- **`SailingSim`: 485 tests, 448 passed, 37 with warnings, 0 failed, 0 not run (153 min).** `sailingsim-tests.json`.
  - The new `SailingSim.World.ObjectTiles.Rules`, `.Instances` and `.HouseRing` all passed.
  - The warnings are the PC's usual ones, as on the 2479e9cf freeze pass:
    - 19 `LogStreaming: Failed to read file` (the optional `<World>.detail` files);
    - 14 `LogHttp` timeouts (the connectivity probe);
    - one each: `Geo.SaveFallback`'s expected "unknown launch spot", `AsyncPhysicsMatchesSync`'s optional audio samples,
      `UI.LoadingStill`'s missing U+2190 glyph, and `Visual.J22HeroMesh`'s canoe volume (1.085 against 1.052 m³), which
      main has too.

## Stills, #851 against main, the same arguments (`stills/`, 1920-wide WebP of the 4K frames; `stills/args.txt`)

Ultra, 3840x2160, screen 100%, crew off on both (the PC's frames rule; `views.ps1`'s helm-eye has crew on).

- **`helm-eye`** (lake, launch 1, HelmEye capture): the same frame on both, the far shore along the horizon in each.
- **`coast-day`** (Galveston launch 1, 11:00; the bench view keeps the HUD): the same boat, wake, HUD and sky. The far
  shoreline on the horizon is drawn on both.
- **The crown tiles at the shore** (`crowns-*`): the camera 200 m off the Kemah shore (map -330,560, 2 m up, looking 240,
  fov 30).
  - **The time-dilation plan (b) didn't move the tide.** With `-SailingSlowMo=60` the tide stood at 6 cm at both stills
    on both builds (`crowns-before-*`, `crowns-after-*`). The tide follows the wall clock, not the dilated game clock.
  - **So the fallback (a) ran:** `-SailingTideStepEvery=30`, before at 20 s and after at 45 s, one forced 3 cm step
    (`crowns-a-*`; `tide-steps.txt`).
  - **Result:** houses, piles and the crowns stand the same on both builds, before and after. A 3 cm step is about 1 px
    here, so only a gross height error would show, and none does.
