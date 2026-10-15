# C2: filming the crew (for Bean)

You film yourself sailing on a mock cockpit at home. On the PC, MetaHuman Animator's markerless body solve turns each
clip into body animation, and `Tools/capture/capture_clips.py` carries that to the game's crew (SK_Sailor and the
three MetaHumans).

The body solve is the Fab plugin "MetaHuman Animator Markerless Motion Capture" (`MetaHumanBodyTracker`, installed on
the PC Oct 15 2026 and enabled for the Windows editor only in `SailingSim.uproject`, with MetaHuman Creator, which its
performer mesh needs; both are optional, so the Mac opens the project without them). The whole chain has run on test
footage (below); it's ready for your clips.

## The camera

From Epic's [video capture guidelines](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-video-capture-guidelines-in-unreal-engine):

- **Phone on a tripod,** landscape, locked off. Don't hand-hold it and don't zoom during a take.
- **Whole body in frame, head to feet,** with a margin on every side through the whole clip, including when you hike
  out or stand to cross.
  - Place the camera about 3–4 m away, level, at chest height. Aim it at you on the bench from 30–45° forward of
    square, so it sees both your front and the arm on the tiller.
  - Avoid a low or high camera, an off-axis angle, standing too close, or any part of you leaving the frame.
- **1080p (or 4K) at 60 fps.** On an iPhone: Settings > Camera > Record Video > 1080p at 60 fps. Format: Most
  Compatible (H.264).
- **Even light:** daylight from a window, or two lamps either side of the camera. No strong back-light and no hard
  shadows across you.
- **Clothes:** fitted, plain clothing that contrasts with the background, so arms and legs read clearly. Shorts or
  fitted trousers, a T-shirt, bare feet or deck shoes. No life jacket or baggy jacket: it hides the shoulders and hips.
- **One person in frame,** and nothing between you and the camera. Keep the tiller stand-in and the line thin.

## The mock cockpit

- **The seat:** a bench or a low coffee table about 45 cm high, as the J/22's side deck. Sit on its edge as you would
  on the rail.
- **The sole:** the floor in front of the bench, as the cockpit floor. Your feet go there or against a box, like the
  opposite seat.
- **The tiller:** a broom handle or a 1 m dowel, its far end resting on a chair behind you at hip height. Hold it like
  the tiller extension.
- **The sheet:** a rope tied to something solid 1–1.5 m to your side and slightly forward, for the jib or main sheet.

Start every clip with 2 seconds sitting still, facing forward, hands on your knees. The clip list trims that off. Make
each clip 10–20 seconds long. Name the files by the clip names below, e.g. `tack_port.mov`.

## The clips

`Tools/capture/clips.csv` holds these, with each clip's trim (start, end) and its label in the game:

| Clip | What to do |
|---|---|
| `helm_steady` | Sit on the windward side, tiller in your aft hand, the sheet in the other. Steer small corrections, glance at the sails and ahead. |
| `helm_hike` | Same, then hike out: feet hooked under the opposite edge, lean back as a puff hits, ease in again as it passes. |
| `tack_port` | Helming on starboard: call "ready about", push the tiller away, duck and cross to the other side, sit and take the tiller in the other hand. |
| `tack_stbd` | The same tack the other way (port to starboard). |
| `ease_sheet` | Sitting in the cockpit facing the sail, ease the sheet out hand over hand, then hold. |
| `trim_sheet` | Pull the sheet in hand over hand, leaning back on the last pulls, then cleat it (a quick flick down). |
| `rail_hike` | As crew on the rail: sit facing outboard, legs over the side, and lean out over the lifeline, in and out with the puffs. |
| `cockpit_sit` | Light air: sit low in the cockpit, relaxed, looking around and up at the sail. |
| `cross_low` | As crew in a tack: from the rail, crouch, cross the cockpit low under the boom, settle on the new side. |

## After filming

Copy the clips to the PC (`D:\dev\capture\`). The solve reads image frames, one folder per clip, so turn each video into
PNGs first (ffmpeg isn't on the PC yet: `winget install Gyan.FFmpeg`; it's a tool, nothing of it ships with the game):

```bat
ffmpeg -i D:\dev\capture\tack_port.mov D:\dev\capture\frames\tack_port\%05d.png
```

Then one command does the rest (build first):

```bat
scripts\windows\capture-solve.ps1 -Fps 60
```

1. `Tools/capture/solve_clips.py` makes an Img Media Source, Footage Capture Data and a MetaHuman Performance (mono
   footage, body tracking on, face off) for each clip in `D:\dev\capture\frames\<clip>\`, runs the solve (blocking,
   about one frame a second on the 4090: a 15 s clip at 60 fps is about 15 minutes) and exports the body to
   `/Game/Crew/Capture/Solved/<clip>` on the plugin's MetaHuman body skeleton. It runs in a full editor window (the solve
   needs the GPU; a `-run=pythonscript` commandlet has no RHI and the performance refuses to start). `-Only tack_port`
   solves one clip; `-Resolve` solves again; `CAPTURE_EXPORT_ONLY=1` re-exports without solving.
2. `Tools/capture/capture_clips.py` carries each solve to SK_Sailor and the MetaHumans, trimmed by `clips.csv`. A solve
   is read through the plugin's performer mesh (`/MetaHumanBodyTracker/SKM_Body`), and leveled: the camera's heading and
   your place on the floor are taken out at the clip's first frame, so start every clip sitting still and facing
   forward, as above.
3. `SailingSim.Visual.CrewCapture` checks what was saved.

The clips and their solves stay on the PC: `Content/Crew/Capture` is git-ignored, like the MetaHumans. Only the clip
list and the scripts are in the repo. C3 (Pose Search, on the Mac) builds the crew's motion from the saved animations.

## Test footage (no filming)

`scripts\windows\capture-solve.ps1 -TestClip tack_port` films the game's own helm instead: `make_test_footage.py`
stages the helm MetaHuman (body, outfit, face) on a 45 cm bench, plays the synthetic `tack_port` clip on it and renders
it through Movie Render Queue as the phone would see it (3.5 m, chest height, 40 deg forward of square, 26 mm, 1080p,
30 fps) to `Saved\CaptureTest\tack_port\`, then solves and carries that like a filmed clip. Nothing licensed is in it.

![The test footage (top) and what the solve gives the crew (bottom)](solve-test-tack_port.png)

Run on Oct 15 2026: 270 frames solved in 284 s; the solve's limbs track the source frame by frame (seated reach, the
crouched cross and back), with the heading and seat height leveled. `CAPTURE_ANIM=<anim> CAPTURE_OUT=<dir>` renders any
clip on the same stage for a comparison like this one (`CAPTURE_MESH=/MetaHumanBodyTracker/SKM_Body` for a raw solve).
