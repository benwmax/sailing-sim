# The running main and its shrouds

Gap 4 from the Oct 28 list: "shrouds show through a running main on most keelboats (8 of 32 samples)". That came from the
known gaps in `docs/rig-clearance/`, which were written before `docs/sail-dent/` and `docs/sail-spreaders/` (both Oct 27).

## How a real main lies on its rig

Eased square on a run, the boom comes to rest against the leeward shroud, or would without a sheet stopping it short. The
sail's belly then lies forward against the shrouds and the spreader tips. It wraps around the wire, takes a crease at the
spreader, and the batten ends catch on the shroud as the boat rolls. That is where sailmakers sew chafe patches. The cloth
is never on the far side of a wire.

`FSailCloth::KeepClear` does this on the main's target shape, which the cloth follows:
- the whole main turns about its luff, up to 0.6 rad (34 deg), as far as its wires need (`docs/sail-dent/`);
- each row dents round a shroud where it passes the shroud's height, and over a spreader near the bar's height
  (`docs/sail-spreaders/`).

The simulated cloth itself isn't pushed off the wires. Denting it directly kinked it across the spreaders.

## Measured (`SailingSim.Visual.SailShrouds`, new)

Every boat with a rig, both gybes at TWA 150, 165 and 175 in 8, 15 and 25 kn, three samples each after 8 s: 54 a boat, on
Medium (the cloth) and High (its wrinkles on the render grid as well). It counts a shroud's or spreader's centreline
through the main's drawn triangles, and its surface on them (within its radius and 3 mm), away from the luff (column 2
and aft) and the head (below the last three rows). The wire's last 12 cm at its fittings are left out. The luff's
columns 0-1 are counted apart.

| Boat | Main 84dc2f4b | With the main's clearance off (control) |
|---|---|---|
| J/22 | 0 | 0 |
| Catalina 22 | 0 | through in 7 samples (2 more at the luff), on in 9; the upper shroud at 25 kn, TWA 165, boom 70 deg |
| Catalina 30 | 0 | through in 6, on in 6; the upper shroud at 25 kn, TWA 150, boom 76 deg |
| Hobie 16 | 0 | 0 |
| Corsair 880 | 0 | on in 1 (the lower shroud at 25 kn, TWA 175) |
| Lagoon 42 | 0 | 0 |
| Maxi 100 | 0 | 0 |

These are Medium's numbers. High's are the same on main (all 0) and in the control within a sample or two (Catalina 22:
through 5, on 6; Catalina 30: through 7, on 7; Corsair: on 1).

The control (`KeepClear` returning at once for the main) shows the test sees a wire through the cloth. With the
clearance on there are none, so the gap was already closed on main.

## What changed here

- **Nothing in the cloth.** No collision on the simulated cloth was added: there is nothing for it to fix in these 756
  samples, and the earlier attempt kinked the cloth. The physics sail shape, every polar and the cloth's cost are
  untouched.
- **A guard:** `SailingSim.Visual.SailShrouds` fails on any centreline through or surface on the main away from its luff.
- The stale line in `docs/rig-clearance/` is closed.

## Not covered

- `HoldForTests` sails with ideal hands in a steady wind. A player's eased main in gusts and lake chop, flogging, isn't in
  these samples.
- The Sunfish, ILCA and other unstayed rigs have no shrouds to meet.

## Gate (`scripts/gate.sh --scope boats`, packaged, the Mac)

Pass: 267 tests (the light set; the packaged game and the bench are unchanged, since no game code changed). On High:
beam8 56.8, beat15 52.6, marina 55.5, helm-eye 58.9, slip 49.1, crew 46.7. `SailingSim.Visual.SailShrouds` was run on its
own and passes in 90 s.
