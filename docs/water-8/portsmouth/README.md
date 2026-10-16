# W8 item 3: Portsmouth

W7 left two classes out of the US Sailing 2017 D-PN bands. The check sails a windward-leeward lap (1/VMG upwind +
1/VMG downwind) at 6, 10 and 15 kn and divides by the ILCA's lap; the band is the D-PN ratio within 8 %.

- **Hobie 16, DPN4 (12+ kn): 0.69 against 0.74-0.87.** At 15 kn she made 11 kn at 45 deg upwind. At 10 kn she was
  13 % over the Hotline polar upwind. Her windage (2.2 m^2 CdA for two crew on the wire, tramp, beams and rig) is
  already about right. What she lacked is the pitching and slamming of a 320 lb beach cat with fine, low bows driving
  into the chop. That is the added resistance in waves, which grows with Hs^2 and with speed into the waves, so it is
  strongest on the upwind leg in a breeze. `AddedResistanceCoef` 4 -> 9 (the J/22 is 1.3).
- **Catalina 22, DPN2 (4-7 kn): 0.93 against 0.96-1.13.** She matched her ORC polar within 6 % (a VPP: faired keel,
  race trim) and still lapped 11 % fast in light air. The swing keel is a cast-iron plate with blunt edges in an open
  trunk slot. Hoerner gives a plate 0.02-0.03 section drag at zero lift, against the faired fin's 0.009 that she had.
  Profile drag goes as V^2, like friction, so it weighs most in light air before wave drag takes over. The keel's
  `ProfileDrag` is now 0.03.

Each knob is justified in a comment in `Fleet.cpp`. The J/22 is untouched: `scripts/polar.sh --quick`, 0 of 39 points
outside tolerance, worst 6.9 %.

## Before and after

`scripts/reference-checks.sh --csv`: `before.csv` (origin/main c0d26d6) and `after.csv`. Two checks were out
before; none are after. The Portsmouth rows:

| Class, band | before | after | band |
|---|---|---|---|
| Sunfish, 4-7 kn | 1.16 | 1.16 | 1.00-1.17 |
| Catalina 22, 4-7 kn | **0.93** | 1.01 | 0.96-1.13 |
| Catalina 30, 4-7 kn | 0.87 | 0.87 | 0.87-1.02 |
| Hobie 16, 4-7 kn | 0.85 | 0.87 | 0.78-0.92 |
| Sunfish, 8-11 kn | 1.13 | 1.13 | 0.99-1.16 |
| Catalina 22, 8-11 kn | 1.00 | 1.05 | 0.96-1.13 |
| Catalina 30, 8-11 kn | 0.94 | 0.94 | 0.86-1.01 |
| Hobie 16, 8-11 kn | 0.80 | 0.84 | 0.75-0.88 |
| Sunfish, 12+ kn | 1.05 | 1.05 | 1.00-1.17 |
| Catalina 22, 12+ kn | 1.10 | 1.13 | 0.99-1.16 |
| Catalina 30, 12+ kn | 0.99 | 0.99 | 0.86-1.01 |
| Hobie 16, 12+ kn | **0.69** | 0.78 | 0.74-0.87 |

The polars: the Hobie's 10 kn upwind point went from +13 % to within 4 % of the Hotline polar. Her reaching points stay
11-20 % under it (that polar is a 1978 brochure, "optimistic"; inside its tolerance). The Catalina 22 has 0 of 39
points outside her ORC tolerance, worst 6.1 %.

`SailingSim.Physics.ReferenceChecks` no longer lists the Hobie's 12+ kn lap as a known gap. Puff veer is untouched,
pending over-water wind data.

## Still open

- The Sunfish sits at the slow edge of 4-7 kn (1.16 of 1.17) and the Catalina 30 at the fast edge (0.87 of 0.87),
  as before.
- The laps are steady VMG legs, without tacks and gybes. Those losses are largest for the cat, so her steady ratios
  ought to sit a little under the middle of each band. At 12+ kn she does (0.78 against 0.81). At 8-11 kn she is a
  little over it (0.84 against 0.81).

## Gate

`scripts/gate.sh --scope boats` passes (140 tests, including the heavy set: `SailingSim.Physics.PolarGate`,
`SailingSim.Fleet.Polar.*`, `SailingSim.Physics.ReferenceChecks`, `SailingSim.Race.AiFleetRace`). Medium 72.7-90.5
fps, High 47.2-56.1 (helm-eye 48.0, slip 47.2, crew 48.2).
