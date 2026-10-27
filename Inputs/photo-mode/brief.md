# Free-fly Photo mode: design and build brief

Bean's ask (Oct 27, cmsg_01LZf6WW82DddXS8e3xrubuG9pKxYhyUgRCY1eLi3Zdi4V): "Picture mode should let the user fly freely around the world to take photos, not just anchor to the boat."

Read against sailing-sim main 9b16cda (#355). Range decided by Bean (Oct 27 18:23 UTC, cmsg_01LZf6WW82DddXS8e3xrubuG8gsgVqEn9dUy15PLtgaTPA): **5 km leash** from the player's boat. Phase 3 ("anywhere") is not planned.

## What exists today

- `ASailboatPawn` owns photo mode: `bPhoto`, `SetPhoto`, `TakePhoto`, `UpdatePhotoLens` (Source/SailingSim/Private/SailboatPawn.cpp ~1808-1855). Toggle key `Photo` = 9, shutter `PhotoShot` = Enter (SailingSettings.cpp ~268-270). No controller binding. Pause menu item "Photo mode" (UI/SailFrontEnd.cpp:1097).
- The camera is the chase `CameraBoom` spring arm: mouse orbits (pitch -89..35), wheel changes arm length 1.5 m..300 m (`OnLook` ~2731, `OnZoom` ~2762). `[`/`]` (ThrottleSplit axis) zoom the FOV 10..110 deg.
- Lens: DoF focused on the boat at f/2.8, 36 mm sensor, lens distortion blendable; cinematic grade forced on (`UsesCinematicLook`, VisualPipeline.cpp:91). HUD hides itself in photo mode (UI/SailHud.cpp:322, SailingHUD.cpp:333 shows the hint).
- "Freeze": `Tick` returns early when `bPhoto` (SailboatPawn.cpp ~1025). That also skips `ClockMode->AdvanceClock` (~1093), and because the player pawn is the thing that advances the world clock, the whole world stops. This works by accident and leans on rule 3/9 the wrong way.
- Shots: `FScreenshotRequest::RequestScreenshot` to Saved/Photos/"Sailing <date>.png", viewport resolution.

## Design (what the player gets)

Modelled on Forza Horizon 5, Gran Turismo 7, Cyberpunk 2077, Ghost of Tsushima and the MSFS 2024 drone camera: a free drone camera with speed control, a short lens/exposure panel, hidden UI, paused time, and full controller support.

**Camera**
- Opens where the chase camera is (no jump), world paused.
- Fly: WASD / left stick move on the camera's heading (level, not pitched, like a drone); Q/E or LT/RT down/up; mouse / right stick look; Z/C or LB/RB roll (Dutch angle, +-45 deg, R3 or X resets roll).
- Speed: Shift / L3 held = 5x boost, Ctrl = 0.2x precision; mouse wheel steps base speed (0.5, 2, 8, 30, 120 m/s), shown as a small readout. Smoothed acceleration (about 0.25 s ease) so motion is filmic, not twitchy.
- "Back to boat" key (F / Y) snaps back to the orbit position. Orbit mode stays available as a toggle (Tab / View button) for boat portraits; free-fly is the default.
- Limits: horizontal leash 5 km from the player boat, soft (speed falls off over the last 500 m, then stops). Ceiling 1,500 m above water. Floor: never below the water surface + 0.15 m at the camera (wave height from the water model at that point, so wave-top shots work) and never below terrain height + 0.5 m (`FLakeTerrain::HeightAt`). Small sphere sweep (r = 20 cm) against the visibility channel so the camera stops at hulls, docks and bridges instead of entering them; skip the sweep where collision is off (instanced shore kit) and accept that, as most games do.

**Panel** (Slate, a narrow left column; Tab-style pages so it never covers the frame; hidden with H / Menu-hold, so the frame can be fully clean)
- Camera: FOV/focal length (14-200 mm equivalent, maps to the existing FOV range), roll.
- Focus: auto (centre trace) / boat / manual distance; aperture f/1.4-f/22 (off = no DoF).
- Exposure: compensation -3..+3 EV on top of the metered value (add to `AutoExposureBias`, do not replace Bean's "Truest" band); vignette 0-1; grain 0-1; look: Natural / Cinematic (default Cinematic, as today) / Black & white.
- Scene: hide my boat, hide other boats, hide crew; time of day (see below). 
- Frame: rule-of-thirds grid toggle; aspect crop guides 16:9 / 3:2 / 1:1 / 21:9 (guides only, shot is full frame).
- Shutter: Enter / A. Capture size: 1x, 2x (HighResShot) on High/Ultra. Save as today, toast with the file name.

**Time of day (phase 2)**: a visual-only sun override in `ASailingEnvironment` (sun angle, sky, night lights) that does not touch the world clock, weather or tide, and drops on exit. Changing real sim time from photo mode would break rule 9.

**Live mode (phase 2, optional)**: a "Pause world" toggle, default on. Off keeps the world running so moving water and traffic can be shot; the player boat keeps its held controls (same as Esc menu behaviour today). This is also the shape multiplayer will need, where the world cannot pause.

## Implementation notes

1. **Split the camera from the pawn.** Add `APhotoCameraPawn` (or an `APhotoCamera` actor + view target): its own `UCameraComponent` with the lens post-process. Enter: spawn at the chase camera's transform, `PC->SetViewTargetWithBlend(PhotoCam, 0.3)`, push input mapping context `IMC_Photo` at higher priority than the sailing context so the left stick no longer reaches the tiller. Exit: pop the context, view target back to the boat, restore the chase camera. Keep `ASailboatPawn::IsPhotoMode()` working (HUD, cinematic look, water glitter read it) by forwarding to the photo state, or move that query to the player controller and update the four call sites (SailHud.cpp:322, SailingEnvironment.cpp:750, WaterSurface.cpp:1928, SailingHUD.cpp:333).
2. **Pause through the clock, not the boat.** Add a single-player pause switch at the top (game mode, e.g. `SetWorldHeld(bool)` that makes `AdvanceClock` skip), and have photo mode set it. Do not rely on the pawn's early return. Ideally `AdvanceClock` is driven from the game mode's own tick instead of the player pawn's (rule 3), but that can be a separate small PR if it moves anything; check traffic, wind and water material all stop when held. Rendering keeps running (water material time comes from the clock, so the sea freezes with it; that is intended).
3. **Input.** New actions in `SailingSettings.cpp` so they appear on the keys page and can be rebound: PhotoMove (2D), PhotoUpDown, PhotoRoll, PhotoBoost, PhotoSlow, PhotoSpeed (wheel), PhotoToBoat, PhotoOrbit, PhotoPanel, PhotoHideUI. Bind the controller: Photo toggle = hold View (Gamepad_Special_Left) 0.5 s or D-pad combo, so it does not clash with ControlsCard; shutter = A. Add the rows to the controls card (SailingHUD.cpp:1218).
4. **LOD and streaming.** Most view-dependent systems already read the camera, not the boat: water rings (WaterSurface.cpp:726), terrain chunks (LakeTerrainActor.cpp:518), landmarks, navaids, night/far lights, boat/sail LODs. Those follow the photo camera for free once it is the view target, and that is fine for online play (camera-based LOD is client-side). Things that follow the **boat** and must stay that way: `GetFollowPoint` (tile streaming, render origin re-centre, physics window), tide height, weather/rain "at the boat", traffic spawning. With a 5 km leash nothing breaks: tiles load to 26 km (`LoadM`), the physics window is 24 km half-width, and the origin re-centres at 20 km, so the camera always sits on loaded tiles and wave/fetch/shelter grids. Check in the gate: Texas coast, camera 5 km from the boat at 1,500 m, no holes, no LOD popping in the far rings, no hitch on entry/exit.
5. **Anywhere (only if Bean picks it; Phase 3).** Split `GetFollowPoint` into a render follow point (camera while in photo mode: tile streaming and re-centre) and a sim follow point (boat: physics window, tide, weather, traffic). Rate-limit tile loads while flying fast; show a small "loading" mark if the camera outruns the loader; re-centre the origin under the camera. Physics window stays on the boat, so far water uses the coarse sea state there.
6. **Replay overlap.** Another thread is reworking Replay (`SetWatching`). Today entering photo mode cancels the replay. Target: photo mode inside a replay freezes the replay frame and flies the same camera. Coordinate so the two PRs do not both rewrite `SetWatching`/`OnButton`; whichever lands second merges the other. The Replay plan's free camera (its PR 5) reuses this camera, so build it as a standalone, reusable class (e.g. `AFreeCamera`: fly/look/limits/collision, no photo-specific logic) with the photo panel and lens layered on top; the leash anchor is a parameter (player boat for photos, the replayed boat for Replay).
7. **Photo quality (PC).** Lens panel post-process on the photo camera only; exposure compensation adds to the metered bias; 2x capture via `HighResShot` must keep the lens distortion blendable and the HUD out; check DoF at f/1.4 on Ultra does not shimmer on the water.

## Online-readiness rules (every PR)

1. Game state lives in SailingPhysics or a sim layer; actors only draw and read input. 2. No new "the player" lookups in sim code; systems take a list of vessels. 3. Time comes from the world clock, never from a boat. 4. Input reaches a boat only as an FBoatControls step. 5. Seeded things use the shared portable random and hash from stable ids. 6. Persistent placements use lat/lon or a stable id. 7. Saved data carries a version and string ids. 8. Results come from the sim, never the HUD. 9. Time compression/pause is one single-player switch at the top. 10. The gate records physics cost per boat. 11. No keys or secrets in the repo (it is public).

Photo mode specifics: the photo camera is client-only and never touches boat state (no FBoatControls while flying); the pause is the rule-9 switch; the camera may use GetFirstPlayerController (client-side, allowed); saved photo settings (if any) carry a version.

## Suggested PRs and lanes

| PR | Lane | Scope |
|---|---|---|
| 1. photo-freefly | Mac (wiring) | Photo camera actor, IMC_Photo with KB/mouse + controller, speed/boost, floor/ceiling/leash, sweep, orbit toggle, back-to-boat, clock pause switch, HUD hint and controls card rows, keys page entries. Tests: leash clamp, water/terrain floor, input context swap, clock held while in photo mode. |
| 2. photo-panel | PC (graphics) | Slate panel, focus modes, aperture, exposure comp, vignette/grain/look, hide boats/crew, grid and crop guides, 2x capture, visual-only time-of-day override. Ultra and Medium screenshots for the PR. |
| 3. photo-anywhere (not planned; Bean chose 5 km) | Mac | Render vs sim follow point split, re-centre under camera, loader rate limit; Texas coast flythrough bench. |

One PR per phase against main, merge main before building, Mac gate (Medium 60 / High 45) before merge; PC fixes MSVC breaks (export macros on nested structs). Finish and push every commit before starting a gate; never commit while gate.sh runs.

## Done when

Bean can press 9 (or hold View on a controller), fly anywhere within 5 km at walking to 120 m/s speed, frame a shot of the boat from the water's surface, a dock, or 1 km up, change lens/focus/exposure, hide the UI and save a clean PNG; leaving puts the player back on the chase camera with the boat exactly where it was, at both Medium and Ultra, on Mac and PC, with no frame-time cost when photo mode is off.
