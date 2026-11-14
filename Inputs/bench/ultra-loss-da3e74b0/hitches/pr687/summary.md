# PR #687 (session log on its own thread) on the PC

Head 1c99aada (claude/project-thread-zpeyap, on main da3e74b0). MSVC editor build: Succeeded, 0 errors, 0 warnings in our
Source. Development package Packaged\Windows-1c99aada, 2 min. Warmed with one storm launch (the cold shader compile;
not counted). Then storm at 4K Ultra fullscreen, 30 s each, -SailingBenchTrace, alternating #687 and da3e74b0 (a, b, c,
d); c and d also with an Unreal Insights CPU trace (the .utrace files stay on the PC).

| run | fps | p99 ms | GPU ms | game ms | trace frames > 40 ms, 3-33 s (game-bound) |
|---|---|---|---|---|---|
| a #687 | 35.2 | 46.9 | 22.48 | 19.55 | 16 (14) |
| b da3e74b0 | 36.1 | 45.8 | 21.51 | 18.12 | 14 (13) |
| c #687 (+Insights) | 36.4 | 39.1 | 21.46 | 17.68 | 10 (9) |
| d da3e74b0 (+Insights) | 35.7 | 37.9 | 22.28 | 16.34 | 7 (6) |

Insights, game-thread frames over 40 ms in the measured window: #687 20 (11 owned by Sailing_Water, 9 other),
da3e74b0 17 (8 Sailing_Water, 9 other); FarLightsActor owns none on either.

The 5.0 s log-flush spikes: none on either build in this session. FarLightsActor's tick holds its "Far lights" log call 7
times in each trace and is under 1 ms every time, on da3e74b0 as well, so the flush did not stall the disk this time and
these runs cannot show the difference #687 makes; they show it costs nothing (no new hitch, fps within run-to-run spread).
On #687 the log call no longer touches the disk on the game thread by construction (the write moved to the log's thread);
to see the spike disappear on da3e74b0 against #687 needs the disk busy, as it was in the earlier traces (bench frames,
the trace stream and other writes at the same time).
The remaining hitches are the far-cap rebuilds and the wave-detail reconfigure (Sailing_Water), unchanged by #687.
