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

STILLS

## Cost (GPU, 1920x1080, ProfileGPU frames in the measured window, main / this branch)

COSTS
