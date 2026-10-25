# The sky probe's readback without a GPU stall (Oct 25 2026)

## The hitch

The daily sweep on 44c174d6 showed p99 frame times of 34–36 ms on several High views (coast-day, slip, crew, stream-run),
against about 20–22 ms before. Average fps hadn't moved.

A frame trace of the packaged slip view showed the pattern: one 35–40 ms frame every 2.0 s on the render thread, with
game and GPU times normal and the next frame short. In views at about 52 fps or slower that is 1% of frames, so it sets
the p99. In faster views it sits just under it.

An Unreal Insights trace of the packaged build (`-trace=cpu,frame -statnamedevents`) named it:
`SkyProbePoll` > `MapStagingSurface_RenderThread` > `RHIMETHOD_SubmitAndBlockUntilGPUIdle_Flush`, 30 to 33 ms every
2 s.

## Cause

#320 (`docs/sky-lower-hemisphere`) reads M_SkyEnvProbe's 2x1 target back every two seconds with
`FRHIGPUTextureReadback`, polled until `IsReady()`. On Metal that readback can't avoid the stall:

- `FMetalDynamicRHI::RHIMapStagingSurface` calls `SubmitAndBlockUntilGPUIdle()` unconditionally.
- A read-only `FMetalSurface::Lock` does the same for private and managed textures.

Only `RHILockStagingBuffer` waits just on its fence, and only when the fence hasn't signalled. Delaying the lock wouldn't
have helped.

## Fix

The probe's two texels go through a buffer instead:

- **A new module, `SailingShaders`** (Runtime, PostConfigInit). It maps `/SailingShaders` to the project's `Shaders/`.
  It is in `SailingSim.uproject`, both targets and SailingSim's dependencies.
- **`Shaders/Private/SailingProbeCopy.usf`**, a one-group compute shader: the texture's first texels into a structured
  buffer.
- **`SailingCopyTexelsToReadback`**: an RDG pass that dispatches it and then `AddEnqueueCopyPass` into an
  `FRHIGPUBufferReadback`.
- **`UpdateLowerHemisphere`** locks the buffer's 32 bytes once `IsReady()`.

The shader cooks into the packaged game.

## Result (packaged, High, two runs)

| View | p99 before | p99 after | avg fps |
|---|---|---|---|
| slip | 35.4 / 34.8 ms | 20.4 / 20.4 ms | 51.6 |
| coast-day | 21.5 / 21.1 ms | 19.5 / 19.6 ms | 53.4 |

The water bounce still sets: the log `Water bounce: ...` lines carry the same values as main's.

## Seen on the way (#320's own, unchanged here)

After the first second the probe's sun texel reads 0 on main and with this change alike. Over a 40 s run the sky mean
also falls from 0.18 to 0.10, so the bounce leans on the sky term alone. This is worth a look in `M_SkyEnvProbe` (the
`SkyAtmosphereLightIlluminance` term drawn through a canvas).
