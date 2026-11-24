# Dev-only debug view modes: test cook on the PC, Nov 24 2026

**Verdict: PASS for the cook route.**
- Wireframe draws in the P1 shot.
- Lighting-only uses the engine's real view mode.
- Nothing crashed.
- The Shipping cook command is unchanged and its cook carries no debug view-mode shaders.

There is one visual gap: **the sails aren't drawn in wireframe** (below).

## Setup

- **Worktree:** a fresh one at #828's head 4dccf304 (`D:\dev\ss-fix-wt\dvm`).
- **The edit:** `scripts/windows/package-win.ps1`, edited **locally**, never pushed. `package-win.diff` here is its exact
  `git diff`.
  - Development only: it appends `-AdditionalCookerOptions="-DPCVars=r.ForceDebugViewModes=1"` to BuildCookRun.
  - The edit was reverted afterwards with `git checkout -- scripts/windows/package-win.ps1`.
- **Development cook:** `-Full`, into `Packaged\Windows-dvm-4dccf304`. 10 min, 0 errors, 2 warnings.
  - The cooker ran with `-DPCVars=r.ForceDebugViewModes=1` (`cook-cmd-dev.txt`).
- **Shipping cook:** then an **incremental** Shipping cook in the same worktree, into `Packaged\Shipping-dvm-4dccf304`.
  3 min, 0 errors.
  - Its cooker command line has no such argument (`cook-cmd-ship.txt`).
- **The game's launch line:** no script launches film runs; my own run script does. So I passed
  `-DPCVars=r.ForceDebugViewModes=1` by hand.

## P1 runs

Shot `p1-layer-peel-orbit.json`, the rehearsal's common args, `-SailingRecord=2`. Every run recorded 120 of 120 frames.
`P1-runs-sheet.jpg` shows frames 0, 60 and 119 of each run.

| Run | Log | Frames |
|---|---|---|
| wireframe + launch `-DPCVars=r.ForceDebugViewModes=1` | "Film view mode: wireframe (the engine's view mode)" | **True wireframe**: hull, deck gear, mast, boom, rig lines, water mesh and the far shore in magenta and cyan wire on black. **No sails**, and the sky and clouds are black (`P1-wireframe-f060-4k.png`, `-1080p.jpg`) |
| lightingonly + launch arg | "Film view mode: lighting only (the engine's view mode)" | Engine lighting-only: no sail number or insignia, grey hull, dark water. The sky and clouds stay rendered (`P1-lightingonly-f060-4k.png`, `-1080p.jpg`) |
| wireframe **without** the launch arg | "Film view mode: wireframe needs a package cooked with debug view modes ...; ... the frames stay lit" | Lit, the same as final (`P1-wireframe-nolaunchcvar-f060-1080p.jpg`) |

**Sails in wireframe:**
- Neither the main nor the jib draws. Their rig lines, battens and telltale ticks do (the short marks up the leech).
- The sails are the runtime cloth mesh, which the wireframe pass apparently doesn't draw.
- The sky and clouds aren't meshes either, so they go black.
- If P1 needs the sails as wire, that's a game-side follow-up.

## The three caveats

**(a) Debug materials and shaders cooked.** Yes.
- The Development cook log compiles `/Engine/EngineDebugMaterials/*` ("Missing cached shadermap for
  /Engine/EngineDebugMaterials/LevelColorationLitMaterial ... compiling", and so on: 17 lines).
- It also compiles `FDebugViewModePS` (364 compiles).
- There was no startup assert and no missing-shader error in any run.
- The crash folders hold only the two ensures every run on this PC has (groom PSO precache, matrix precision); there was
  no crash.
- No change to `DefaultGame.ini` was needed.

**(b) Is the launch-line argument needed?** Yes.
- Without `-DPCVars=r.ForceDebugViewModes=1` on the game's command line, #828 guards correctly: one warning, lit frames.
- No script launches film runs, so the argument belongs in the film-run instructions (`docs/film-mode/README.md`, "A
  run"), not in a script.

**(c) Incremental Shipping cook stays clean.** Yes, as far as these signs show:
- Its cooker command line has no `-DPCVars`.
- The cook log has 0 lines naming `DebugViewMode` or `EngineDebugMaterials`.
- The project shader archive `ShaderArchive-SailingSim-PCD3D_SM6` went from **51.0 MB** (the flagged Development cook) to
  **47.6 MB** (the Shipping cook). So the incremental cook dropped the debug shaders rather than reusing them.
- For reference, main's normal Development cook on Nov 16 had 41.8 MB, with older content. The global archive is
  221.1 MB in all three.

Bean's Saved was held aside for every run and restored (7B5CA7BE). No crew is visible.
