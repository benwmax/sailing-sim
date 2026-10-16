# Boats 11 on the Mac (Oct 16 2026)

Branch at e910fba5 (f4b83eed plus origin/main 741899dc merged). Editor build, `import_boat_detail.py` and
`import_j22_hero.py` ran clean (they resave the PC's assets, nothing new). The fleet meshes are the PC's
(`make-boat-models.sh` not rerun). Tests: the gate's 132 plus `SailingSim.Visual.FleetMesh` and `J22Mesh` pass.

## Gate (`scripts/gate.sh --scope boats`, packaged, Medium 60 / High 45)

| view | Medium fps | High fps | High p99 ms | High GPU ms | main High fps (sweep, same night) |
|---|---|---|---|---|---|
| beam8 | 87.5 | 58.5 | 18.56 | 15.83 | 58.5 |
| beat15 | 79.8 | 51.3 (52.3, 52.3 rerun) | 21.66 | 15.85 | 53.7 |
| marina | 92.9 | 59.7 | 17.58 | 15.17 | 59.6 |
| coast-day | 81.4 | 52.8 | 19.95 | 15.57 | 52.7 |
| helm-eye | 85.0 | 53.2 | 21.55 | 17.68 | 53.6 |
| slip | 79.7 | 51.8 | 20.73 | 17.82 | 51.6 |
| crew | 69.1 | 49.7 | 22.86 | 18.65 | 49.8 |

Pass. Every view but beat15 is within 0.5 fps of main. beat15 High is 1.4 fps under main on reruns, all of it render
thread (18.8 against 18.3 ms; game thread 2.74 against 2.65, GPU lower): the 8-sided rope tubes' draw cost with the
sails close in frame. 7 fps of headroom remains.

## Look

- `fleet-10kn-high.jpg`: all eight boats at 10 kn, High, beam reach (J/22, Sunfish, ILCA, Catalina 22; Catalina 30,
  Hobie 16, Corsair 880, Lagoon 42). They all build and sail. The ILCA's "100000" and the white flecks on the water
  come from main (fixed in their own PRs).
- `j22-hero-closeups.jpg` (`-SailingJ22Hero`): cockpit view, the cockpit and traveler, the fore hatch, the cabin side.
  The braid reads on the red jib sheet and the interior shows through the portlight.
- **Defect: the glass is never drawn.** `SM_J22H_Glass` and `M_J22HeroGlass` are imported, but
  `ModelMeshesFor` (`BoatModelVisuals.cpp`) loads only `Interior` and `FBoatModelMeshes` has no glass slot, so the
  portlights are open slots: the cabin and the crew's legs show through them in full light, not through smoked acrylic.
  Fix: load `SM_J22H_Glass` like the interior and add it as a part (player's boat only).

## Glass (ee94b408)

The editor build is clean, and `SailingSim.Visual.J22Mesh` and `FleetMesh` pass. `SM_J22H_Glass` now draws on the
player's boat. From outside, the portlight reads as dark smoked acrylic (`j22-hero-glass-portlight.jpg`). Before this
commit it was a clear slot. From inside the cabin, the panes tint the sky blue-grey (`j22-hero-glass-from-cabin.jpg`).
The cabin doesn't glow through, so the 0.8 opacity in `import_j22_hero.py` stays as it is. The cockpit view
(`-SailingCockpit`) shows no change.

Packaged on High, against this branch's earlier numbers: helm-eye 54.3 fps (53.2 before), slip 51.5 fps (51.8 before).
The difference is within noise.
