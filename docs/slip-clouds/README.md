# Lighter fair-weather cloud sampling on High (the marina slip view's floor)

The full sweep of main 8e3d57c8 (Nov 16 2026) had the marina slip view on High at 44.3 fps, under its 45 floor. Its
profile put 2.3-2.5 ms in the clouds and fog slice, twice the helm-eye view's 1.2 ms: the slip camera looks out under a
lot of open fair-weather sky.

High's fair-weather clouds now march at a view sample scale of 0.65 and a shadow sample scale of 0.5
(`CloudViewSampleScale`, `CloudShadowSampleScale` in `VisualPipeline.cpp`; the values `-SailingCloudScale=0.65,0.5`
gives). Under a storm deck the storm-adaptive code (docs/storm-high/) eases the view scale back to 1 and keeps the shadow
rays at 0.5, so the storm samples exactly as before (view scale 1 with the 56 cap, shadow 0.5). Medium, Low and Ultra
are unchanged; `-SailingCloudScale` still overrides.

Measured on the 8e3d57c8 package with the arg, High at full resolution, base / combo / base / combo, means of two runs:

| view | fps base | fps combo | clouds_fog ms base | combo |
|---|---|---|---|---|
| slip | 45.5 | 46.4 | 2.29 | 2.00 |
| coast-day | 51.8 | 52.7 | 2.16 | 1.81 |
| helm-eye | 55.1 | 55.3 | 1.16 | 1.16 |
| beat15 | 51.6 | 51.5 | 1.27 | 1.21 |

The two cuts don't add up: shadow 0.5 alone took 0.36 ms off slip's clouds, view 0.65 alone 0.32 ms, both 0.30 ms; the
sample count cap (`-SailingCloudSamples` 72, 64, 56), the shadow distance (2 km) and the reconstruction mode moved it
less. The fair-weather cumulus in the slip, coast-day, helm-eye and beat15 stills look the same at 1080p with and
without the cut (`Inputs/slip-clouds/` on the inputs branch: slip and coast-day, base and combo).
