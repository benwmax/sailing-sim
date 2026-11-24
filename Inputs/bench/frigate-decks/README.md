# Frigate decks (#823) on the PC at 44733c87, Nov 24 2026

**Branch** `claude/project-thread-xkunbh` at **44733c87** ("Frigate: the berth deck's placed copies and the lanterns
below"), on main 9291fbf6, code only. It ran in a fresh worktree (removed afterwards, crew link unlinked only). Nothing
was pushed.

- **MSVC build:** Succeeded, 0 errors.
- **Tests:** `SailingSim.ShipOutside` 4/4 (Commonwealth, **Decks**, Groups, Table); `SailingSim.ShipWalk` 8/8;
  `SailingSim.Smoke` 36/36 (1 standing warning).
- **Package:** Development `Packaged\Windows-pr823-44733c87` (kept): 4 min; cook 0 errors, 1 warning.
- **Log on every deck run:** "Ship outside Commonwealth: 244 parts on the boat, 0 did not load"; "Ship rig
  Commonwealth: 87 parts on the model, 0 to load, 0 with the outside model, 0 not in the project"; the walk line for
  each deck. No log line names the berth deck's copies or the lanterns, so they can't be counted from the log.

## Perf (Ultra, 100%, 20 s, GPU slices, `-SailingBenchTrace`; Gulf launch 2, 12 kn; one warm-up launch first)

| Deck, resolution | fps | p99 ms | max ms | GPU ms | base | Lumen | post | game | render | Last night's gun deck (3946b08c) |
|---|---|---|---|---|---|---|---|---|---|---|
| berth (`-SailingWalkAt=Berth,-12,0,0`), 1080p | 73.7 | 17.70 | 19.4 | 10.42 | 4.72 | 1.14 | 0.75 | 9.42 | 13.53 | |
| gun (`Gun,-19,0,0`), 1080p | **72.6** | 20.04 | 26.3 | 10.13 | 4.78 | 1.17 | 0.75 | 9.75 | 13.74 | **76.4** fps, GPU 8.64 (base 3.14, Lumen 0.96) |
| berth, 4K | **41.0** | 27.30 | 28.9 | 23.93 | 10.70 | 2.47 | 2.47 | 12.75 | 24.40 | |
| gun, 4K | **45.4** | 24.88 | 26.2 | 21.54 | 8.73 | 2.59 | 2.38 | 12.55 | 21.99 | **54.0** fps, GPU 18.05 (base 5.14, Lumen 2.54) |

- **The gun deck is slower:** -3.8 fps at 1080p and -8.6 at 4K. That's GPU time, +1.5 ms at 1080p and +3.5 ms at 4K,
  almost all in the **base pass** (+1.6 and +3.6 ms). Lumen is about the same, and the game and render threads hardly
  move.
- The base pass growing with resolution points to the lanterns' lit pixels rather than draw calls. The 29 point lights,
  if shadowed, also draw their shadow depths into the base slice. The 406 berth-deck copies are mostly out of view on
  the gun deck.
- **The berth deck at 4K is 41.0 fps: under the 45 limit.** The gun deck at 4K is 45.4, just over it. At 1080p both are
  well over 60.
- **No hitch:** the largest frame is 28.9 ms.

## Stills (1080p, the bench's own screenshot)

- `berthdeck-1080p.png`: the spot faces a bulkhead with two doorways. Through them, the berth deck's placed copies
  (mess tables and benches, slung hammocks) under warm lantern light. A spot facing along the deck would show more of
  the copies.
- `gundeck-1080p.png`: the battery under the beams, lit warm by the lanterns hanging from the beams. It's much brighter
  than round 3's ambient-only gun deck.

Bean's Saved was held aside and restored (7B5CA7BE).
