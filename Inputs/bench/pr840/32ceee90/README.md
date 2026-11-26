# PR #840 (frigate grain, head 32ceee90) on the PC, Nov 25 2026

**Worktree:** `D:\dev\ss-fix-wt\pr840` at 32ceee90.

## How it ran

There's no REGENERATE.md in the branch, so I followed the README and `export.py`'s docstring. Nothing was installed.

1. **Export:** the branch's `Tools/shipkit/frigate/export.py` ran in the existing venv `D:\dev\frigate\venv` (bpy 5.3.0,
   set up for the Nov 23 regen on Bean's OK) on `D:\dev\frigate\lt\frigate_light.blend` with `--build D:\dev\frigate\build`.
   It finished in 4 min with exit 0: 959 FBX into `D:\dev\frigate\out-pr840`.
2. **Build:** MSVC, editor target. Succeeded, 0 errors, 0 warnings in the project's `Source/`.
3. **Material:** `run-python.ps1 make_materials.py -Only build_boat_library`, exit 0. The PR changes the boat library's
   Grain code.
4. **Import:** `run-python.ps1 import_frigate.py -ScriptArgs D:\dev\frigate\out-pr840`, exit 0, 46 min.
5. **The reimported Content is committed locally only**, as **`ed3b269e`** (1084 files) on the worktree's detached head.
   I haven't pushed it and won't.
6. **Tests:**
   - `SailingSim.ShipOutside`: **4 of 4 pass**.
   - `SailingSim.Visual`: 108 tests, **1 fails**: **`SailingSim.Visual.BoatShaderLiterals`**. It reads: "BOAT_CODE: a
     conditional between bare literals (type them, 0.5f): `? 2 : 1`" and "`? 1 : 0`". These come from the PR's new line
     in `scripts/make_materials.py`:
     `int gAxis = VC.r < 0.5 ? (VC.g < 0.25 ? 0 : (VC.g < 0.75 ? 2 : 1)) : (GrainUp > 0.5 ? 1 : 0);`
     They are integer selects, fine in HLSL, but the check bans any bare-literal conditional. Typing them, for example
     `int(2) : int(1)`, or a small lookup would pass. The same test passed on #839's branch.
7. **Package:** Development `Packaged\Windows-pr840-32ceee90`, built with the local Content.

## 4K Ultra after-stills against the 2fb7bc35 set

**Files:** `compare-<view>.webp` has 2fb7bc35 on the left and 32ceee90 on the right; `<view>-after.webp` is the after
still alone at 1920. They're the same args as before: Gulf, launch 2, wind 12, Comm, `-SailingWalkAt=...`.

| View | Walk spot | What changed |
|---|---|---|
| gun-4k | Gun,-19,0,0 | **Grain along the beams and the deck planks overhead**, which were flat before. The pillar's grain runs up it, but as broad, very regular bands that read more like fluting than figure: worth a look at its scale or noise on a turned round. Guns and carriages unchanged. |
| berth-90-4k | Berth,2,0,90 | **The beams show grain along their length.** The short block under the beam shows a wavy cross figure; it may be grain across a short end. |
| orlop-m12-180 | Orlop,-12,0,180 | **The orlop floor's zigzag is gone**, replaced by straight figure along each plank. The pillar has fine lengthwise grain. The overhead beams have grain. |

**Worn paint:** I can't see it in these three views. The carriages' red and the panelled bulkheads look as before. It
may need a closer or lit view of painted wood.

Bean's Saved was held aside and restored for every run (7B5CA7BE).

## Update: rebased onto 0302437e (gAxis by step() sums)

- **No export regen:** the 32ceee90 export is still valid.
- **Rebase:** the local Content commit was rebased onto 0302437e. There was no conflict, the working tree is clean, and
  no replayed file is pointer-sized.
- **Material:** `make_materials.py -Only build_boat_library` was re-run, exit 0, and folded into the local commit. **The
  local Content commit is now `8e556a98`**, parent 0302437e, still not pushed. The push to the PR branch waits for
  Bean's label and his typed OK.
- **`SailingSim.Visual`: 108 tests, 0 failed** (105 clean, 3 with warnings), with **BoatShaderLiterals passing**.
