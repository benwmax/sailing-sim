# PR #703 round 2 on BEN-PC: head 4d3e42c0

**Head 4d3e42c0** (branch `claude/project-thread-blitx3`, which contains main 6f44708f). Since round 1's c6a0e6ab:
- 6e403a9f: materials rebuilt on the Mac;
- eee00a77: keep main's UI art;
- 4d3e42c0: "break up the whitecap plates, keep torn-crest spray near the camera".

## Build, material and cook

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **`run-python.ps1 make_materials.py -Only build_water_v4`:** exit 0, no Python or material errors. Saved
  `Materials/M_WaterV4.uasset`; it was kept local and not committed. The copy is on the PC in
  `Artifacts\bench\p703r2\assets-local`, and the checkout is back to clean 6f44708f.
- **Package `Windows-4d3e42c0-703`:** 3 min. The cook compiled M_WaterV4, M_LensWater, M_LensDistortion, M_SkyDome,
  M_BoatSurface, M_BoatMast, M_BoatPacked, M_J22HeroSurface and M_J22HeroGlass for SM6 with **no shader or material
  errors**.
- **Warm-up:** once, with no shader errors in the game log.
- **Saved:** Bean's Saved was held aside and restored (F6458EAB).

## Stills (`stills/`, 4K Ultra, 10 s, the same args and cameras as round 1)

| still | package | HUD wind |
|---|---|---|
| storm-30kn | #703 r2 | 29 kn |
| storm-30kn-classicfoam | #703 r2 | (as round 1) |
| downpour-shore | #703 r2 | 29 kn |
| storm-28kn-b (`-SailingWind=35`, which the storm front overrides) | #703 r2 | (as round 1) |
| main-downpour-shore | main 6f44708f | 29 kn |
| main-storm-30kn | main 6f44708f | 29 kn |

### Caps

On #703 r2 the near caps are ragged:
- broken edges, holes through the old foam, and lace and strings trailing downwind;
- no smooth solid plates like round 1's.

Further out they read as broken patches. Main's caps at the same moment are rounder solid patches.

### Puffs

In `downpour-shore` the white puffs of mist over the crests are still there, as dense as on main.
`main-downpour-shore` (main, the same camera and moment) has the same puffs over its crests. **So what is left is main's
own crest spray, not #703's torn crests.**

Close to the camera (within about 25 m), #703 r2 adds short torn sheets near the boat and no mist of its own.

### Downpour and the far shore

In round 1 (c6a0e6ab) the far shore was gone in `downpour-shore`. In round 2 it shows faintly: a grey tree line and a
building, much dimmer than on main, where it is plain. It is the same weather time (200 s) and the same camera.

The round-1 still had 30 kn and heavier rain on the HUD at that moment; this one shows 29 kn. So the rain at the boat at
that instant may simply differ between runs. It is worth a check if "the far shore gone" in a downpour is meant to hold.
