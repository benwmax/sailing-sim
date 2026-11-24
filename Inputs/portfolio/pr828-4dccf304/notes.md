# Draft PR #828 at 4dccf304 (guarded film view modes) on the PC, Nov 24 2026

**Head:** `claude/project-thread-q73bv9` at **4dccf304** ("Film mode: never force debug view modes; lighting only falls
back to its show flag"). I built it in a fresh worktree and removed the worktree afterwards. I only unlinked the crew link;
all 541 crew files are still there. Nothing was pushed to the PR.

- **MSVC build:** Succeeded, 0 errors.
- **`SailingSim.Smoke.FilmMode.*`:** 4 of 4 passed.
- **Package:** Development `Packaged\Windows-pr828-4dccf304`; the cook had 0 errors and 1 warning.

## P1 with `-SailingViewMode`

Shot `p1-layer-peel-orbit.json`, the rehearsal's common args, `-SailingRecord=2`. **Neither run crashed**, and both
recorded 120 of 120 frames.

**`-SailingViewMode=lightingonly`:**
- Log: "Film view mode: lighting only (ShowFlag.LightingOnlyOverride: this package has no debug view modes)".
- **The sail number and insignia are gone.** "1288" on the main and the jib's window marks don't show in any frame;
  compare `P1-final-vs-lightingonly-f060.jpg`, rehearsal final on the left.
- The sails are plain cloth: seams, batten pockets and telltales stay, since they're geometry and shading, not the marks
  texture.
- **The sails aren't a neutral grey.** They take the warm late-sun light (the override drops the materials' colour, not the
  light's), so they read cream or tan.
- The hull and deck go a flat light grey, and the water goes very dark.
- **The sky and clouds stay fully rendered**, as in the rehearsal's show-flag test.
- Mean luminance difference from the final pass: 21.5 of 255.
- Previews: `P1-lightingonly-f060-1080p.jpg` and `P1-lightingonly-sails-crop.jpg`.

**`-SailingViewMode=wireframe`:**
- Exactly one warning line: "Film view mode: wireframe needs a package cooked with debug view modes
  (r.ForceDebugViewModes=1 in the config when cooking); this one has none, so the frames stay lit".
- The frames are lit and match the final pass (0.66 of 255 mean difference, which is noise).
- Preview: `P1-wireframe-f060-1080p.jpg`.

There were no crashes and no missing-shader errors.

## Q3: can `r.ForceDebugViewModes=1` apply to Development cooks only? (read-only; nothing changed, no cook run)

### What the engine does (UE 5.8 source)

- **The cvar is read-only** (`ShaderCore.cpp:570`, `ECVF_ReadOnly`), so it has to be set at startup: from an ini, an
  `-ini:` override, or `-DPCVars=`.
- **The cooker decides about debug view-mode shaders per shader platform.** It does this through
  `FShaderPlatformCachedIniValue<int32>("r.ForceDebugViewModes")` in `ForceEnableDebugViewSupport`
  (`DebugViewModeHelpers.cpp:87`).
  - When the target platform is the one the cooker runs on, which it is for Windows cooked on Windows,
    `ShaderPlatformCachedIniValue.h` (lines 113-138) reads the **live console variable of the cooker process**.
  - So a value given on the cooker's own command line counts, not only one in a Config file.
- **One cook serves both configurations.** The cooked content is the same for Development and Shipping:
  `-clientconfig` picks the exe, not the cook. Config has no per-build-configuration layer for cooking.
  - So putting the value in `Config/DefaultEngine.ini` or `Config/Windows/WindowsEngine.ini` adds the debug shaders to
    **every** Windows cook, Shipping included.
  - Shipping can't use them (view modes are compiled out of Shipping), so it would carry dead shaders and a bigger
    cook.
  - `Config/Custom/<Name>/` with UAT `-CustomConfig=` would separate them, but it needs both a Config file and a script
    argument.

### Cleanest way: a cook argument in `scripts\windows\package-win.ps1`, Development only

```
-AdditionalCookerOptions="-DPCVars=r.ForceDebugViewModes=1"
```

- **Where it goes:** appended to the BuildCookRun line only when `-Config Development`. `AdditionalCookerOptions` is a
  documented BuildCookRun parameter (`AutomationUtils\ProjectParams.cs:26`), passed straight to the cooker.
- **Shipping:** its cooks stay exactly as now. No Config file changes.
- **Approval:** it's a script change, so it fails the "Sensitive files" check until Bean adds his label. The Config route
  would need his label too, and would also touch Shipping.

### Caveats to check with one test cook (not run, per the brief)

1. **Incremental cooks.** The cook is incremental (Zen), so after a Development cook with the flag, a Shipping cook
   could reuse shader maps that include the debug shaders, and the other way round.
   - Safest: a full cook (`-Full`) whenever the flag changes between the two.
   - Or check that the shader map key includes the setting.
2. **The game needs the cvar at startup too.** The engine loads its debug materials (wireframe and so on) only if
   `AllowDebugViewmodes()` is true at init.
   - That's the crash 89ec83ed hit when it set the cvar late, at a null material in `ApplyViewModeOverrides`.
   - So film runs would add `-DPCVars=r.ForceDebugViewModes=1` to the game's own command line. That's a launch argument,
     not a file change.
3. **The debug materials might not get cooked.** The engine's own comment (`ShaderCore.cpp:583-584`) says
   `EngineDebugMaterials` must be in the startup packages on cooked platforms.
   - If the cook doesn't pull them in by itself, `/Engine/EngineDebugMaterials` would need adding to the packaging
     settings' always-cook list. That one *is* a Config change (`DefaultGame.ini`).
   - A test cook with the argument above would show whether it's needed.

Bean's Saved was held aside for both runs and restored (7B5CA7BE). No crew is visible.
