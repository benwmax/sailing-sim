# True Replay: design and build brief (Mac lane)

Written Oct 27 2026 against sailing-sim main 9b16cda (#355). Bean's ask: "Why does the Replay option load a live session that I can control? It should just replay a previous session and have controls for speeding up time and fast forwarding/rewinding."

## 1. What happens today (why Bean sees a live session)

- Title menu `Replays` (`UI/SailFrontEnd.cpp:533`) calls `ASailboatPawn::WatchLastRun()` then `Close()`.
- `WatchLastRun()` (`SailboatPawn.h:155`) does nothing when `LastRun` is empty. At the title `LastRun` is always empty: runs live only in memory (`FReplay Recording, LastRun`), and a run only becomes `LastRun` when the *next* run begins (`BeginRun`, >20 s). Nothing is saved to disk.
- So the menu closes and the player is handed the live backdrop session. That is the bug Bean hit.
- When a run does exist (the `,` key in game), `SetWatching` hides the player and puts the camera on a ghost pawn fed by `FReplay::Sample`. But:
  - Only the player's boat is recorded. AI racers, traffic and power vessels keep sailing live.
  - The world clock keeps advancing (`ASailingGameMode::AdvanceClock` only stops when the world is paused), so wind, waves, gusts, sky and tide show *now*, not the recorded moment. The replayed hull sits on the wrong waves.
  - The player's own boat stops stepping while hidden, then jumps to the clock on exit (`SailboatPawn.cpp:1097`).
  - Controls: Left/Right jump 10 s, Up/Down change speed 0.25x to 16x, no pause, no reverse play, no timeline, no on-screen controls.
  - The stale comment at `SailboatPawn.cpp:1027` ("the world holds still, everything runs on the boat's clock") predates the world clock.

What is good and should be kept: `FReplay` already records full `FBoatState` + sail strips at 10 Hz with a binary search `Sample()` and interpolation. The ghost pawn, ghost material and orbit camera all work.

## 2. Research: how games do it

- **Input recording + re-simulation** (Trackmania ghosts, RTS games): tiny files, but needs bit-exact determinism across machines and builds. Rewind still needs periodic full snapshots. Our physics is double precision on Mac (ARM) and PC (x64) with different compilers, AI trimmers and crew reaction (#350); a recording would drift between machines and break on every physics PR. Not a fit.
- **State snapshots** (iRacing .rpy, Forza/GT replays, most sims): record each car's pose and visible state at a fixed rate, interpolate on playback. Seeking and rewind are free because any time is a lookup. Cost is file size, which is fine at 10 Hz with quantizing.
- **Unreal's built-in Replay System (DemoNetDriver)**: records *replicated* actor data with checkpoints every 30 s by default and scrubs with `GotoTimeInSeconds` by resetting the world and replaying checkpoint + deltas. Our sim lives in plain C++ (`SailingPhysics`, `FBoatModel`, `FTrafficSim`), not replicated UObjects, so DemoNetDriver would capture almost nothing without making the sim replicated first. It also rebuilds the world on every scrub (slow with our streaming). Not a fit now; revisit for v3/v4 online.
- **Hybrid used by many sims**: snapshot the moving things, and recompute everything that is a pure function of seed + time. That fits us well: `FWeatherSystem::Evaluate(T)`, `FWaveField(Seed)`, ocean, tides (`Tides.CurrentAt(..., UnixTime)`), sun and sky are already deterministic from seed + world-clock time (online-readiness rules 3 and 5).

Sources: Epic, [Replay System](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-the-replay-system-in-unreal-engine) and [DemoNetDriver and Streamers](https://dev.epicgames.com/documentation/en-us/unreal-engine/demonetdriver-and-streamers-in-unreal-engine); [UDemoNetDriver::GotoTimeInSeconds](https://docs.unrealengine.com/4.26/en-US/API/Runtime/Engine/Engine/UDemoNetDriver/GotoTimeInSeconds/index.html); general replay design notes at [bugnet.io](https://bugnet.io/blog/how-to-build-a-replay-system) and [Kodeco](https://www.kodeco.com/7728186-creating-a-replay-system-in-unity).

## 3. Design

**Approach: state snapshots for vessels, world recomputed from seed + recorded clock.**

### 3.1 What a replay file holds (`FReplayFile`, versioned, rule 7)
- Header: format version, game build id, string ids for world/area, launch spot, boat type, mode (Free/Drill/Race/Career lesson), label, real start date/time (UTC), duration.
- The full `FSailSessionConfig` (conditions, real day, traffic level, easy/realistic) plus the weather seed, wave/ocean seeds and the world-clock time at run start. This is what lets playback rebuild the same wind, waves, sky and tide.
- Event track: weather cues (`CueSquall`, `CueClearing`, `LocalizeStorm`, scene cues), race signals and results, drill pass/fail, collisions, capsizes, horn/whistle, log entries. Each with clock time. Rule 8: results come from the sim, so the file just stores what the sim said.
- Vessel tracks, keyed by a stable string id (player = `player`, race boats `race:<n>`, traffic `traffic:<Id>`, power vessels `power:<Id>`):
  - Player: the existing `FReplayFrame` (full state + strips) at 10 Hz, plus crew pose inputs the crew anim needs (crew offset is already in state; add helm/trim hand targets if the anim reads them).
  - Other boats: a light frame (position, orientation, boom, jib, spin, rudder angles, sides, reef, heel, speed, sail flow per sail), 5 Hz. Power vessels: x, y, heading, speed.
  - Vessels appear/disappear with spawn/despawn events.
- Size: player ~550 B/frame raw; quantize (positions to cm as int32 relative to an origin, angles as int16, quats smallest-three) and zlib the file. Target under 4 MB for a 40-minute run with a race fleet.

### 3.2 Recording
- Move recording out of the pawn into a `UReplayRecorder` (world subsystem or game mode component): it takes the list of vessels from the game mode / traffic manager (rule 2: no "the player" lookups; it records every vessel it is handed).
- Samples on world-clock time at fixed intervals (not frame time), so playback lines up with the clock.
- A run starts at session start, reset, drill start, race start (same triggers as `BeginRun` now). A run ends on the next of those, on returning to the title, or on quit. Runs over 20 s are written to `Saved/Replays/<utc>-<mode>-<boat>.sreplay` on a background thread.
- Keep the 40-minute cap; long Free Sail sessions roll into a new file every 40 min.
- Retention: see Bean's decision (default: the last 10 runs auto-kept, plus any the player stars; starred ones never auto-delete).

### 3.3 Playback ("Replay mode", a separate session type)
- Title > Replays opens a **Replays screen** listing saved runs (date, place, boat, mode, duration, race place / drill result, star, delete). Empty state says "Sail a run first; runs over 20 seconds are saved here." It never drops the player into a live session.
- Choosing one loads the recorded world/area and conditions through the normal session loading screen, with `ESailMode::Replay`: no player input to boats, no physics stepping of any vessel, traffic manager and race in "puppet" mode (they spawn the pawns the file names and pose them from the tracks, no AI).
- **The replay clock drives the world.** In Replay mode the game mode's `FWorldClock` is set from the replay clock each frame (`SetTime(StartClock + T)`) instead of advancing on its own. Weather `Evaluate`, waves, sky, sun, tides and water material then all show the recorded moment, at any speed and in reverse. Weather cues from the event track are re-applied (`ClearCues` + replay the cues up to T on every seek).
- Vessels: each frame, `Sample(T)` per track (existing interpolation), `SetGhostFrame`-style apply, no translucent ghost material (the replay boats draw as normal boats).
- Integrated visuals that are not functions of time (wake grid, sail cloth, crew secondary motion, spray particles): on any jump > 1 s or reverse play, reset them and warm up from the poses of the last 2 s (wake grid re-stamp along the track). In forward play they run normally.
- Audio: plays from the replayed state at 1x; muted except wind/water ambience above 2x and in reverse.

### 3.4 Controls (keyboard + controller, rebindable rows in Settings > Controls)
- Play/pause: Space / A (Cross).
- Speed: 0.25x, 0.5x, 1x, 2x, 4x, 8x, 16x, 32x forward; Down/Up or LB/RB step it.
- Rewind / fast forward: hold Left/Right or LT/RT plays backward/forward at the next speed up (2x, then 8x after 1 s held); tap jumps 10 s.
- Scrub: on-screen timeline, mouse drag or right stick; event markers on it (start gun, marks rounded, tacks/gybes, collisions, drill passes). Previous/next event: Q/E or the shoulder buttons.
- Cameras: chase orbit (existing), cockpit/helm, a fixed "TV" mark camera for races, and free camera (share the free-fly camera being built for picture mode). Follow target: cycle boats with Tab / Y.
- HUD toggle (H), photo mode allowed from a paused replay (that is how players will want to take race photos).
- Esc opens a replay pause menu: Resume, Restart, Sail from here (optional later), Back to Replays, Title.
- Show the in-game HUD instruments for the followed boat (speed, heading, wind) from the recorded telemetry, plus a slim replay bar with time, speed, and the run label.

### 3.5 The in-game `,` key and the ghost
- `,` mid-session opens the **just-finished or current run** in Replay mode as an overlay: the live session is paused (world paused, so the clock stops), the replay plays the current file from memory with the same controls, and Esc returns to the exact live moment. While in this overlay the world clock is driven by the replay as above, and is restored to the live time on exit.
- Ghost racing (Tab > Ghost) keeps working, now reading the saved file's player track, so you can race any saved run, not just the last one.

## 4. Online-readiness check
1 recorder and playback live in a sim/world layer, pawns only draw. 2 records a list of vessels by stable id. 3 time is the world clock (Replay mode sets it). 4 no boat input in Replay mode at all. 5 world recomputed from the stored seeds. 6 file stores string world/area ids; positions are map metres but always paired with the area id and origin (fine for a replay; it is not a persistent world placement). 7 versioned file, string ids. 8 results come from the sim's event track. 9 replay speed is a single top-level switch in Replay mode only, never inside world systems. 10 no physics cost in playback; recorder cost per vessel added to the gate report. 11 n/a.

## 5. PR plan (one PR per phase, against main, not stacked)
1. **Fix the title bug now (small).** Title `Replays` shows "No saved replays yet" when empty and never drops into the live session; `,` pauses the world while watching so the clock and the boat do not drift. Unit test: watching does not advance the clock.
2. **Recorder + file format.** `UReplayRecorder`, all vessels, event track, seeds and session config, background save to `Saved/Replays`, retention. Tests: round-trip a file, version upgrade stub, size budget for a 40-minute 6-boat race, determinism of world evaluation at a recorded T.
3. **Replay mode playback.** `ESailMode::Replay` session, world clock driven by the replay, puppet traffic/race, weather cue re-application on seek, integrated visuals reset on jumps. Gate: `scripts/gate.sh --scope world` and a new `-SailingReplay=<file>` launch arg for scripted checks (play 60 s at 1x, seek back 5 min, 16x forward, reverse 4x) with screenshots compared against live frames at the same T.
4. **Replays screen + replay HUD and controls.** List, star, delete, timeline with event markers, speed/pause/rewind/FF, cameras, rebindable rows, controller. Uses -SailingUIScript for checks, no synthetic input.
5. **Free camera + photo mode from replay** (shares the picture-mode free-fly camera; coordinate with that thread).

Acceptance (Bean's words): picking Replays never gives you a boat to sail; you watch a saved run with the same wind, waves and boats as when you sailed it, and can pause, speed up, fast forward and rewind.
