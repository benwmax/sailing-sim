# #843 bow wave phase 3 at 61bef6a4: PC check (Nov 27 2026). **PASS**

**Checkout:** a clean 61bef6a4 (`claude/project-thread-5n19m3`, with the Mac's M_WaterV4 and M_BowWave committed) in
`D:\dev\ss-fix-wt\pr839`.

| Check | Result |
|---|---|
| MSVC build | succeeded, **0 errors, 0 project warnings** |
| `SailingSim.Visual.WakeFold` | **pass** |
| `SailingSim.Visual.BowCrest` | **pass** |
| `SailingSim.Visual` (all) | **111 tests, 0 failed** (4 with warnings: ChaseCamera.Pawn, J22HeroMesh, TreeSpecies, WakeGridShip) |
| `SailingSim.Smoke` | **38 tests, 0 failed** (1 with warnings, the usual `AsyncPhysicsMatchesSync`) |
| D3D SM6 shaders | **The cook compiled M_WaterV4 and M_BowWave fresh for PCD3D_SM6, with no material compile errors.** Across all 48 game runs the logs have no material compile error and no default-material fallback, and the water and bow wave draw normally in every still (no checker). |

**Package:** Development `Packaged\Windows-pr843-61bef6a4`, complete. Main 95220b32 was packaged the same way
(`Packaged\Windows-95220b32`, also the next queued package). Both were warmed once.

**Stills:** every scene of `docs/bow-wave/bow-scenes.csv`, at Ultra 1920x1080, crew off.
- `compare-<scene>.webp`, from left to right: **main 95220b32 | #843 with -SailingClassicBowWave3 | #843**.
- `stills/843-<scene>.webp` are #843 alone at full size, including the two `-SailingClassicBowWave` "before" scenes.

**The look:** at 6 kn from the bow quarter (`compare-bow-6kn-quarter.webp`), #843 shows a brighter white crest
breaking along the bow, aft from the stem. Main and the ClassicBowWave3 look show a smaller, plainer bow wave. Abeam and
from above, the difference is smaller at this resolution.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
