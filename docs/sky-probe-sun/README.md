# The water bounce's sun term from the light, not the probe (Oct 25 2026)

#320's water bounce (`docs/sky-lower-hemisphere`) takes the sun's illuminance on the horizontal water from
M_SkyEnvProbe's second texel. That texel is `SkyAtmosphereLightIlluminance(CameraPositionWS) x max(sun z, 0)`, drawn
into a 2x1 target through a canvas.

## What went wrong

- **On Metal the texel read 0 now and then.** In one 40 s run (lake, 10:00) it read the right value once and 0 after. In
  another it held through a passing cloud shadow. D3D12 held throughout.
  - A canvas draw isn't a scene view. What it sees of the atmosphere's lights is whatever the view uniform buffer holds
    when the canvas renders.
  - A zero sun removes the sun term from the bounce: the lower hemisphere fell to about 40% of its value.
- **It took the wrong path through the atmosphere everywhere.** The node's World Position input is the canvas camera's
  position, not a point in the scene. Its value implies about 16% less atmosphere than the scene's surfaces get.

## Fix

The sun term is computed from the light itself in `ASailingEnvironment::UpdateLowerHemisphere`:

`GetColoredLightBrightness() x GetAtmosphereTransmitanceOnGroundAtPlanetTop(light) x max(-forward.z, 0)`

That is the light's outer-space illuminance and colour, through the transmittance the engine itself gives an atmosphere
sun light on opaque surfaces, times the sine of its elevation. The probe keeps its sky texel; its sun texel is only logged
now, as `(probe ...)`.

## Before and after (lake, LeavetheDock start, 10:00, High, uncooked; log `Water bounce: ...`)

| | Sun on the water | Sky mean |
|---|---|---|
| main, 40 s, clouds free | (3.29, 2.71, 1.90) once, then 0 for the rest of the run | 0.18 to 0.10 (a cumulus shadow: cloud shade 1.0 to 0.54) |
| this, 14 s, `-SailingCloudShade=1` | (2.85, 2.32, 1.62), steady | 0.18, steady |
| this, 40 s, clouds free | 2.85 to 1.54 as the same shadow crosses, never 0 | 0.18 to 0.10 |

- At 10:00 the light is 10 x transmittance (0.639, 0.520, 0.365) x sin elevation 0.445.
- The probe's own reading on D3D12 (3.28, 2.71, 1.99) is about 16% over this, for the camera-position reason above.
- The sky mean's fall over 40 s wasn't Metal's. It is a cumulus crossing the camera in that run (the sun light dims with
  it). With the shade held it stays put.
