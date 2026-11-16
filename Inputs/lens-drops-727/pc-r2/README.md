# #727 lens drops round 2, on the PC

- **Branch:** `claude/project-thread-pz8kri` head **0be9a000** ("M_LensWater rebuilt on f22bf3a"), on top of f22bf3a (outline wobble with two and three lobes, brighter glint).
- **Merge:** merged locally with main **f148592b**, giving 6ed4c470 (not pushed). Round 1's head ea7120ec sat on main 0da7d6ea instead.
- **Build:** MSVC clean, 0 errors and 0 warnings in our Source.
- **Test:** `SailingSim.Visual.LensDrops` Success.
- **Package:** `Packaged\Windows-0be9a000-727r2`, Development, 3 min, no shader or material errors. One warm-up run.
- **Settings:** same as round 1's rain set. 3840x2160 fullscreen, Ultra, RTX 4090: `-SailingWorld=ray-hubbard -SailingBoat=J22 "-SailingStartAt=8759,152,-124" -SailingWind=27 -SailingTWA=67 -SailingWeather=Thunderstorm -SailingWeatherTime=200`
- **Saved:** Bean's Saved was held aside and restored (profile hash B57AA3AF).
- **Stills:** `rain-stills-branch/frame_0000..0002.png` (2 s apart), `end.png` and `bench.json`.
  - `crop-sky-1to1.png` is frame_0000 x 2500-3700, y 0-800.
  - `crop-mid-1to1.png` is x 1300-2500, y 700-1500.
  - These are the same spots as round 1's `pc/rain-stills-branch/crop-*-1to1.png`.
  - The bench reports post 2.66 ms (round 1's branch: 2.64). That's one run, not an A/B.

## What I see at 1:1 against round 1

**The drops are where they were in round 1** (same count, positions and sizes; the seed didn't change), so the two rounds compare drop for drop. `zoom4x-r1-vs-r2-dropA.png` and `-dropB.png` show the same drop at 4x, round 1 on the left and round 2 on the right.

- **Outline:** round 1's faceting is gone. In round 1 the larger drops had a cut-off, angular top end: straight edges meeting at corners (dropB shows it clearly). In round 2 the same drops have smooth, rounded outlines with a gentle unevenness from the lobes. They read as water now, not as polygons. I see no faceting anywhere in either crop.
- **Glint:** the specular point and the thin streak beside it are in the same place and only slightly brighter (most visible on dropA). On the dark sea the small drops still read mostly as a dark rim with a faint bent interior. They don't read as bright beads.
- **Count:** still about 10 drops in the mid crop. Main had about 60 identical stamps in round 1.
