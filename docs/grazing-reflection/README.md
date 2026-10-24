# The rough water's grazing reflection: a check, no change (Oct 24 2026)

#289's README left a lead: at 10 kn the far water's reflection alone was 0.29 of the sky at 3°, against Cox-Munk's
0.39, as though M_WaterV4's rough GGX reflection were too weak at grazing angles. Measured properly, it isn't.

## Method

`Tools/water/sky_reflection_check.py <capture> <mean wind m/s>` works on a capture of the bridge view, cloudless
(ClearMistral), with the water body removed (`-SailingWaterAlbedo=0,0,0 -SailingWaterExtinction=100,100,100`, new
here). It takes the sky's luminance from the frame by elevation, 0.5–31°, held at the top row above that. It then
integrates Cox-Munk facets over that sky:

- each facet weighted by its area toward the eye;
- Fresnel for water;
- Smith (Gaussian) shadowing of each reflected ray;
- rays below the horizon counted as 0.

It compares the result with the water the frame renders, both over the sky at the mirror elevation. The wind is the
sea's mean wind (the weather's), not the local wind at the boat in the camera file.

## Results

At 4.5 m/s under a uniform sky the expected ratio is 0.36 / 0.32 / 0.26 at 3 / 5 / 8°. The 0.39 above is the same model
without shadowing. Our clear sky darkens upward, though, and a rough surface reflects sky well above the mirror angle,
so the expected ratio for this sky is lower:

| Wind | 3° (rendered / for this sky) | 5° | 8° |
| --- | --- | --- | --- |
| 6 kn | 0.37 / 0.28 (1.32) | 0.31 / 0.26 (1.20) | 0.21 / 0.23 (0.90) |
| 9 kn | 0.28 / 0.24 (1.15) | 0.25 / 0.22 (1.12) | 0.22 / 0.20 (1.09) |
| 14 kn | 0.16 / 0.19 (0.80) | 0.15 / 0.18 (0.81) | (whitecaps in the row) |

The reflection is within about 10–30% of the model: a little bright in light air, a little dim at 14 kn, where the GGX
lobe at grazing is widest and samples the black lower hemisphere. There is no systematic deficit to correct. The 12°
row is left out: the boat is near the camera there, and the water by the hull has its specular cut (`HULL_NEAR_SPEC`).

## What it means for the water's colour

With the body removed, the far water's colour follows its sky (#289). What reads olive-red on the bridge view (red over
blue 0.91 at 3°, the photo 0.56) is the water body's light, not a weak reflection. That is the next place to look:

- the olive body's scattering (`WaterBodyFor`: albedo 0.16 / 0.18 / 0.11 on the lake);
- how much of it the surface lets out at a grazing look.
