# The Sunfish sailor's duck

Fix-list item 15. The Sunfish's boom is 0.5 m over her deck, and her mainsheet runs along it to the hand. Crossing
through a tack, her sailor crouched at the stance's lowest: the pelvis 30 cm over the cockpit floor, the trunk leant
45°. That put the back at the boom's own height, so the sheet ran 3 to 4.5 cm into the back's flesh radius
(`SailingSim.Visual.SheetClearance`, from #229).

## The fix (`CrewPlacement`, the crossing pose)

When the boom is less than a metre over the floor, a crossing sailor stoops. `FCrewPoseParams::Stoop` goes from 0 at a
metre to 1 at half a metre, times the duck:

- **The trunk** folds up to 35° further (spine 20°, chest 15°), and the head lifts to keep the eyes forward.
- **The crouch** goes up to 12 cm lower, kneeling. The 30 cm floor was set so a keelboat sailor's folded knees stay out
  of the sole. `CrewClipLimits` and `CrewHullClearance` still hold the knees and feet out of it.

Any boat whose boom is under a metre over her floor stoops in proportion. The Sunfish's is by far the lowest; the
dinghies' crew tests and SheetClearance cover the rest.

## Checks

With #229 merged in locally, so its test runs:

- `SailingSim.Visual.SheetClearance` lists no Sunfish contact through a tack or a gybe.
- `SailingSim.Visual.RigClearance` and `SailingSim.Visual.Crew*` pass.
- `SailingSim.Drills.SunfishLessons` passes: the triangle in 5:00, the quick-stop in 0:54.

This is a pose change only: the physics and her polar are untouched.

## Stills

`tack-before` and `tack-after`: High, 10 kn, a second into a tack (`-SailingCrudeTackAt=10`). Before, she crosses in a
crouch with her back at the boom; after, folded low under it.

With #229 on main, SheetClearance's Sunfish allowance (listed, not failed, while turning) is gone and fix-list item 15 is
done.
