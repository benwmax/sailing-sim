# Sail wrinkles, cheaper (Ultra perf)

The PC's Ultra bench bisect (`Inputs/bench/cloth-bisect.txt` on the inputs branch, Nov 10 2026) put the biggest step in
`cloth_cpu_ms` on ff3663d5, the sail wrinkles (docs/sail-wrinkles/): 1.20 -> 3.11 ms a frame, sails 1.36 -> 4.03 ms,
Windows Ultra 7-30 fps down per view since Oct 20. Same look, less work:

- **The fixed part is kept.** `SailWrinkleCm` worked everything out at every render vertex every frame: the corners' angle
  (an `acos`), each vertex's angle from them (`atan2`), the fades, a `pow` for the wavelength, for all 3,358 vertices of
  each sail. Only the loads change from frame to frame, so `FSailWrinkleCache` (`SailCloth.h`) keeps, once per sail, the
  vertices a wrinkle can reach and their fixed numbers; the wavelength's `(B r^2 / T)^(1/4)` splits into a kept
  `(B r^2)^(1/4)` and `T^(-1/4)` (two square roots). A frame is then two square roots and a sine per touched vertex.
- **Normals only where something moved.** The normal pass copied the whole grid and checked every vertex's 3 x 3
  neighbours; it now visits the vertices next to a wrinkle (kept as `Near`, by kind), taking the smooth normal there
  before the move.
- **Only where they can show.** A sail not drawn in the last 0.25 s (cockpit view looking aft, off screen), or so far off
  that a 20 cm wrinkle spans under 2 pixels (about 100 m at 90 deg on 1080p), is drawn smooth.

Same numbers: `SailingSim.Visual.SailWrinkleCache` holds the cache to `SailWrinkleCm` at every vertex of a J/22 main's grid
under six loads (largest difference under a micron; 1e-7 cm in a standalone build). `SailWrinkleCm` stays as the
reference. Standalone (Linux, -O2, one J/22 main): the offsets 0.13-0.21 ms -> 0.03 ms; the whole wrinkle pass with its
normals 0.26 -> 0.10 ms.

Measuring: bench.json has `wrinkle_cpu_ms` (the wrinkles' share of the sails' tasks, summed over the sails, which run side
by side). `-SailingNoSailWrinkles` still draws them smooth for an A/B.

Note: the standalone figures are smaller than the bisect's 1.9 ms step, so the PC A/B (main with and without
`-SailingNoSailWrinkles`, then this branch, with `wrinkle_cpu_ms`) is what says how much of that step this recovers.
