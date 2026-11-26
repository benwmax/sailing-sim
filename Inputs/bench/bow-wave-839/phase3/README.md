# Bow-wave phase 3 look test (PC, Nov 26 2026). LOCAL ONLY: nothing from this patch is on any branch

**The patch:** `Inputs/bow-wave/phase3-local.patch.enc`, decoded (`@SP@` to a space, `@TAB@` to a tab, LF line endings,
no BOM). Its **sha256 matched**: `71513b52...12af9`, 35,439 bytes.
- **Applied:** `git am` in a scratch worktree, `D:\dev\ss-fix-wt\phase3`, onto **a60bfc49**. It's two commits: ae9970f9
  ("wake crests sharpen by the water's own displacement") and 841a7f08 ("the bow's crest breaks white at speed").
- **Never pushed.**

## Build, materials, tests

- **MSVC build:** succeeded, 0 errors, 0 warnings in the project's `Source/`.
- **Materials:** `run-python.ps1 make_materials.py -Only build_bow_wave,build_water_v4`, exit 0.
- **`SailingSim.Visual.WakeFold`: Success**
  - 3.0 kn: fold at her bow 0.957 (on water 0.005 m high); lowest in open water 0.832; crests 0.940 (58 cells); troughs
    1.063 (48); mean 1.0000.
  - 6.0 kn: fold at her bow 0.839 (on water 0.027 m high); lowest in open water 0.683; crests 0.959 (1560 cells);
    troughs 1.040 (1462).
- **`SailingSim.Visual.BowCrest`: Success**, unchanged from a60bfc49:
  - crest 0.008 / 0.032 / 0.041 m at 3 / 5 / 6 kn;
  - foam there 0.00 / 0.11 / 0.85;
  - foam 6 m ahead 0.00.

## Stills: phase 3 against `-SailingClassicBowWave3`

**Package and settings:** `Windows-phase3-a60bfc49`, 1080p Ultra, the demo, one frame at 14 s.
**Files:** `p3-<speed>-<view>-<phase3|classic>.webp`.

| Pair | Framing | Phase 3 | Classic |
|---|---|---|---|
| 6 kn, `bowq` | 7 m ahead, 3 m to leeward, looking back at the stem (fov 50) | A thicker, brighter white lip just aft of the stem, with torn edges and streaks along it | A thinner, dimmer lip |
| 7 kn, `bowq` | the same | The same, a little broader | Thin lip and a mist puff |
| 6 kn, `abeamB` | 2.5 m to leeward, 0.4 m up, at the forward hull (fov 40) | **The crest breaks into a torn white band of several bright strands**, starting just aft of the stem, with streaks running down its outer face and flecks at the waterline | One thin bright line along the crest |
| 7 kn, `abeamB` | the same | The same, brighter, with more strands | One thin line |
| 3 kn, `bowq` (TWA 150) | the same as 6 kn | No crest, no white | No crest: **unchanged, as expected** |

**Against the brief:**
- **As described:** the torn white band a few cm wide, starting just aft of the stem, streaks down its outer face, and
  **not a flat white blob** at the stem.
- **Not as described: "fading within about a metre."** In the abeam frames the band runs across most of the frame
  (about 1.8 m wide at 2.5 m with fov 40) before thinning, so it looks longer than a metre here.
- **The 3-4 kn control is unchanged.**

Bean's Saved was held aside and restored for every run (7B5CA7BE).
