# Saturday capture on Windows-2479e9cf (the freeze's Development package), 4K, PC, Nov 27 2026

`reel-saturday.ps1 -Package Windows-2479e9cf` (film mode, 3840x2160 Ultra, crew off), 22 takes, 12:23 to 15:53 local. Frames
stay on the PC at `D:\dev\reel\saturday-Windows-2479e9cf\<take>\rec` (73 GB; nothing deleted). Here: each take's first,
middle and last frames, 1280 wide, WebP quality 80 (`<take>-first|mid|last.webp`; the two single-frame stills are `-only`).

| Take | frames | warning and error lines in its log |
|---|---|---|
| P1-final | 720 | 117 |
| P1-lightingonly | 720 | 117 |
| P1-wireframe | 720 | 117 |
| P2-storm | 800 | 117 |
| P3-realday | 300 | 117 |
| P4-topdown | 1 | 117 |
| P5-then-now | 1 | 117 |
| R01-dawn-marina | 360 | 117 |
| R05-tack-orbit | 420 | 117 |
| R06-helm-eye | 360 | 117 |
| R09-polar-chase | 480 | 117 |
| R10-gust | 420 | 118 |
| R12-sunfish | 480 | 117 |
| R13-jibclew | 180 | 117 |
| R14-c22-dolly | 420 | 117 |
| R21-golden | 420 | 117 |
| R22-night | 420 | 117 |
| H02-reach | 360 | 117 |
| R03-briefing | 240 | 116 |
| R08-career | 240 | 117 |
| R08b-checkride | 960 | 117 |
| R23-worldmap | 240 | 117 |

**The log lines are the same in every take** (116 to 118 each, `LogHttp` left out):
- 21 `AttachTo` warnings: the lake's shore-edge models are Static and attach to a movable root, which the engine refuses
  (the known issue #846 notes as lake-only).
- The audio-sample lookups (`/Game/Audio/Samples/S_*`), which aren't in the project; those sounds are synthesized.
- Two handled ensures at frame 0 (`LogOutputDevice: Error` lines with their callstacks), including
  `!IsComponentPSOPrecachingEnabled() || bPSOPrecacheCalled` (`PSOPrecache.cpp`, from `UGroomComponent::CreateSceneProxy`),
  as in every package; and `OriginX <= OriginMax ...` (`DoubleFloat.cpp` line 19, from
  `FDFMatrix::MakeToRelativeWorldMatrix` in the distance-field visualisation pass), the distance-field transform
  precision ensure CLAUDE.md notes for uncooked runs.
- No take stopped, timed out or came up short of its frame count. R08b's seeded logbook is kept on the PC and the
  package's own was restored. Bean's Saved was restored (7B5CA7BE).

## P1-lightingonly re-take (`P1-lightingonly-relit-first|mid|last.webp`)

The first P1-lightingonly kept the sail number and showed grey squares on the far water. It was launched with
`-ExecCmds=viewmode lightingonly`, which sets the engine's view mode only. The pawn takes the sails' marks and colour off
only on the `-SailingViewMode` route (`FilmMode.cpp`). The squares are the far whitecap sprites (`M_FarCap`, masked quads
300 m to 1.25 km out): a 1-frame 1080p pair with and without `-SailingNoFarCaps` showed them on and gone.

**Re-take:** 4K, P1-final's shot and timing (720 frames from frame 600), with `-SailingViewMode=lightingonly
-SailingNoFarCaps`. The log says "Film view mode: lighting only (the engine's view mode)". No sail number, no squares.
Frames are in `D:\dev\reel\saturday-Windows-2479e9cf-lofix\P1-lightingonly\rec`; the old take is kept. Its telemetry has
the same checksum as the three earlier P1 passes, so she sails the same path. `P1-relock/overlay-final-vs-lightingonly-relit-f*.webp`
lay it over P1-final at frames 0, 360 and 719.
