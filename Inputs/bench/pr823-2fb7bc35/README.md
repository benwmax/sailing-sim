# PR #823 (frigate decks) at 2fb7bc35 on the PC, Nov 25 2026

**Head:** `claude/project-thread-xkunbh` at **2fb7bc35** ("Frigate: the deck above is shown as the overhead below,
unlit"). I built it in a fresh worktree and removed the worktree afterwards. I only unlinked the crew link; all 541 crew
files are still there. Nothing was pushed to the PR.

- **MSVC build:** Succeeded, 0 errors.
- **Tests:**
  - ShipOutside 4/4.
  - ShipWalk 8/8.
  - Smoke 36/36 (1 warning, `AsyncPhysicsMatchesSync`, as in earlier runs).
- **Package:** Development `Packaged\Windows-pr823-2fb7bc35`; the cook had 0 errors and 1 warning.

## 4K Ultra on the decks

Settings: `-SailingBoat=Comm -SailingWorld=Gulf -SailingLaunch=2 -SailingWind=12`, 3840x2160 at 100%, 20 s benches.

| Run | `-SailingWalkAt` | fps | p99 ms | max ms | GPU ms (base / Lumen / post) |
|---|---|---|---|---|---|
| berth-0 | Berth,2,0,0 | **42.1** | 26.97 | 28.3 | 23.26 (10.05 / 3.12 / 2.36) |
| berth-90 | Berth,2,0,90 | **43.0** | 27.39 | 29.5 | 22.80 (9.87 / 2.75 / 2.36) |
| gun | Gun,-19,0,0 | **46.1** | 25.85 | 27.0 | 21.23 (8.67 / 2.23 / 2.48) |
| orlop | Orlop,0,0,0 | (42.3) | | | **not on the orlop**: "-SailingWalkAt=Orlop,0,0,0: nowhere to stand there". She stood at the helm on the upper deck instead (`orlop-4k-1080p.jpg`). I'll rerun at another spot. |

**The 4K hang stays fixed.** The gun deck ran 20 s at 4K with no DXGI hang, with the deck above's mesh loading
overhead. No run had a GPU crash or device-removed line.

**Berth deck** (`berth-0-4k`, `berth-90-4k`):
- **Planks overhead, no sky.** Looking up you see the planking and beams of the gun deck above; no sky shows through.
- **No gun carriages** between the beams.
- **No light leaking down** from the gun deck's lanterns: the overhead is lit only by the berth deck's own lanterns.
  The bright patch top right in `berth-90` is a berth lantern lighting the beam beside it.

**Berth fps:** 42-43 at 4K. That's a little better than 44733c87's 41.0 there, but still under the 45 fps 4K line.
- The GPU frame is about 23 ms. Base pass is 10 ms, with about 1 ms of it from the gun deck now drawn overhead.

**Log:**
- The berth runs log "Ship decks Berth: 406 copies, 12 lanterns (unshadowed)".
- They also log one "Ship decks Gun: 0 copies, 15 lanterns (unshadowed)". That line is at frame 2, at spawn on the
  upper deck, *before* the walker is moved below ("-SailingWalkAt: walking on Berth" at frame 28).
- After that, no Gun line appears while below.

Bean's Saved was held aside and restored (7B5CA7BE).
