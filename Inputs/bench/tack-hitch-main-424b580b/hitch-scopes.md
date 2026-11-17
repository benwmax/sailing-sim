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

