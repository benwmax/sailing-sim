# Gelcoat and rig lines: the Mac's helm-eye cost

After #311 (`docs/gelcoat-cost/`), helm eye on the Mac's High was still about 0.5 ms over in Lumen (3.58 against
3.10 ms). Then #312 (`docs/rig-lines/`) added 0.48 ms to its base pass (8.85 to 9.33). Two follow-ups, one PR.

## 1. Lumen: what actually runs, and why it traced more

**Hit shaders don't run our material.** High runs Lumen with hardware ray tracing in the default
`r.Lumen.HardwareRayTracing.LightingMode` 0 (surface cache). In that mode every hit is shaded by the engine's global
`FLumenHardwareRayTracingMaterialHitGroup` (`LumenHardwareRayTracingMaterials.cpp/.usf`), which reads the surface cache
and never evaluates a material. So no grime, curvature, slab or texture fetch from the gelcoat reaches a Lumen hit.
Modes 1 and 2 (hit lighting) would evaluate it, but this project doesn't use them. The `RAYHITGROUPSHADER` guards still
matter for any material-evaluating ray tracing, and `LUMEN_CARD_CAPTURE` (#311) covers the surface-cache capture.

**The extra Lumen time is traced reflections.** `LumenMaterial.ush` (`InternalReadMaterialData_Substrate_Regular`)
traces a reflection ray for any pixel whose roughness is under `r.Lumen.Reflections.MaxRoughnessToTrace` (0.4, the
default here). It also traces any Substrate pixel with a haze weight above zero: such a pixel gets
`TopLayerRoughness = min(roughness, haze roughness, 0.4)`. Before #309 the lee guard roughened the gelcoat past 0.4 by
about 15 deg under the horizon (it ran from the horizon to 18 deg). #309 moved its start to 15 deg, so from 15 to
about 25 deg under the horizon the gelcoat stayed glossy and traced. From the helm that band is the cockpit walls and
the cabin sides: a good share of the frame.

**Fix.** The guard runs from 5 to 14 deg under the horizon again (`saturate((-r.z - 0.08) * 6)`). Roughness passes 0.4
by about 12 deg, and the coat (haze) weight in `M_BoatSurface` is gone by then too (`saturate(1 - 1.25 * guard)`). The
hero re-applies the guard after folding its coat into the roughness, so the fold can't pull the band back under 0.4.
The water's olive in the albedo keeps #309's later start (`seeW`), so the hull's lower band doesn't darken. The band
from the horizon to 5 deg, where the shore sits, stays traced.

Lumen slice (`gpu.lumen_ms`), High with `-SailingLumenHW=1` on Bean's RTX 4090, mean of five 20 s runs at 1920x1080:

| View | Main (#311) | This branch | Before #309 (docs/gelcoat-cost) |
| --- | --- | --- | --- |
| Helm eye | 0.724 (0.71 0.74 0.73 0.71 0.73) | 0.710 (0.68 0.72 0.73 0.71 0.71) | 0.69 |
| beam8 | 0.576 | 0.576 | 0.57 |
| Chase | 0.626 | 0.614 | |

The 4090 sees only 0.03 ms of the Mac's 0.48 at helm eye, and gets back about half of it. The Mac's gate is the
measure. The look is unchanged; the chase hull is a shade flatter low down (`Artifacts/gelrt` stills, main against this branch).

## 2. Rig lines: WPO moved back to the CPU

#312 widened each rig line to 1.2 px in `M_RigRope`/`M_RigWire` by world position offset. A WPO material costs more than
its few vertex instructions. It needs its own depth-only and shadow-depth permutations (not the fast position-only path).
It forces velocity output for the moving lines, and keeps virtual shadow maps treating them as animated. Where the rig
fills the frame (helm eye) that showed in the Mac's base pass.

The widening is now on the CPU again, but **per ring**, not per line as in boat fidelity 4. `RingRadius()` gives each
of a line's 17 rings at least 1.2 px across at its own distance from the camera (1.25x steps). So the far end of a shroud
still never falls between pixel centres, and the near end isn't fat. The materials have no WPO. The section's change
key includes each line's total of steps, so a moving camera re-uploads a line only when one of its rings steps. The
braid keeps its true scale (UVs from the true radius). `-SailingNoMinLineWidth` turns it off.

Helm eye, five 20 s runs each at 1920x1080 on the 4090 (base pass `gpu.base_ms`, GPU `gpu.total_ms`, game thread `game_ms`):

| Tier | Base, WPO (#312) | Base, per-ring CPU | GPU, WPO | GPU, CPU | Game thread, WPO | Game thread, CPU |
| --- | --- | --- | --- | --- | --- | --- |
| High | 2.764 | 2.756 | 5.82 | 5.64 | 14.00 | 13.48 |
| Ultra | 3.632 | 3.472 | 8.17 | 7.83 | 14.99 | 14.42 |

The backstay in the 55 m wide shot stays unbroken to the masthead (`flicker.py`, `docs/rig-lines/`):

| Tier | Flicker, boat fidelity 4 | #312 (WPO) | This branch |
| --- | --- | --- | --- |
| Ultra | 0.275 | 0.162 | 0.183 |
| High | 0.241 | 0.149 | 0.208 |

A little more than #312: the 1.25x steps draw a ring between 1.2 and 1.5 px, a touch heavier, where the WPO was exactly
1.2 px. It's still well under where boat fidelity 4 was.

## Checks

Full suite 234/234 on the PC on main e90baeb4 plus this branch (MSVC clean). `SailingSim.Visual.RigClearance` records the lines before any widening, so it is unaffected.
