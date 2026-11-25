# Far-shore spread repeat: 9291fbf6 vs fa51d3a6 vs 83aa7652 (4K Ultra), Nov 25 2026

**Why:** the fa51d3a6 baseline (1080p, single runs) had five views 3.6-9.1 fps down on 9291fbf6, with the game and
render threads 1.0-1.8 ms heavier.

**Setup:**
- **Packages:**
  - A = `Windows-fa51d3a6`
  - B = `Windows-9291fbf6`
  - C = `Windows-83aa7652` (a fresh Dev package of main, with #827)
- **Views:** coast-day, marina-night, far-coast, far-coast-night and marseille-port, with the view args from fa51d3a6's
  `views.ps1`.
- **Runs:** 3840x2160 Ultra at 100%, 12 s benches, **3 rounds per view rotating A B C**. That's 45 runs, all in
  `ab.csv`.
- **Traces:** then one `-trace=cpu,frame` run of marseille-port on each build.
- Bean's Saved was held aside and restored (7B5CA7BE).

## Means of 3 (fps, and ms per frame)

| View | Build | fps (min-max) | GPU | game | render | RHI |
|---|---|---|---|---|---|---|
| coast-day | 9291fbf6 | 53.4 (53.3-53.7) | 18.14 | 11.79 | 18.70 | 8.94 |
| | fa51d3a6 | 53.7 (53.2-54.4) | 18.05 | 11.44 | 18.59 | 8.70 |
| | 83aa7652 | **52.4** (50.1-53.9) | 18.23 | **12.87** | 19.05 | 8.98 |
| far-coast | 9291fbf6 | 54.6 | 17.77 | 10.58 | 18.28 | 8.25 |
| | fa51d3a6 | 54.6 | 17.82 | 10.58 | 18.31 | 8.30 |
| | 83aa7652 | 54.1 | 17.96 | **11.13** | 18.48 | 8.47 |
| far-coast-night | 9291fbf6 | 54.7 | 17.75 | 10.47 | 18.26 | 8.09 |
| | fa51d3a6 | 54.9 | 17.73 | 10.31 | 18.23 | 8.07 |
| | 83aa7652 | 54.0 | 18.00 | **11.31** | 18.51 | 8.51 |
| marina-night | 9291fbf6 | 54.4 | 17.87 | 10.72 | 18.38 | 8.33 |
| | fa51d3a6 | 54.4 | 17.86 | 10.54 | 18.37 | 8.36 |
| | 83aa7652 | 54.3 | 17.89 | 10.81 | 18.40 | 8.31 |
| marseille-port | 9291fbf6 | 54.5 | 17.83 | 10.73 | 18.34 | 8.27 |
| | fa51d3a6 | 54.4 | 17.85 | 10.69 | 18.35 | 8.24 |
| | 83aa7652 | 54.5 | 17.83 | 10.90 | 18.34 | 8.38 |

## Reading

1. **The fa51d3a6 CPU rise is NOT real.**
   - Interleaved, fa51d3a6 matches 9291fbf6 on all five views: fps within 0.3, game thread within ±0.35 ms (fa51d3a6 is
     a little lighter on four of them), and render and GPU equal.
   - The 1080p single-run drops were spread.
   - At 4K every view is GPU-bound at about 18 ms, so a small CPU change wouldn't show in fps. But the game and render
     thread times themselves match, so it isn't hidden either.
2. **#827 (83aa7652) does add game-thread time on the Galveston coast views:**
   - coast-day **+1.08 ms** against 9291fbf6 (+1.43 against fa51d3a6), and one round dipped to 50.1 fps;
   - far-coast +0.55 ms;
   - far-coast-night +0.84 ms;
   - marina-night +0.09 and marseille-port +0.17: about nothing on the lake and Marseille.
   - GPU is +0.1-0.25 ms on the coast views.
   - At 4K it costs coast-day 1.3 fps and the far-coast views about 0.5-0.9 fps. At 1080p, where these views are
     CPU-bound, expect more.

## marseille-port traces

`marseille-<A|B|C>-GameThread.csv` and `-RenderThread.csv` hold the timer statistics over each run's last 12 s.
- No scope differs by more than 0.07 ms between the three builds on marseille-port, on either thread.
  - The largest game-thread differences are idle time (-0.16 on fa51d3a6), PNG compress (the bench's screenshot, +0.07)
    and `Sailing_RigLines` (+0.04).
  - The render thread's largest is `WaitForTasks`.
- That fits the bench: marseille-port is the same on all three builds.
- Since #827's cost shows on the Galveston coast views, the trace that would name it is **coast-day** on 83aa7652
  against 9291fbf6. That's not run yet; I can do it next if wanted.
