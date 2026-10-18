# Wisps and the storm cover (round 12, after C2)

This work is built on C2 (#132) and needs its sky cache. It is on the branch `storm-wisps-dev` until #132 merges; the PR
then goes from main.

## Wisps

Round 12's verdict on the clouds was "not wispy enough, too solid". In `CLOUD_CODE`, where the march steps are short
(under 90 m), the cumulus change in three ways:

- **Thinner.** The density is 0.1 of the full value (`SAILING_WISP_THIN`). At full density a cumulus closes within tens
  of metres and reads as a solid lit skin, the clay look. Real cloud light diffuses deep through the skin; the short-step
  march only shows that with thinner vapour. Bean chose 0.1 over 0.15 ("fluffier").
- **A gentler edge ramp,** 1.2 to 2.5 against C1's 2.5 to 6.
- **Fine detail at the outline and the base:** 30 m of fine curl distortion and high-frequency erosion. The detail is
  filtered at the step and the pixel footprint, never finer.

Short steps are the near live clouds (5 km rays with full samples on High, Ultra's 3 km) and the cache's fine steps inside
cloud. The cache's `Tracer` now describes those fine steps, so `CLOUD_CODE` sees them. On long steps nothing changes.
`-SailingNoWisps` compares.

## Storm cover

The sky cache now runs under storms as well:
- It refreshes every second.
- The shelf's lit face (`CLOUD_CODE`'s emission) is integrated into the sun term.
- The cached light is tinted toward the deck's slate as the storm builds, and its sky term lifted.
- The panorama reaches 75 degrees up (896 rows) for the deck.

`-SailingNoStormCache` gives a storm's sky back to the live clouds.

## Stills (packaged, High: `<scene>-high.jpg`; left both off, i.e. #132; right both on)

- **lake-towers, Kemah, Texas City, north shore.** The clouds are softer and fluffier and less solid. At Texas City
  some of the crisp cauliflower detail is traded for softness.
- **storm-shelf.** The grain is gone and the shelf is slate (grain read 1.09 off against 0.92 on). Three things
  aren't right yet:
  - The deck above the shelf is a darker navy than the live storm's grey.
  - The shelf's tiers read as spiky teeth.
  - The lip has a brownish band.

## Cost (GPU, 1080p, ProfileGPU, off / on)

| | GPU frame, ms | clouds + fog, ms |
|---|---|---|
| storm-shelf, High | 5.59 / 5.84 | 0.64 / 0.49 |
| storm-shelf, Ultra | 10.85 / 11.90 | 3.49 / 4.60 |

The 1 s storm refresh is four times the strip work (`other` +0.1 to 0.3 ms). On Ultra the live near storm clouds cost
more with all their samples.
