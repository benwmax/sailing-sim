# The cockpit camera inside the crew

The PC's Ultra audit (`docs/clipping-audit-2/cat30-cockpit-camera.jpg` on `audit-fixes`) found that the cockpit camera
(`\`, `-SailingCockpit`) sat inside a sailor on the Catalina 30, and in other sailors on the Hobie 16 and the Catalina 22.
The helm's own figure was already hidden. The eye was somewhere else, though: a fixed guess on the windward rail,
where another crew sat.

## Fixes

- **The eye is the helm's head** (`UpdateCockpitCamera`): 10 cm ahead of the hidden helm's head bone and 8 cm above
  it, wherever the crew model put them. The old guess is kept for a boat with no crew figure. While hidden, the helm is
  still posed (`AlwaysTickPoseAndRefreshBones`), so the eye follows them across on a tack.
- **The Catalina 30's helm at the wheel** (`CrewPlacement`):
  - They sit on a helm seat 25 cm above the after deck, to windward of the rim (`build_fleet.py`: wheel at x -3.45).
  - Both hands are on the rim, on their own side.
  - Before, they sat on the rail beside the wheel, facing inboard at the end of the crew's row, so the eye looked
    along four heads.
- **Room ahead of the helm** on both Catalinas:
  - The crew spread along the cockpit with at least 0.8 m clear ahead of the helm. It was 0.6 m, and the 22's middle
    hand's back was at the eye.
  - The minimum spacing between crew goes from 0.55 m to 0.45 m, so the 30's row of four fits ahead of the helm. That
    is still above the 0.4 m that `CrewHeldLine` holds.

## Stills

High, 15 kn, 45° TWA, `-SailingCockpit`:

- `c30-before` / `c30-after`. After, the view goes over the wheel to the dodger, with the crew on the rail ahead.
- `c22-before` / `c22-after`.
- `hobie-before` / `hobie-after`. The Hobie only needed the eye: the arm in the corner is the crew's, at arm's length.
- `c30-top-before` / `c30-top-after`, from above: the helm moved from the rail beside the wheel to the seat to windward
  of it.

`SailingSim.Visual.Crew*` passes (11 tests).
