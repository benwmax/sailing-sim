# Loading stills that match the weather

Bean approved "loading screens that are photographs" (Nov 15 2026): the loading screen shows a still of the session's own
boat in the session's own light and sky, with the lesson's own tip. The code (PR #713) tags each still with a look
(`SailCatalog::ELoadingLook`: Day, LowSun, Grey, Storm, Night) and shows only stills of the session's look, else the
plain screen. This folder is the capture list for the missing stills.

## What the lake has and needs (slice boats)

| Look | When | J/22 | Sunfish |
|---|---|---|---|
| Day | sun 12 deg+, clear or fair (every lesson, the first job) | have (T_Load_RayHubbard_1) | have (_3) |
| LowSun | sun under 12 deg, clear or fair | j22-lowsun | sunfish-lowsun |
| Grey | overcast, rain, fog | j22-grey | sunfish-grey |
| Storm | sky Storms, sun up | have (_2) | sunfish-storm |
| Night | sun down, any sky | j22-night | sunfish-night |

Seven new stills. The Catalina 22 (stretch boat) has only a Day still; the Catalina 30 only a LowSun one.

## Capture (Mac, packaged build, High)

    SCENES=docs/loading-stills/scenes.csv OUT=docs/loading-stills/captures scripts/capture-scenes.sh

Then check each still at 1:1 by eye: the boat clear in frame, the sky reading as its look (night: the moon and shore
lights visible, not a black frame). Shrink each to a JPEG of 1600x900 under 300 KB (docs JPEGs are plain git), keep the
camera.json beside it, drop the PNG and telemetry.

## Into the game

1. `Tools/ui/make_ui_art.py`: crop the seven into `T_Load_RayHubbard_5` .. `_11` (order of scenes.csv).
2. `scripts/import_ui_art.py` (`UI_ART_ONLY=T_Load_RayHubbard`): imports them to `/Game/UI` (Git LFS: commit from the Mac,
   cloud sessions cannot push LFS objects). `docs/licences/assets.csv` already covers `Content/UI/*`.
3. `SailCatalog.cpp`: append their boats and looks to the lake's `LoadingBoats` and `LoadingLooks`;
   `SailingSim.UI.LoadingStill` checks every still has both.

`Content/` and `Tools/` changes need Bean's `bean-approved` label.
