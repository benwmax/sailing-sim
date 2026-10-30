# SailingSim tester guide

Thanks for testing. This is a work-in-progress build of the single-player game: Ray Hubbard and Galveston Bay, the J/22,
Sunfish and Catalina 22, and the first career tiers. `BUILD.md` beside this file says which build it is; the title
screen's bottom corner shows the same build number.

## Install

1. Windows 10 or 11, 64-bit, a DirectX 12 graphics card and about 10 GB free (the zip plus the unzipped game). There's no
   minimum spec yet: tell us your card and how it runs.
2. Unzip the whole zip into a folder of its own (not inside another game's folder, and not run from inside the zip).
3. Run `SailingSim.exe`. If Windows SmartScreen says it doesn't recognise the app, choose More info, then Run anyway:
   test builds aren't signed.

## The first launch

The first time it starts, the game compiles its shaders for your graphics card. The title screen can take a few minutes
to appear and the first minute on the water can stutter. That's expected, once per build: later launches are quick.

## Controls

A gamepad (Xbox layout) works everywhere. Press `/` (or tap View on the pad) on the water for the full controls card;
every key can be changed in Settings > Controls.

| | Keyboard | Gamepad |
| --- | --- | --- |
| Menus | Arrows, Enter, Esc | D-pad, A, B |
| Pause | Tab | Menu |
| Steer (tiller) | A / D or Left / Right | Left stick |
| Mainsheet in / out | W / S | RT / LT |
| Jib sheet in / out | E / Q | RB / LB |
| Traveler windward / leeward | Z / C | D-pad left / right |
| Hike out / in | F / V | D-pad up / down |
| Look around, zoom | Mouse, wheel | Right stick |
| Learning hints on / off | L | Y |
| Reset the boat | R | |
| Chart, hand-bearing compass | P, U | |
| Photo mode | 9 | Hold View |

## Reporting

For each problem, send:
- what you were doing (world, boat, career or free sail, the wind) and what happened;
- whether it happens again if you repeat it;
- a screenshot or a phone video if you can;
- the build number from the title screen.

Anything is worth reporting: crashes, a boat that does something a real one wouldn't, confusing menus or tutorials,
slow frame rates (say which graphics tier, in Settings > Graphics), and what you enjoyed.

## If it crashes

Zip and send these two folders (paste the path into File Explorer's address bar):

- `%LOCALAPPDATA%\SailingSim\Saved\Crashes` (a folder per crash)
- `%LOCALAPPDATA%\SailingSim\Saved\Logs` (if it's there)

Your settings and career save are in `%LOCALAPPDATA%\SailingSim\Saved` too. A new build keeps them; delete that folder
to start fresh.
