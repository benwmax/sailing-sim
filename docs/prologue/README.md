# Prologue: scripted scenes and crew stations

Bean's opening level replaces the Title-to-first-lesson flow: about ten minutes on a 30 m maxi in a Mediterranean
mistral (30–35 kn gusting 40, light rain, a short steep 3–4 m sea), a captain calling orders that teach the controls,
no free sailing, then a cut to the lake club and the Day Sailor career. This step builds the machinery every later
step fills with data: a scene read from a JSON file, judged by the sim, shown by the HUD.

| Step | What | State |
| --- | --- | --- |
| 1 | Data-driven scripted scenes | done |
| 2 | Crew-station control mode ([below](#step-2-crew-stations)) | done |
| 3 | The maxi class (`Tools/boats/maxi/ref.json`, `sections.json` on `maxi-hero`) | next |
| 4+ | The gale preset, the captain's voice, cameras, the first-launch flow (prologue, then Easy/Realistic, then the career) | later |

## How it runs

- **Data:** `Content/Prologue/prologue.json`, staged loose like `Content/Career` (`DefaultGame.ini`). Check it with
  `python3 Tools/prologue/validate.py` (`--self-test` shows it rejecting broken scenes).
- **Sim:** `Sailing::FScriptedScene` (`Source/SailingPhysics/Public/ScriptedScene.h`), plain C++ like `FDrillRunner`,
  with its own small JSON reader so it still builds standalone. `LoadText` checks the file; `Start(Boat, MeanWindKn)`,
  then `Update(Boat, Input, Dt)` once a physics frame on the sim clock. `FSceneInput` is the crew's input: the
  `FBoatControls`, the station they hold and the crew actions done this frame. The scene judges every answer from the
  boat's telemetry and those controls (online rule 8), never from the HUD.
- **Game:** `-SailingPrologue=1` makes a session a prologue (the first-launch wiring comes later). `ASailingGameMode`
  loads the scene, sails it on the stand-in boat and wind (`setting.stand_in`: the J/22 in 25 kn gusting 32 until the
  maxi and the gale exist; `-SailingWind`/`-SailingGust` still win), and steps it from the player's boat
  (`ASailboatPawn::TickAfterPhysics` hands over the boat, the merged controls, the player's station, the station
  controls they worked, and the **crew action** button, Space or X on the pad, which answers a call that asks for an
  action). The boat starts on the first checkpoint's pose; R
  (reset) goes back to the last checkpoint and its pose. The front end is off in a prologue run.
- **HUD:** `SSailHud` shows the caption bottom centre in the rules callout's panel ("Captain"), with the keys that
  answer it (from the live bindings), in every HUD mode.
- **Voice:** each call id resolves to `/Game/Audio/Pack/Voice/<id with . and - as _>` (`captain_ease_jib`) if the pack
  has it, played when the call or a repeat goes out. There are none yet; the caption carries the scene.
- **Save:** a finished scene is kept by id under `progress.scenes` (`FSailSave::FSceneRecord`): done, plays, best time,
  the last finish's answered, assisted and repeated counts, first completion (UTC). Added in version 1 without a
  version change (a missing field reads as empty). `IsSceneDone("prologue")` is what makes it skippable after the
  first play. Bench, capture and automation runs never write it.

## The data format

```json
{
  "schema_version": 1, "id": "prologue", "title": "Mistral",
  "setting": { "boat": "Maxi", "world": "mistral-coast", "weather": "Mistral", "rain": "light",
               "wind_kn": 32, "gust_kn": 40, "sea_hs_m": 3.5,
               "stand_in": { "boat": "J22", "wind_kn": 25, "gust_kn": 32 },
               "then": { "cut": "lake-club", "tier": "day-sailor" } },
  "assist_caption": "I've got it. Watch how it's done, then it's yours.",
  "cameras": ["deck-wide", "jib-sheet", ...], "stations": ["helm", "grinder", ...], "actions": ["clip-on", "grind"],
  "steps": [
    { "id": "ease-jib", "camera": "jib-sheet",
      "trigger": { "type": "gust", "over_mean_kn": 6, "after_s": 4, "or_after_s": 45 },
      "call": { "id": "captain.ease-jib", "caption": "Gust! Ease the jib! Ease, ease!",
                "retry": "She's rounding up! Let the jib sheet out, a good arm's length!",
                "ok": "That's it. Feel her come back on her feet." },
      "expect": { "type": "sheet", "sheet": "jib", "by": 0.12, "within_s": 4 },
      "retry_after_s": 3, "crew_takes_over_after": 3 }
  ]
}
```

A step waits for its **trigger**, then the captain makes the **call**; the scene watches for the **expected** answer.
If it does not come within `within_s`, the call repeats `retry_after_s` later (in the `retry` wording when there is
one); after `crew_takes_over_after` repeats the rest of the crew does it and says `assist_caption` (0: repeat for
ever). Nothing ever fails the scene: it only counts answered steps, assisted steps, repeats and restarts. On success
the `ok` line shows for 3 s and the scene goes to `next` (a step id, `"end"`, or by default the following step).

| Trigger `type` | Fields | Fires when |
| --- | --- | --- |
| `previous` | | the step before succeeded |
| `time` | `at_s` | the scene clock reaches it |
| `gust` | `over_mean_kn` | the true wind at the boat passes the scene's mean wind by this much |
| `twa` | `twa_min_deg`, `twa_max_deg` | \|TWA\| is inside the band |
| `heel` | `heel_above_deg` | \|heel\| is above it |
| `speed` | `speed_above_kn` | boat speed is above it |
| `past-mark` | `bearing_deg`, `meters` | she has sailed this far along the bearing (true) from where the scene started |

Every trigger takes `after_s` (at least this long after the step became current); all but `time` take `or_after_s`
(fire anyway after this long, so a calm patch never stalls the story).

| Expect `type` | Fields | Answered when |
| --- | --- | --- |
| `none` | `seconds` | narration: that long after the call |
| `sheet` | `sheet` (main, jib), `by`, `at_least`, `at_most`, `controls` | eased (`by` > 0) or trimmed (`by` < 0) that far from where it was at the first call, and / or past an absolute value (0 = in, 1 = out) |
| `tack` / `gybe` | | the wind is on the other side and settled: \|TWA\| 30–100 for a tack, over 100 for a gybe |
| `hold` | `hold_s`, `twa_min_deg`/`twa_max_deg`, `max_heel_deg`, `min_speed_kn`, `station`, `controls` | all the given conditions held for `hold_s` |
| `station` | `station` | the crew member holds that station |
| `action` | `action` | the crew action was done after the call |

`controls` (step 2) names station controls the crew member must work after the call, in that order, at the step's
station: `wheel`, `jib-sheet`, `grinder`, `main-sheet`, `traveller`, `traveller-dump`. All take `within_s` (default 10). Every step names its `station` (one of the scene's `stations`: `helm`, `jib-trimmer`, `main-trimmer`): the scene puts
the crew member there when the step begins. A step may be a `checkpoint` (a restart point) with a `restart` pose
(`twa_deg`, `speed_kn`: where the game puts the boat), and a `camera` (one of the scene's `cameras`: a named view the
renderer may use). Unknown fields, triggers and expectations, repeated or reserved ids, a `next` that names no step, a
camera, station or action the scene does not list are all refused by both the loader and the validator; the validator
also wants call ids under `captain.`, captions under 120 characters, a pose on every checkpoint, the first step a
checkpoint, every step at a station, every step reachable and the scene reaching its end. A control the step's
station does not work is refused by both.

## The seven steps

Placeholder captions in the captain's voice; the later steps only change data.

| # | Id | Station | Trigger | Call | Answer | Camera |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `clip-on` (checkpoint, TWA 60 at 8 kn) | jib trimmer | 3 s in | "Clip on to the jackline before you do anything else." | action `clip-on` in 10 s | deck-wide |
| 2 | `ease-jib` | jib trimmer | a gust 6 kn over the mean (or 45 s) | "Gust! Ease the jib!" | the jib sheet eased 0.12 in 4 s | jib-sheet |
| 3 | `ready-about` (checkpoint, TWA 55 at 8 kn) | helm | 8 s after | "You're on the wheel. Ready about!" | a tack in 25 s (the crew work the sheets) | helm-over-shoulder |
| 4 | `grind` | jib trimmer | at once | "Back on the jib. Grind! Bring the new sheet in, all the way!" | the grinder, jib in to 0.15 in 14 s | grinder |
| 5 | `take-helm` (checkpoint, TWA 150 at 10 kn) | helm | 6 s after | "Take the helm. Bear away and let her run down the face of this one." | the wheel, TWA 130–170 for 8 s | wave-face |
| 6 | `dump-main` | main trimmer | a gust 8 kn over the mean, 10 s on (or 40 s) | "Squall! Dump the traveller, then ease the main!" | the traveller dump, then the mainsheet, main out past 0.8 in 6 s | squall-astern |
| 7 | `the-break` (checkpoint, TWA 140 at 9 kn) | helm | 12 s after | "There's the break. Harbour on the bow. Bring her up onto a reach." | the wheel, TWA 60–120 for 6 s, then the end | harbour-ahead |

![The captain's call over the HUD (packaged High, the first call; Space answers it)](callout.jpg)

## Measured

Oct 18 2026, M5 Pro, packaged build: `scripts/gate.sh --scope ui` passed (181 tests; helm-eye High 60.5 fps, beam8
High 64.2). With the scene running and the callout up (`ONLY=beam8 BENCH_EXTRA=-SailingPrologue=1
scripts/bench-visual.sh 12 prologue-callout High`) beam8 High is 64.5 fps; the storm view on Medium is 68.5 fps.

## Tests

- `SailingSim.Prologue.Scene`: the whole scene headless on the J/22 stand-in in 25 kn with a scripted crew member at
  the stations the scene names (the wheel, the jib sheet and grinder, the traveller dump and mainsheet) and the rest of
  the crew in `FStationControls`; gusts to 35 kn when a step waits for one. Oct 18 2026: all 7 steps answered, none
  assisted, no repeats, 83 s of sim time, the calls in order with captions and camera hints; the result saved by id
  and read back (two plays, best time kept, an unfinished run ignored).
- `SailingSim.Prologue.Repeats`: ignoring the first "ease the jib" brings the softer repeat and the scene still finishes
  (7 answered, 1 repeat, 90 s); a crew member who never answers gets 6 steps done by the crew after 17 repeats and the
  scene still finishes (533 s); a restart after the tack goes back to its checkpoint and the scene finishes.
- `SailingSim.Prologue.Validator`: the shipped file loads; an unknown trigger, a dangling `next`, a repeated id, an
  unknown expectation, an unlisted camera, a misspelt field and broken JSON are each refused with a reason.
- `SailingSim.Prologue.Stations` (step 2): the merge gives the crew every control the player's station does not work;
  a player at the jib on the wheel, mainsheet and traveller dump leaves the boat sailing exactly as without; the grind
  times above (4–12 s in 25 kn, quicker in 12 kn); the playthrough at the stations.
- `SailingSim.UI.GamepadBindings`: the station layer keeps its buttons through the boat layer's swaps and swaps within
  its own.
- `SailingSim.Save.RoundTrip` carries a scene record.

The J/22 will not tack on the helm alone in 25 kn (`RunTack(25)` fails; 20 kn tacks in 6.3 s), so the crew tack the
way a crew would in heavy air: the jib let fly and the main in hard to head up, then the jib held aback and the main
eased to push the bow down onto the new tack. Since step 2 that is `FStationControls`' crew, so a player at the wheel
gets it too.

## Step 2: crew stations

Bean's design: in the prologue the player is crew on a big boat and works one station at a time; the scene moves them
between stations and the rest of the crew hold everything else, so a player at the jib cannot steer.

- **Sim:** `Sailing::FStationControls` (`Source/SailingPhysics/Public/CrewStation.h`, plain C++). `Reset(Boat,
  Controls, Station)`, `MoveTo(Boat, Station)`, then `Step(Boat, FStationInput, Dt)` every physics step returns the
  controls to step with: `Merge(Station, Player, Crew)` takes the controls the station works from the player's hands
  and the rest from the crew. Ownership: the helm the tiller (as a wheel), the jib trimmer the jib sheet (and backing
  it), the main trimmer the mainsheet and traveller; `None` (normal sailing) everything. `TakeWorked()` reports the
  station controls the player worked (`StationControlBit`), which the scene reads as `FSceneInput::Worked`.
- **The crew:** `FAutoTrim` on the sheets, sail shape and hiking; `FAutopilot` on the wheel holding the course the
  player left (no higher than close-hauled); and the heavy-air tack while the player steers one (the J/22 will not tack
  on the helm alone in 25 kn): as the helm goes down the jib is let fly and the main hard in, through the wind the jib
  is held aback and the main eased, then the new sheet is ground in.
- **The wheel:** the tiller keys or stick turn it at the boat's rate (`WheelHardOverSeconds`, 0.9 s amidships to hard
  over on the stand-in) and it stays where it is put.
- **The grinder:** trimming the jib in at a station is grinding, for the crew too. Line speed is
  `effort x min(MaxLineSpeedMs, efficiency x GrinderPowerW / sheet load)`: 300 W at the handle, 80% through the winch,
  0.6 m/s unloaded, over 3 m of sheet travel. The sheet load is the jib's sail force from the telemetry times 1.6 (the
  clew holds the leech and foot; Harken's sizing rule, 0.00431 x area ft² x AWS kn² lb, is 2400 N for the J/22's jib
  at 30 kn apparent), or 0.5 rho AWS² x the jib's area before the first step. Hold the grind key to grind, or tap it
  (each tap is 0.35 s of grinding, about half a turn); the jib-trim key grinds too. Through the wind the old sheet is
  let go (the jib sheet goes to fully eased) and the new one has to be ground in. Easing is free (0.5 of the travel a
  second).
- **The main trimmer:** mainsheet and traveller at the pawn's usual rates; the traveller dump puts the car to leeward
  in one go.
- **Game:** the pawn is in station mode whenever a scene runs (`ASailboatPawn::UpdateStations`, never on traffic boats
  or the ghost; normal mode is unchanged). The player's hands go to the station merge each frame instead of straight to
  the controls, and the steps run the merge (`FBoatStepJob::Stations`, on the physics task). The scene's station order
  arrives by `GetStationSerial()`; a reset to a checkpoint starts the crew again from the reset boat.
- **Input** (built from `USailingInputSettings`, rebindable in Input.ini and on the Controls screen in both columns):

  | Command | Key | Pad |
  | --- | --- | --- |
  | Crew action (answer the captain) | Space | X |
  | Grind the jib winch (tap or hold) | G | A |
  | Dump the traveller | X | B |
  | Move to the next station | F | Y |

  These four are a **station layer** (`SailingBindings::IsStationAction`, `SameLayer`): only live at a crew station,
  where the crew hold the boat's other commands, so they share keys and buttons with wing-on-wing, the backstay,
  learning mode, righting and hiking without clashing; a rebind swaps only within its layer (Menu and the controls
  card clash with both). At a station the pawn ignores the boat's other button commands.
- **HUD:** the callout's header shows the station ("You: jib trimmer"); its hint is the key for the next control the
  call asks for ("G: grind (tap or hold)", "X: dump the traveller", "A / D: turn the wheel"), or the station key when
  the player has walked away from the step's station. The corner hint offers the station key instead of steering away
  from the helm.

![The callout with the station (High, the first call: Space answers it, the player is on the jib)](callout-station.jpg)

### Measured (step 2)

Oct 18 2026, `SailingSim.Prologue.Stations`: grinding the J/22's jib sheet from fully eased to 0.15 (the grind step's
"all the way") takes **6.8 s** of grinding in 25 kn and **4.5 s** in 12 kn (power-limited for the last metre in the
gale, at the winch's top speed in the breeze). The whole scene with the scripted crew member at the stations: all 7
steps answered, none assisted, no repeats, 87 s, 2.6 m of sheet ground; the stations at the calls are jib trimmer,
jib trimmer, helm, jib trimmer, helm, main trimmer, helm.

Packaged build, Oct 18 2026: `scripts/gate.sh --scope ui` passed (182 tests; helm-eye High 60.3 fps, beam8 High
63.0); the storm view on Medium (`ONLY=storm scripts/bench-visual.sh 12 stations-storm Medium`) is 68.3 fps.

## What the later steps need

- **Step 3, the maxi's stations:** `FStationConfig::For` returns the J/22 stand-in's hardware for every boat; the maxi
  needs its pedestal grinders (several crew, more power), longer sheets, a slower wheel and its own sheet load. The HUD
  draws no wheel yet (`GetWheel()` is there for it).
- **Step 3, the maxi:** `setting.boat` names it; drop `stand_in` (or keep it for the tests) and retune the sheet
  amounts and TWA bands on the maxi's polar.
- **The gale preset and the mistral world:** `setting.weather`, `world`, `rain`, `sea_hs_m` are recorded but not
  applied yet; the game mode applies only the stand-in wind and gust.
- **Cameras:** the renderer reads `FScriptedScene::GetCamera()`; nothing consumes it yet.
- **Voice:** record the seven calls (and repeats) as `/Game/Audio/Pack/Voice/captain_<step>` with licence rows.
- **The first-launch flow (step 7):** title, prologue, Easy/Realistic, career; skip from `IsSceneDone("prologue")`;
  `setting.then` names the cut (`lake-club`) and the tier (`day-sailor`).
- **Pacing:** the real scene is about ten minutes; the placeholder steps run in a minute and a half when every call is
  answered. Longer narration (`none` steps) and the maxi's slower manoeuvres make up the rest.
