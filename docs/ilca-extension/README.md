# ILCA: the tiller extension clear of the helm's leg (Oct 24 2026)

RigClearance (#296) listed the ILCA's tiller extension 3.0 cm into the helm's leg, reaching on starboard (12 kn, TWA 94):
the line from the tiller's end (-137, 1, 50) cm to the hand (-123, 59, 53).

## Cause

The bones (the test's segment "calf_l" runs from the hip to the knee: the thigh) showed the aft leg going back from the hip
(x -1.21 m) to a knee at x -1.35, beside the tiller's end, although its foot was under the strap ahead of the hip. The
strap's feet (#281, #287) reach with two-bone IK that keeps the stance's bend plane, and the hiking stance's aft knee bent
aft. The foot's place was right; the knee was folded the wrong way. Moving the feet forward of the tiller's end didn't
help, and it pushed a MetaHuman shin into the strap when slid aft.

## Fix

`CrewSolver::ReachArm` takes an optional bend direction, and the legs under a strap bend up and a little forward
(knees up, as a sailor sits hooked under a strap).

- `SailingSim.Visual.RigClearance`: no ILCA or Sunfish note left.
- `SailingSim.Visual.DinghyStrap`: passes unchanged (ankles by the strap, insteps under it, shins clear, both boats, both
  tacks, slid aft).

`before-after.jpg`: the ILCA reaching on starboard, before (left) and after (right). The aft leg no longer lies back along
the deck by the tiller.
