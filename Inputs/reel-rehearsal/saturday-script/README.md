# Saturday capture script (PC, local; tested Nov 25 2026 on Windows-83aa7652)

## Files

- `reel-saturday.ps1`: every take, in order.
- `rec.ps1`: one take. It holds Bean's Saved aside and restores it with a hash check, ends only its own processes, and
  moves the frames to `D:\dev\reel\saturday-<package>\<take>`.
- `test-profile-daysailor-certified.json`: a throwaway profile for R08. Never Bean's.

On the PC the scripts run from `D:\dev\ss-fix\Artifacts\bench`. The shot files come from `Inputs/reel-rehearsal/shots/`
in the inputs worktree. This copy is for the record; nothing here goes into the game repo.

```
reel-saturday.ps1 -Package Windows-<freeze sha> [-Res 4k|1080p] [-Only 'P2-storm','R05-tack-orbit'] [-ViewModeArg]
```

- `-ViewModeArg` uses #828's `-SailingViewMode` and `-SailingNoHullClip` once #828 is merged. Without it, P1 uses
  `-ExecCmds=viewmode ...`.
- Every take carries `-SailingShowCrew=0` (in `rec.ps1`'s common args) and `-DPCVars=r.ForceDebugViewModes=1`.

## Decisions folded in (from the dry run and the coordinator, Nov 25)

| Take | Setting |
|---|---|
| P1 | Three passes, final, lighting-only (clay) and wireframe, on the same path, light and seed. Recorded as is: in wire the sails don't draw and the sky is black. |
| P2 | Front at about 205 s of game time (`-SailingStormDelay=60`, 10 s warm-up). Now **`-SailingRecordInterval=0.75` over 600 s = 800 frames**. **Outputs:** the full take as `P2-storm-full.mp4`, and a 300-frame **`P2-storm-scrub.webp` from frames 93-392 = 70 s to 295 s of the take**. The front lands at about 195 s of the take (205 s game time less the 10 s warm-up), which is about 55-60% into the scrub. |
| P3 | `-SailingDay=2023-06-11 -SailingHour=18.892`, **TWA 90 held** through the front. |
| P4 | `p4-topdown.json` with `-SailingStartAt=6500,-1750,0`, ClearMistral 10 kn 12:00 (needs #827, now on main). |
| P5 | The rehearsed P5 (`p5-then-now.json`). With `-ViewModeArg` it adds `-SailingNoHullClip` (#828). |
| R01 | Hour **7.4**. |
| R05 | **`-SailingBenchWarmup=11.5`**: the demo tacks at 12.6 s, so the take starts 1.1 s before the tack. |
| R06 | **`-SailingUiMode=helpful`**, HUD on. |
| R08 | The Career screen on a **throwaway profile with the Day Sailor certificate earned**. It's copied fresh to `Artifacts\bench\seed\run-profile.json` each run and named with `-SailingSave=<that path>`. A measuring run ignores the profile unless `-SailingSave` names one, so it never reads or writes Bean's. **Test: the Day Sailor card shows "Certified, certificate earned", and Club Racer is open** (`R08-career-test-1080p.jpg`). The certificate *document* only appears right after passing the checkride quiz, which a script can't answer, so it isn't filmed. |
| R12 | The Sunfish tacks at 14.2 s, about 4 s into the 8 s take. |
| R13 | **Reshot underway:** a reach at 10 kn, TWA 90 held, shot file `s13b-jibclew-underway.json` (boat frame, 30 deg, 2.7 s slow push).<br>**Test:** the jib clew with its bowline and the loaded sheets, close in (`R13-jibclew-test-1080p.jpg`).<br>The shot format has no socket to lock a mount to the clew. A `mount` frame near the clew sat inside the eased jib, so I used the boat frame from just outside the leeward rail. That's the jib clew, not the main. |
| R21 | Hour 16.85, sun about 4.9 deg. |
| R22 | **`-SailingEV=-4.5`, about +1.5 EV** on the -3 the scene metered.<br>**Test:** the boat reads as a silhouette with stars and the far shore lights (`R22-night-test-1080p.jpg`). It's no longer muddy, so the hour-19.6 fallback isn't needed. |
| R03, R23 | `-SailingFrontEnd=Briefing` (with the drill) and `-SailingFrontEnd=World`, 8 s at 30 fps, HUD on. |

The R13, R22 and R08 tests ran at 1080p on Windows-83aa7652. Bean's Saved was held aside and restored (7B5CA7BE) for
each.

## R08b: the live checkride (added Nov 25, tested at 1080p)

**The throwaway profile:** `test-profile-daysailor-ready.json`, every Day Sailor lesson at silver with its quiz passed and
no checkride yet. It's copied fresh to `Artifacts\bench\seed\run-profile.json` each run and named with `-SailingSave`.

**The `-SailingUIScript`:**
1. `WaitFor:Career`, then 12 x `Tab`, then `Enter`. The Tab order is the four tier cards, the six lessons, then "Take the
   written checkride". Arrow keys stay on the tier cards.
2. `WaitFor:Quiz`, then **`Answer:all`**: the dev step that clicks each question's correct option in turn. It needs a
   Development build or developer tools.
3. A hold on the score and certificate.
4. `Escape` twice to the title, then `Down`, `Down`, `Enter` to the Logbook.

**Test** (`R08b-1-career`, `-2-score-certificate`, `-3-logbook` JPGs):
- **"answer all: ok, 12 answered"**, and the frames show **"12 of 12 right"** with the **Day Sailor certificate**
  document ("Awarded 25 November 2026", "Day Sailor certificate earned. Open now: Club Racer").
- The Logbook follows, with the entry **"Quiz after Day Sailor checkride: 12 of 12"** and the Certificates count at 1.

**Timing (re-tested Nov 25):**
- **Why the hold was short:** the UI script's `Wait` is real time (2.6 s each). Each recorded frame takes about 0.35 s of real time to render and write. So 10 Waits held the score for only 80 frames, 2.7 s of the take.
- **Fix:** the hold is now **26 x `Wait`**. In the re-test the score and certificate are on screen from about frame 60 to 255, **about 6.5 s** of the 32 s take. Then Career, the title and the Logbook follow; the Logbook holds to the end.

**Clean logbook (added Nov 25):** `reel-saturday.ps1` sets the package's own `Saved\Logbook` aside for R08b and puts the four sails in `test-logbook-clean/` in its place. After the take it moves the take's book to `D:\dev\reel\<reel dir>\R08b-checkride-logbook` and puts the package's book back.
- **The four sails:** short J/22 day sails from Rush Creek on Lake Ray Hubbard, on 7, 12, 16 and 21 Nov. Each is 1.5 to 2.5 h, in 8-11 kn, with watch entries and a lesson remark or two. There are no test names.
- **The profile's totals:** `test-profile-daysailor-ready.json` now carries matching totals, 4 sessions, 29.9 nm and 8.0 h.
- **Re-test (`R08b-3-logbook-1080p.jpg`):**
  - "In all" reads 29.9 miles, 8.0 hours, 5 sails, 6 medals, 1 certificate.
  - The list is the checkride sail on top ("25 Nov 2026, 20:00"), then the four seeded sails.
  - The page shows the session's "Quiz after Day Sailor checkride: 12 of 12".
- **Known wart, not changed:** the list shows each file's name, and the game names the file in UTC. The checkride sail at 14:00 on the game clock reads "20:00". The seeded files follow the same rule, so the list is consistent.

R08, the Career screen with "Certified", stays as the fallback. Bean's Saved was held aside and restored (7B5CA7BE) for every run.