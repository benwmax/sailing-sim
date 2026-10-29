# The Sunfish in light air: no justified friction knob flattens her

Following `docs/portsmouth-edges/`: the Sunfish's speed rises too steeply with the wind against her reference polar (the
ILCA's, scaled by their Portsmouth numbers). She beats 10.4% slow at 6 kn and 14.8% fast at 15 kn, and her 4-7 kn lap
sits at the slow edge of its Portsmouth band (1.16 of 1.17). Her sail's aspect ratio and her foils couldn't fix it
(that doc). This round tried her hull's friction, the other listed knob. No change is made.

Her polar at the beat (TWA 48) against her reference, from `scripts/polar.sh --boat sunfish`, and her lap over the ILCA's
from the full `scripts/reference-checks.sh`:

| Variant | 6 kn beat | 10 kn beat | 15 kn beat | Polar points out | DPN2 4-7 | DPN3 8-11 | DPN4 12+ |
|---|---|---|---|---|---|---|---|
| Main 6f8ba92b | -10.4% | -1.2% | +14.8% | 0 | 1.16 | 1.14 | 1.03 |
| Laminar run, K 1700 | -13.6% | -10.1% | +3.6% | 2 | 1.13 | 1.12 | 1.02 |
| Laminar run, K 3400 | -10.7% | -6.6% | +4.6% | 3 | 1.09 | 1.09 | 1.01 |
| Wetted area 2.8 (from 3.2) | -7.8% | +1.1% | +16.8% | 5 | 1.13 | 1.11 | 1.01 |
| Wetted area 3.6 | -13.0% | -3.6% | +13.3% | 0 | 1.19 (out) | 1.20 (out) | 1.05 |

## The laminar run (a Reynolds effect)

`FBoatModel`'s friction is ITTC-57, fully turbulent, at a Reynolds number on 0.7 of her waterline. Beating in 6 kn of
wind she makes about 3 kn, Re about 3.6 million, where a smooth dinghy carries a laminar run at the bow.
Prandtl-Schlichting's transition (Cf less 1700/Re for transition at Re 5e5) takes about 15% off her friction there and 8%
at 15 kn: the right shape on paper.

In the boat it turned her beat the wrong way at 6 and 10 kn. Her rudder angle doubled (2.4 to 4.8 deg at 6 kn): with
less drag on the hull her yaw balance went to weather helm, and the extra rudder cost more than the friction saved. Her
10 kn run went out of tolerance (+24.5% at 150 deg). What it did do was bring her 15 kn beat in (+3.6%). So her steep
slope isn't the friction's Reynolds dependence alone.

## Her wetted area

Scaling it moves her whole polar up or down together; it doesn't flatten her slope. At 2.8 she is faster everywhere and
five points go out (her reaches and runs up to +41.6%). At 3.6 she is slower everywhere and her 4-7 and 8-11 kn
Portsmouth ratios go out. No published wetted surface for a Sunfish was found to justify a change either way, so 3.2 stays.

## What is left

- **The residuary table.** The Sunfish's is `kPlaningDinghy`, which the ILCA's table extends.
  `SailingSim.Physics.LaserPlaningDrag` holds the ILCA's to be the Sunfish's up to Froude 1.3, so a Sunfish-only table
  would need that test's premise changed.
- **Her yaw balance.** The laminar run showed how much her upwind speed depends on her helm. A look at her weather helm
  (the board's and rudder's positions, her `HeelYawCoef`) might be what tilts her slope.
- **Her reference.** It is an estimate (the ILCA's polar times their Portsmouth ratio, 0.85 at 120 deg and beyond), not a
  measured Sunfish. The slope may be partly the reference's.

## Her yaw balance against a real Sunfish (Oct 29 2026)

Checked her geometry (`Fleet.cpp`, `Sunfish()`) against the class drawing. Her hull runs from x = 2.10 m (bow) to -2.09 m
(transom), 4.19 m:

| | The model | A real Sunfish | |
|---|---|---|---|
| Daggerboard | centre 1.55 m aft of the bow, chord 0.24 m: leading edge 1.43 m aft | the well about 1.4 m aft of the bow on a 4.2 m hull | right |
| Board area | 0.17 m² | a 37 by 12 in board, about 0.6 m of it under the hull | right |
| Rudder | transom-hung at x = -2.15 m, 0.08 m² | transom-hung | right |
| Mast | 0.85 m aft of the bow | the mast step a little under 1 m aft of the bow | right |
| Lateen | boom 0.55 m over the water, yard raked far aft | the boom low, the yard raked aft | right |
| Centre of effort | about 0.3 m aft of x = 0 (the four corners' mean: tack 1.9, clew -1.7, head -0.6 and -0.85) | aft of the board | right: weather helm |

She has weather helm, as sailors report: her rudder at the beat is 2.4 deg at 6 kn, 2.7 at 10 and 2.6 at 15 (her
polar's rudder column). What she lacks is the feel of it. Her tiller load in the polar is 1 to 4 N, where sailors call a
Sunfish's helm noticeably heavy (eased by raking the board aft). That is `HelmStiffness` and the helm's feel, not her
geometry. More weather helm wouldn't help her speed: the laminar run above showed that a heavier helm slows her beat.

So her geometry is already right. Only tuning would move her slope, and per the brief nothing is changed. What remains is
the residuary table (the `LaserPlaningDrag` premise) and her reference polar itself (an estimate scaled from the ILCA by
Portsmouth).
