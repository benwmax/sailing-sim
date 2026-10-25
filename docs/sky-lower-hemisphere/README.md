# The water's bounce (sky light lower hemisphere)

Backlit-fill option 3, decided by the sim thread after the investigation (`docs/hull-water-bounce` findings, below):
the water's light reaches the hull's lighting through the sky light's lower hemisphere, grounded in the water's optics.

## Why it was missing

- The water is `UProceduralMeshComponent` rings with a Single Layer Water material. They have no mesh distance field
  and no Lumen cards, so they're outside software Lumen's scene and have no surface cache for hardware ray-traced hits.
- Lumen's screen traces run before SLW is drawn, so they can't see the water either. The deep bed is hidden
  (`HideBelow`).
- So a ray from the topsides going down misses, and returns the sky light's lower hemisphere: black by default
  (`bLowerHemisphereIsBlack`, never set).
- Measured with a stand-in (`-SailingWaterGIProxy=<albedo> -SailingWaterGIProxyVisible`, a visible 4 km plane 3 cm
  under the surface): at albedo 0.08 the lower topsides were about 6% brighter and the water itself unchanged. A hidden
  stand-in (`bAffectIndirectLightingWhileHidden`) doesn't reach Lumen here.

## What changed

`ASailingEnvironment::UpdateLowerHemisphere` (Medium, High and Ultra; Low keeps black):

- **The sky's mean radiance and the sun on the water.** Every two seconds `M_SkyEnvProbe` (`build_sky_env_probe`) draws
  two texels: the sky light's cube sampled straight up at full roughness (the cosine-weighted mean of the upper
  hemisphere, its irradiance over pi), and the sun's illuminance on the horizontal water
  (`SkyAtmosphereLightIlluminance x max(sun z, 0)`: the scene sun, already dimmed by the clouds, through the
  atmosphere). They're drawn into a 2x1 half-float target and copied back without a stall (`FRHIGPUTextureReadback`,
  polled on the render thread).
- **What the water sends up**, per channel:
  `[(0.066 + R_body) x sky mean + R_body x sun / pi] / (sky light intensity x colour)`.
  - 0.066 is water's reflectance of a diffuse sky (Fresnel, hemispherically averaged, n = 1.33).
  - `R_body` is the body's upwelling seen from above: a deep medium's diffuse reflectance from its single-scattering
    albedo, `0.55 (1 - sqrt(1 - a)) / (1 + sqrt(1 - a))`. The 0.55 is the light crossing the surface down and back up.
    The albedos mirror `WaterBodyFor` (WaterSurface.cpp). Lake (0.16, 0.18, 0.11) gives about (0.023, 0.027, 0.016).
  - The sun's specular reflection is left out: it leaves as the glint, not diffusely.
  - The probe includes the sky light's intensity and colour, and the lower hemisphere colour doesn't, so they're divided out.
- Set when it moves by 2%, so it follows dusk and storm decks by itself.
- `-SailingNoWaterBounce` keeps the old black. `-SailingSkyLowerHemisphere=<grey>` sets a fixed grey (measuring), and
  the automatic value then stands aside.

**The computed values** (lake, High, log `Water bounce: ...` at every set):

| Condition | Sky mean | Sun on the water | Lower hemisphere |
| --- | --- | --- | --- |
| AfternoonBreeze, 15:00 | (0.160, 0.161, 0.164) | (1.76, 1.52, 1.17) | (0.028, 0.028, 0.019) |
| Dusk, 19:36 | 0.0001 | 0 | 0.00016 |
| Night, 22:00 | 0.0001 | 0 | 0.00013 |
| Thunderstorm, 16:00, 10 min in | (0.158, 0.151, 0.144) | (1.27, 1.04, 0.75) | (0.026, 0.025, 0.017) |

About a third of the day's value is the sky (its Fresnel reflection and the body's upwelling of it), two thirds the
body's upwelling of the sun. (The first readback at start-up comes before the sky light's capture has converged and is
tiny; the next one, two seconds later, is the real value.)

## Effect (Ultra, linear luminance, mean of three runs per state, `-SailingCloudShade=0.15`)

| View | Before (`-SailingNoWaterBounce`) | After | Change |
| --- | --- | --- | --- |
| Side, lower topsides | 0.3107 (sd 0.0002) | 0.3316 (sd 0.0003) | **+6.7%** |
| Backlit chase topsides | 0.0335 (sd 0.0016) | 0.0371 (sd 0.0005) | **+10.8%** |
| The albedo-0.08 stand-in, side lower topsides (one run) | 0.2990 | 0.3184 | +6.5% |
| Crew underside view, hull lower (sky term only, one run) | 0.2210 | 0.2210 | none |
| Boom underside (sky term only, one run) | 0.2352 | 0.2350 | none |

The side view lands on the albedo-0.08 stand-in. With the sky term alone it was +3.3% (the sun's share of the body's
upwelling is the other half). Where Lumen's rays find the lake bed or the hull itself first (the close underside
views), the lower hemisphere isn't reached and nothing changes.

The sheets below are from the sky-term-only build (before above, after below); the sun term adds to them.
| Side | Chase | Crew underside | Boom from below |
| --- | --- | --- | --- |
| ![side](side.jpg) | ![chase](chase.jpg) | ![crew](crewunder.jpg) | ![boom](boomunder.jpg) |

(Before above, after below.)

## Cost

Helm eye, two 20 s runs each on the 4090, GPU ms before -> after: Medium 4.21 -> 4.00, High 5.56 -> 5.61, Ultra 7.96 ->
8.11. Within noise. The probe is one 1x1 draw and a 4-byte-per-channel copy every two seconds.

## Checks

Full suite 235/235 on the PC on main 81771c73 plus this branch (MSVC clean).
