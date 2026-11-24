# Draft PR #828 (film view mode, hull-clip switch) at 89ec83ed on the PC, Nov 24 2026

**Head:** `claude/project-thread-q73bv9` at **89ec83ed** ("Film mode: -SailingViewMode layer passes, timed console
commands reach the viewport"). I built it in a fresh worktree and removed the worktree afterwards. I only unlinked the crew
link; all 541 crew files are still there. Nothing was pushed to the PR. The base my script logged was 6630fe1e, because
it didn't refresh origin/main; the brief says the branch is from f61daaf7.

- **MSVC build:** Succeeded, 0 errors.
- **`SailingSim.Smoke.FilmMode.*`:** 4 of 4 passed (FrameClock, ShotMoves, ShotParse, Switches).
- **Package:** Development `Packaged\Windows-pr828-89ec83ed`; the cook had 0 errors and 1 warning.

## (b) P1 with `-SailingViewMode`: both runs CRASH on frame 0

The P1 shot is `p1-layer-peel-orbit.json` with the rehearsal's common args and `-SailingRecord=2`.

| Run | Log | Result |
|---|---|---|
| `-SailingViewMode=wireframe` | "Film view mode: wireframe (r.ForceDebugViewModes 1, debug view modes allowed)" | **Crash**, 0 frames |
| `-SailingViewMode=lightingonly` | Same line for lightingonly | **Crash**, 0 frames |
| Fallback: `-ini:Engine:[SystemSettings]:r.ForceDebugViewModes=1 "-ExecCmds=viewmode wireframe"` | "Set CVar [[r.ForceDebugViewModes:1]]", then "Incomplete material WorldGridMaterial, missing (FDebugViewModePS, 0)" | **Crash at startup**, 0 frames |

**The view-mode crash:**
- `EXCEPTION_ACCESS_VIOLATION reading address 0x0`.
- Stack: `ApplyViewModeOverrides < FMeshElementCollector::AddMesh < FSkeletalMeshSceneProxy::GetDynamicElementsSection < ...`
  on a render worker, at the first frame drawn in the view mode.

**The fallback crash:**
- A fatal assert: "Failed to find shader map for default material WorldGridMaterial ... Please make sure cooking was
  successful".
- Stack: `FMaterial::CacheShaders < UMaterial::CacheResourceShaders`.

**Reading:**
- Setting `r.ForceDebugViewModes` at run time turns the view modes on.
- But this package was cooked without the debug view-mode shaders, so the engine's debug materials have no shaders and the
  first draw crashes.
- For the view modes to work, the cook itself has to include them: `r.ForceDebugViewModes=1` in the project's
  `DefaultEngine.ini` before packaging. That's a Config change, which needs Bean's OK.
- So I couldn't check whether the sails lose their insignia and number in lighting-only.

`crashes.txt` lists every crash report from these runs. The same two ensures (groom PSO precache, and "precision loss
while converting matrix to GPU format") also fire in the P5 runs, which didn't crash, so they aren't the cause.

## (c) P5 with and without the hull clip

The P5 still was shot exactly as rehearsed (`p5-then-now.json`, the same args as rehearsal C try 5). Her state was the same
in both runs: heading 218.7, heel 9.5 to starboard, 5.52 kn, AWA 25.6.

| | Hull clip on (as is) | `-SailingNoHullClip` |
|---|---|---|
| Still | `P5-hullclip-4k.png`, `P5-hullclip-1080p.jpg` | `P5-nohullclip-4k.png`, `P5-nohullclip-1080p.jpg` |

`P5-hullclip-vs-nohullclip.jpg` has both, with a close crop of the bow and waterline underneath.

**`-SailingNoHullClip` reads better:**
- **Hull clip on:**
  - A flat, smeared sheet of water sits against the lee side with a straight edge.
  - A pale band of hull shows below it, which is the cut-off look flagged in the rehearsal.
- **Hull clip off:**
  - The water meets the topsides along a curving contact line that follows the hull toward the bow.
  - The band below the waterline is mostly gone.
  - The bow-wave curl is still there, since it's its own effect.
- **Waterline foam:** the thin foam line along the waterline is gone with the switch. From this angle and distance it was
  hardly visible with the clip on anyway, and the bow wave carries the white water.
- The water inside the hull didn't show up in this view, since the camera is outside and low.

Bean's Saved was held aside for every run and restored (7B5CA7BE). No crew is visible in either P5 still.
