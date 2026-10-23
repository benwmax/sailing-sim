# Water and the sky it reflects (draft, Oct 23 2026)

Realism audit Oct 23, items 1 and 5: the far water reads pale and olive, where the photos read blue. This is a
diagnosis, not a change. The draft lift (below) is the wrong lever and stays unmerged.

## Measuring

`-SailingWaterAlbedo=<r,g,b>` and `-SailingWaterExtinction=<r,g,b>` (1/m) replace the water body; albedo 0 with
extinction 100 leaves only the surface. `-SailingWaterRough=<r>` and `-SailingWaterSpec=<s>` force M_WaterV4's
roughness and Specular. `-SailingSkyLightScale=<x>` scales the sky light; `-SailingSkyCubeRes=<n>` sets its cubemap size.
Console settings that the tier's scalability can reset are run with `-SailingExecAt=1:<cvar>+<value>`.

The view is the bridge (G5 `g5-bridge`) on High: cloudless (ClearMistral), wind 0.5 m/s (glassy), 13:00. For each
angle below the horizon, the water is compared with the sky at the same angle above it.

## Findings

1. **The reflection itself is right.**
   - With the body removed, the glassy mirror is the sky at the mirror elevation times flat Fresnel, within about 10%,
     once a near-water term is taken off (it doesn't change with Specular or the sky light). Water over sky times
     Fresnel: 0.134 against 0.148 at 8°, 0.082 against 0.078 at 12°, 0.016 against 0.014 at 25°.
   - The reflected sky on the water is the sky light's real-time capture. At 1% sky light the far water goes black, and
     `r.Water.SingleLayer.Reflection 0` blacks it all.
   - Lumen reflections, `r.ReflectionMethod`, the reflection environment, screen traces, fog and the cubemap's size
     change nothing on the open water.
2. **The draft lift is the wrong lever.** Lifting each pixel's mirror direction by Cox-Munk's mean reflected elevation
   made the far water darker (water over sky 0.2, against the photos' 0.37–0.50) without making it bluer.
   - The engine's rough-surface lookup already leans toward the normal.
   - Steeper facets have lower Fresnel.
   - A rippled surface reads a blurred mip of the capture.
3. **The far water takes its colour from the low sky.** On the bridge view at 10 kn:

   | | Water red/blue | Water green/blue | Sky red/blue, 3–8° | Sky green/blue, 3–8° |
   | --- | --- | --- | --- | --- |
   | Ours | 0.86 | 1.04 | 0.78–0.86 | 0.95–1.01 |
   | Photo | 0.55 | 0.78 | 0.59–0.75 | 0.74–0.86 |

   Our near-horizon sky is paler and greener than the photo's, and the rippled water averages that band. So the next
   lever is the low sky's colour (the haze's inscattering and the atmosphere near the horizon), not the water.
4. **Side issues seen on calm water.**
   - The whitecap debug view (`-SailingDebugFoam=1`) still flags a sparse sprinkle of single pixels at 0.5 m/s, where
     there should be none.
   - The near water carries blocky 2×2 white specks: small reflected highlights. `r.Water.SingleLayer.Reflection.
     DownsampleCheckerboard 0` doesn't remove them.

`mirror.jpg`: left, the glassy clear mirror; right, the same with Specular 0. The far water goes black; the near sheet
and the specks remain.
