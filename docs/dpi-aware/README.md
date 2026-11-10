# Windows: per-monitor DPI awareness (Nov 10 2026)

`Config/Windows/WindowsEngine.ini` sets `bAllowHighDPIInGameMode=True` under `[/Script/Engine.UserInterfaceSettings]`.
Without it the packaged Windows game is not DPI-aware: on a 4K desktop at 150% Windows scaling it sees a 2560x1440 screen,
renders that, and Windows stretches it to the panel. Any scaled 4K or 1440p display got this. Found on BEN-PC while taking
the first 4K Ultra baseline: every fullscreen run read 2560x1440 until the key was set.

Windows only: on macOS the same key turns on full Retina rendering, a GPU load the Mac gates (Medium 60 / High 45) do not
budget, so it stays out of `DefaultEngine.ini`.

## What changes

- Fullscreen and borderless on a scaled 4K desktop render real 3840x2160 (log: `Setting process to per monitor DPI aware`,
  then `3840x2160 (window mode 1)`). That is 2.25x the pixels those players rendered before, on Ultra by default: a 4090
  runs today's main at 51-55 fps at 4K (`Inputs/bench/4k-baseline-5e8233ef/fullscreen/` on the `inputs` branch) against
  about 85 at 1080p. Players on weaker cards at 4K should lower Render scale or Quality; the Settings rows already offer
  every physical mode.
- A 1920x1080 *window* is now really 1920x1080 pixels, so on a 150% display it appears about two-thirds the size it used
  to. Its backbuffer was already 1080p, so 1080p bench numbers and screenshot sizes are unchanged.
- The menus keep their share of the screen: the project sets no DPI curve, so the engine's default (ShortestSide, 1.0 at
  1080 rows) gives 1.333 at 1440 and 2.0 at 2160. At 1920x1080 the title screen is pixel-identical with and without the key.
- The save file carries no pixel size (`resolutionScale`, `hudScale`, `textScale` only); window size and mode live in the
  engine's `GameUserSettings.ini`, so older profiles map to nothing wrong.

## Follow-ups (not in this change)

- `docs/windows/README.md` "Bench at 4K" (`-ResX 3840 -ResY 2160`) was clamped to the logical desktop before this; a
  3840x2160 window still exceeds the work area, so a true 4K windowed bench needs `-ForceRes` in `bench-win.ps1` when the
  requested size reaches the desktop. No 4K Windows numbers from before this change exist.
- Mixed-DPI multi-monitor setups (dragging the window to a 100% monitor) are untested.

Verification stills and log lines: `Inputs/dpi-aware/` on the `inputs` branch (383a0f70).
