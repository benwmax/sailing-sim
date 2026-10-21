# Headroom for the storm view on High

The storm view on High sat at about 44.7 fps against its 45 floor. Its GPU frame is 21.8 ms, and the clouds and fog take
9.5 ms of it, the largest slice. This finds about 1.2 ms there.

## The measurements

The storm view on High, packaged build, `ONLY=storm scripts/bench-visual.sh 12`:

| run | fps | GPU ms | clouds/fog ms |
| --- | --- | --- | --- |
| main | 45.2 / 45.0 | 21.8 / 22.2 | 9.5 |
| shadow rays over 3 km (`-SailingCloudShadowKm=3`) | 47.2 | 20.7 | 7.9 |
| shadow samples × 0.75 (`-SailingCloudScale=1,0.75`) | 46.4 | 21.0 | — |
| view samples × 0.85 (`-SailingCloudScale=0.85,1`) | 45.2 | 21.7 | — |
| main, then this branch, alternating (a slower Mac later in the day) | 43.9, 44.8 / **46.3, 46.9** | 22.7, 21.4 / **21.7, 19.7** | 9.6, 9.4 / **8.1, 8.1** |

The shadow rays are the cost. The view samples barely matter here, because the view inside the storm is short.

## The change

On High, the clouds' shadow rays take their samples over 3 km instead of 4 (`ASailingEnvironment::BeginPlay`). The
sample count stays the same, so the samples are denser over a cloud's own few kilometres. Medium and Ultra keep 4 km.

## The look

The pairs are main (4 km) and this branch (3 km), High:

- `storm-4km` / `storm-3km`: the bench's storm view, inside the rain.
- `cumulus-4km` / `cumulus-3km`: the lake's afternoon cumulus, looking up.
- `storm-shore-4km` / `storm-shore-3km`: G5's blind-test game-04, a Catalina 30 against the storm.
- `storm-bay-4km` / `storm-bay-3km`: game-08, the shelf and its rain over the bay.

Each pair differs by 2 to 3 levels in 255 on average, which is the clouds' jitter and the rain. The sky's mean brightness
is within 1 level. Neither the cumulus' shading nor the storm's dark base and bright band change.

## Gate

`scripts/gate.sh --scope clouds`: pass, 208/208 tests. beam8 60.5, beat15 58.3, storm 45.4, gulf-sea 61.6,
helm-eye 57.5, bridge 61.9, storm on Medium 63.2. This was measured late in the day, with every view 1–2 fps under the
morning sweep; the alternating runs above compare like with like.
