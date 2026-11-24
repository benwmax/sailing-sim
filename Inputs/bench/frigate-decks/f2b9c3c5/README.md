# Frigate decks (#823) at f2b9c3c5 on the PC, Nov 24 2026

**Head:** `claude/project-thread-xkunbh` at **f2b9c3c5** ("Frigate lanterns: unshadowed on every tier"), which keeps
the 15 m gate and no fog scattering. Fresh worktree, removed afterwards. Nothing was pushed.

- **MSVC build:** Succeeded, 0 errors.
- **Tests:** ShipOutside 4/4, ShipWalk 8/8, Smoke 36/36.
- **Package:** Development `Packaged\Windows-pr823-f2b9c3c5` (kept); cook 0 errors, 1 warning.

## Ship decks lines

```
Ship decks Gun: 0 copies, 15 lanterns (unshadowed)
Ship decks Berth: 406 copies, 12 lanterns (unshadowed)
Ship decks Orlop: 0 copies, 2 lanterns (unshadowed)
```

## Perf (Ultra, 100%, 20 s)

| Run | fps | GPU ms | base | Lumen | game | render |
|---|---|---|---|---|---|---|
| berth 1080p | 65.1 | 10.49 | 4.31 | 1.13 | 11.19 | 15.32 |
| gun 1080p | 72.6 | 10.35 | 4.45 | 1.16 | 9.65 | 13.73 |
| berth 4K | **GPU hang** | | | | | |
| gun 4K | **GPU hang** | | | | | |
| gun 4K, `ShowFlag.PointLights 0` | 54.3 | 17.95 | **5.19** | | | |
| *control: 44733c87's package, gun 4K, run just after* | 45.7 | 21.43 | 8.61 | | | |

**The 4K hang is still there with every lantern unshadowed.**

- Both 4K runs hung with `DXGI_ERROR_DEVICE_HUNG` in the first frames.
- The breadcrumbs are the same as at 0ec5fcb5: ShadowDepths > `RenderVirtualShadowMaps(Nanite)` culling, then
  `RenderVirtualShadowMaps(Non-Nanite)` > Batched > CullingPasses active (`gundeck-4k-gpu-crash.txt`).
- With `ShowFlag.PointLights 0` this head's 4K gun deck runs (54.3 fps).
- Run straight after, **44733c87's package runs 4K normally** (45.7 fps). So the GPU and driver are fine, and the hang is
  specific to the lanterns as 1186594d and later set them up.
- It isn't the lanterns' shadows: they're all unshadowed now.
- It's something else about those lights: the 15 m gate, toggled visibility or properties, or how they're created.
  Even unshadowed, it upsets VSM's page culling at 4K on the first frames. 1080p doesn't hang.

**Gun deck base pass at 4K:** with the lanterns on it can't be measured (it hangs). With point lights off it's
**5.19 ms**, over 5.1 by a hair. Last night's 3946b08c, with no lanterns, was 5.14.

Bean's Saved was held aside and restored (7B5CA7BE).
