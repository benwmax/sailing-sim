# The storm view's cost

The storm view (Ray Hubbard, Thunderstorm, 16:00, the front 200 s in, camera astern looking at the shelf) is the
gates' tightest view: on main 45.8-46.1 fps on High against a floor of 45, and 67 on Medium against 60. This looked for
about 3 fps on High without changing how the storm looks.

## Where the frame goes (High, one profiled frame)

| Pass | ms |
|---|---|
| VolumetricCloud (`CloudView`, 360x270 traced) | 3.55 |
| SingleLayerWater | 3.13 |
| VolumetricFog::ConservativeDepth (`GenerateConservativeDepthBuffer`) | 1.19 |
| PostProcessing | 0.89 |
| Lights | 0.50 |
| Translucency (rain curtains, spray, foam sprites) | 0.47 |

The gate's slices for the same view: base about 6.8 ms, clouds_fog 5.5 ms. The clouds were cut twice already: shadow
rays to 3 km (#222) and fewer samples under a dark deck (#344); see `docs/storm-headroom/` and `docs/storm-high/`.

## Candidates (packaged, the storm view, two rounds each, fps)

| Candidate | High | Medium |
|---|---|---|
| main | 45.8 / 46.1 | 67.0 / 66.9 |
| fog conservative depth off (`-dpcvars=r.VolumetricFog.ConservativeDepth=0`) | 46.6 / 46.9 | 67.1 / 67.2 |
| no rain curtains (`-SailingNoRainCurtains`) | 47.3 / 47.3 | 67.8 / 67.8 |
| fog grid 16 px | 46.3 / 46.2 | 66.9 / 67.1 |
| no lightning (`-SailingNoLightning`) | 46.4 / 45.5 | 67.0 / 66.9 |

The fog grid row is probably noise: `QualityCVars` sets `r.VolumetricFog.GridPixelSize` and overrides the command line.
There is no single 3 fps cut in this view: the clouds and the water are the frame, and both have been cut before.

## What changed

**The fog's conservative depth pass is off on Medium and High** (`QualityCVars`, `VisualPipeline.cpp`); Low and Ultra
keep the engine's default. The pass builds a coarse depth buffer so the fog can skip froxels behind the scene; in this
view the water and the sky fill the frame, there is almost nothing in front to cull against, and the pass cost 1.2 ms
on High for nothing on screen. +0.8 fps on High; Medium is within noise.

## The rain curtains

See the section below (measured on this branch with `-SailingRainCurtains=<n>`, the cap on the number of veils).
