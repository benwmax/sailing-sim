# PR #838 (`-SailingCaptureHud`, head 65ba8a7) on the PC, Nov 25 2026

**Worktree:** `D:\dev\ss-fix-wt\pr838` at 65ba8a7, on main d8f2a3dc. **Package:** Development
`Packaged\Windows-pr838-65ba8a7`.

## Build and tests

- **MSVC build: succeeded, 0 errors.** All 53 warnings are in engine headers; none are in the project's `Source/`.
- **`SailingSim.Smoke.FilmMode`: 5 of 5 pass**, including the new **`.CaptureHud`**, plus FrameClock, ShotMoves,
  ShotParse and Switches (`test-film.json`).

## HelmEye capture, three ways

**Setup:** 1080p Ultra on the lake, launch 1, afternoon breeze 12 kn, the demo at TWA 45, crew off.
`-SailingCapture=HelmEye`, a 4 s bench after an 8 s warm-up.

| Still | Switches | HUD |
|---|---|---|
| `helmeye-a-none.webp` | none | **No HUD**, as before |
| `helmeye-b-capturehud.webp` | `-SailingCaptureHud` | **The Helpful HUD:** time, wind and sky panel, a learning tip, the compass strip, the minimap, the wind dial, speed, VMG and depth, telltales and the key hints |
| `helmeye-c-capturehud-natural.webp` | `-SailingCaptureHud -SailingUiMode=natural` | **The Natural HUD:** the compass strip, a small dial, speed, depth and the telltales only |

**It passes.**

**The R06 frame with the switch:**
- **What:** `Inputs/reel-rehearsal/rehearsal-d8f2a3dc/fixes-webp/R06-helm-eye-capturehud-pr838.webp`.
- **How it was shot:** a film-mode take with the rehearsal's R06 shot file and `-SailingCaptureHud -SailingUiMode=helpful`.
- **Result:** it shows the full Helpful HUD over the helm-eye view.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
