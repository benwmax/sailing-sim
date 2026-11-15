# Storm look round 3: draft PR #707 (crest spray) on BEN-PC

**Head 1737476a** (branch `claude/project-thread-blitx3`). It already contains main a9514c07, so there was no merge.
Against main it changes `WaterSurface.cpp/.h`, `WaterTests.cpp` and docs.

## Build and tests

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **SailingSim.Visual:** 87 passed, 0 failed, 4 with warnings, 0 not run (`test-visual.json`). The new
  **SailingSim.Visual.SprayQuad passed**.
- **The four warnings**, none from #707:
  - J22HeroMesh: its usual tolerance warning;
  - RigClearance: the optional S_* samples missing on this PC;
  - TreeSpecies: missing .detail bake;
  - CockpitEye: the engine's blocked `generate_204` HTTP probe, which lands on whichever test is running.

## Packages

- **#707:** `Packaged\Windows-1737476a-707`, 3 min.
- **Main:** `Packaged\Windows-a9514c07`, 3 min. This is the first main package that carries #703's assets.
- Neither cook had shader or material errors. Each package was warmed once.
- Bean's Saved was held aside and restored (F6458EAB).

## Stills (`stills/`, 4K Ultra, 10 s, round 2's args, cameras and moment)

| still | package | HUD wind |
|---|---|---|
| 707-downpour-shore | #707 | 30 kn S G32 |
| main-downpour-shore | main a9514c07 | 30 kn S G33 |
| 707-storm-30kn | #707 | 30 kn S G32 |
| main-storm-30kn | main a9514c07 | (same camera and moment) |

**The puffs are gone.** On main, `main-downpour-shore` still has the grey-white balls of mist sitting over the crests
across the whole sea. In `707-downpour-shore` (same camera, same moment) there are none. What is left over the crests
is faint and low:
- smears and short streaks lying along the wind, most visible to the right of the boat and in the foreground;
- nothing standing up off the water.

**Far spray.** In `707-storm-30kn` the far crests are flat foam and lace, with no white balls past the near water. The
near caps keep #703's ragged look.

**The far shore differs again.** In `707-downpour-shore` the far shore is gone into grey and the sky is lighter. In
`main-downpour-shore` the tree line is plain. #707 changes only the crest spray, so this looks like the same
run-to-run difference in the downpour I noted in round 2: the rain at the boat at that instant. It is not the spray
fix. The HUD shows the same wind. If it matters, a few runs of each at the same moment would settle it.
