# C2: filming the crew (for Bean)

You film yourself sailing on a mock cockpit at home. On the PC, MetaHuman Animator's markerless body solve turns each
clip into body animation, and `Tools/capture/capture_clips.py` carries that to the game's crew (SK_Sailor and the
three MetaHumans).

**Still needed:** the body solve is a separate Fab plugin, "MetaHuman Animator Markerless Motion Capture" (Windows
only, UE 5.8+). It isn't in the engine install, so it needs your yes to install
([Epic's page](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine)).
Everything after the solve is built and tested with stand-in clips.

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

Copy the clips to the PC (`C:\dev\capture\`). The PC then does the rest:

1. Ingest them in Live Link Hub's Capture Manager.
2. Solve each one with the body solve.
3. Export each as an animation to `/Game/Crew/Capture/Solved/<clip>`.
4. Run `Tools/capture/capture_clips.py`.
5. Run the test `SailingSim.Visual.CrewCapture`.

The clips and their solves stay on the PC: `Content/Crew/Capture` is git-ignored, like the MetaHumans. Only the clip
list and the script are in the repo. C3 (Pose Search, on the Mac) builds the crew's motion from the saved animations.
