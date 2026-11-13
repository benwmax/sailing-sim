# The club launch ramp, cut into the bank

Bean's call (Nov 13 2026, after the 1 m club shore of #660 and the 7 m slab of #668): the launch ramp beside the
`*.ramp` pier is a real one, 12 to 15 % grade, level across its width, cut into the bank where the bank is higher and
built up where it is lower, with low kerbs on both edges.

Before: the slab's length came from where the bank's centre line reached its foot (7 m, a 34 % grade), and the bank,
which falls about 0.8 m across the slab's 5 m from the pier side, buried the slab's pier-side corner near the head.

After:

- `FMarina::PlaceRamps` (`Marina.cpp`): the head is still walked up the beach to dry ground. `Top` is the mean of the
  two head corners' ground (0.35 m above the water at least), and `Length` is `(Top - Foot) / Grade`, `Grade` 0.14,
  clamped 4 to 18 m. On the club shore that is about 15 m.
- `FLakeTerrain::AddGroundPatch` (`LakeTerrain.h`, SailingPhysics, plain data): `FLakeData::Load` lays one
  `FGroundPatch` per ramp after `PlaceRamps`. Inside the slab's plan plus the kerbs (half width 2.7 m) `HeightAt` returns
  the slab's plane 5 cm down (so the terrain mesh and the concrete don't fight); over the next 1.5 m the ground returns to
  the bank's own height with a smoothstep. `NaturalHeightAt` is the bank as baked. The terrain actor meshes the shore at
  1 m from `HeightAt`, the physics ground on it, and the water's shore map reads the same bed, so the cut and the fill
  show, ground and lap in one place.
- `AMarinaActor::BuildGeometry` (`MarinaActor.cpp`): kerbs 0.2 m wide and 0.15 m tall with an inner face, a top and an
  outer face down to the patch's level; the pier-side kerb stands against the cut, the far one over the fill.
- `FMarinaRamp::ZAt`, `DryLength`, the water's ramp stamp and the dry-part obstacle follow the new `Length`;
  `OverRamp` in `PlaceAlongside` keeps the fixed 18 m, so no Catalina lies beside the ramp's run into the water.
- `SailingSim.Lake.Marina` samples the centre line and both edges: the bed is never over the slab, never 0.1 m under
  it, the grade is 11.5 to 15.5 %, the slab is cut into the bank somewhere, cut and fill stay under 2 m, and 3 m past
  the kerbs the ground is the bank's.

The marina's baked tile (`/Game/World/Baked/SM_Marina_*`) must be rebuilt on the Mac (`scripts/make-world-models.sh`,
or the marina bake alone) after this, as for #668.
