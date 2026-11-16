# Camera views

Plan: the "Camera Views Plan" page (Nov 16 2026). Bean's answer to its nine questions: "go with your picks".
Slice 1 is the chase camera and the view cycle. Slice 2 is photo mode's movement. Slice 3, the new cameras (masthead,
bow, low water, side, drone), comes after the vertical slice.

## Slice 1: the chase camera and the view cycle

The old chase camera turned about the boat's waterline and lifted its lens a third of the masthead (3 m on the J/22).
That push stayed the same whatever the zoom. The result was a lens about 7 m up, looking 14 deg down, and a boat that
slid down the screen and out of the frame as you zoomed in.

`ChaseCamera.h` now holds each rig as plain numbers, so the tests can check every boat at every zoom:

| View | Turns about | Default distance | Lens push | Pitch | Follows the hull |
|---|---|---|---|---|---|
| Chase (default) | boom height (gooseneck; 0.6 to 4 m) | the larger of 1.8 boat lengths and 1.55 masthead heights | 6% of the arm | -4 deg | yes, with a lag |
| Overview | the waterline | 2.4 boat lengths | a third of the masthead at the default arm, scaled with the arm | -14 deg | yes, with a lag |
| Classic | the waterline | 2.4 boat lengths | a third of the masthead, fixed | -14 deg | no (the old rig exactly) |
| Helm | the cockpit view (`UpdateCockpitCamera`) | | | | |

On the J/22 the chase lens is about 3 m over the water, 14 m astern, with the masthead in a 16:9 frame at 90 deg.

- **Zoom** works by ratio: each wheel notch moves the camera to 0.88 of its distance, inside each rig's own range.
  Because the push grows with the arm, the boat keeps her place on screen at any zoom.
- **Following the hull:** while nobody is turning the camera, the arm follows the hull's heading through the spring
  arm's rotation lag (`YawLagSpeed`). A tack turns the boat in the frame instead of spinning the world.
- **Easing back:** 2.5 s after the player's last look, the view eases back behind the boat (time constant 0.8 s), keeping
  the pitch. Settings > Camera returns behind turns this off.

### Keys

| Control | Keyboard and mouse | Pad |
|---|---|---|
| Change view (Chase, Overview, Helm) | F5, or the middle mouse button | tap the right stick |
| Helm view on and off | `\` | |
| Dock lines | T | hold the right stick for half a second |

- The pad's dock lines moved from a press to a hold so the tap is free for changing the view (`SailingBindings::IsHoldAction`).
  Briefings say "(hold)" on the pad.
- The pad's look now has a response curve (exponent 1.7, for fine aim near the centre) and turns in degrees per second,
  not per frame. The speed is the same as before at 60 fps, and the same at 30 or 120.

### Settings > Display

- **Camera:** Chase, Overview or Helm. This is the view a sail starts in, and the cycle remembers the last one you chose.
- **Look speed:** 25 to 300%.
- **Invert up and down.**
- **Camera returns behind.**

They are saved under `display` as `cameraView` (`"chase"`, `"overview"` or `"helm"`), `lookSpeed`, `invertLook` and
`cameraRecentre` (docs/save/).

### Measured runs

- Benches, gates and the demo that name no view keep the Classic rig, so their numbers and screenshots don't move.
- `-SailingView=Chase|Overview|Helm` picks a view for stills and for any run.
- Automation tests use the players' rig.

### Tests

- `SailingSim.Visual.ChaseCamera.Rig`: every boat and rig, at the closest, default and farthest zoom, keeps the boat in
  frame and the lens over the water. Zoom never moves the boat on screen. The chase camera is lower than the old view, with
  the masthead in frame. Classic is the old rig.
- `SailingSim.Visual.ChaseCamera.Controls`: zoom ratio and limits, easing back, the view cycle and names, and the save.
- `SailingSim.Visual.ChaseCamera.Pawn`: a sail starts in Chase at boom height. The cycle runs Chase, Overview, Helm and
  back. The lens is low with the boat near the middle, Overview is higher, and zoom keeps the boat in place.
- `SailingSim.UI.PadNoCollisions` allows the dock lines' hold and the view's tap on the right stick.
