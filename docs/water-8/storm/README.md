# W8 item 1: storm from the sunshine

Round 11 couldn't frame a shelf cloud seen from sunlit water on the lake. From the start of the storm's timeline the
boat was already in the deck's gloom, the shelf's base was grainy, and its edge was soft. Fair cumulus inside the
storm's painted extent were flat grey towers. All four came from the code:

- **The gloom followed the clock, not the front.** `CloudDarkness` and `CloudCover` ramped with the storm's build
  (0 to 150 s) at the start point. With the front 7 km off (`-SailingStormDelay=600`), the sky light, the exposure, the
  colour (saturation down 70%) and the haze were already the storm's. Now `FWeatherState::LocalizeStorm` sets them from
  how far ahead of the gust front the boat is (`FStormShape::Overhead`: none 3 km ahead, all 300 m behind). The game
  mode calls it at the boat, as it does for the rain. Under rain (the core, or a real day's radar) it stays dark.
- **The anvil shaded 9 km ahead.** Its density fell linearly to its tip, and the sun ray through it counted as water
  cloud. It now thins as the square of what is left ahead (`AnvilDensity`). Ice dims the sun a third as much as water
  cloud at the same density (`AnvilIceExtinction`: extinction 3 IWC / 2 rho r, about 3e-3 /m against 1e-2).
- **Every cloud in the storm's lateral extent was slate.** `wet` took `w.a * 2`, the storm's extent along the front,
  which runs the whole track ahead. Now only near the front (`nearF`). The fair cumulus fade out from 5 km ahead to
  1.5 km ahead and under the core (`FStormShape::CumulusFade`, in the material and in `SunTransmittance`). With the
  sunlit cells far ahead and none near, there are no flat grey towers.
- **The grain was the march's scattered light.** A storm sample is either sunlit skin or dark interior, and the jittered
  march landed on one or the other per pixel. The depth cap only washed it out (0.4: grey, still grainy). The shelf's
  sloping face above its base is now lit by emission in proportion to the extinction (`Emit = L * d * Density`). The
  engine takes emission as luminance per metre, so it integrates to the same radiance wherever the ray closes. The
  face's scattering albedo is cut by 0.9. The face's tone varies only at the march's scale or coarser (the tiers'
  risers, the coarse billows `nS`, dimming from 450 m to 1.8 km back), per the G1 rule. `SunLum`/`SunDir` come from
  `ASailingEnvironment::UpdateSun` (the undimmed sun, reddened near the horizon). The base takes the coarse billows
  instead of the fine detail. The face is hardly eroded, and the leading edge rises to full density in `ShelfEdgeM`
  (60 m): a crisp arcus line.

New: `-SailingNoLightning` (a flash lights the water white at random times; both rounds' stills use it).

## Stills

`scenes.csv` (Chase, from the boat's ESE toward the storm, 15:00 on Oct 15, sun at 41 deg from 218 deg, 72 deg off the
storm's track). The front is about 6.7 km off, about 2.2 km off, and arriving (`-SailingStormDelay` 600, 200, 15 with
the build complete, 16 s into the capture):

```bash
SCENES=docs/water-8/storm/scenes.csv OUT=docs/water-8/storm/after scripts/capture-scenes.sh 12
```

![before (left, origin/main c0d26d6 with only the no-lightning switch added) and after (right): front 6.7 km, 2.2 km, arriving; round 11's bay storm](storm-before-after.jpg)

Rows: far, near, arrival, then `r11-bay-storm` (left: the round 11 still). Before, the boat sits in gloom 6.7 km
ahead of the front. After, it is sunlit until the shelf is close, the shelf's face is lit over a dark, crisp-edged base
and the rain behind, and on arrival it is dark. On the bay the fair cumulus far ahead stay white, and the shelf shows as
its own lit band with a clean base.

Sky grain (the standard deviation of the image less a 2 px blur, over the sky left of the mast, against the sky's
mean): far 1.1% before, 0.75% after; near 0.8% before, 0.45% after. The bay is 1.0% in both (its grain is now in the
cumulus, not the shelf).

## Checks

`SailingSim.Visual.StormSunshine` (new), with the sun 72 deg off the track and the storm's shade alone (fair cumulus
off):

| front ahead | 8 km | 6 km | 4 km | 3 km | 2 km | 1 km | 0 | -1 km |
|---|---|---|---|---|---|---|---|---|
| sun reaching the water | 1.00 | 0.96 | 0.81 | 0.69 | 0.57 | 0.55 | 0.00 | 0.00 |
| CloudDarkness | 0.10 | 0.10 | 0.10 | 0.10 | 0.26 | 0.59 | 0.83 | 0.85 |

It holds the sun over 0.7 from 4 km out, under 0.3 under the front, no gloom from 3 km out, and full gloom under the
front. `SailingSim.Visual.ShelfCloud` now also checks the edge: 0 density just ahead of the lip, 1.0 100 m behind it,
and the lit face 8.7 times the underside (`FStormShape::ShelfShade`, mirrored in `CLOUD_CODE`).

## Still open

- With the sun this far off the track, the shelf's upper face reads as a broad pale wall from 7 km. Its top, where
  the face meets the core, keeps some streaky scattering.
- Lightning lights the water a uniform white for a frame or two (seen in two of the old stills). It reads as a flash,
  but the water should keep its waves.

## Gate

`scripts/gate.sh --scope clouds` passes (141 tests, then 129 on the reruns). The first run had helm-eye High at 44.6:
the new storm terms ran on every cloud sample. They now sit under one branch on the storm's density. A/B on the same
package, helm-eye High: main's material 46.7 fps (clouds 3.74 ms), this one 46.0 (3.93-3.98 ms over three runs).

| view | Medium fps | High fps |
|---|---|---|
| beam8 | 85.6 | 53.5 |
| beat15 | 82.9 | 50.1 |
| storm | 68.8 | 45.4 |
| coast-day | 80.0 | 46.9 |
| gulf-sea | 102.4 | 59.4 |
| helm-eye | 78.0 | 45.7 |
| slip | 76.5 | 47.2 |
| bridge | 95.6 | 53.8 |
