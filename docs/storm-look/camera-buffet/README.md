# Storm look: camera shake (`FCameraBuffet`)

A camera on a boat takes the boat's blows: a hard slam or a sea coming aboard jolts it, and strong wind makes it
tremble. Bean asked for it as a setting (Settings > Display > Camera shake, on by default, saved as
`display.cameraShake`).

## The model (`Source/SailingPhysics/Public/CameraBuffet.h`, plain logic, no randomness)

- **Kicks.** Each fires on the rising edge of its event, so a bow held in a wave kicks once:
  - a slam is the water closing on her bow faster than 1.2 m/s, with strength (closing - 1.2) / 1.3;
  - a sea aboard is more than 3 cm of green water, with strength 0.7 x depth / 15 cm.
- **Envelopes.** Each kick feeds two:
  - a judder at 7 Hz (e-fold 0.12 s, gone in about a third of a second);
  - a lurch at 1.6 Hz (e-fold 0.4 s, about a second), alternating side from kick to kick.
- **Size at the hardest kick:** about 3 cm up and down, 1.5 degrees of pitch and a degree of roll.
- **Tremble.** Past 11 m/s (22 kn) of apparent wind the camera trembles, full by 21 m/s: a sum of sines of the world
  clock, a tenth of a degree and a few millimetres.
- `SailingSim.Visual.CameraBuffet` checks that:
  - a breeze is still;
  - a 2.5 m/s slam kicks it (0.5 to 2 degrees, 1 to 5 cm);
  - a held bow settles;
  - it is settled a second later;
  - a sea aboard kicks it;
  - a gale's wind trembles it a little.

## In the game (`ASailboatPawn::UpdateCameraBuffet`)

- The inputs come from `UpdateBoatWetness`: the bow's closing speed while it is in the water and the green water's
  depth.
- The chase camera's relative transform is set to the shake; nothing else uses it. The cockpit view is placed in the
  world every frame, so the shake is added after it.
- It is off when:
  - the setting is off;
  - in photo mode, the capture mode or a watched replay;
  - in a measured run (`USailingSettings::IsMeasuring`);
  - with `-SailingNoCameraShake`.
  When it turns off, the chase camera's transform is reset once.
