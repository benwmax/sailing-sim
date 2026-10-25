# The weather map's hand-off without copies (Oct 25 2026)

Every two seconds the cloud weather map is repainted on a worker (`FWeatherMap::Paint`). The game thread then takes the
result and uploads two half-float textures. On the PC that cost the game thread 10 to 15 ms every 2 s. On the Mac it was
+3 to 4 ms; there the GPU bounds the frame, so it didn't show in fps.

## Where the time went

Packaged slip on High, Mac, ten hand-offs per run. These are named trace scopes, median per hand-off:

| Scope | Before | After |
|---|---|---|
| `Sailing_WeatherMapHandOff` (all of it) | 3.82 ms | 0.73 ms |
| `Sailing_WeatherMapTake` (the frame from the future) | 2.40 ms | 0.001 ms |
| `Sailing_WeatherMapUpload` (both textures) | 0.71 ms | 0.002 ms |
| `Sailing_WeatherMapLaunch` (the next paint) | 1.09 ms | 0.002 ms |
| `SailingEnvironment` tick, its 2 s peak | 3.9–4.05 ms | 0.85–1.35 ms |

## Causes

- **The take.** `FWeatherMapFrame Done = PendingWeatherMap.Get();` copied the whole frame. `TFuture::Get()` returns a
  reference, so taking the frame by value copied about 30 MB: the float map, the cumulus tops and both half images. It is
  now `Consume()`, which moves.
- **The upload.** Each half image was copied once more into a buffer for `UpdateTextureRegions`. The worker's arrays now
  go to the render thread as they are, each owned and freed by its upload's callback.
- **The launch.** Its 1.1 ms was the old frame's copy being freed when the future was replaced. The terrain copy is shared
  heights (`Sailing_WeatherMapTerrainCopy` measures 0) and stays as it was.

What's left (0.73 ms) is mostly freeing the previous map's arrays as `LastWeatherMap` takes the new one.

## The free on a worker

The previous map is now moved to the heap and deleted by a background task (`Sailing_WeatherMapSwap`). On the same
packaged slip view, ten hand-offs:

| Scope | Before | After |
|---|---|---|
| `Sailing_WeatherMapHandOff` | 0.73 ms | 0.006 ms (max 0.008) |
| `Sailing_WeatherMapSwap` | | 0.001 ms |

Clouds gate on main 161992d0 + weather-free: 225/225 tests; High beam8 58.1, beat15 57.1, storm 48.2, gulf-sea 61.9,
helm-eye 56.1, bridge 60.9 fps; Medium storm 69.1.
