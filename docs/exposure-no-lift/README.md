# Exposure without the clear-air lift (Oct 23 2026)

Phase 8 added +0.5 EV of `AutoExposureBias` in clear air, fading out with `CloudDarkness`. It put a clear sky half a
stop over a still camera's, and the tone curve's shoulder washed out the colour of the low sky. Bean compared the
four views in `docs/exposure-choice/` and chose the truer exposure, so the lift is gone: the bias is now the player's
Settings > Brightness only, on the metered tiers and on Low. The cloud and storm gloom (Low's -1.5 EV x darkness,
the metered tiers' gloom adaptation) are unchanged.

Nothing depends on the lift. `SailingSim.Visual.MeteredExposure` checks `CameraEV100`, not the bias.
`scripts/make_lake_map.py` still writes 0.5 into the map's post-process volume, but `ASailingEnvironment` sets the
bias every frame, so the map's value is never used.

Bridge view, red over blue in the sky by elevation (`bridge-before-after.jpg`, before on the left):

| elevation | 3 deg | 5 deg | 8 deg | 12 deg | 20 deg |
|-----------|------:|------:|------:|-------:|-------:|
| before    | 0.87  | 0.81  | 0.81  | 0.56   | 0.36   |
| after     | 0.85  | 0.79  | 0.85  | 0.51   | 0.29   |

Above 10 deg the sky is bluer. At 8 deg the after shot reads redder because the band there is cloud, and cloud
comes out whiter at the truer exposure.
