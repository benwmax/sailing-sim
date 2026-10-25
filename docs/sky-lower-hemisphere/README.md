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

**The sun reaching the water is the direct light after the clouds.** The probe's sun is the light through the atmosphere,
but the clouds take the direct sun off the scene by the light's diffuse scale (`UpdateSun`: its intensity keeps a 0.35
floor for the storm sky's sake). So the sun term is multiplied by `DiffuseScale`. The first version left that out and
overstated the sun under any cloud: under a storm deck the lower hemisphere hardly fell.

**The computed values** (lake, High; log `Water bounce: ...` at every set). "Effective" is the lower hemisphere times the
sky light's intensity, which is what lights the topsides: the sky light's intensity falls under a deck (`UpdateSun`),
and the stored colour is in its units.

| Condition | Sky mean | Sun on the water x direct | Effective lower hemisphere | vs full sun |
| --- | --- | --- | --- | --- |
| AfternoonBreeze 15:00, full sun (`-SailingCloudShade=1`) | (0.312, 0.337, 0.379) | (5.02, 4.35, 3.36) x 1.00 | **(0.066, 0.069, 0.048)** | |
| Same, under a cumulus shadow (`-SailingCloudShade=0.15`) | (0.161, 0.163, 0.164) | (1.76, 1.52, 1.17) x 0.43 | (0.020, 0.021, 0.016) | -1.7 stops |
| Thunderstorm 16:00, front arriving (`-SailingStormDelay=-140`, darkness 0.10) | (0.087, 0.088, 0.094) | x 0.36 | (0.011, 0.012, 0.009) | -2.5 stops |
| Thunderstorm, **under the shelf** (`-SailingStormDelay=-250`, darkness 0.85, sky light 0.49) | (0.042, 0.045, 0.049) | x 0.35 | **(0.0078, 0.0080, 0.0056)** | **-3.1 stops** |
| Thunderstorm, behind it (-500 s, darkness 0.55) | (0.045, 0.043, 0.040) | x 0.37 | (0.0073, 0.0071, 0.0046) | -3.2 stops |
| Dusk 19:36 | 0.0001 | 0 | 0.00016 | |
| Night 22:00 | 0.0001 | 0 | 0.00013 | |

`-SailingWeatherTime` doesn't bring the front overhead: it runs on the sim clock and reaches the start at 150 s
(`kFrontArrives`). `-SailingStormDelay=<negative s>` moves it earlier along its track, which is how these were taken.
Dividing by the sky light's intensity doesn't cancel a real drop: the probe includes that intensity and the lighting
multiplies it back. In full sun about a fifth is the sky (its Fresnel reflection and the body's upwelling of it) and the
rest the body's upwelling of the sun.

## Effect (Ultra, linear luminance, mean of three runs per state, `-SailingCloudShade=0.15`)

| View | Before (`-SailingNoWaterBounce`) | After | Change |
| --- | --- | --- | --- |
| Side, lower topsides | 0.3105 (sd 0.0004) | 0.3256 (sd 0.0002) | **+4.8%** |
| Backlit chase topsides | 0.0350 (sd 0.0014) | 0.0353 (sd 0.0005) | +0.9%, within spread (the sky region itself differed 6%) |
| The albedo-0.08 stand-in, side lower topsides (one run, unforced shade) | 0.2990 | 0.3184 | +6.5% |

Under the shaded sky of these runs, the water's bounce lifts the lower topsides about 5%; in full sun it's larger, as
the sun term grows with the direct light. (The +6.7%/+10.8% of the first sun-term push were the overstated sun.)
Where Lumen's rays find the lake bed or the hull itself first (the close underside views), the lower hemisphere isn't
reached and nothing changes.
The sheets below are from the final build, sky and sun terms with the clouds' dimming (before above, after below).
| Side | Chase | Crew underside | Boom from below |
| --- | --- | --- | --- |
| ![side](side.jpg) | ![chase](chase.jpg) | ![crew](crewunder.jpg) | ![boom](boomunder.jpg) |

(Before above, after below.)

## Cost

Helm eye, two 20 s runs each on the 4090, GPU ms before -> after: Medium 4.21 -> 4.00, High 5.56 -> 5.61, Ultra 7.96 ->
8.11. Within noise. The probe is one 1x1 draw and a 4-byte-per-channel copy every two seconds.

## Checks

Full suite 235/235 on the PC on main 81771c73 plus this branch (MSVC clean).
