# AI boat rig rebuild rate

## Why

The PC's Nov 17 profile of main (687f777c, crew view, Ultra 1080p; `Inputs/bench/profile-main-nov17/` and `split/` on the
`inputs` branch, 921eb7d8) was render-thread bound at 21.6 ms. The biggest single item was procedural mesh section
uploads ("UpdateSection RT" 5.3 ms, plus 1.8 ms on the game thread), about 16 a frame. About 10 of them were the three AI
traffic boats: each rebuilt its main, jib and telltale sections every frame, and its rig lines every frame or two.
`-SailingTraffic=0` took the view from 49.1 to 58.2 fps.

## What changed

`ASailboatPawn::UpdateRigVisuals` paces an AI boat's (and the ghost's) rig lines, sail cloth, telltales and boom by
distance from the camera (`TrafficRigRate.h`):

| Camera distance | Rebuilds |
|---|---|
| under 50 m | every frame |
| 50 to 100 m | 30 Hz |
| 100 to 400 m | 8 Hz |
| 400 m to 1 km | 3 Hz |
| past 1 km | every 4 s (all but static) |
| off screen | once a second |

Between rebuilds the sections hold their last shape in the boat's frame, so the boat still heels, pitches and moves; the
boom holds with them so the sheets and the main's foot stay on it. A rebuild happens at once when the sails change sides
(tack, gybe), a spinnaker is set or dropped, the sails are stowed, or the boat comes back on screen. Rebuilds fall on a
time grid offset per boat (`TrafficRigRate::Phase`), so the count is the same at any frame rate and the boats don't all
rebuild on the same frame. The rebuild steps the sails and the spinnaker's gybe timer by the time since the last one.

Not paced: the player's boat (rope lay sections keep their fixed vertex counts and are untouched), the gallery's display
boat, any boat with no player camera (automation), and the AI bow wave (world space on the waves, only within 120 m).
The old frame-count pacing inside `UpdateModelRig` (every 1/2/4/8/15 frames) is replaced by this.

## Measuring

Crew and traffic views, `-SailingTraffic=0` and `=1`, on the PC (Ultra 1080p) and the Mac (High). Test:
`SailingSim.Traffic.RigRebuildRate` (the rate table, frame-rate independence, stagger). Results go in the table below.

| Machine | View | Main, traffic on | Main, traffic off | #778, traffic on | #778, traffic off |
|---|---|---|---|---|---|
| PC Ultra 1080p | crew | 49.1 | 58.2 | 59.1 | 60.7 |
| PC Ultra 1080p | traffic (lake-busy) | 52.9 | 72.7 | 69.5 | 70.5 |
| Mac High | crew | (not run) | | 50.2 | 50.6 |
| Mac High | traffic (lake-busy) | (not run) | | 61.1 | 61.4 |

PC data: `Inputs/bench/pr778-7d62a930/` on `inputs` (90cba375). Insights trace of the crew view with traffic on: section
uploads 7.0 a frame at 2.39 ms of render thread (main 16.5 at 5.3 ms; the player's boat alone is 6.0), so the three AI
boats now rebuild about one section a frame between them. The runs were not in the foreground: treat 1-2 fps as noise.
MSVC build clean; RopeLay 10/10, Traffic 8/8, Race 2/2 on Windows.

Mac (Nov 17): build, RopeLay 10/10, Traffic 8/8, Race 2/2, boats gate passed 392/392. With traffic on and off within half
an fps at High, the Mac was not limited by the AI boats there (main was not re-run: its packaged app was stale).
