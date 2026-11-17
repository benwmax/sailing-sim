# Tack hitch on main 424b580b (PC, Nov 17)

## Diagnosis

**The game-thread hitches in the helm-eye tack runs belong to the capture mode, not to tacking.**

- **The owner:** in both hitch frames of this run, almost all the time is one scope, **`Sailing_BoatCapture`**: 63.4 of 72.4 ms, and 114.3 of 122.8 ms. It has no instrumented children.
  - That scope only runs with `-SailingCapture=` (`ASailboatPawn::UpdateCapture`, `SailboatPawn.cpp:1460`).
  - Once per second of capture time it calls `WriteCaptureSettings()`, which writes `<shot>.camera.json` with a **synchronous `FFileHelper::SaveStringToFile` on the game thread** (`SailboatPawn.cpp` around 5200 and 5247).
  - The only other per-frame work there is a small array append and the camera pose.
- **The timing fits a periodic file write, not the manoeuvre:**
  - Both hitches fall at the same phase of the one-second cycle (boat time 8.863 s and 16.892 s, so .86 and .89).
  - Neither is in the turn. The first is in steady close-hauled sailing on starboard, before the tack. The second is with the boat settled on port after it (telemetry below).
- **Likely cause:** most of those writes cost nothing. An occasional 60-120 ms stall on a small file save looks like the disk or a real-time antivirus scan on file close. That is an inference; the trace can't see inside the save.
- **What it affects:**
  - Every helm-eye tack trace in the #787 work used `-SailingCapture=HelmEye`, and so does bench-visual's `helm-eye` view. The hitches there are capture-mode artefacts and won't happen in normal play.
  - The fix, if wanted: write `camera.json` off the game thread, or only once (at the end).
- **Not seen:** no sail-cloth, rig-line or crew rebuild, world shift, re-centre or streaming scope over 1 ms in either hitch frame. Rig lines are 1.5 to 1.9 ms, their normal cost.

## Run

- **Package:** the Development `Packaged/Windows-424b580b` (main 424b580b), High 1920x1080. Bench scripts from 424b580b with the PID-only stop.
- **Args:** `-SailingWorld=Lake -SailingLaunch=1 -SailingCapture=HelmEye -SailingWeather=AfternoonBreeze -SailingWind=12 -SailingHour=15 -SailingTWA=45 -SailingDemo -SailingScreenPct=100 -SailingBenchTrace -trace=cpu,frame -statnamedevents -tracefile=<abs>`, 20 s (`args.csv`).
- **Saved:** Bean's Saved was held aside and restored (B57AA3AF).
- **The trace (not pushed, 90 MB):** `D:\dev\ss-fix\Artifacts\profile\tackhitch-main-424b580b-164515.utrace`.
- **Exports:** headless UnrealInsights (`-NoUI -AutoQuit -ExecOnAnalysisCompleteCmd="@=<rsp>"`):
  - `FEngineLoop::Tick` frames, in `insights-frames.csv`.
  - Every GameThread event, 224 MB, kept on the PC at `D:\dev\ss-fix\Artifacts\bench\tackhitch-424b580b\game-events.csv`.
  - The commands are in `*.rsp`.
- **Matching the clocks:** the bench clock (`tackhitch-high.frames.csv`) and the Insights clock differ by a fixed 7.94 s. Bench 8.863 s is Insights 16.802 s, and bench 16.892 s is Insights 24.780 s.
- **Frames left out:**
  - Frames over 50 ms before Insights 9.3 s are loading, before the bench starts.
  - The two at the end (bench 23.3 and 23.5 s; 308 and 142 ms) are the bench's own screenshot and profile capture.

## The hitches (over 50 ms in the measured window)

| Bench time | Insights time | frame ms | game ms | Owner | What the boat was doing (telemetry) |
| --- | --- | --- | --- | --- | --- |
| 8.863 s | 16.802 s | 72.4 | 71.3 | `Sailing_BoatCapture` 63.4 ms | close-hauled, starboard: heading 142.8, TWA 38.5, heel 9.8, 5.5 kn. **Before the tack.** |
| 16.892 s | 24.780 s | 122.8 | 122.4 | `Sailing_BoatCapture` 114.3 ms | settled on port after the tack: heading 225.7, TWA -49.9, heel -8.7, 4.4 kn |

## Game-thread scopes in each hitch frame (inclusive ms, top 10; then every event over 1 ms in order)

### Hitch frame 16.802-16.875 s (Insights time), 72.4 ms

| Scope | depth | inclusive ms | calls |
| --- | --- | --- | --- |
| Frame | 1 | 72.4 | 1 |
| FrameTime | 2 | 72.4 | 2 |
| Tick_Engine | 3 | 71.2 | 1 |
| GameEngine Tick | 4 | 71.2 | 1 |
| UWorld_Tick | 5 | 70.4 | 1 |
| World Tick Time | 6 | 70.4 | 1 |
| Tick Time | 7 | 70.2 | 3 |
| ReleaseTickGroup Block | 9 | 70.1 | 6 |
| TickCompletionEvents | 10 | 70.1 | 7 |
| ProcessUntilTasksComplete | 11 | 70.1 | 7 |

Events over 1 ms in order (depth, start offset ms, duration ms, scope):

```
FEngineLoop::Tick  @    0.0     72.4 ms
  Frame  @    0.0     72.4 ms
    FrameTime  @    0.1     72.4 ms
      Tick_Engine  @    0.1     71.2 ms
        GameEngine Tick  @    0.1     71.2 ms
          UWorld_Tick  @    0.1     70.4 ms
            World Tick Time  @    0.2     70.4 ms
              Tick Time  @    0.2     70.2 ms
                TG_PrePhysics  @    0.2      1.2 ms
                  ReleaseTickGroup Block  @    0.2      1.2 ms
                    TickCompletionEvents  @    0.2      1.2 ms
                      ProcessUntilTasksComplete  @    0.2      1.2 ms
                TG_PostPhysics  @    1.6     68.8 ms
                  ReleaseTickGroup Block  @    1.6     68.8 ms
                    TickCompletionEvents  @    1.6     68.8 ms
                      ProcessUntilTasksComplete  @    1.6     68.8 ms
                        FTickFunctionTask  @    1.6     66.1 ms
                          Sailing_BoatVisuals  @    1.7      2.6 ms
                            Sailing_RigLines  @    1.8      1.5 ms
                          Sailing_BoatCapture  @    4.3     63.4 ms
                        FTickFunctionTask  @   68.0      1.4 ms
                          WaterSurface  @   68.0      1.4 ms
                            Sailing_Water  @   68.0      1.4 ms
```

### Hitch frame 24.780-24.903 s (Insights time), 122.8 ms

| Scope | depth | inclusive ms | calls |
| --- | --- | --- | --- |
| Frame | 1 | 122.8 | 1 |
| FrameTime | 2 | 122.8 | 2 |
| Tick_Engine | 3 | 122.2 | 1 |
| GameEngine Tick | 4 | 122.2 | 1 |
| UWorld_Tick | 5 | 121.4 | 1 |
| World Tick Time | 6 | 121.3 | 1 |
| Tick Time | 7 | 121.1 | 3 |
| ReleaseTickGroup Block | 9 | 121.1 | 6 |
| TickCompletionEvents | 10 | 121.1 | 7 |
| ProcessUntilTasksComplete | 11 | 121.1 | 7 |

Events over 1 ms in order (depth, start offset ms, duration ms, scope):

```
FEngineLoop::Tick  @    0.0    122.8 ms
  Frame  @    0.0    122.8 ms
    FrameTime  @    0.0    122.7 ms
      Tick_Engine  @    0.1    122.2 ms
        GameEngine Tick  @    0.1    122.2 ms
          UWorld_Tick  @    0.2    121.4 ms
            World Tick Time  @    0.2    121.3 ms
              Tick Time  @    0.3    121.1 ms
                TG_PrePhysics  @    0.3      1.1 ms
                  ReleaseTickGroup Block  @    0.3      1.1 ms
                    TickCompletionEvents  @    0.3      1.1 ms
                      ProcessUntilTasksComplete  @    0.3      1.1 ms
                TG_PostPhysics  @    1.5    119.8 ms
                  ReleaseTickGroup Block  @    1.5    119.8 ms
                    TickCompletionEvents  @    1.5    119.8 ms
                      ProcessUntilTasksComplete  @    1.5    119.8 ms
                        FTickFunctionTask  @    1.5    117.5 ms
                          Sailing_BoatVisuals  @    1.6      3.1 ms
                            Sailing_RigLines  @    1.7      1.9 ms
                          Sailing_BoatCapture  @    4.7    114.3 ms
                        FTickFunctionTask  @  120.0      1.1 ms
                          TrafficManager  @  120.0      1.1 ms
                            Sailing_Traffic  @  120.0      1.1 ms
                              Sailing_TrafficStep  @  120.0      1.1 ms
```


