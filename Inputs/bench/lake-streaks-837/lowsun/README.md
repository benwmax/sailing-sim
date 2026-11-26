# Lake streaks at low sun: d8f2a3dc, a3f81854, a3f81854 -SailingNoWindrows (PC, Nov 26 2026)

**Builds:**
- `Windows-d8f2a3dc`;
- `Windows-a3f81854` (main with #837; it stands in for 20f03152);
- `Windows-a3f81854` with `-SailingNoWindrows`.

**Clips:** 24, 10 s each at 1080p (300 frames at 30 fps), 12 kn, AfternoonBreeze.
- **Times:** 08:00 and 18:00.
- **Places:** the club (launch 1) and 3 km out.
- **Cameras:** the default chase camera, with no capture mode, and the helm eye.
- **Course:** she sails at TWA 160, so both cameras look roughly downwind, along the streaks.
- **Files:** `compare-ls-<hour>-<place>-<camera>.webp` shows the three builds side by side: d8f2a3dc, a3f81854, no
  windrows. `zoom-ls-8h-3km-chase.webp` crops the water band of each, top to bottom. `clips/` has the 08:00 mp4s.

## What they show

**18:00 is night.** On Nov 26 the lake's sunset is about 17:20 local, so every 18:00 clip is dusk-dark water under a lit
sky. There are no streaks to judge in them. They're in `compare-ls-18h-*` for the record. A late-afternoon low sun needs
about 16:00-16:45.

**08:00 (sun about 10 degrees up, in the east-south-east), looking downwind (north):** **no bright streaks in any build.**
- d8f2a3dc, a3f81854 and a3f81854 without windrows look almost the same, in both the full frames and the water-band
  crops.
- The low sun lights the water from the side here. The glints and the sky reflection dominate, and the windrows don't
  separate from them.
- **So, from this side, #837's streaks don't add anything visible at 12 kn.** Bean's bright white streaks would likely
  need the camera looking toward the sun, where glitter lines up with the windrows, or a higher view.

**Suggested reshoot:**
- 08:00 and about 16:30, with the camera **looking into the sun**, at about TWA 60 with `-SailingCamYaw` set so the
  chase camera faces the sun;
- plus the 30 m `up30` shot file from the 2 PM set.
- Same three builds.
- Or Bean's own time and view if he sends one.

Bean's Saved was held aside and restored for every clip (7B5CA7BE).
