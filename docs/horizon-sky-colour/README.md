# The near-horizon sky's colour (Oct 24 2026)

The water-sky-reflection diagnosis (`docs/water-sky-reflection/` on its draft branch) found that the far water takes
its colour from the low sky, and that our sky 3–8° up was paler and greener than the photos'.

## Cause

On the bridge view (G5 `g5-bridge`, High), cloud pixels filtered out, these are red over blue / green over blue in linear
light:

| | 3° | 5° | 8° | 12° |
| --- | --- | --- | --- | --- |
| Photo, bridge (Tawakoni) | 0.66 / 0.81 | 0.75 / 0.86 | 0.59 / 0.74 | 0.43 / 0.68 |
| Photo, open lake | 0.77 / 0.89 | 0.76 / 0.89 | 0.72 / 0.86 | 0.76 / 0.85 |
| Before | 0.84 / 1.01 | 0.77 / 0.95 | 0.83 / 0.95 | 0.53 / 0.78 |
| After | 0.74 / 0.90 | 0.71 / 0.90 | 0.60 / 0.83 | 0.48 / 0.74 |

What I ruled out, on the bridge view and a cloudless one:

- **The tone curve:** three stops less exposure leave green over blue at 3° at 1.0, and with the tone mapper off the
  scene's own sky still reads 0.96 there.
- **The fog:** the height fog and the volumetric fog don't reach the sky; turning them off changes nothing.
- **The dome, white balance, blue correction and gamut expansion:** our sky dome (the engine's own sky gives the same),
  and the three colour settings, move it by a few hundredths at most.
- **Ozone and the Rayleigh coefficients:** with ozone at 0 or doubled, or the coefficients moved to the sRGB
  primaries' wavelengths, the excess green stays.

Without the tone mapper, the cloudless sky matches a Preetham clear sky (turbidity 2.5) from 12° up: 0.37/0.66,
0.30/0.57 and 0.28/0.52 at 12, 20 and 30°, against 0.44/0.65, 0.32/0.57 and 0.26/0.52. Below 8° it is cyan, 0.70/0.96
at 3° against 0.84/0.85. That is a nearly pure Rayleigh horizon.

The aerosol that whitens a real low sky was missing from the atmosphere:

- The weather's visibility (25 km on a lake afternoon) was all in the height fog, a 50 m layer that doesn't reach the
  sky.
- The atmosphere kept the engine's Mie: 0.004 per km, an alpine 200 km.
- 25 km of visibility is 0.145 per km of aerosol at the surface (Koschmieder less clean air), about 32 times that.

## Change

`ASailingEnvironment::UpdateHaze`:

- **The split:** a share of the visibility's aerosol (`kAtmosphereHazeShare`, 0.3) goes to the atmosphere as Mie
  (`FHaze::AerosolExtinctionPerKm`; the engine's 1.2 km scale height; single-scattering albedo 0.9). The fog keeps the
  rest, so the visibility at the surface stays the weather's.
- **The share:** 0.3 brought the low sky between the two photos at 3–12° (0.5 and 0.7 went past them toward white).
- **Where it fades out:**
  - Under a stratus deck and in rain: the clouds don't shadow the atmosphere, and its sunlit aerosol would glow under
    them.
  - With the sun under 12° (gone at 2°): at sunset and dusk the aerosol's long path dimmed the clouds' sunlit faces to a
    dull brown and spread an orange glow toward the sun. The low sun keeps the old look until the clouds' lighting
    through aerosol is checked on its own.
- **Measuring:** `-SailingAtmoHaze=<share>` sets the share; 0 is the old sky.

## The water

The reflection follows the sky. With the water body removed, the far water's red over blue goes from 0.69 to 0.73 as its
sky goes from 0.84 to 0.74.

The whole water reads redder, though: 0.87 → 0.91 at 3° on the bridge, 0.93 → 1.00 on the open lake. The photos are
0.56 and 0.77. Two things cause it:

- The brighter, whiter sky light lights the olive body more.
- At 10 kn the reflection alone is only 0.29 of the sky at 3° (Cox-Munk 0.39), so the body carries more of the colour
  than it should.

That is the water's own gap. A rough GGX reflection is too weak at grazing angles, as M_WaterV4's roughness comment
says. It is the next water item.

## Stills

`before-after.jpg`: High, capture mode. Before is `-SailingAtmoHaze=0` on the same build (left); after is right. From
the top: the bridge, the open lake, the Gulf (shore telephoto) and Galveston dusk (sun 4.1° up, where the share has
nearly faded out).
