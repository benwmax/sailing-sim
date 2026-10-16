# C1b: crew idles from motion capture

Between reactions the crew used to hold the stance exactly, apart from C1's breathing and sway. Now a clip layer plays
small motions of real people under the reaction layer: weight shifts, waits, a look round, seated idles. The stance stays
the base pose. The clip only moves the sailor about it, and heel, puff, slam, bracing and tack moves stay on top.

![The helm, trimmer and bow idling on the rail (High)](idle.gif)

Top row: the clips. Bottom row: the same run with `-SailingNoCrewClips` (stance plus the C1 reaction layer). The heads,
shoulders and trunks shift between frames in the top row. In the bottom row only the boat's motion moves them.

![Stills 2.4 s apart](idle-strip.jpg)

## Source

CMU Graphics Lab Motion Capture Database ([mocap.cs.cmu.edu](http://mocap.cs.cmu.edu)). The terms let the data go
into commercially sold products, but it may not be resold as data, even converted. Here it is compiled into the game's
code, credited in `CREDITS.md`, and has rows in `docs/licences/assets.csv`. The originals are the ASF/AMC files from the
CMU site, not a third-party BVH conversion. `Tools/crew/fetch_cmu.sh` fetches only the listed trials into
`Data/CMU/raw` (git-ignored; the site asks not to be crawled). There are no faces or video. Mixamo and Epic's Game
Animation Sample need sign-ins, so they are not used.

| Clip | CMU trial | Description (CMU) | Kind | Segment | Moves | Weight-shift onsets |
|---|---|---|---|---|---|---|
| wait | 137_28 | Normal Wait | standing | 4–15 s | trunk, arms, gaze | 14 |
| shift | 139_02 | Shifting Weight | standing | 0–7.8 s | trunk, arms, gaze | 13 |
| idle | 140_06 | Idle | standing | 9–23 s | trunk, arms, gaze | 19 |
| idle2 | 140_07 | Idle | standing | 5.5–10.3 s | trunk, arms, gaze | 4 |
| look | 139_01 | Looking Around | standing | 5–9 s | trunk, arms, gaze | 6 |
| chair | 114_05 | Sitting in chair | seated | 0–10 s | trunk, arms, gaze | 7 |
| stool | 13_04 | sit on stepstool, chin in hand | seated | 33–38 s | trunk, gaze | 4 |
| ground | 82_05 | sitting on ground relaxing | seated | 1–12 s | trunk, gaze | 7 |

That is 67 s in all. Each segment was picked from the per-second motion (`Tools/crew/cmu.py`) to avoid gestures,
sitting down and standing up. The arms of `stool` and `ground` hold a chin or a knee, so those two drive the trunk and
gaze only. (CMU's 77_02 "standing" is the same take as 139_02, so it is left out.)

## Bake

`Tools/venv/bin/python Tools/crew/bake_idles.py` writes `Source/SailingSim/Private/CrewClipData.inl` (124 KB, 35,455
values). Edit `Tools/crew/clips.csv` or the script, then rebake. Never edit the .inl.

- **Retarget.** A CMU bone turns in its parent by `C M C^-1` (ASF axis, AMC degrees of freedom). At rest every frame
  is the world's, which is how SK_Sailor's stance joints work too (`CrewSolver::Solve`: D = D(parent) R). So a CMU
  rotation becomes a sailor joint's by a change of axes. CMU is Y up and faces +Z; the character frame is X forward, Y
  right, Z up (left-handed), so R' = P R Pᵀ. The joints are pelvis (root, without the heading), spine (lower and upper
  back), chest (thorax), shoulders (clavicles), upper arms, forearms and hands. The MetaHumans take the same turns
  through `FCrewRig`. The shoulders now map to `clavicle_l/r`.
- **Motion, not posture.** Each joint becomes the motion about a slowly moving posture: R = Delta × Slow, with Slow a
  Gaussian quaternion mean over 4 s and the jitter smoothed over 0.08 s. A captured person's held posture (arms folded,
  a lean on the stool) never reaches the sailor; their shifts, sways and glances do.
- **Gaze.** The neck and head are not written to the joints, because C1 levels the head and turns it to the gaze. The
  head's turn on the neck becomes a yaw and pitch added to the gaze target, so look-arounds look around.
- **Limits.** Every joint has a limit, which the bake approaches softly (L tanh(a/L)) and the runtime clamps: pelvis
  2.5°, spine 7°, chest 6°, shoulder 6°, upper arm and forearm 14°, hand 18°, gaze 25° yaw and 10° pitch.
- **Weight-shift onsets.** The trunk's lean (pelvis × spine × chest, applied to "up"), sideways and fore and aft,
  smoothed over 0.3 s. Wherever it starts a move of at least 1.2°, the frame and direction are kept (148 onsets).
- 15 frames a second in hundredths of a degree. Played back by Catmull-Rom.

## Runtime (`CrewClips.h`, in `FCrewMotionState::Clip`)

- **Choosing clips.** Each sailor plays one clip and crossfades into the next a second before its end (minimum jerk,
  1 s). The next clip is seeded per sailor, seated clips are 1.5 times as likely as standing ones, the start point is
  random, and half are mirrored (left and right swapped; a rotation vector becomes (-x, y, -z)). Standing clips on a
  seated sailor keep 0.3 of the pelvis, 0.7 of the spine and 0.8 of the chest.
- **Per stance.** The cockpit seat and rail take the clip fully, less as they hike (half when hiked hard). The helm
  takes 0.8, since the tiller and sheet IK keep the hands anyway. The dinghy sailor takes 0.7 down to 0.3 hiked, with
  the pelvis held still: on the ILCA the strap's foot planting jumped 30 cm for a 1° pelvis turn. The crossing,
  trapeze and righting stances take none.
- **Quiet for moves.** The weight ramps to zero within 0.2 s whenever the sailor crosses (a tack or gybe), changes
  seat, braces or ducks under the boom, or with `-SailingCrewStill`. It comes back over 1.5 s once they have settled.
- **Shifts in step with the heel.** The sailor's balance roll and pitch (`FCrewBalance`, as felt in their own frame)
  pass through three 1 s lags. That leaves the trend of a puff heeling the boat and filters out the chop. When the trend
  passes 1.2°/s, the layer crossfades (0.35 s) into a clip's own weight-shift onset that moves against it: tipping
  right, it leans left; tipping forward, it leans back. A sailor facing forward (the helm) feels the heel sideways, and
  one facing across the boat feels it fore and aft, so the axis is whichever tilts more. Ten random onsets are scored
  by how near their start is to the trunk's current lean (never ahead of it) and how far they move in the next second.
  Nothing starts if the clip is already moving or leaning that way, and there is a 3 s cooldown.
- **Order in the pose.** stance → clip (pre-multiplied on each joint) → C1 reaction layer (lean to the felt up,
  breathing, sway, slam, duck, pull) → feet, braces, hands (IK) → head (level, gaze plus the clip's glance).
- `-SailingNoCrewClips` turns the layer off (the comparison above). `-SailingDebugCrew` now logs each sailor's clip
  and weight.

## Tests

- `SailingSim.Visual.CrewClipLimits`. Every baked frame, both ways round, keeps each joint and the gaze within its
  limit (4,028 frames). Of the 148 onsets, 144 lean the marked way within a second (the test needs 95 %). Then SK_Sailor
  and the MetaHumans, in every idling stance of the J/22 and the ILCA (cockpit, rail, helm, dinghy hike; sitting up and
  hiked; both sides), go through chop and a 12° puff for 20 s. The runtime keeps every joint within its limit. Compared
  with the same sailor without clips, the head moves at most 7 cm, a free hand 14 cm (bound 30), an elbow 7 cm (bound
  20) and a foot 3 cm.
- `SailingSim.Visual.CrewClipTack`. Idling on the rail, six seeds tack: the clip's weight is zero from 0.2 s into the
  crossing until the settle onto the new rail, with no joint turned by more than 0.01°. It comes back above 0.8. A 12°
  puff over 3 s, on the cockpit seat (facing inboard) and at the helm (facing forward), for 8 seeds each way: every
  sailor starts a shift against it on the right axis, or is already leaning that way. In at least 75 % the trunk then
  leans that way within a second. Measured: 30 of the 32 started one, and in 28 of those the trunk leaned that way; the
  other 2 were already leaning that way.
- C1's crew tests (`CrewHeadLevel`, `CrewMotionFeet`, `CrewBalanceStep`, `CrewFeet`, `CrewPose`, `CrewFalls`,
  `CrewCapture`), `SailingSim.Visual.MetaHumanCrew` and `SailingSim.Smoke.CrewAnimation` pass unchanged.

## Gate

`scripts/gate.sh --scope crew --label c1b` on this branch (main 6bc7495d plus C1b): build OK, tests 144 passed and 0
failed, package OK. Bench on the packaged build (`gate-c1b.csv`, game-thread slices in `gate-c1b-gt.csv`):

| View | Medium fps | High fps |
|---|---|---|
| beat15 | 84.5 | 56.7 |
| crew | 71.8 | 52.1 |
| helm-eye | 89.0 | 56.5 |
| slip | 83.8 | 52.8 |
| coast-day | 85.5 | 54.3 |

Medium's lowest is 71.8 (gate 60) and High's 52.1 (gate 45): pass.

**The clip layer's cost.** This is an A/B on the same packaged build, helm-eye and slip on High, with
`-SailingNoCrewClips` and without, run alternately twice (`clip-cost-ab.csv`). The game thread is 2.65 ms on helm-eye
and 2.75–2.76 ms on slip either way. The crew slice is 0.061–0.062 ms either way, render 18.35–18.38 and 19.04–19.11
ms, and the fps 53.4–53.5 and 51.5–51.7. That is no measurable difference against the 0.3 ms budget. The sampling
(two cursors, 35 channels, Catmull-Rom) runs on the animation workers with the rest of the C1 node. (This A/B ran
after the gate, warmer, so its fps are lower than the gate's.)

## Left for later

- There are no kneeling clips: the bow kneels nowhere in today's stances. A kneeling stance at the mast would want
  CMU's kneeling trials or a capture of our own (C2's solve).
- Each clip's arms are free motion, but the helm's hands and the trimmer's sheet hand are on IK, so for them the
  shoulders and chest carry the idle. A clip with a hand on a line would need captured holds.
- The heel trigger uses the felt tilt. A sailor who sees a puff coming might shift before it heels the boat
  (anticipation from the gaze's "upwind" glance).
