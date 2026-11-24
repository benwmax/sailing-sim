# Berth deck cost split, Windows-pr823-44733c87 (PC, Nov 24 2026)

**Setup:** the berth deck at 4K Ultra (3840x2160, 100%, 20 s, `-SailingWalkAt=Berth,-12,0,0`, Gulf launch 2), one warm-up
launch first. Each variant adds `-ExecCmds`; the log confirms each ShowFlag took effect ("ShowFlag.PointLights = 0" and
so on). The args are in `args.csv`.

| Run | fps | GPU ms | base | Lumen | post | other | MegaLights (two passes) | ShadowDepths | Deferred lighting | Fog light scattering |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | **42.0** | 23.31 | 10.35 | 2.35 | 2.42 | 1.55 | 1.93 + 4.84 | 2.65 | 6.12 | 0.87 |
| `ShowFlag.PointLights 0` | **54.3** | 17.91 | 5.04 | 2.39 | 2.46 | 1.61 | none | 2.72 | 0.97 | 1.52 |
| `ShowFlag.InstancedStaticMeshes 0` | **43.2** | 22.69 | 10.18 | 2.51 | 2.33 | 1.46 | 1.97 + 5.43 | 2.28 | 6.41 | 0.87 |
| both | **56.5** | 17.25 | 4.70 | 2.35 | 2.37 | 1.41 | none | 2.54 | 0.91 | 1.39 |

The MegaLights, ShadowDepths, deferred lighting and fog columns come from each run's ProfileGPU dump (the bench's GPU
slices), first frame shown.

## What costs what

- **The lanterns cost about 5.4 ms of GPU at 4K** (23.31 down to 17.91, base 10.35 down to 5.04), or 12.3 fps.
  - They're drawn through **MegaLights**, which Ultra turns on: a 1.9 ms pass and a 4.8 ms pass in deferred lighting,
    about 6.8 ms in all. With point lights off, both passes go and deferred lighting falls from 6.1 to 1.0 ms.
  - The fog's light scattering goes *up* (0.87 to 1.52 ms) with the lights off. It's a small offset.
- **The 406 instanced copies cost about 0.6 ms** (23.31 down to 22.69), or 1.2 fps. Shadow depths drop 0.37 ms without
  them. They're cheap.
- **Are the lanterns shadowed?** Not through shadow maps: ShadowDepths (VSM, about 2.3-2.7 ms, the sun's) is the same with
  point lights off. They are shadowed through MegaLights' own traces. The dump shows `ScreenSpaceRayTraceLightSamples`
  0.90 ms and `HardwareRayTraceLightSamples` 0.61 ms inside the MegaLights pass, plus `VolumeShadeLightSamples` 1.17 ms
  for the fog. So each lantern's shadow is a ray-traced sample, paid per pixel, which is why the cost grows with
  resolution.

## For the fix

The cost is the MegaLights shading of about 29 local lights over a 4K screen. Fewer lights in view (#823's new head
lights only those within 15 m), a smaller radius, or no shadows on the lanterns (MegaLights skips the trace for
unshadowed lights) all cut it directly. The instanced copies don't need work.

Bean's Saved was held aside and restored (7B5CA7BE).
