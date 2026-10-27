# Boat showroom and live conditions: implementation brief

For the build lanes (PC UI/graphics, Mac wiring and gate). Written Oct 27 2026 from main at 9b16cda (shallow read of
`Source/SailingSim`). Class names below are suggestions; the repo's real types win.

- Bean's ask (Oct 27 18:15 UTC, cmsg_01LZf6WW82DddXS8e3xrubuG9pKxYhyUgRCY1eLi3Zdi4V):
  1. Boat selection: the boat the user selects replaces the default boat shown when the start screen loads, centered on
     screen and "shown off" like racing-game car selection, rotatable with controls, UI reworked to make room.
  2. Conditions: the background world updates to match the conditions being set, so the user sees what they look and
     feel like.
- Layout mockup (3 artboards, two clickable): https://claude.ai/artifact/E1VMw9HXuF38faVZkwFF5M
  The boat pictures in it are the Oct 20 fleet stills and a crop of the title screen; the conditions tints are CSS
  stand-ins for the game's real sky, light, rain and waves.
- Pending with Bean (decision card in the thread): whether the picked world loads behind the menus (recommended) or the
  lake stays behind them. Build everything else first; section 6 is the only part that depends on it.

## 1. What the code does today

- The front end is one Slate widget, `SSailFrontEnd` (`Private/UI/SailFrontEnd.cpp`), drawn over the live world. The
  world behind it is the real level with the player's `ASailboatPawn`, held by `SetHeldByUI(true)`
  (`SailingHUD.cpp` `OpenFrontEnd`). Held means the boat's physics clock is carried with the world clock and no steps run
  (`SailboatPawn.cpp` around line 1097), so the boat is frozen mid-heel while waves and clouds move.
- The backdrop is `SBackdrop` with a left-heavy gradient (LeftAlpha 0.86, RightAlpha 0.15 on the front end).
- Boat screen (`BuildBoat`): a 4x2 card grid (60%) and a detail panel (40%). Choosing only sets `Pending.Boat`; the pawn
  behind keeps the default J/22. Nothing reaches the world until Cast off reloads the map with the session.
- `ASailboatPawn::SetBoat(int32)` already swaps the boat at runtime: new `FBoatModel`, `RebuildBoatVisuals()`, camera
  distance from the boat's length, then `ResetBoat()` (moves the boat to the launch spot). It logs "Boat ready: ... in
  N ms". Meshes load synchronously: `ModelMeshesFor` uses `LoadObject` for `/Game/Boats/<Tag>/SM_<Tag>_*` and for the
  hero J/22 `/Game/Boats/J22Hero/SM_J22H_*` (plus Interior and Glass). That is a hitch on first load of each boat.
- Conditions screen (`BuildConditions`): presets, real days, wind dial, sliders. Front end: values only go to `Pending`.
  In game (`ConditionsInGame`): Apply calls `ASailingGameMode::ApplyConditions(Pending.Conditions)`, which sets the
  preset, hour, wind overrides and date and calls `ApplyWeatherSettings()` with no reload. Wind direction changes
  rebuild the shelter map on the thread pool (`SailingGameMode.cpp` ~297 and `UpdateShelter`), so that part is async.
  In game the menus pause the world (`UGameplayStatics::SetGamePaused` in `OpenPause`), so nothing would animate.

So both asks can reuse existing paths: `SetBoat` for the showroom, `ApplyConditions` for the preview. The work is a
camera rig, a showroom hold, async loading, debouncing and blending, and the two layouts.

## 2. Boat screen (mockup artboards 1 and 2)

Pattern taken from car select and garage screens (Forza Horizon and Motorsport, Gran Turismo 7, Need for Speed, The
Crew Motorfest): the vehicle owns the middle of the screen, the name is big on one side, the numbers are compact bars on
the other, the roster is a strip along the bottom, a turntable or orbit camera with an idle auto-spin, and a button that
hides all panels so you can just look.

Layout (1440x1080 reference, scale with the existing safe-zone rules):
- Top left: eyebrow "FLEET OF EIGHT", title "CHOOSE A BOAT" at 44 px (smaller than today). Top right: the step tracker.
- Left column (about 380 px): type line, boat name at about 96 px, "Your lesson boat" pill, description, flag chips.
- Right column (about 330 px, translucent panel): Length, Beam, Weight, Close-hauled at 12 kn as value plus a bar
  scaled to the fleet, Handling pips, the polar note. "Next: conditions" button under it.
- Middle (about 500 px clear): the boat. Under it a small orbit ring with the view angle ("View from starboard quarter"),
  rotate buttons for mouse users, Auto spin toggle, Reset view.
- Bottom strip: 8 compact cards (silhouette and name), LB/RB at the ends. Locked boats stay in the strip with a lock and
  the certificate that opens them; the showroom still shows a locked boat (racing games let you look at cars you can't
  drive yet), but Choose and Next are disabled on it with the reason shown.
- Backdrop: replace the left-heavy gradient on this screen with soft vignettes top and bottom only and a light one on
  the left, so the boat stays bright.
- View mode (artboard 2): V or the gamepad View button hides every panel, leaving the boat name and the control hints;
  orbit and zoom work the same. Any of V, View, Esc or B brings the panels back.

Input:
- Boat: Left/Right or LB/RB (and Q/E, to match the Settings tabs) move along the strip. Focus is the selection here:
  moving to a boat shows it. Enter/A on the shown boat goes to Conditions (today's "confirm on the chosen card moves on"
  rule stays). Mouse click on a card shows it; click again or Next moves on.
- Orbit: right stick X / mouse drag (left button on empty space) yaws; right stick Y / drag pitches within limits.
  Zoom: mouse wheel / LT RT. Reset: R3 / Home. These need routing from `SSailFrontEnd::OnAnalogValueChanged`,
  `OnMouseButtonDown/Move/Up` and `OnMouseWheel` to the camera rig (the widget has keyboard focus, so the pawn's input
  does not see them).
- Auto spin: on by default, about 6 degrees a second, starts after 4 s without orbit input, stops on any orbit input.

## 3. Front-end camera rig

One rig with named framings, blended (about 0.6 s, ease in-out) on screen changes:
- Title: today's chase framing.
- Showroom (Boat screen): orbit around the boat's center of rig, target at about 0.4 of mast height. Distance from the
  boat's size (today's `LengthOverall * 2.4`, clamped 9 to 40 m, is a good start), zoom 0.6x to 1.6x. Pitch 3 to 35
  degrees above the water; never below wave height plus 0.5 m at the camera's position (sample the wave field).
  Yaw default 135 degrees (starboard quarter, the classic three-quarter view). The boat's on-screen center sits in the
  middle column; if the side columns make it look off-center at 16:9 and 4:3, use a small lateral target offset rather
  than moving the boat.
- Weather (Conditions screen): wider and higher, about 4 boat lengths out, sky about 45% of the frame, boat in the right
  60% of the screen (the panel takes the left). Gentle look-around with right stick or drag, no auto-spin.
- Leave exposure alone: the tuned auto exposure (#345 "Truest" band) handles the light. Optional on PC High and Ultra
  only: a little depth of field focused on the boat in the showroom. No extra lights: the real sky is the studio, which
  is also what makes the conditions preview honest.
- Build it on the photo-mode camera, not beside it. `Inputs/photo-mode/brief.md` (28dfb5d1, step 6) has photo PR 1 build a
  standalone, reusable `AFreeCamera` (fly, look, floor and ceiling, leash anchor as a parameter, sphere sweep, an orbit
  toggle for boat portraits), entered with `SetViewTargetWithBlend`. The front end uses that same actor in its orbit
  mode, so there is one camera class for photo mode, Replay's free camera and the menus. What the front end adds to it:
  - Orbit parameters it can set from code: target (boat center of rig), yaw, pitch, distance, zoom range, a lateral
    target offset, and an auto-spin rate with an idle delay. Named framings (Title, Showroom, Weather) are just preset
    values for these, blended over about 0.6 s.
  - The floor rule is shared (water surface + 0.15 m at the camera, terrain + 0.5 m); the showroom's pitch limits sit
    above it.
  - Input comes from Slate, not `IMC_Photo`: the front end widget has focus, so `SSailFrontEnd` forwards stick, drag and
    wheel to the camera's orbit setters. The camera class must not assume its own input context is active.
  - The Title framing can stay on the pawn's chase boom; only the Showroom and Weather framings need the view target on
    the free camera. Hand back to the chase camera on Cast off and on Resume.
  - Controller: in the menus, a press of View hides the panels (section 2). Photo mode's "hold View 0.5 s" toggle is
    only live in game, so the two don't clash; keep it that way when wiring input.
- So the PC boat-screen PR waits for photo PR 1 (the `AFreeCamera` class) as well as this brief's PR 1.

## 4. Showroom hold (pawn)

Today's hold freezes the boat. For the showroom and the conditions preview the boat should float and respond:
- New hold mode (e.g. `SetHeldByUI(EUIHold::Showroom)`): physics steps run with the trim assist trimming for a close
  reach and the rudder holding that heading, so it heels, pitches and fills its sails with the live wind and waves.
- Keep it on its spot: a soft XY spring (or a re-centre when it drifts more than about 2 m) so it never sails away or
  onto the shore during a long stay on the menu. Yaw follows the wind so the sails stay drawing as the wind is changed.
- The showroom spot: open water near the launch spot with a clear background, not the slip. If the launch spot is a
  slip or a dock, pick the nearest open-water point (the launch spot data already has headings and positions).
- Crew stays aboard (it shows scale). Traffic and ghost boats are untouched.
- `ResetBoat()` inside `SetBoat` must place the boat at the showroom spot while in the showroom, not the launch spot.

## 5. Swapping the boat (async)

- On focus change, wait 200 ms (so flicking across the strip doesn't load every boat), then start an async load of that
  boat's meshes with `FStreamableManager::RequestAsyncLoad` on the same soft paths `ModelMeshesFor` uses. When it lands,
  call `SetBoat` (it then finds the meshes already in memory). Hide the swap with a short dip: the camera pulls back
  about 10% and the boat fades or the screen dips 150 ms. Show a small spinner on the card while loading.
- Add a `SetBoat` variant that keeps the showroom pose (no launch-spot reset) and logs load and build times separately:
  "Showroom swap <boat>: load X ms, build Y ms".
- Memory: keep at most the shown boat and the one loading resident; release the previous boat's handle once the new
  one is shown. The hero J/22 always stays (it is the default). Measure with `memreport -full` after cycling all 8 on
  Mac Low (the min-spec stand-in) and PC Ultra; budget is no more than the in-game peak with the largest boat plus
  150 MB.
- Hitches: no frame over 33 ms on Mac Medium during a swap. Shown within 400 ms of focus on PC, 800 ms on Mac.
- Title remembers the boat: on start, if the save's last session used another boat, the title shows that one (same
  async path). Choosing a boat and then backing out to the title keeps the chosen boat behind the title.
- Packaging: async loads by path need the assets cooked. They are loaded by path today, so they should already be in
  the cook, but run the packaged-build check (cycle all 8 in a Shipping build) before merge.

## 6. Live conditions preview

- New `ASailingGameMode::PreviewConditions(const FSailConditions&)` that runs the `ApplyConditions` path, plus
  `EndPreview(bool bKeep)`. Call it from every change on the Conditions screen: right away for discrete choices
  (preset, sky, real day), debounced 150 to 250 ms for slider drags and the wind dial.
- Blends, so the world eases rather than pops: time of day moves the sun continuously while the slider moves (cheap),
  but sky light and reflection recapture only after the slider settles; sky preset changes cross-fade cloud cover, rain
  and fog over about 1.5 s; wind speed eases over about 2 s so the waves and heel build up naturally. If the weather
  system has no blend for a value, a snap is acceptable for the first PR; note which ones snap.
- `ApplyWeatherSettings` restarts the weather timeline, so a preset with a storm later in the day shows the start of
  that day at the chosen time, which is what the player will get when they cast off. Good; keep it.
- Real days: loading a `.wxday` is a file read; fine on change, not per frame.
- Lake level: check what a change rebuilds (water height, shoreline, docks). If it is heavy, apply it on release only.
- Audio follows: wind in the rigging, rain and water sounds should already follow the weather; make sure the front-end
  doesn't mute the ambience, because "feel" is half sound.
- Over the world (artboard 3): a "Live preview" badge with the clock, a wind arrow and "N kn from X, gusts to Y" near
  the boat, and the "What to expect" text as a caption bottom right.
- Layout: all controls in one left column (about 540 px, translucent); presets as a 2-column grid; then wind speed,
  gusts, wind from, sky, time of day, date, air temp, lake level or tide; Next at the bottom. The real-day row stays,
  under the presets. V / View hides the panel for a full-screen look; right stick or drag looks around.
- In game (Pause > Change conditions): unpause the world while this screen is open (keep the boat held in the showroom
  hold), preview live, Apply keeps it, Back restores the conditions from when the screen opened (snapshot on entry).
  Photo mode's brief adds a clock pause switch (`SetWorldHeld`-style, rule 9); whichever lands first, the Conditions
  screen must leave the clock running and the other pause path must not override it.
- Front end: no revert needed; the preview is the pending choice and Back keeps choices, as now.
- World behind the menus (pending Bean's answer): if he picks "load the picked world", leaving the World screen with a
  different world loads it behind the menus (a short loading wipe, the front-end state carried in
  `USailSessionSubsystem` across the travel), so the showroom and preview show the real place. Cast off can then skip
  the reload when world and launch spot already match. If he picks "keep the lake", show a one-line note on the
  Conditions screen ("Preview on Lake Ray Hubbard; you'll sail in <world>").
- Online readiness: the preview is local presentation only. Keep it in a client-side path that the session commit
  replaces, so a later server-owned weather doesn't inherit menu changes. The camera rig may use the first player
  controller (client-side only), per the rules.

## 7. Suggested PRs (one per phase, against main, not stacked)

1. Mac (wiring and physics): showroom hold, `SetBoat` keep-pose variant with async preload and timing logs,
   `PreviewConditions`/`EndPreview`, unpause in game while previewing, title shows the last boat. Testable from launch
   args, e.g. `-SailingFrontEnd=Boat -SailingUIScript=Right,Wait,Right,Wait,...,Log` and a new `-SailingShowroom=<type>`.
2. PC (UI and graphics), after 1 and photo PR 1 (`AFreeCamera`) merge: orbit parameters, auto spin and the three
   framings with blends on `AFreeCamera`, Boat screen layout, strip,
   orbit and zoom input, auto spin, View mode, optional DOF. Mac gate (Medium 60 / High 45) with the Boat screen open
   and while cycling all 8 boats.
3. PC, after 2: Conditions layout, live preview hookup and blends, wind HUD and caption, in-game revert. Mac gate with
   the Conditions screen open while dragging time of day and switching Clear to Storms.
4. Only if Bean picks it: load the picked world behind the menus (Mac, it is session and travel wiring).

Each PR: stills at 1440x1080 and 1920x1080 for the docs folder (Boat with three boats including the Lagoon 42 and a
dinghy, View mode, Conditions at 07:30 clear, 15:00 fair, 19:00 storms, fog), the swap and memory numbers, and the
packaged-run check.

## 8. Questions still open (lanes decide unless Bean says otherwise)

- Whether focus or a click should swap the boat: the brief says focus (racing-game feel), debounced.
- Exact showroom spot per launch spot: pick by eye in stills.
- Whether the Maxi (prologue boat) belongs in the strip: today the screen says "Fleet of eight", so it stays out.
