# The main's clearance, kept

The PC measured `FSailCloth::KeepClear` on the main's target shape at about 0.26 ms of game thread per frame on Ultra. It
turns the whole main off the shrouds (`docs/sail-dent/`) and dents it round the shrouds and spreaders
(`docs/sail-spreaders/`), worked out afresh every frame. While the sail holds its shape that is the same answer frame
after frame.

## The change (`FSailCloth::KeepClearTarget`)

- The result is kept: each target vertex's offset from the clearance, and the boom's `FootTurn`, with the target it was
  worked out on.
- A frame whose target is within 1 cm of that one at every vertex takes the kept offset.
- It is worked out again when the target has moved further, 0.25 s after the last time, while the main's turn is still
  easing (it moved more than 0.002 rad), and when the wires change (`SetObstacles` compares them) or the cloth resets or
  is rebuilt.
- The turn's easing runs over the time since it was last worked out, so it keeps its 0.3 s rate.
- **The leech flutter** (a 9 Hz shiver of the last three columns, up to 1.5 cm) is now added to the target after the
  clearance, not before. Before, it moved the target past 1 cm every frame, and the reuse was 18-63%. The leech is the
  part of a running main furthest from the wires.

## How often it is reused (`SailingSim.Visual.SailShrouds`: TWA 150-175, 8-25 kn, 30 fps)

| Boat | Flutter before the clearance | After (this change) |
|---|---|---|
| J/22 | 48% | 70% |
| Catalina 22 | 46% | 64% |
| Catalina 30 | 18% | 22% |
| Hobie 16 | 63% | 65% |
| Corsair 880 | 49% | 55% |
| Lagoon 42 | 51% | 76% |
| Maxi 100 | 36% | 37% |

The Catalina 30 and the maxi run with their main's turn easing most of the time (the turn they want moves with the
waves). A tolerance scaled with the luff (0.15%, 1.6 cm on the Catalina 30's, 5 cm on the maxi's) changed their reuse by
under 1 point, so it stays at 1 cm. The 0.25 s refresh caps reuse at about 87% at 30 fps.

`SailShrouds` stays at 0 wires through or on the main on every rigged boat, on Medium and High.

## Cost (`cloth_cpu_ms`, all sails' cloth on the game thread, packaged High, the Mac)

| View | Main (tack-timing's gate) | This change |
|---|---|---|
| beam8 | 0.845 ms | 0.806 ms |
| beat15 | 0.802 | 0.750 |
| marina | 0.815 | 0.769 |
| helm-eye | 0.851 | 0.813 |
| slip | 0.527 | 0.495 |
| crew | 0.830 | 0.800 |

The saving is 0.03-0.05 ms a frame on the Mac, out of the whole cloth. Most of these views aren't running, where the
clearance does the most work. The PC's 0.26 ms was the clearance alone on Ultra.

## Gate (`scripts/gate.sh --scope boats`, packaged, the Mac)

Pass: 269 tests, every view over its floor on High: beam8 53.9, beat15 51.6, marina 53.8, helm-eye 57.4, slip 47.8,
crew 46.0. That is 0.8-2.4 fps under tack-timing's gate, in GPU time (beam8's GPU frame 16.6 -> 17.2 ms), which this
change (CPU, game thread) doesn't touch.
