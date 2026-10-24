# The water body's light at a grazing look (Oct 24 2026)

After #289 and #294, the far lake still read olive-red: red over blue 0.91 at 3° below the horizon on the bridge view,
against the photo's 0.56. With the body removed the water followed its sky, so the body was the place to look.

## The body itself is right

The USGS 2020 field campaign on north Texas reservoirs (ScienceBase `5fe38f8ed34ea5387deb4923`, public domain) measured
Ray Hubbard and Tawakoni:

- **Water quality** (`WaterQualityData.csv`):
  - Ray Hubbard: Secchi 0.2–0.75 m, chlorophyll-a 24–57 µg/L, turbidity 3–37 FNU.
  - Tawakoni, the photos' lake: Secchi 0.55–1.0 m, a little clearer.
- **Spectra** (`SpectroradiometricData.csv`, reflectance against a white reference):
  - `Tools/water/usgs_reflectance_rgb.py` turns them into linear sRGB under D65.
  - Ray Hubbard from above: Y 0.025–0.06, with one glinty visit at 0.11.
  - Colour: red over blue 1.6–2.1, green over blue 2.1–2.5, olive-yellow.

Our body (`WaterBodyFor`: albedo 0.16 / 0.18 / 0.11, extinction 2.4 / 2.0 / 2.8 per metre, about half a metre of
visibility) shows 0.03 from above, so its brightness and colour match. If anything it is a little less olive than the
measurements.

## The angle was wrong

The light the body sends up leaves through the surface, which passes 1 − F of it. At a grazing look that is a small share
(Fresnel for water, n 1.333). I captured the cloudless bridge at 9 kn from three cameras (1.5 m level, 3 m pitched 14°
down, 6 m pitched 55° down) at a fixed exposure (`-SailingEV=0.3`). The body's light is the difference between the
normal water and `-SailingWaterAlbedo=0,0,0`, averaged over wide bands because it follows the waves:

| Below the horizon | 2° | 3° | 5° | 8° | 10° | 20° | 40° | 80° |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Before, over straight down | 1.32 | 1.41 | 1.32 | 1.29 | 1.19 | 1.06 | 0.92 | 1.00 |
| After | 0.38 | 0.53 | 0.62 | 0.78 | 0.74 | 0.89 | 0.90 | 1.00 |
| 1 − F, flat water | 0.20 | 0.28 | 0.43 | 0.59 | 0.67 | 0.88 | 0.99 | 1.00 |

The single layer water pass drew the body's light the same at every angle, and a little brighter toward the horizon.

## Change

- **M_WaterV4:** `BodyT`, each pixel's own facet's transmission (1 − F at n · v, over its straight-down value) scales
  the body's scattering albedo. Rippled water averages its facets, and the facets tilted toward the eye pass more, which
  is why the after row sits above the flat 1 − F at grazing angles. Straight down nothing changes.
- **C++ mirror:** `AWaterSurface::BodyTransmission`, checked by `SailingSim.Visual.WaterBodyTransmission`.
- **Comparing:** `-SailingNoBodyTransmission` draws the body as before.
- **Other worlds:** the same term applies to every body. The lake, the bay and the Gulf all lose the veil.

## The water's colour

At 3° below the horizon, High, capture mode, auto exposure:

| View | Red / blue | Green / blue | Water over sky |
| --- | --- | --- | --- |
| Bridge, before → after | 0.91 → 0.81 | 1.04 → 0.96 | 0.46 → 0.38 |
| Bridge photo (Tawakoni) | 0.56 | 0.78 | 0.50 |
| Open lake, before → after | 1.00 → 0.90 | 1.12 → 1.02 | 0.50 → 0.39 |
| Open-lake photo | 0.77 | 0.92 | 0.51 |
| Gulf (shore telephoto), before → after | 0.76 → 0.75 | 1.02 → 0.91 | 0.44 → 0.35 |
| Galveston Bay (chase, 1–3°), before → after | 0.90 → 0.81 | 1.05 → 0.91 | (Y 0.114 → 0.086) |

The far water moves toward the photos' colour. Some of the gap that remains is the lakes themselves: Ray Hubbard is more
turbid than Tawakoni. The water is now a little darker against its sky than the photos'. The reflection itself matches
Cox-Munk over its own sky (#294), so the difference lies in the photos' skies above the frame, which a rough surface
reflects and the comparison can't see.

`before-after.jpg`: before (left) and after (right). From the top: the bridge, the open lake, the Gulf and Galveston Bay.
