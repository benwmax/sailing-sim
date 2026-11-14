# #687 under disk load: the log-flush spikes are gone

Storm, 4K Ultra fullscreen, 30 s, warm packages, `-SailingBenchTrace` plus an Unreal Insights CPU trace on every run,
alternating A/B/A/B: Packaged\Windows-da3e74b0 and Packaged\Windows-1c99aada (#687).

During each run a background copy kept the game's drive (D:) busy. It was an unbuffered `robocopy /J` of a 6 GB
random-data scratch file under `D:\dev\ss-fix\Artifacts`, looping, started before the game and stopped after it by PID.
The scratch files were deleted afterwards. The .utrace files stay on the PC.

| run | fps | p99 ms | GPU ms | game ms | game-thread frames > 40 ms | far-lights ticks with the log call: count, max | over 40 ms of them |
|---|---|---|---|---|---|---|---|
| a da3e74b0 | 34.4 | 51.2 | 22.19 | 20.78 | 30 | 7, max 678 ms (678, 349) | 2: 695 and 367 ms frames |
| b #687 | 35.2 | 42.0 | 22.41 | 19.80 | 34 | 7, max 0.2 ms | 0 |
| c da3e74b0 | 35.3 | 43.7 | 21.50 | 19.26 | 28 | 7, max 657 ms (657) | 1: 678 ms frame |
| d #687 | 35.3 | 38.2 | 22.61 | 18.81 | 24 | 7, max 0.1 ms | 0 |

On da3e74b0 the every-5-s `SAIL_LOG(Display, "Far lights: ...")` tick took 349-678 ms when the disk was busy: the session
log's per-line `Flush()` on the game thread. On #687 the same seven log calls per run take at most 0.2 ms: the write is
off the game thread. p99 is 4-9 ms lower on #687 under load (42.0 and 38.2 against 51.2 and 43.7).

The remaining long frames are the same on both builds:
- one about 400 ms trees frame (`LakeTerrainActor > Sailing_Trees`) early in every run;
- the bench's end screenshot (about 1 s of `FPngImageWrapper::Compress`, after the measured window);
- the far-cap rebuilds and wave-detail reconfigures in `Sailing_Water`, which #687 doesn't touch.
