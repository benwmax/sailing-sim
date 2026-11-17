# Camera views

Plan: the "Camera Views Plan" page (Nov 16 2026). Bean's answer to its nine questions: "go with your picks".
Slice 1 is the chase camera and the view cycle. Slice 2 is photo mode's movement. Slice 3 is photo mode's menu. Slice 4,
the new cameras (bow, transom, masthead, chase boat, drone), follows. With the first release moved to the end of
November (Bean, Nov 16), slices 3 and 4 aim for the Fri Nov 27 build.

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

## Slice 2: photo mode's movement and buttons

Photo mode's camera (`AFreeCamera`) moved like a drone only. Its orbit took no movement, the wheel set a speed rather
than zooming, and on the pad the bumpers tilted the horizon while B hid the panel. Bean's picks:

- **Opening view.** Photo mode opens orbiting the boat, from where the view was (the pivot is the chase camera's, at boom
  height). Y (Tab) lets the camera fly free, and pressing it again goes back to orbiting.
- **Orbit movement.** The left stick (WASD) moves the camera round the boat and in and out, and the triggers (Q, E) move
  it over and under (`FreeCameraMath::OrbitTurnDegPerSec`, `OrbitTiltDegPerSec`, `OrbitDollyPerSec`; Shift is faster,
  Ctrl slower). The right stick and mouse turn the view as before.
- **Lens zoom.** The wheel and the bumpers zoom the lens from one focal mark to the next (14 to 200 mm, the panel's Lens
  row). Held bumpers repeat. The tilt is now on Z and C, with the panel's Tilt row; X levels the camera.
- **Speed.** Flying speed has eight steps from 0.5 to 120 m/s, each about twice the last, set with the D-pad's up and
  down or with = and -. The last step chosen is kept in the save (`display.photoSpeed`). In orbit, these keys move the
  camera in and out.
- **Back and hide.** B (Backspace) closes the panel and hints first, and leaves photo mode when they are already closed.
  A tap of View (H) hides them or shows them again. Holding View still leaves photo mode.
- **Back to the boat.** The right stick's click (F) brings the camera back to the boat's view.

Saved key lists get the new commands (`USailingInputSettings::AddMissingActions`), but not on a button another command
in the same layer already holds there. A hold and a tap may share a button.

Stills placed with `-SailingPhotoCam` fly, as before. Slice 3 moved the lens zoom off the bumpers (below).

Tests:

- `SailingSim.UI.PhotoFreeFly.Limits`: the eight speeds.
- `SailingSim.UI.PhotoFreeFly.Camera`: the orbit's moves (dolly, round, over) and that it keeps facing the boat.
- `SailingSim.UI.PhotoFreeFly.Input`: the new buttons.

## Slice 3: photo mode's menu

The panel walked 16 rows in one loop on X, the D-pad's up and down set the speed, its hints were plain text, it could
not be clicked and it sat over the boat. Bean's picks, as built (`SSailPhotoPanel`, `PhotoSettings.h`):

- **Tabs in plain words:** Lens, Focus, Light, Scene, Frame, on the bumpers (Page Up, Page Down), between their glyphs.
  The rows go round on their tab with the D-pad's up and down (the arrow keys); its sides change the value.
- **The UI modes:** Helpful shows every row on the tab and a line under the current one on what it does
  (`PhotoMath::RowHelp`); Natural shows the tabs and the current row only; Off opens photo mode with the panel closed.
- **Open and close:** a tap of View (H) opens or closes the panel; closed, the hints go too, and B leaves. A bumper
  opens a closed panel where it was.
- **Prompts as glyphs:** the card ends in the drawn controller glyphs (`KeyCap`), rebuilt when a key is rebound, the
  device changes or the UI mode changes.
- **X held (pad):** the left stick zooms the lens (a full push doubles the focal length in a second), the right stick
  tilts, the D-pad's up and down set the speed. With the panel closed the D-pad's up and down set the speed alone.
- **Alt held (keyboard):** the pointer comes out to click a tab, a row or a value's arrows; the wheel sets the speed.
- **Reset the tab:** R, or hold the right stick's click (its tap is still back to the boat) (`PhotoMath::ResetPage`).
- **Out of the way:** the card slides to the other side when the boat comes into its third of the screen, and back
  only once she is in the far third (`PhotoMath::PanelOnRight`).

Stills: `-SailingUiMode=helpful|natural|off` sets the UI mode the panel follows for one run (the setting is left as it
is), for example `-SailingPhoto=8 -SailingView=Chase -SailingUiMode=natural`.

A key list saved with slice 2's pad layout is moved to this one once (`USailingInputSettings::AddMissingActions`: the
old pad defaults come off and the new ones go where nothing else in photo mode holds the button).

Tests: `SailingSim.UI.PhotoPanel` (tabs, rows round their tab, help lines, the tab reset, the side, glyph text) and
`SailingSim.UI.PhotoFreeFly.Input` (the new buttons, the saved list moved once).
