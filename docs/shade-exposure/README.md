# Exposure in a cloud's shadow (Oct 24 2026)

Ultra audit 2 (`docs/ultra-audit-1024/`): backlit and shaded faces go near-black. In the chase, helm-eye and action-cam
captures the sails, crew and water fell toward silhouette, with no detail in the crew's faces and vests. This is the Mac
side, the exposure. The PC side (Ultra GI and the boat and crew materials' fill) is separate.

## Cause

The physical camera's exposure follows an incident meter (`CameraEV100`, Visual V1). Under cloud it opened only a tenth of
the way to the light it lost (`kGloomAdaptation`), so a storm keeps its gloom. That rule applied under every sky. A fair
day's cumulus shadow takes about two stops of the sun's direct beam (12–17% of it left), and the camera opened 0.2 stop
for it. The whole frame went 1.8 stops dark, and the shaded faces went toward black.

A camera's auto exposure opens nearly all the way for a passing cloud's shadow, and so does the eye, within seconds.

## Fix

How far the exposure follows depends on how gloomy the sky is:

- **Fair sky** (CloudDarkness 0.1 or under): 80% of the way (`kShadeAdaptation`). A cumulus shadow comes out 0.4 stop
  under the sunlit frame, so it still reads as a shadow.
- **Storm or overcast** (0.35 and up: the Overcast, Rain and Thunderstorm presets): the gloom's tenth, unchanged.
- **Between the two:** a smooth blend.

`shade.jpg` shows helm-eye, chase and action-cam at 15:00 with the sun held at 15% through a cell (`-SailingCloudShade=0.15`):
- left, the old rule (`-SailingClassicShadeExposure`): EV100 0.47;
- right, this change: EV100 -0.75.

## Measuring

- `-SailingCloudShade=<0..1>` holds the direct sun reaching the camera, so a cloud's shadow can be compared still for still.
  The cells' shadows don't land at the same moment from run to run.
- `-SailingClassicShadeExposure` restores the old rule.
- Capture metadata (`<shot>.camera.json`) now carries `sun_through_cloud` and `meter_ev100`.
- `SailingSim.Visual.MeteredExposure`:
  - a fair-sky cumulus shadow opens over 70% of its stops;
  - an overcast keeps the tenth;
  - the storm checks are unchanged.
