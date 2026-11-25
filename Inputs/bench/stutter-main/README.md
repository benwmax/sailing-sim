# Stutter on main d8f2a3dc: frame pacing and the chase camera (PC, Nov 25 2026)

## The run

**Package:** a Development package of main d8f2a3dc **plus a local camera trace**, `Packaged\Windows-camtrace-d8f2a3dc`.
The trace is in `camtrace.patch`, 32 lines in `SailingGameMode`, and I haven't pushed it to any branch.
- **What it logs:** with `-SailingCamTrace`, at the end of every frame (`FCoreDelegates::OnEndFrame`) it records the
  view's location minus the player boat's location, the view's rotation, and the boat's yaw and speed. They go to
  `<shot>.camera.csv`.
- **Why this was needed:** the bench's frame trace has no camera.

**Settings:** 60 s measured after an 8 s warm-up, at 4K Ultra (100% screen) in a window. It's normal chase-camera sailing
on the lake, demo on, launch 1, afternoon breeze 12 kn, TWA 60, crew off.

**VSync:** set by `-ExecCmds="r.VSync 0|1"`. A bench run ignores the player's VSync setting
(`USailingSettings::ApplyDisplay` returns while measuring).

**The display** reports 120 Hz.

## Frame times

From the measured frames in `stutter-vsync-off.frames.csv` and `stutter-vsync-on.frames.csv`.

| | p50 | p95 | p99 | max* | Frames > 2 ms off the median | Frame-to-frame change > 2 ms | Medians: game / render / GPU |
|---|---|---|---|---|---|---|---|
| VSync off | 21.3 ms | 26.2 | 31.5 | 82 | **38.5%** | **56.5%** (mean change 4.6 ms) | 15.5 / 21.2 / 20.0 |
| VSync on | 19.6 ms | 21.6 | 23.3 | 77 | 8.7% | 19.7% (mean change 1.95 ms) | 9.6 / 19.6 / 19.1 |

*The max leaves out the exit frame (1.1-1.7 s, the bench writing its results). Both runs also have 40-300 ms frames
in the first 3 s while things settle.

**Reading it:**

- **The stutter is frame pacing, not the camera.**
  - With VSync off the GPU is steady at 19-20 ms a frame, but the render thread jumps from frame to frame.
  - A typical run of frames (frame / render ms): 20/20, 24/24, 26/26, 17/17, 18/19, **32/32**, 21/20, 18/19 ...
  - More than half the frames differ from the one before by over 2 ms, which shows as judder at about 47 fps.
- **With VSync on, the render thread is steady** (18-20 ms) and the game thread drops from 15 to 10 ms. Without
  VSync, the game thread runs ahead and seems to fight the render thread for CPU.
- **VSync didn't lock to the 120 Hz refresh here.** The VSync-on frame times are 17-20 ms, not multiples of 8.3 ms. In
  a windowed 4K run, presentation probably goes through the compositor, or the display is variable-refresh.
- **The game runs under 60 fps at 4K Ultra here** (about 47-51). On a fixed-refresh display, any frame rate that isn't
  a divisor of the refresh will judder however even the frames are.

## The chase camera against the boat

From `*.camera.csv`, the measured window.

| | Distance | Offset in the boat's frame | Jitter of the offset (the frame against the mean of its neighbours) | Jitter of the boat's angle in view |
|---|---|---|---|---|
| VSync off | 16.3 m | x 12.7-13.1 m, y 6.7-7.5 m, z 6.9-7.0 m | p50 0.19, p95 0.54, p99 0.74 cm; max 15.5 cm | p95 0.013 deg (about 0.5 px at 4K, 90 deg HFOV); max 0.36 deg (about 15 px) |
| VSync on | 16.3 m | the same | p50 0.10, p95 0.34, p99 0.44 cm; max 13.0 cm | p95 0.008 deg (about 0.3 px); max 0.33 deg (about 14 px) |

- **The camera follows the boat to well under a pixel**, frame to frame.
- The one jump of about 14-15 px in each run lines up with a hitch frame.
- **There's no camera-smoothing jitter to fix.** What a player sees as the boat or water stuttering is the uneven frame
  times above.

## Next steps worth trying (not done)

1. **Fullscreen with VSync.** Run 60 s, and look at whether the frame times quantise to 8.3 or 16.7 ms.
2. **A frame cap that divides the refresh.** Try `t.MaxFPS=40` on 120 Hz, VSync off, and check that the frames come out
   even at 25 ms.
3. **Unreal Insights on the render thread.** Take a `-trace=cpu,frame` around the VSync-off 26-32 ms frames, to see what
   makes the render thread uneven. The GPU is flat, so it's CPU work on the render thread.
