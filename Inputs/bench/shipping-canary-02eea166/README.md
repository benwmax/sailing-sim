# Shipping canary of main 02eea166: a dry run for the Nov 27 Friday build (PC, Nov 26 2026)

**Build:** the way the Friday build is made, with three differences:
- **Sentry off:** no DSN staged, as usual for canaries;
- **no zip;**
- **not shared.**

**Steps:**
- **Editor build:** in the kept worktree `D:\dev\ss-fix-wt\main-02eea166`. MSVC succeeded, 0 errors.
- **Version line:** `02eea166, Nov 26 2026 canary, Sentry off`.
- **Slice switch on:** the version line and the slice switch were staged into the worktree for the cook, then removed.
  Afterwards `git status` on Config and Content was clean.
- **Package:** `package-win.ps1 -Config Shipping -Full`, 5 min, exit 0, into the new `Packaged\Shipping-02eea166-canary`.
  It's kept locally.

**Smoke:** `-SailingShippingSmoke -SailingWorld=Lake -SailingLaunch=1 -SailingBench=60`, 1920x1080 windowed, Ultra.
- Each launch got its own fresh Saved.
- Bean's Saved was held aside throughout and restored (7B5CA7BE).
- Shipping writes no log, so start-up time is wall time minus the bench's 60 s and its 3 s warm-up.

| Launch | Wall time | Start-up, about | fps | p99 | Max | Game / render / GPU ms | Exit | Crashes |
|---|---|---|---|---|---|---|---|---|
| warm (first launch: shader and PSO caches) | 120 s | 55 s | 86.6 | 17.0 | 48.0 | 9.8 / 10.8 / 8.2 | 0, clean | 0 |
| **smoke** | **78 s** | **15 s** | **109.5** | **13.4** | **26.1** | 7.4 / 8.1 / 8.2 | **0, clean** | **0** |
| ad60911e canary (Nov 18), smoke | 73 s | 10 s | 111.2 | 13.6 | 22.8 | | 0 | 0 |

**Result:** the Shipping build packages, starts, runs 60 s and exits cleanly, at the same speed as the Nov 18 canary
(1.5% lower fps).
- **Start-up** is about 5 s longer than ad60911e's (78 s against 73 s wall). That's within what this measure can tell
  apart.
- **For Friday:** the same recipe with the DSN staged and the zip; this canary needed nothing else.
