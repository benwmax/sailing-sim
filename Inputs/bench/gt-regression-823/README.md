# Lake game thread: d8f2a3dc against 8e5cbfce (#823 merged), A/B/A/B (PC, Nov 26 2026)

**Question:** the traced runs on 8e5cbfce-based builds showed game-thread p50 of about 16 ms against about 10 ms on
d8f2a3dc. #823 (frigate decks) is the only merge between them. Is that a real regression?

**Setup:**
- **Packages:** Development `Windows-d8f2a3dc` (used many times before) and a clean, freshly built `Windows-8e5cbfce`
  (the scopes worktree with its local patch reverted).
- **Runs:** each 60 s, the same lake chase as `stutter-main/followup/` (4K Ultra, windowed, VSync off, demo TWA 60,
  12 kn, crew off), with `-trace=cpu,frame -statnamedevents`.
- **Order:** interleaved A1, B1, A2, B2, alone on the PC.

## Answer: no consistent regression. The 16 ms runs were each the FIRST run of a freshly built package

| Run | Package | Bench game ms | Bench render ms | fps |
|---|---|---|---|---|
| A1 | d8f2a3dc | 11.2 | 20.8 | 48.0 |
| B1 | 8e5cbfce, **its first launch** | **16.9** | 21.8 | 45.8 |
| A2 | d8f2a3dc | 10.4 | 20.9 | 47.8 |
| B2 | 8e5cbfce, second launch | **10.7** | 21.0 | 47.6 |

- **B2 matches the A runs.** The +6 ms appears only in B1.
- **The two earlier "16 ms" traces fit the same pattern:** `stutter-main/scopes/` (8e5cbfce + scopes) and
  `lake-streaks-837/stutter/` (#839 f186aa47) were each the first run of a freshly built package.
- **What's different in B1 is broad, not one system.** Comparing B1 with B2, everything in the trace's 40-50 s window
  is slower:
  - background task time is +7.5 s of worker time in the 10 s window;
  - audio/texture decode (`FAsyncDecodeWorker`) is +0.44 s;
  - the terrain, the rig lines, `UpdateSection` on the game and render threads, RHI submits and RDG setup are all
    1.3-3x slower.
- **That points to the machine being busy** in a new package's first run. Likely causes are a one-time shader, PSO or
  DDC warm-up, or the OS or antivirus scanning the new pak files on first read. I haven't confirmed which.

**Per-frame game-thread timers** (40-50 s; the average of two runs each; the `*-gamethread-40-50s.csv` files): the
biggest deltas, B minus A, are `Tick_Engine` +2.9, `Sailing_BoatVisuals` +1.4, `Sailing_RigLines` +0.7, `TG_PrePhysics`
+0.6, `sails` +0.6, `Sailing_Terrain` +0.6, `UpdateSection GT` +0.5, `Sailing_Water` +0.45 ms. These averages are
**entirely B1's**: the spread between B1 and B2 is about 6 ms, against 0.2 ms between A1 and A2. B2 alone is within
noise of A.

**Frigate systems on the lake:** none tick. No `Ship*`, `Frigate*`, `Cannon*`, `Walk*`, `Gun*` or `Deck*` game-thread
timer appears in any run, except `CrewDeck` (the crew-falls deck box, 0.4-0.8 ms per 10 s), which is on both builds.

## What this means for the earlier traces

- **The `lake-streaks-837/stutter/` comparison of f186aa47 against `followup/` is partly a first-run effect.** Its game
  thread at 16 ms was this, not the wake FFT.
- **For a fair frame-pacing comparison,** run each new package once to warm it, then measure the second run. I'll do
  that from now on: the #837 trace runs after its 18 clips, so that package will be warm.

Bean's Saved was held aside and restored for every run (7B5CA7BE).
