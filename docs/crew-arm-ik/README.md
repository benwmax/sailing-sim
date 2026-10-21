# The arm on a held line

This follows up `docs/crew-held-line/`. The PC, on Ultra, saw the J/22 trimmer's wrist cocked 60–70° on the jib sheet's
tail. The sheet comes from the winch along the forearm. The stance's elbow kept the forearm in line with the sheet, so
the palm could only meet it by bending the wrist.

## Changes (`CrewPose.cpp`, `CrewSolver`)

- **The elbow swings** (`ReachArm`, given the held line). It turns about the shoulder-to-wrist axis, up to 60° in 10°
  steps, to where the forearm runs most nearly square to the line.
  - The elbow never rises above the shoulder. Swung up, the arm went past the head and tore the vest.
  - It costs a little to move away from the stance's own elbow, and the swing only happens for a real gain.
- **The wrist** (`ClampWrist`) bends at most 40° when the line is led along the reach (within 20° of shoulder to hand),
  and 60° across it. The hand takes four turn-and-reach passes on a line instead of two.
- **The fingers stop at the line** (`ClearFingers`, new). The curl's fixed angles suit a line square across the palm.
  Led diagonally across it, the middle finger closed through it.
  - After the hands are placed, a finger whose bones pass within 0.75 cm of the line's axis opens, 15% a step, up to
    five steps. 0.75 cm is a 6 mm sheet's radius plus a finger bone's distance from its axis.
  - If the first bone, by the knuckle, is still too close, the hand moves off the line by the shortfall, square to it.

## Test

`SailingSim.Visual.CrewHeldLine` checks each MetaHuman rig's hand on six lines: the five directions it had before, plus
one led along the reach, as the sheet comes from the winch.

- **Wrist:** within 48° of rest for the line along the reach (40 flexion, 25 deviation), 66° for the others.
- **Fingers:** every finger bone at least 0.6 cm from the line's axis.
- **On the line:** the middle knuckle within 4 cm of the line. A hand that misses the line also clears it, so this check
  is needed too.

All 18 cases pass. Before this branch, the line along the reach failed on the wrist, and the diagonal line through the
palm failed on the fingers (0.38 cm).

## Stills

High, before (main) and after:

- `winch-*`, `winch-side-*`: the J/22 trimmer at the self-tailer, 4 kn, 50° TWA, the PC's repro view.
- `tiller-*`: the ILCA's tiller hand at 10 kn.
