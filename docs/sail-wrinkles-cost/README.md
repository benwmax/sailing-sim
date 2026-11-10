# Sail wrinkles, cheaper (Ultra perf)

The PC's Ultra bench bisect (`Inputs/bench/cloth-bisect.txt` on the inputs branch, Nov 10 2026) put the biggest step in
`cloth_cpu_ms` on ff3663d5, the sail wrinkles (docs/sail-wrinkles/): 1.20 -> 3.11 ms a frame, sails 1.36 -> 4.03 ms,
Windows Ultra 7-30 fps down per view since Oct 20. The same look (within a micron), less work:

- **The fixed part is kept.** `SailWrinkleCm` worked everything out at every render vertex every frame: the corners' angle
  (an `acos`), each vertex's angle from them (`atan2`), the fades, a `pow` for the wavelength, for all 3,358 vertices of
  each sail. Only the loads change from frame to frame, so `FSailWrinkleCache` (`SailCloth.h`) keeps, once per sail, the
  vertices a wrinkle can reach and their fixed numbers; the wavelength's `(B r^2 / T)^(1/4)` splits into a kept
  `(B r^2)^(1/4)` and `T^(-1/4)` (two square roots). A frame is then two square roots and a sine per touched vertex.
- **Normals only where something moved.** The normal pass copied the whole grid and checked every vertex's 3 x 3
  neighbours; it now visits the vertices next to a wrinkle (kept as `Near`, by kind), taking the smooth normal there
  before the move.
- **Only where they can show.** A sail not drawn in the last 0.25 s (cockpit view looking aft, off screen), or so far off
  that a 20 cm wrinkle spans under a pixel (about 190 m at 90 deg on 1080p; on again at 1.2 px, so no flicker at the
  edge), is drawn smooth. Automation runs (no renderer) always wrinkle, so `SailingSim.Visual.SailShrouds` still checks them.

Within a micron: `SailingSim.Visual.SailWrinkleCache` holds the cache to `SailWrinkleCm` at every vertex of a J/22 main's grid
under six loads (largest difference 1e-7 cm in a standalone build of this code). `SailWrinkleCm` stays as the
reference. Standalone (Linux, -O2, one J/22 main): the offsets 0.13-0.21 ms -> 0.03 ms; the whole wrinkle pass with its
normals 0.26 -> 0.10 ms.

Measuring: bench.json has `wrinkle_cpu_ms` (the wrinkles' share of the sails' tasks, summed over the sails, which run side
by side). `-SailingNoSailWrinkles` still draws them smooth for an A/B.

## What the step really was (PC A/B, Nov 10)

On main, `-SailingNoSailWrinkles` saves only 0.24-0.37 ms of `cloth_cpu_ms` (default 3.07 -> 2.70, beat15 2.83 -> 2.60):
the wrinkles were a small part of the bisect's 1.9 ms. The bisect walked only the sail-cloth commits; between c1c6bd43
and ff3663d5 sit 81d44a23 (the sails drawn on a grid three times finer: 3,358 vertices a sail instead of 400) and
8b9d7cd1 (the sails in parallel, each with fresh arrays every frame). The render grid's cost is the rest:

- **Two-pass Catmull-Rom.** `RefineSail`'s `SailCubic` did five Catmull-Rom curves per render vertex (four along cloth
  rows, one up through them), and the four row curves were the same for every render row in a cloth cell. Now each cloth
  row is curved once at every render column (`RowCurve`, 25 x 46), and each render vertex takes one curve up through four
  of those: the same sums with the same clamps, so the same numbers bit for bit, about a quarter of the work.
- **Arrays kept.** Each sail's per-frame arrays (cloth normals and tangents, the render grid's positions, normals and
  tangents, the row curves) were made fresh every frame, about a dozen blocks of 50-110 KB per sail, beyond the
  small-block allocator. They live on the cloth now (`FSailCloth::FRenderScratch`) and are reused.

Standalone (Linux, -O2): the render grid for one sail 0.34 -> 0.10 ms with identical output.
