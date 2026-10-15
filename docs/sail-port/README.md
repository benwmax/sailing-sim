# Sail numbers on both sides

Before this, `M_SailCloth` drew one set of marks from the cloth's UVs, the same on both faces of the (two-sided) cloth. It
read right from port and mirrored from starboard.

Now each face draws its own set (`TwoSidedSign` into the sail code as `Face`, +1 on the starboard face):

- **Starboard:** the insignia and the number, looked up mirrored along the chord, so they read right from that side.
- **Port:** the number one row lower (0.48 instead of 0.62 of the height), as the class rules ask, so the two sets don't
  show through each other. The insignia are back to back, as on a real sail.
- **Against the light:** both sets block the light through the cloth, so the other side's number shows faintly, mirrored.
  A real sail does the same.

This covers every class: the J/22's insignia and number, and the numbers of the other classes (`Marks` 1 and 2). The hero
J/22's sails are the same `FSailCloth` meshes, and its numbers aren't baked anywhere else.

![Port (left) and starboard (right), close-hauled, morning; the insignia close up in the evening (bottom)](both-sides.jpg)

The top row is lit from the morning sun, so the port side is front-lit and starboard is against the light (the port number
shows through). The bottom row is the evening, the other way round.

## Gate

`scripts/gate.sh --scope boats` against the sail-font gate (main with #60): 136 tests passed, every view over 60/45. The
sail code now does a second lookup for the other side's set (two texture taps where there was one).

| View | Medium fps | vs before | High fps | vs before |
|---|---|---|---|---|
| beam8 | 88.4 | -2.0 | 54.6 | -0.4 |
| beat15 | 85.1 | -1.0 | 50.3 | -0.7 |
| marina | 88.0 | -2.1 | 51.0 | +0.7 |
| crew | 71.2 | -0.3 | 48.0 | +0.5 |
| helm-eye | 79.6 | -1.2 | 46.4 | -0.7 |
| slip | 78.2 | -0.3 | 47.6 | +0.7 |
| coast-day | 81.3 | -0.9 | 47.2 | -0.5 |

The Medium drops run up to 2 fps (0.25 ms), on views where the sail is a small part of the frame. They are most likely run
to run noise, since High doesn't move.
