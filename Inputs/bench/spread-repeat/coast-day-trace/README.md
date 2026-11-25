# coast-day: is #827's +1 ms real? (4K Ultra, Nov 25 2026)

## 1. dd737d32 (#826 only) vs 83aa7652 (#826 + #827)

Both are fresh Dev packages. The A/B ran 3 rounds per view rotating the two builds, followed by one `-trace=cpu,frame`
run each. Per-run numbers are in `ab-dd737d32-vs-83aa7652.csv`.

| View | Build | fps (range) | game ms (range) | render | GPU |
|---|---|---|---|---|---|
| coast-day | dd737d32 | 54.0 (53.5-54.3) | 11.21 (10.98-11.62) | 18.51 | 17.98 |
| | 83aa7652 | **54.5** (54.4-54.7) | **10.75** (10.54-10.88) | 18.34 | 17.83 |
| far-coast-night | dd737d32 | 53.8 (53.1-54.3) | 11.34 (10.69-12.33) | 18.56 | 18.03 |
| | 83aa7652 | **54.6** (54.5-54.7) | **10.61** (10.54-10.69) | 18.31 | 17.81 |

This time 83aa7652 is the *lighter* build, by 0.5-0.7 ms of game thread.

**Trace of coast-day, last 12 s of each run:**
- **`Sailing_Terrain`** (the terrain actor's tick): 0.479 s over 585 frames = **0.82 ms/frame** on dd737d32, against
  0.454 s over 593 frames = **0.77 ms/frame** on 83aa7652. #827 doesn't make it heavier.
- **HUD and Slate** (`Sailing_Hud`, `SailingHUD`, Slate tick and paint) are about 0.01-0.02 ms per frame on both. #826's
  wind dial costs nothing measurable.
- **No game-thread scope grows by more than 0.03 s over 12 s** (about 0.05 ms/frame) between the two. The only big
  differences are idle and wait time: game idle +0.35 s and render `WaitForTasks` +0.56 s on 83aa7652. That's the lighter
  build waiting more.

## 2. 9291fbf6 vs 83aa7652, 2 rounds each with traces

The `coastday-r*-*Thread.csv` files:

| Run | 9291fbf6 game ms | 83aa7652 game ms |
|---|---|---|
| round 1 | 13.79 | 14.13 |
| round 2 | 12.60 | 12.79 |

- That's +0.2-0.3 ms, inside the spread between rounds.
- The largest scope difference is `Sailing_RigLines`, +0.07 s over 12 s (+0.1 ms/frame). Nothing touches the terrain or
  the HUD.

## Reading

**The +1 ms on coast-day in the first repeat was noise, not #827 or #826.**
- Across the three repeats, the same coast views moved between builds by -0.7 to +1.4 ms of game thread in either
  direction.
- Each round's game thread varies by about 1 ms on its own (10.5 to 12.3 ms).
- In the traces, the terrain scope is 0.77-0.82 ms/frame on every build, and the HUD is about 0.01 ms.

At 4K all of these views are GPU-bound at about 18 ms, and GPU time is equal across builds. I'd call #827 and #826
performance-neutral on the Galveston coast. If a tighter answer is wanted, 5+ rounds at 1080p would show CPU-side
differences under 0.5 ms.
