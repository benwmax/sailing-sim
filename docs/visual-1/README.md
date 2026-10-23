# Visual V1: rendering pipeline

The first step of the Visual Realism Plan: the lighting, shadows, materials, anti-aliasing and camera every later
visual phase is judged under. All of it sits behind the quality tiers. Low keeps the Phase 8 renderer and cost.

## What changed, per tier

| | Low | Medium (default) | High |
| --- | --- | --- | --- |
| Engine scalability | 1 (no Lumen) | 2 | 3, with Lumen at the High GI level |
| Global illumination and reflections | screen space | Lumen, software ray tracing | Lumen, hardware ray tracing (Metal, M5 Pro) |
| Shadows | cascaded shadow maps | virtual shadow maps | virtual shadow maps |
| Anti-aliasing, resolution | as Phase 8 (TSR) | TAA, 67% upscaled to native | TAA at native |
| Exposure and look | as Phase 8 | physical camera, V1 look | physical camera, V1 look |
| Cloud view samples | 48 | 72 | 80 |

Project-wide (`Config/DefaultEngine.ini`):
- Substrate materials. The generators in `scripts/make_materials.py` are unchanged and M_Water's 48-wave sum still matches `FWaveField::Height`.
- Ray tracing is compiled in on demand (`r.RayTracing`, `r.RayTracing.EnableOnDemand`, `r.SkinCache.CompileShaders`; without the last, the packaged game dies at startup) and enabled at runtime on High only.
- Virtual shadow maps.
- Nanite enabled. The scene has no static meshes yet (every hull, sail, chunk and dock is procedural), so Nanite starts paying with the V2 hull.

The tier table is `QualityCVars` in `Source/SailingSim/Private/VisualPipeline.cpp`, tested by
`SailingSim.Visual.TierSettings`.

### Anti-aliasing and Lumen, measured (`aa-and-lumen.csv`)

**MetalFX is not in this engine build.** There is no plugin, RHI code or config for it in UE 5.8.3 as installed, so
the plan's MetalFX upscaling is replaced by the engine's TAA upsampling. The measurements below are on the packaged
build at 1440×1080.

| Case | beam8 fps | beat15 fps | GPU ms |
| --- | --- | --- | --- |
| Medium, TAA at 67% (chosen) | 83 | 86 | 10.9-11.5 |
| Medium, TSR at 67% | 76 | 78 | 12.6-12.7 |
| Medium, TSR at 87% (about Phase 8) | 71 | 62 | 13.9-15.3 |
| Medium, TAA at native | 66 | 70 | 14.1-14.9 |
| Medium, SMAA at native | 66 | 70 | 13.9-14.7 |
| High, TAA, Lumen hardware RT, Epic GI | 42 | 43 | 20.7-21.6 |
| High, SMAA, hardware RT, Epic GI | 42 | 43 | 21.2-22.3 |
| High, TSR, hardware RT, Epic GI | 38 | 38 | 23.4-24.5 |
| High, TAA, Lumen software RT, Epic GI | 45 | 45 | 20.9-21.5 |
| High, TAA, hardware RT, **High GI (chosen)** | 49 | 50 | 17.9-19.5 |

- TSR is the costliest option on this GPU, as the plan expected, and stays off.
- SMAA costs the same as TAA here but leaves Lumen's and the water's shimmer untreated, so both tiers use TAA.
- On High, hardware ray tracing costs about 2.5 fps more than software ray tracing at the same GI level. It keeps the more accurate reflections of the sail and hull in the water.
- Lumen's Epic final gather alone costs 5.5 ms at native, so High uses the High GI level.

## The physical camera

On Medium and High, exposure follows the light the way a hand-held incident meter does, not the frame:
- **Illuminance at the boat.** It comes from the sun's elevation (clear-sky direct and diffuse light), the cloud state, twilight and the moon.
- **Metered exposure.** EV100 = log2(E / 2.5): 15.5 in full sun, 12-13 under overcast, 7-8 at sunset, about -3 under a full moon. `SailingSim.Visual.MeteredExposure` checks these values.
- **Gloom.** The camera opens only a tenth of the way into gloom, so a storm stays as dark as Phase 8 made it.
- **Night.** The night floor is unchanged.
- **Framing.** The auto-exposure histogram may still move ±1 EV for framing in clear air, narrowing to ±0.3 under a storm deck.
- **Calibration.** The scene's lights are not in real lux (the sun is 10), so `kSceneEVOffset` (14.1) and a half-stop lift in clear air tie the metered EV to the Phase 8 look. The calibration is measured on the 12 reference captures: the clear-day scenes match within 0.1 stop. (Oct 23 2026: the half-stop lift is gone. It put a clear sky half a stop over a still camera's and washed its colour; Bean chose the truer exposure, `docs/exposure-choice/`.)
- **Capture mode.** The exposure lock is unchanged (`-SailingEV` or frozen at 2.5 s).

The look (`ASailingEnvironment::ApplyCameraLook`):
- the engine's filmic tone curve with a slight warm white balance (6900 K, neutral under a storm);
- local exposure, so a white sail against a bright sky keeps its detail;
- bloom 0.35, lens flare 0.15, vignette 0.25;
- per-object motion blur at a 90° shutter;
- no chromatic aberration or grain;
- depth of field only in photo mode (unchanged).

## GPU time per slice

Every `bench.json` now carries a `gpu` object. Three `ProfileGPU` frames are taken after the measured window, so they
do not count in the fps, and their pass trees are summed into the plan's budget slices (`Source/SailingSim/Public/GpuSlices.h`,
tested by `SailingSim.Visual.GpuSlices`). All bench-phase CSVs carry the slice columns. `scripts/bench-visual.sh` runs the
eight views below on each tier.

**Medium**, packaged build, 1440×1080 (`bench-after.csv`, `bench-before.csv`):

| View | fps before | fps after | GPU ms | base | Lumen | clouds and fog | post |
| --- | --- | --- | --- | --- | --- | --- | --- |
| beam8 | 78.0 | 85.2 | 11.4 | 4.4 | 2.0 | 3.9 | 0.8 |
| beat15 | 68.2 | 88.2 | 9.7 | 3.9 | 2.2 | 2.4 | 0.8 |
| storm | 104.8 | 119.0 | 7.5 | 3.1 | 2.2 | 0.6 | 0.8 |
| marina | 77.6 | 91.8 | 11.8 | 5.2 | 2.0 | 3.6 | 0.7 |
| coast-day | 76.5 | 79.7 | 11.4 | 3.8 | 2.1 | 3.8 | 0.7 |
| coast-night | 65.7 | 100.3 | 9.3 | 2.6 | 1.9 | 3.6 | 0.7 |
| gulf-sea | 89.4 | 104.2 | 8.8 | 2.8 | 2.1 | 2.8 | 0.8 |
| helm-eye | 81.5 | 94.4 | 10.8 | 4.2 | 1.9 | 3.8 | 0.5 |

**High:**

| View | fps before | fps after | GPU ms | base | Lumen | clouds and fog | post |
| --- | --- | --- | --- | --- | --- | --- | --- |
| beam8 | 45.2 | 48.2 | 19.4 | 9.0 | 4.0 | 5.3 | 0.8 |
| beat15 | 45.7 | 49.3 | 16.1 | 6.9 | 4.9 | 3.2 | 0.8 |
| storm | 67.6 | 74.1 | 12.7 | 6.4 | 4.3 | 0.8 | 0.9 |
| marina | 53.3 | 58.0 | 17.9 | 9.1 | 4.1 | 3.6 | 0.8 |
| coast-day | 46.9 | 50.6 | 19.6 | 9.2 | 4.6 | 4.5 | 1.0 |
| coast-night | 48.4 | 60.2 | 15.4 | 5.2 | 4.1 | 5.0 | 0.8 |
| gulf-sea | 59.1 | 62.7 | 15.0 | 5.8 | 4.3 | 3.8 | 0.9 |
| helm-eye | 52.0 | 54.3 | 17.5 | 7.9 | 3.9 | 4.8 | 0.7 |

Low is unchanged at about 119 fps (the frame cap), 5.6-8.4 ms of GPU.

**Against the plan's Medium budget** (16.7 ms: base 4.0, Lumen 4.5, water 2.5, clouds and fog 2.5, Niagara and cloth 1.2,
post 1.5):
- Every view is under the total by 5 ms or more.
- Lumen (about 2 ms) and post (under 1 ms) have room.
- Base (2.6-5.2 ms; it includes the water, which draws in the base pass until V4) runs up to 1.2 ms over its 4.0 budget in the marina and the lake chase views. The cause is the virtual shadow maps: they cost about 2 ms on Medium and 4 ms on High because nothing in the scene is Nanite yet. The V2 hull and the V6 marina are where that comes back.
- Clouds and fog (2.4-3.9 ms) run over their 2.5 budget in the clear-sky views. This was already true in Phase 8; V5 reworks the clouds.

## Regression (`regression.csv`)

Every earlier phase's bench views were rerun on this build (bench-phase2..8):
- Medium is at or above 75 fps everywhere. The lowest views are the Galveston dusk (75.1) and the logbook (75.5); Phase 8 had 63-68 at its lowest.
- High is at or above 48 fps everywhere it is measured (Phase 2 and 3 views).

## Tests

74 automation tests, all passing, including four new ones under `SailingSim.Visual.*`:
- tier settings;
- metered exposure;
- GPU slices;
- a pipeline smoke test (Substrate, ray tracing, Lumen). It skips itself under `-nullrhi`.

## Comparison (`compare/index.html`)

The 12 Phase 8 reference scenes were recaptured with the capture mode (`captures/`), next to the reference clip and the
Phase 8 frame. Open the page locally.

The lighting is re-scored as a new category, "light" (exposure, shadows, bounce light), so its "before" scores are
assigned now rather than taken from Phase 8:
- **Clear-day scenes: 3 → 2.**
  - The rig and crew throw crisp contact shadows (virtual shadow maps).
  - Sails take soft bounce light from the sky and water.
  - Sky highlights keep their detail (local exposure).
  - Exposure no longer jumps when a sail fills the frame.
- **Storm scenes: 3, unchanged.** The scene is as dark as Phase 8 made it, but there is no shelf-cloud structure until V5.

Water, sky, sails and boat keep their Phase 8 scores. The geometry (box decks, cylinder crew, flat sails) is still what
gives a frame away, and that is V2 and V3.

## Not done in V1, and why

- **MetalFX:** not available in this engine build (see above). TAA upsampling is in its place.
- **Nanite on the hull, docks and terrain:** those are procedural meshes today. Nanite is enabled, and V2's Blender hull is the first Nanite mesh.
- **Lens flare from a lens profile:** Unreal's image-based flare is used at a modest intensity. There is no profile import.
