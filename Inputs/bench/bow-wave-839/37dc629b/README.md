# #839 at 37dc629b (no texture-upload leak under -nullrhi): PC build, memory and Visual (Nov 26 2026)

**The fix:** under `-nullrhi` the runtime textures have no resource, and `UpdateTextureRegions` leaked each upload's
copy. All seven upload sites now check for a resource first.

**MSVC build:** a clean 37dc629b in `D:\dev\ss-fix-wt\pr839`. Succeeded, 0 errors, 0 project warnings.

**`SailingSim.Visual.SheetClearance` alone,** with the editor's commit sampled every 5 s (the `*-memory.csv` files):

| Tree | Result | Editor commit peak | Shape |
|---|---|---|---|
| main 20f03152 | pass, 3 min | 13.3 GB | climbs about 1.3 GB per boat |
| #839 622cdae4 | pass, 3 min | 28.6 GB | climbs about twice as fast |
| **#839 37dc629b** | **pass, 2 min** | **3.0 GB** | **flat** |

**Full `SailingSim.Visual` on 37dc629b:**
- **110 tests: 107 passed, 3 with warnings, 0 failed, 0 not run,** in 12 min.
- **Memory:** the editor's commit peaked at **5.4 GB**. The lowest system commit free was 68.7 GB.
- **On 622cdae4,** the same suite died out of memory in `SheetClearance` at about 145 GB virtual (`../622cdae4/`).
- `WakeGrid`, `WakeGridShip`, `BowCrest` and `SheetClearance` all pass with 0 warnings.
- **Warnings:** the 3 tests with warnings are ChaseCamera.Pawn, J22HeroMesh, TreeSpecies.

**Reading:**
- The leak was in the runtime texture uploads under `-nullrhi`. It's there on main too, where it's slower, and #839's
  extra uploads made it twice as fast.
- 37dc629b removes it for both: `SheetClearance` is flat at 3 GB, and the full suite stays under 6 GB.
