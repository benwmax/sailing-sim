# #839 bow views, re-shoot 1 (fc9a8be, Ultra, 1080p)

## Why the first set's -10 and -30 looked from astern

**Files:** `pose-minus10/`, the camera json and telemetry of `bow-6kn-ahead`.
- **The convention holds:** the capture camera's json gives `bearing_off_bow_deg -10`, so the camera stands at her
  heading + bearing. That's degrees off her bow, + to starboard.
- **The stand is fixed:** it's placed once, at the start, and doesn't follow her.
- **She isn't steered:** `bow-scenes.csv` has no `-SailingDemo`, so `-SailingHoldTWA` doesn't steer.
  - In the telemetry her TWA drifts 97 -> 83 -> 80 -> 60 -> 51 over 3-15 s while her heading swings 93 -> 132.
  - At about 5.6 kn she sails past the fixed stand, and the still at 15.5 s sees her from astern.
- **Fix for the CSV:** add `-SailingDemo`, or take the still earlier.

## This set: the game's own camera, not capture

**Settings:** `-SailingCamYaw=10|30|90 -SailingCamPitch=-8 -SailingCamDist=7`, `-SailingDemo` at TWA 90, at 6 kn (10 kn
wind) and 7 kn (15 kn), new against `-SailingClassicBowWave`.

**Finding: `-SailingCamYaw` counts from astern** (0 = behind her).
- **10 and 30:** look down at her from just behind.
- **90:** abeam; the bow wave runs along her side, but the bow itself is out of frame.
- So these don't show the bow, and the bow-wave difference can't be judged from them.
- The HUD is on in these. Without capture mode the game draws it; the next set has `-SailingNoHud`.

**Next set (queued):** yaw **170, 150, 90**, which is 10 and 30 deg off the bow plus abeam, with the HUD off. It will be in
`bow-plus2/`.
