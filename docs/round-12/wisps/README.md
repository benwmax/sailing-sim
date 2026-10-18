# Wisps (round 12, after C2)

Round 12's verdict on the clouds was "not wispy enough, too solid". In `CLOUD_CODE`, where the march steps are short
(under 90 m), the cumulus change in three ways:

- **Thinner.** The density is 0.1 of the full value (`SAILING_WISP_THIN`). At full density a cumulus closes within tens
  of metres and reads as a solid lit skin, the clay look. Real cloud light diffuses deep through the skin; the short-step
  march only shows that with thinner vapour. Bean chose 0.1 over 0.15 ("fluffier").
- **A gentler edge ramp,** 1.2 to 2.5 against C1's 2.5 to 6.
- **Fine detail at the outline and the base:** 30 m of fine curl distortion and high-frequency erosion. The detail is
  filtered at the step and the pixel footprint, never finer.

Short steps are the near live clouds (5 km rays with full samples on High, Ultra's 3 km) and the sky cache's fine steps
inside cloud. The cache's `Tracer` now describes those fine steps, so `CLOUD_CODE` sees them. On long steps nothing
changes. `-SailingNoWisps` compares.

Storms are unchanged: the sky cache still stands aside under a storm, as on main.

## Stills (packaged, High, Windows: `<scene>-high.jpg`; left main, right this branch)

The cameras are `scenes.csv` (packaged Development builds, 16 s captures on Bean's RTX 4090; main 092cadc5).

- **lake-towers, north shore, Kemah.** The cumulus are softer and fluffier: a translucent fringe instead of the lit
  clay skin, and the frosted speckle along main's outlines is gone.
- **Texas City.** The softness costs detail here. The near cells lose most of their crisp cauliflower lobes and read
  as soft rounded masses; the rows farther out keep their shape. Worth a look before merging: at 0.15 more of the
  lobes stayed.

## Cost (GPU, 1920x1080, ProfileGPU frames in the measured window, main / this branch)

| | fps | GPU frame, ms | clouds + fog, ms |
|---|---|---|---|
| lake-towers, High | 76.6 / 78.3 | 5.01 / 5.30 | 0.38 / 0.34 |
| lake-towers, Ultra | 74.5 / 69.9 | 7.51 / 8.58 | 1.45 / 1.92 |
| Texas City, High | 70.5 / 70.2 | 6.31 / 6.36 | 0.33 / 0.34 |
| Texas City, Ultra | 63.0 / 65.2 | 9.10 / 9.72 | 1.25 / 1.58 |

High is unchanged within the noise. On Ultra the near clouds cost 0.3 to 0.5 ms more. Ultra keeps every near sample
(3 km at full count), and the thinner vapour lets the march go deeper before it is opaque.
