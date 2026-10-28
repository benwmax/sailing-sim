# Photo mode, PC PR 2: the panel

This is PR 2 of `Inputs/photo-mode/brief.md`, built on the Mac's free-fly camera (PR 1, `docs/photo-freefly/`). It adds:

- a Slate panel with five pages: Camera, Focus, Exposure, Scene, Frame;
- the lens and look settings on `AFreeCamera`'s camera;
- hiding boats and crew;
- a time of day that changes only what is drawn;
- the frame guides;
- 2x capture.

## Using it

Press 9 (or hold View) to open photo mode. The panel sits in a narrow column at the top left.

| | Keyboard | Pad |
| --- | --- | --- |
| Row | Up / Down | X (steps down through every row) |
| Change | Left / Right | D-pad left / right |
| Page | Page Up / Page Down | (X walks every page) |
| Hide the panel, guides and hints | H | B |

- The pad's D-pad up and down still set the speed, so X walks the rows instead.
- The new commands are their own photo-layer actions (`SailingBindings::IsPhotoPanelAction`), so they can be rebound on the keys page. They also have a row on the controls card.
- Saved key lists get them as new defaults.

## The pages

**Camera**
- **Focal length** steps 14, 18, 24, 28, 35, 50, 70, 85, 105, 135 and 200 mm.
  - It is a horizontal field of view on a 36 mm sensor.
  - `[` and `]` still zoom smoothly in between; the row shows where the lens is.
- **Tilt** moves in 5° steps up to ±45° (Z/C and the shoulders still roll it).

**Focus**
- **Focus** has three modes:
  - **Auto** focuses on the centre of the frame: a visibility trace, or the water under a camera looking down, else 2 km.
  - **My boat** focuses on the boat.
  - **Manual** uses the Distance row (0.5 m to 2 km, ×1.25 a step).
  - Focus eases like a lens motor over 0.2 s, in log distance.
- **Aperture** runs f/1.4 to f/22 in full stops, then Off (no depth of field).
  - It starts at f/2.8, the old lens.

**Exposure**
- **Exposure** is -3 to +3 EV in half stops. It is added to the scene's metered `AutoExposureBias` (Bean's band and Settings > Brightness stay underneath).
- **Vignette** and **Grain** run 0 to 1. On the first open they start from the scene look's values.
- **Look** is one of three:
  - **Cinematic**, the default, as before;
  - **Natural**, which takes the cinematic grade off: `ASailboatPawn::IsPhotoNatural`, at the `UsesCinematicLook` call in `SailingEnvironment.cpp`;
  - **Black & white**, `ColorSaturation` 0 on the photo camera.

**Scene**
- **My boat** hides the boat and her crew.
- **Other boats** hides the AI sailboats and power vessels. Only what the panel hid is shown again, so a ghost that was off stays off.
- **Crew** hides the crew only.
- **Time of day** is a drawn hour, `ASailingGameMode::SetDrawnHourOverride` / `GetDrawnHour`:
  - The sun, sky, exposure meter and lights (`IsDark`) follow it.
  - The clock, the weather and the tide never see it (rule 9).
  - It steps in half hours from the clock's. Passing the clock's own half hour goes back to following the clock.
- Everything on this page drops when photo mode closes.

**Frame**
- **Thirds grid** on or off.
- **Crop guide**: 16:9, 3:2, 1:1 or 21:9.
  - The guide's frame is drawn with the outside dimmed.
  - The grid sits inside the guide.
  - The shot is always the full frame.
- **Capture size**: 1x, or 2x on High and Ultra.
  - 2x is a `HighResShot` at twice the viewport: a 1920×1080 window saves 3840×2160.
  - The lens blendables are included.

## Notes

- **The photo is clean.**
  - The panel and guides are Slate over the viewport, so they are never in a shot.
  - The canvas hint and the "Photo saved" toast used to land in every saved PNG, at 1x and 2x. They are now held off for the frames the shot takes (`IsTakingPhoto`) and show after it.
- **Hiding my boat and the water.**
  - With the boat hidden, the water's hull clip would leave her shape cut into the sea.
  - `WaterSurface.cpp` is off-limits for this PR, so the pawn ticks after the water while photo mode is open. It clears `HullClipA.w` on the water's material, the same switch `-SailingNoHullClip` uses (`UpdatePhotoHullClip`).
  - The stills show no mark where she was.
- **Not changed:** the water's sun glitter still keys off `IsPhotoMode` (its `UsesCinematicLook` call is in `WaterSurface.cpp`). Under Natural it keeps the glitter.
- **Medium:**
  - Every row works except 2x capture, whose row is dimmed and reads "1x (2x on High)".
  - Medium's depth of field is the tier's own (`QualityCVars`), so f/1.4 blurs less than on Ultra.
- **Cost:** none with photo mode off. The panel is collapsed, and the lens work runs only in photo mode's tick. In photo mode on Ultra the focus run averaged 77 fps (uncooked, world held).
- **Not checked:** DoF shimmer on the water in motion at f/1.4. The stills are single frames.

## Stills

All are 1440 wide, from `-SailingPhoto=2 -SailingPhotoCam=-12,8,2.2 -SailingHour=17`. Uncooked editor build, 1920×1080, driven by `-SailingUIScript` (Slate key events) with `-SailingNoGpuSlices`. A bench's ProfileGPU window takes keyboard focus partway through a run.

| Still | What it shows |
| --- | --- |
| `ultra-focus-panel.jpg` | Focus page: 35 mm, focus on my boat at f/1.4, thirds grid, 3:2 guide (Ultra) |
| `ultra-focus-photo.jpg` | The photo saved from it: full frame, no panel, guides or hint |
| `medium-focus-panel.jpg`, `medium-focus-photo.jpg` | The same on Medium |
| `ultra-mono-panel.jpg` | Exposure page: +1 EV, grain 0.3, Black & white |
| `ultra-dusk-panel.jpg`, `ultra-dusk-photo.jpg` | Scene page: other boats hidden, the time of day drawn at 18:30 with the clock at 17:00 |
| `ultra-hideboat-photo.jpg` | My boat hidden: no hull cut in the water |
| `ultra-2x-photo.jpg` | A 2x capture (saved at 3840×2160; shown downscaled) |

## Tests

`SailingSim.UI.PhotoPanel` covers:
- focal length to field of view, and the marks;
- aperture stops and Off;
- exposure, look, tilt and capture steps (no 2x below High);
- the time of day's steps and its return to the clock;
- the rows and pages in order;
- crop rectangles;
- the panel's keys in photo mode's context;
- the drawn hour leaving the weather's hour alone.
