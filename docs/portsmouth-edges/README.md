# The Portsmouth edges

Gap 8 from the Oct 28 list: the Sunfish at the slow edge of 4-7 kn, the Catalina 30 at the fast edge, and laps that
leave out tack and gybe losses. `scripts/reference-checks.sh` (the full set) on main 75168a19, lap time over the ILCA's:

| Band | Sunfish | Catalina 22 | Catalina 30 | Hobie 16 |
|---|---|---|---|---|
| DPN2 4-7 kn | 1.16 [1.00-1.17] | **0.95** [0.96-1.13] out | **0.80** [0.87-1.02] out | 0.86 [0.78-0.92] |
| DPN3 8-11 kn | 1.14 [0.99-1.16] | 1.07 [0.96-1.13] | 0.94 [0.86-1.01] | 0.86 [0.75-0.88] |
| DPN4 12+ kn | 1.03 [1.00-1.17] | 1.15 [0.99-1.16] | 1.01 [0.86-1.01] | 0.85 [0.74-0.87] |

A lap is 1/VMG up + 1/VMG down at 6, 10 and 15 kn: steady legs, no tacks or gybes.

## The Catalinas in light air: two references that disagree

At 6 kn the Catalina 30's polar is within 5.4% of her ORC certificate (US 3522) at every angle, and a little slow upwind
(-3.6% at TWA 52). The ILCA, the lap's yardstick, matches her measured racing speeds within tolerance. So the
Catalina 30 sails as her ORC certificate says. The light-air D-PN (87.1 against the ILCA's 92.3) asks for her to be 10%
slower than that.

The two references measure different boats:
- **An ORC certificate is an optimised boat:** a clean bottom, racing sails, a full crew, the best angle at every
  moment.
- **US Sailing's D-PN for a cruiser comes from club racing:** furling genoas, cruising sails, dirty bottoms and short
  courses with many marks. The gap between those grows as the wind falls, when sail shape and a clean bottom count most.

The Catalina 22's reference polar is the Catalina 30's ORC scaled by their PHRF (270/183), so it inherits the same
conflict.

The Catalinas' bands and references stay as they are. The 4-7 kn band stays out of the quick set that
`SailingSim.Physics.ReferenceChecks` runs. Its keelboat lines test which reference is right, not the physics.

## Tack and gybe losses: measured, too small to matter

`ManeuverLossSeconds` (`ReferenceChecks.h`, a measurement tool) measures the leg time a tack or gybe costs. She sails her
best VMG angle as the polar crew sail it (autopilot, ideal trim, the calibration sea), then the autopilot takes her onto
the other tack or gybe with the tiller to 0.8. The loss is 40 s less her progress along the wind over those 40 s, over her
steady VMG.

| Seconds lost | 6 kn tack / gybe | 10 kn | 15 kn |
|---|---|---|---|
| ILCA 7 | 1.7 / 0.6 | 3.1 / -0.1 | 2.2 / -5.8 |
| Sunfish | 2.8 / 0.5 | 5.3 / 2.5 | 1.5 / 3.5 |
| Catalina 22 | 3.0 / 0.5 | 3.1 / 0.8 | 2.4 / -0.1 |
| Catalina 30 | 12.5 / 5.2 | 8.8 / 3.4 | 6.0 / 1.3 |
| Hobie 16 | 5.1 / 1.4 | 4.8 / 3.0 | -0.4 / 34.4 |

The numbers are noisy: a negative loss is a gybe or tack she came out of faster, and the Hobie's 15 kn gybe nearly went
over. No test depends on them.

With 1 nm legs, four tacks a beat and two gybes a run, they move the Catalina 30's light-air ratio from 0.80 to about
0.82, still out, and the ILCA's lap by 0.3%. They would also take the Catalina 22's 12+ kn ratio past its 1.16 edge. So
the lap stays steady VMG.

## The Sunfish's slow edge: not by her sail or foils

Her light-air edge is her beat: at 6 kn she points 10.4% slower than her reference polar (the ILCA's, scaled by their
Portsmouth). At 15 kn she is already 14.8% fast against the same reference, near its tolerance.

**Her sail's induced aspect ratio, swept.** The geometric value is 2.0, for a 3.75 m span over 6.97 m². With the boom
only 0.55 m over the water, the end-plate effect argued for more. But it lifts her 15 kn beat even more than her 6 kn one:

| Aspect ratio | 6 kn beat | 15 kn beat | Polar points out | DPN2 | DPN4 |
|---|---|---|---|---|---|
| 2.0 (main) | -10.4% | +14.8% | 0 | 1.16 | 1.03 |
| 2.4 | -5.2% | +19.5% | 3 | 1.12 | 1.00 |
| 2.7 | -2.0% | +22.2% | 3 | 1.10 | 0.99 (out) |
| 3.0 | +0.7% | +23.6% | 3 | 1.08 | 0.97 (out) |

Hiked flat at 15 kn she still sails at high lift, so induced drag counts there too.

**Her foils.** Her daggerboard's 0.17 m² is a real Sunfish board's immersed area (37 by 12 in, about 0.6 m under the
hull). A smaller one isn't justified by her geometry.

So the Sunfish is unchanged. Her speed rises too steeply with the wind for either knob: 10% slow at 6 kn, 15% fast at 15.
That looks like her hull's light-air drag (friction, `WettedAreaCoef` 3.2) rather than her rig. That knob wasn't in this
round's scope.
