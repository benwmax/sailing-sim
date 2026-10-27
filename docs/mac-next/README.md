# What the Mac should do next (Oct 27 2026)

This is a planning note: no code here. It covers quality first, on the Mac's lanes: boats and sails, water, clipping and
physics realism.

I read:
- `docs/physics-gaps/` and its "Still open";
- the realism audit (`docs/realism-audit-1022/`);
- the Ultra re-audit (`docs/ultra-audit-1025/`);
- CLAUDE.md's known gaps;
- what merged since: #338 (the cumulus blocks), #341 (the sail window), #347 (orbital flow), #349 (gale tack), #350
  (trimmer hands).

Already closed: the audit's wake at speed (`docs/wake-at-speed/`), boats sitting in the water (both halves:
`docs/hull-waterline/`, 888f9161), the shore margin, and the grazing reflection (a check). Crew cloth motion waits on the
PC's crew zip. The far haze is the Marseille lane's.

## 1. The main through the spreaders and shrouds on a run (clipping)

**Evidence.** Today's gate on #350 (`SailingSim.Visual.RigClearance`) lists, and doesn't fail, the spreader through the
main on four boats running (TWA 158–159, boom at 72–80 deg):

| Boat | Samples | First at (cm) | Cloth row, column |
|---|---|---|---|
| J/22 | 8 | (55, -28, 464) | 86, 10 |
| Catalina 30 | 8 | (103, -21, 786) | 112, 6 |
| Corsair 880 | 8 | (58, -35, 633) | 83, 10 |
| Maxi 100 | 8 | (280, -26, 1395) | 48, 15 |

Running is the chase and drone camera's commonest point of sail, and a spreader poking through a sail reads at any
distance. In real life the eased main lies on the spreaders and shrouds and takes their shape (chafe patches are sewn
there for it).

**Fix.** Give `FSailCloth` the rig as colliders: the spreaders as capsules from the mast to the tips, and each shroud as
a capsule along its line, in the boat frame the cloth already solves in. The PBD's collision pass pushes cloth particles
out of them, as it does for the mast, so the belly drapes over the spreader with a crease. `FSailCloth::KeepClear`'s
"turned in a few degrees" stays as the first guard. RigClearance then fails on the main as it does on the jib.

The physics stays as it is. `MainMaxEaseDeg` already stops the boom near the shrouds; if it is past the shroud angle on
a boat, that is a separate config fix, checked against that boat's polar.

**Risk.**
- The polars don't move: cloth only.
- Cloth cost on Medium and High: about 4 capsules more per sail and step, against the mast's one. Measure it with
  `cloth_cpu_ms`.
- The boats and crew gates' slip and helm-eye views.

**Estimate.** 2 gate runs: `--scope boats` while tuning, then `--scope all` before the PR.

## 2. The waves' inertia on the keel and rudder (physics realism)

**Evidence.**
- CLAUDE.md's wave-physics known gap: "Wave inertia on the foils: a known gap" (`docs/surfing/`).
- In #347 the orbital flow cut the J/22's false creep adrift beam-on to a 1.2 m swell from 0.68 to 0.43 kn. What is left
  is the keel taking the water's flow without its acceleration.
- #349's two sea tacks that still miss a reference (seed 5, 19% of her speed at the slowest; seed 6, 28.8 s) are the
  seeds where a face meets her head to wind.
- It is felt: the broach onset, the yaw kick on a face and her roll in a beam sea.

**Fix.** Add the Morison inertia term on each foil:

`F = rho V_foil (1 + Ca) a_water_lateral - rho V_foil Ca a_foil`

- `V_foil` is the foil's volume.
- `Ca` is the added-mass coefficient of a flat plate in sway, about 1 on the chord's square per span.
- `a_water` is the orbital acceleration: `FWaveField::OrbitalAcceleration`, the time derivative of #347's velocity
  (`A omega^2 cos(Arg)` per component, the ocean's from two more FFT grids or a finite difference of its 30 Hz grids).

Both terms act at the foil's centre in the body frame. The added-mass part goes into the effective inertia in sway and
yaw, so the integration stays stable.

**Risk.**
- The calibration sea is untouched, so PolarGate is safe.
- The sea trials move: the ORC band (1–10% upwind in the gale), `SailingSim.Physics.Surfing`, `SurfingFlow` and
  `GaleTack`'s 12 tacks. That is where the risk is: every number from #347 and #349 needs re-reading.
- The roll period in the reference checks may move a little from the sway added mass.

**Estimate.** 3 gate runs: water twice (one tuning round expected), then all.

## 3. The lake's wave periods are short (water realism)

**Evidence.** `docs/physics-gaps/` "Still open":
- at 28 kn the lake's peak period is 2.08 s against SWAN's 2.34 (11% short);
- in a northerly at Rush Creek (14 kn, a lee shore) it is 1.34 s against SWAN's 1.86 (28% short).

The chop's period is what reads as scale on the water. Short periods make the lake look like a pond scaled up, with
steeper, busier waves than SWAN's. They also set the boats' pitching rhythm.

**Fix.** Fit the period the way #41's steepening fitted the height:
- take the period law's stress wind, plus a fetch-dependent factor fitted to the Ray Hubbard SWAN bake's Tp per cell;
- `scripts/wave-check.sh --map` already compares the bake;
- keep the SPM U^(1/3) form and fit only the residual by effective fetch (short fetches are where it is off);
- `FWaveField` and the `FSeaMap` ratios follow; `M_WaterV4`'s components keep their count, and only their frequencies
  move.

**Risk.**
- Polars are safe (calibration sea).
- Longer periods at the same height are less steep, so the caps fold less. W8's cap refit (`docs/water-8/capshape-mac/`,
  fitted at 12, 16 and 20 kn) and `SailingSim.Visual.Whitecaps` need a refit.
- `SailingSim.Physics.WaveGrowthSwan` gains a period check.

**Estimate.** 3 gate runs: water, the caps refit, then all.

## Order

Do 1 first: it is visible in the commonest view, low risk, and the polars can't move. Then 2, the felt realism; it
touches the numbers #347 and #349 grounded, so give it a clean day. 3 is the quietest of the three.
