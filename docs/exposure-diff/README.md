# Auto exposure against locked, on the Mac (Oct 26 2026)

For the PC's diff (gap 2). The chase capture (`-SailingCapture=Chase`), AfternoonBreeze, 15:00, 14 kn, TWA 60, on main
9d10c6e3, uncooked (`capture-scenes.sh`), 1440x1080. Auto exposure is frozen at 2.5 s, as captures do; "locked" is
`-SailingEV=-0.85`. Luminance is linear: water from patches in the lower corners clear of the boat, low sky just over the
horizon (left edge), upper sky at the top left.

| Run | Water (L, R) | Low sky | Upper sky | Frame mean | meter_ev100 |
|---|---|---|---|---|---|
| High, auto | 0.021, 0.025 | 0.146 | 0.078 | 0.094 | -0.86 |
| High, locked -0.85 | 0.054, 0.069 | 0.303 | 0.178 | 0.177 | -0.86 |
| Ultra, auto | 0.020, 0.023 | 0.119 | 0.091 | 0.086 | -0.86 |
| Ultra, locked -0.85 | 0.046, 0.054 | 0.232 | 0.216 | 0.166 | -0.86 |

**The Mac sits about a stop low on auto too**, as the PC does. My earlier "Mac water 0.064" came from a band that held
the hull. On water-only patches the Mac's auto chase read 0.023-0.031 (`docs/pc-water-grazing/`), the same condition as
the PC's 0.021-0.024. So the audit's comparison mixed two conditions.

## Why auto is a stop low

The exposure is set in `ASailingEnvironment::Tick` (the scene's post-process volume) and, for captures, on the capture
camera (`ASailboatPawn`):

| Setting | Auto (game, bench, capture) | Locked capture |
|---|---|---|
| AutoExposureMethod | Histogram | Histogram (the volume's) |
| AutoExposureMinBrightness | meter - Band + 2.5 x IntoSun = -1.86 here | -0.85 |
| AutoExposureMaxBrightness | meter + Band + 2.5 x IntoSun = +0.14 here | -0.85 |
| AutoExposureBias | Settings > Brightness, 0 when measuring | 0 |
| Speed | frozen at 2.5 s (captures: 0.0001) | - |

Here meter = `CameraEV100` = -0.86; Band = 1 in clear air (`lerp(1, 0.3, CloudDarkness)`); IntoSun = 0 (sun 34 deg up).

The auto frame is 0.91 stop darker than the locked one (frame means 0.094 against 0.177; the low sky 1.05 stops), so
auto applied about EV100 +0.1: the top of its band (+0.14). The histogram wants this framing (white sails and large
sunlit cumulus over half the frame) darker than the incident meter and is clamped at the band's darkest edge. The PC's
numbers say the same: band -1.9..0.1 around incident -0.9, and pre-exposure 0.97 against 1.72 locked (0.83 stop). So
it is the histogram's framing room (plus or minus 1 stop, "Visual V1: a little room for the histogram to react to
framing"), not a calibration mismatch between the two paths. #342's deeper cumulus put more bright cloud in the frame.

`ShowFlag.VisualizeHDR 1` crashes the game on Metal (a fatal pipeline-state compile failure,
`PipelineStateCache.cpp:712`, "Shader compilation failures are Fatal"), so the Mac has no overlay numbers. The PC's
band and pre-exposure fit the arithmetic above.

## Cvars (identical on High and Ultra; `DumpCVars` in the auto runs)

```
r.DefaultFeature.AutoExposure = "1"      LastSetBy: Constructor
r.DefaultFeature.AutoExposure.Bias = "1"      LastSetBy: Constructor
r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange = "1"      LastSetBy: ProjectSetting
r.DefaultFeature.AutoExposure.Method = "0"      LastSetBy: Constructor
r.ExposureOffset = "0"      LastSetBy: Constructor
r.EyeAdaptation.BlackHistogramBucketInfluence = "0"      LastSetBy: Constructor
r.EyeAdaptation.CachedLightingPreExposure = "4"      LastSetBy: Constructor
r.EyeAdaptation.ExponentialTransitionDistance = "1.5"      LastSetBy: Constructor
r.EyeAdaptation.ExposureCompensationCurveLUT = "true"      LastSetBy: Constructor
r.EyeAdaptation.ExposureCompensationCurveLUT.MaxX = "20"      LastSetBy: Constructor
r.EyeAdaptation.ExposureCompensationCurveLUT.MinX = "-10"      LastSetBy: Constructor
r.EyeAdaptation.ExposureCompensationCurveLUT.NumSamples = "64"      LastSetBy: Constructor
r.EyeAdaptation.LensAttenuation = "0.78"      LastSetBy: Constructor
r.EyeAdaptation.MethodOverride = "-1"      LastSetBy: Constructor
r.EyeAdaptation.PreExposureOverride = "0"      LastSetBy: Constructor
r.EyeAdaptation.VisualizeDebugType = "0"      LastSetBy: Constructor
r.EyeAdaptation.VisualizeLuminanceScale = "1"      LastSetBy: Constructor
r.Tonemapper.Quality = "5"      LastSetBy: Scalability
r.Tonemapper.Sharpen = "-1"      LastSetBy: Constructor
```
