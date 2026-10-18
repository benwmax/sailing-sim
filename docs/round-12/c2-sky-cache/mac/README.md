# C2 sky cache: the Mac gate (Apple M5 Pro, Metal, 1440x1080 window)

Packaged Development build, `-SailingNoSkyCache` as the "before" on the same package. This Mac's GPU times fall in two
clusters, so the states were run interleaved. On the PC's first head (16fcd304 plus main) the order was on, off, on,
off. On the final head (with the PC's 994953dc near-ray samples and the two fixes below) it was one more on and off
pair. `clouds+fog` and `other` are the bench.json `gpu` slices: three ProfileGPU frames after the window, in ms. The
strip draw lands in `other`.

## Verdict: pass

- **Floors.** Every clouds-scope view is over Medium 60 and High 45 on the final head (`gate.sh --scope clouds`, run
  c2-on4). The light test set passed (144/144); the full set passed 156/156 on the first head.
- **Clouds and fog** are down on every fair-weather view. At lake-towers on High they went from 5.9 to 2.4 ms. The
  strip adds about 0.65 ms to `other` on Metal (0.25 on the PC). Counting the strip as cloud cost, it is about 3.1 ms
  against the 3 ms target. The frame is 2.3 to 3.3 ms cheaper on High.
- **Swaps.** After the two fixes, no swap flashes or drops a frame. What is left is a soft half-second dissolve every
  4.5 s. It is the far clouds catching up on 4 s of drift, about 3 to 5 px at this size. See "Swaps" below.
- **Storm High** was under 45 on the first runs, with the cache on (43.7, 43.2, 42.8) and off (43.3, 43.2) alike: the
  cache steps aside under storms, so this is not C2. On the final head's runs it read 45.5 on and 45.2 off. That is the
  faster cluster. It sits on the floor either way, and it was 50.7 on main this afternoon.

## Gate tables

Final head (c2-on4 and c2-off3, adjacent runs):

| View | Tier | fps off | fps on | clouds+fog off | clouds+fog on | other off | other on | GPU off | GPU on |
|---|---|---|---|---|---|---|---|---|---|
| beam8 | Medium | 86.1 | 97.3 | 2.06 | 0.45 | 0.68 | 1.03 | 11.01 | 9.82 |
| beam8 | High | 58.0 | 63.5 | 3.77 | 1.32 | 0.58 | 0.96 | 16.26 | 13.94 |
| beat15 | Medium | 80.3 | 94.3 | 2.69 | 0.36 | 0.63 | 1.22 | 11.79 | 10.39 |
| beat15 | High | 50.2 | 62.1 | 5.51 | 1.27 | 0.58 | 1.46 | 18.04 | 15.09 |
| storm | Medium | 67.3 | 67.3 | 5.36 | 5.56 | 0.69 | 0.66 | 15.36 | 14.86 |
| storm | High | 45.2 | 45.5 | 9.69 | 9.87 | 0.55 | 0.60 | 21.91 | 21.56 |
| coast-day | Medium | 78.5 | 81.2 | 1.65 | 1.01 | 0.83 | 1.08 | 12.41 | 11.63 |
| coast-day | High | 52.7 | 53.5 | 2.33 | 1.66 | 0.65 | 0.93 | 15.87 | 16.46 |
| gulf-sea | Medium | 104.0 | 107.1 | 1.31 | 0.80 | 0.60 | 0.65 | 9.57 | 8.74 |
| gulf-sea | High | 67.7 | 69.5 | 2.63 | 2.20 | 0.54 | 0.69 | 13.46 | 13.03 |
| helm-eye | Medium | 82.0 | 101.2 | 3.25 | 0.34 | 0.49 | 1.11 | 11.83 | 9.34 |
| helm-eye | High | 51.5 | 58.9 | 4.37 | 1.04 | 0.28 | 1.03 | 18.34 | 15.90 |
| slip | Medium | 79.8 | 82.0 | 1.39 | 0.69 | 0.71 | 0.81 | 12.96 | 12.18 |
| slip | High | 51.0 | 52.4 | 2.27 | 1.34 | 0.55 | 0.83 | 17.41 | 17.25 |
| bridge | Medium | 97.2 | 101.3 | 1.35 | 0.64 | 0.68 | 1.00 | 10.03 | 9.64 |
| bridge | High | 62.2 | 64.6 | 2.65 | 1.53 | 0.56 | 0.95 | 14.36 | 14.04 |

First head, two runs each, interleaved (fps off / on, clouds+fog off / on, run 1 and run 2):

| View | Tier | fps off | fps on | clouds+fog off | clouds+fog on |
|---|---|---|---|---|---|
| beam8 | Medium | 82.0, 82.1 | 93.4, 93.4 | 2.07, 2.08 | 0.39, 0.40 |
| beam8 | High | 56.2, 55.4 | 61.5, 61.6 | 3.93, 3.68 | 1.69, 1.40 |
| beat15 | Medium | 77.1, 77.1 | 90.9, 90.7 | 2.61, 2.66 | 0.36, 0.41 |
| beat15 | High | 49.8, 50.0 | 59.9, 59.7 | 5.18, 5.62 | 1.25, 1.34 |
| storm | Medium | 64.4, 64.4 | 64.9, 64.7 | 5.57, 5.40 | 5.45, 5.35 |
| storm | High | 43.3, 43.2 | 43.7, 43.2 | 10.0, 9.12 | 9.92, 9.88 |
| coast-day | Medium | 75.5, 74.7 | 80.7, 80.6 | 1.64, 1.61 | 0.58, 0.57 |
| coast-day | High | 51.0, 50.9 | 53.7, 53.4 | 2.30, 2.37 | 1.10, 1.03 |
| gulf-sea | Medium | 100.0, 99.4 | 105.0, 105.7 | 1.31, 1.27 | 0.52, 0.53 |
| gulf-sea | High | 65.0, 65.1 | 68.9, 69.0 | 2.67, 2.72 | 1.83, 1.77 |
| helm-eye | Medium | 78.7, 77.8 | 97.6, 97.4 | 3.22, 3.23 | 0.34, 0.34 |
| helm-eye | High | 49.3, 49.5 | 56.9, 57.0 | 4.36, 4.54 | 0.97, 1.09 |
| slip | Medium | 76.5, 76.1 | 80.1, 80.1 | 1.37, 1.46 | 0.48, 0.47 |
| slip | High | 49.0, 48.7 | 51.4, 51.5 | 2.33, 2.38 | 1.18, 1.21 |
| bridge | Medium | 92.9, 93.8 | 99.3, 99.4 | 1.26, 1.32 | 0.41, 0.46 |
| bridge | High | 59.5, 59.7 | 63.2, 63.2 | 2.67, 2.71 | 1.40, 1.68 |

lake-towers is the plan's reference, so it was benched too (`scenes.csv` camera, `-SailingCapture=Chase`, 12 s).

| lake-towers | fps off | fps on | clouds+fog off | clouds+fog on | other off | other on | GPU off | GPU on |
|---|---|---|---|---|---|---|---|---|
| Medium, first head (r1, r2) | 92.5, 92.6 | 112.3, 112.7 | 3.29, 3.23 | 0.76, 0.75 | 0.56, 0.57 | 1.20, 1.37 | 10.67, 10.42 | 8.67, 8.69 |
| High, first head (r1, r2) | 63.3, 63.2 | 78.5, 78.0 | 5.90, 5.96 | 2.25, 2.17 | 0.61, 0.62 | 1.28, 1.32 | 15.18, 15.53 | 12.03, 12.14 |
| Medium, final head | 95.9 | 110.7 | 3.27 | 1.30 | 0.59 | 1.19 | 9.92 | 8.61 |
| High, final head | 67.4 | 77.9 | 5.85 | 2.44 | 0.61 | 1.28 | 14.32 | 12.03 |

The PC's near-ray change (994953dc) costs the live clouds about 0.2 ms on High and 0.55 ms on Medium here, and it
clears their grain (the stills). The Metal strip cost didn't threaten the floors, so `kSkyCacheWidth` and the refresh are
the PC's defaults. No halved-width or slower-refresh variant was needed.

## Swaps

Fair-weather sky, lake-towers at 17:00. The camera was raised to 60 m (`-SailingCamWorld=0,0,60,80,10`) so the boat
stayed out of the frame. Frames came from `RECORD=16 RECORD_INTERVAL=0.05 scripts/bench-mac.sh` on Metal; screenshots
cap it at about one frame per 0.14 s. The measure is the mean absolute change between consecutive frames over the
upper 72% of the frame (0-255 grey). `-SailingBenchTrace` frame times showed no spike at the swaps (the one spike is
at 14.2 s in every run, cache on or off).

- **Cache off:** 0.75 every frame. That is the live march's grain shimmering plus the drift.
- **Cache on, between swaps:** 0.3. The far clouds hold still.
- **Each swap** spreads over about 4 frames (the 0.5 s fade) at 1.3 to 2.1 each, about 7 in total. Over the same
  4.5 s, the live clouds (cache off) moved by 6.7. `swap-strip.jpg` shows four crops across one swap and their
  difference times 4: the cloud edges shift by a few pixels and nothing else changes. The far clouds hold for 4 s, then
  slide in a half-second dissolve. At normal size I'd call it hard to see, and I couldn't watch it in motion here.
  Moving the dome's panorama with the clouds' mean drift between refreshes would remove it (follow-up).
- **First handover** (about 4.5 s after load): one step of 12.8. The far clouds change from the live march's grainy
  look to the cache's smooth one in one frame (no fade). It is cosmetic and happens once.

Two defects the recording found, fixed in 447b63a8:

1. **The first panorama drew another sky.** It started on the first frame, before the first weather map existed, and
   read the empty map with the default `WeatherRect`. For its first 4 s the far sky showed different clouds, a step of
   31.9 at the handover and 8 per frame at the next swap. It now waits for the first map.
2. **The swap frame drew the wrong blend.** `CacheParams` was set before the swap, so the swap frame drew the new
   panorama at full blend, then went back to the old one and faded. At the first handover, that frame had the live
   clouds cut at 5 km and no cache, so the far sky went empty for one frame (seen in the recording). The fade now
   starts on the swap frame.

## Texas City step lines

They show on Metal too, faintly. They are horizontal bands in the darker underside of the largest far cell (upper right
of `galv-texascity-after.jpg`), visible at 1:1 and easy to miss at normal size. More noticeable here is a ragged,
texel-sized fringe on the edges of the mid-distance clouds on the left of that still. It looks like the live clouds' fade
between 4.5 and 5 km.

## Stills

Mac High, uncooked editor build (`scripts/capture-scenes.sh` with `scenes.csv`). The `-before.jpg` files have
`-SailingNoSkyCache` (main's look); the `-after.jpg` files are the final head. Five scenes: lake-towers,
lake-north-shore, galv-kemah, galv-texascity, storm-shelf. storm-shelf is the same both ways, because the cache steps
aside under a storm. `real-flat-country-cumulus.jpg` and `real-field-cumulus.jpg` are Commons photos of fair-weather
cumulus over flat country, for comparison (`credits.md`).
