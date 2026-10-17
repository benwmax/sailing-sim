# E1: seeded wear (environment-1)

Plan: the Claude Doc "Shore, Dock and Wildlife Plan", phase E1. Every structure gets a small set of numbers drawn from a hash
of its id. Materials read them, so variety costs nothing at runtime and comes out the same on the Mac and the PC. This branch
has two halves. The Mac's wiring half is here: the seed, written to per-instance custom data, and the slip looks. The PC's
material half is `M_WorldSurface` and `M_BoatSurface` reading the seed.

## The seed (`FWearSeed`, `WorldKit.h`)

`FWearSeed::Make(Id, Site, Water, FacingDeg, Variant = -1)` is a pure function of its inputs. No random stream is used, so
adding a house or a slip somewhere else changes nothing here.

- **Id.** For a named structure, `FWearSeed::IdOf(Name)`: FNV-1a over UTF-16 code units, then lowbias32. The Mac's 4-byte
  `TCHAR` and the PC's 2-byte one agree, and `SailingSim.Visual.SlipWear` pins one value. For an unnamed structure,
  `FWearSeed::IdAt(PlanM)`: its plan position rounded to 0.25 m.
- **Site.** `WearSiteFor(Lake)`: a world whose file name contains Gulf is Gulf, a tidal world is Bay, anything else is Lake.
- **Water.** Dry for houses. Floating for boats and floats: the band rides the water. Fixed for pilings and private docks:
  the band spans the level's range.

| Slot | Field | Range | Meaning |
|---|---|---|---|
| 10 | `Age` | 0-25 (years) | Uniform. Drives silvering, UV fade, rust and replaced boards. |
| 11 | `Care` | 0-1 | 0.25 + 0.75 u - 0.3 age/25, clamped. 0 is neglected, 1 is kept. Older things are kept less on average. |
| 12 | `Sun` | 0-1 | 0.5 + 0.35 cos(facing - 225 deg) ± 0.15. Faces looking south-west (the afternoon sun) bleach; north faces stay damp and green. |
| 13 | `Wet` | metres | Height of the stain band above the waterline. Dry: 0. Floating: 0.05-0.25. Fixed: lake 0.3-0.9 (the drawdown's "bathtub ring"), bay 0.5-1.0 (tide plus splash), Gulf 0.9-1.6 (surf). |
| 14 | `Site` | 0, 1, 2 | Lake, Bay, Gulf: fresh against salt fouling, white rust near salt. |
| 15 | `Variant` | integer | A berthed boat's cover (0-4, `FSlipLook::Cover`). Elsewhere, 0-7 hashed from the id. |

`FWearSeed::Slot` = 10, `NumFloats` = 6, `TotalFloats` = 16. Facing is the map-frame yaw (0 north, 90 east), the same as an
instance's Unreal yaw.

## Custom-data layout, by component (for the PC's materials)

Slots 0-9 are unchanged: each instance's own data, as before.

| Component | Material | 0-9 (as before) | 10-15 |
|---|---|---|---|
| Berthed sailing hull, club and coast (`SpawnBerthedBoats`, part 0) | `M_BoatSurface` | 0-3 livery wear, 4-6 hull colour (`SampleBoatLivery`); 7-9 are -1 | wear seed (Floating, facing = heading) |
| Berthed sailing boat's mast, boom, rudder and dress (`SM_<Class>_Berthed[_1..5]`) | `M_BoatSurface` and others | -1 in 0-9: M_BoatSurface's "no livery" (its `CD` defaults are -1), so they draw exactly as before | the boat's wear seed (same values as her hull) |
| Painted power hull (express, sportfish, motor yacht) | `M_VehiclePaint` | 0-2 paint; 3-9 are 0 | wear seed |
| Unpainted power hull (runabout, trawler yacht) | | none, as before | not written yet: their materials read their own defaults |
| Far house archetypes (`SM_House_Gable/Hip/Flat`) and near houses (`SM_HouseNear_*`) | `M_HouseWall`, `M_HouseRoof` | 0-2 wall, 3 pattern, 4 height, 5 hash, 6-8 roof, 9 ground | wear seed (Dry, facing = the house's yaw) |
| Private docks and boathouses (`SM_HouseNear_Dock`, `_Boathouse`) | `MI_World_*` (`M_WorldSurface`) | 0 | wear seed (Fixed, facing = toward the water) |

The data is written once at spawn (all of these are static), so the frame cost is the GPU scene's few extra floats per
instance.

Not covered yet:

- The baked kit tiles: the marina's docks, the shore kit and the coast's walkways. Each is one Nanite static mesh per tile,
  not an instance, so per-structure numbers would have to go into the bake (vertex colour or UV1, then `make-world-models.sh`).
  Until then `M_WorldSurface` should hash per board from world position, with this README's ranges.
- The Low tier's cube docks, the bridges, the navaids and the riprap. The riprap is 324,000 boulders on the coast: six
  floats each would be 7.8 MB of instance data for little gain.

## Slip looks (`FSlipLook`, `AssignSlipLooks`, `MarinaActor.h`)

Each slip of the club's marina gets three values, hashed from the slip's id:

- Dress: 0-5, one of `build_berthed.py`'s six dresses.
- Clutter: 0-3, the dock clutter set E2's props will read.
- Cover: 0-4, the berthed boat's wear `Variant`.

`AreNeighbourSlips` covers two cases: side by side along a row (the finger between them), and bow to bow across the row's
dock. A slip steps each value off any neighbour that already has it. Slips are taken row by row, one side and then the
other, so a slip has at most two values to step off, and every set has at least four. `AMarinaActor` passes the dress and
cover to `SpawnBerthedBoats` (`FBerthedBoat::Dress`, `Cover`). The coast's moored boats keep the hashed dress.

Before this change, the dress was an independent hash per slip, so about one neighbour in six wore the same dress.

## Test

`SailingSim.Visual.SlipWear` checks the following:
- On Ray Hubbard's marina, no neighbouring slips share a dress, a clutter set or a cover. All values are in range, all are
  used, and the assignment is deterministic.
- `IdOf` is pinned to one value.
- `Make` is a pure function and stays in range. Mean age is 12.5 ± 1 years.
- South-west faces bleach more than north-east ones.
- The band heights by site and water contact.
- The slot order.

## Cost and gate (the Mac, packaged)

`scripts/gate.sh --scope world` (branch with main 778c56a4 merged) passes: 150/150 tests, every view over Medium 60 and
High 45 (`world.csv`). High fps: marina 58.2, bridge 61.1, coast-night 57.7, marina-night 50.9, helm-eye 52.6, slip 50.8,
coast-day 52.8.

Run straight after the gate, the branch came out 0-2 fps under the main bench taken before it (`ab-main`, `ab-branch`), the
same order effect as `docs/water-8/w4-mac`. Back to back (the branch, then main repackaged, `ab-branch2`, `ab-main2`):

| View | Branch Medium | Main Medium | Branch High | Main High | GPU ms High, branch / main |
|---|---|---|---|---|---|
| marina | 92.5 | 94.0 | 60.2 | 61.1 | 14.66 / 14.68 |
| coast-night | 97.0 | 96.3 | 59.8 | 60.2 | 16.15 / 16.14 |
| bridge | 99.0 | 98.7 | 63.0 | 63.5 | 14.19 / 14.17 |

About 0 ms: the custom data is written once at spawn.

## The material half (the PC, `make_materials.py`)

`M_BoatSurface` and `M_BoatMast` read slots 12-15 beside the 10-11 that `dirt` already read. A boat with no seed (the player's,
the AI boats, slot 12 = -1) draws exactly as before.

- **Sun** scales oxidation by 0.6 + 0.8 Sun: a hull facing south-west chalks faster.
- **Wet** draws a stain band from the waterline up to Wet metres, ragged along the hull. It is stronger with age and weaker
  with care. On the lake it is green-brown algae. On salt water it is a tan band with a thin line of dried salt at its top.
- **Site:** salt water also makes rust streaks more frequent and stronger.
- **Variant** shifts the gelcoat by up to 3% either way.

`M_WorldSurface` reads slots 10-15 on the private docks and boathouses. The baked tiles carry no instance data, so they
hash a seed per 4 m of world plan with the ranges above, using the Fixed water bands. They take the site from
`MPC_World.Site`, which `ASailingEnvironment` sets from `WearSiteFor`. Variant shifts each structure's colour by up to 4%.

- **Deck planks** silver within about 4 years, faster in the sun. An old dock that is kept has some replaced boards, which
  stay brown. A neglected, shaded one goes dark with mildew.
- **Pilings** carry their stain band up to Wet metres. Below it they are green-black algae on the lake, and a pale, rough
  crust of barnacles on salt water, thicker with age. They crack more when neglected and silver with age in the sun.
- **Dock boxes** yellow with age in the sun and green at the base when neglected.
- **Painted steel** weeps rust from more seams near salt and with age, and fades in the sun.
- **Concrete** bulkheads and bridge piers carry the water's ring up to Wet metres above the datum, with a pale salt line on
  salt water. Buildings stand well above the ring.

Checks on the PC (Ultra, D3D12, packaged Development):
- 152/152 tests.
- Marina 70.7 fps and slip close 75.7 fps. These are 8 s stills, not a gate.

Stills in `pc/`: `lake-slip-ultra.jpg`, `lake-slip-dock-crop.jpg` and `marina-ultra.jpg`. A close bay still is still to
come: the bay marina I tried was too shallow at the start point I picked, and the boat ran aground.

**Follow-up (Oct 17, with round 12's Kemah towers):** at Kemah's pier the first piling bands didn't read. The barnacle
crust filled exactly the low part of the band where the stain was strongest. Its shells were paler than the wood and
3.5 cm across, so a few metres off they blurred into plain pale wood, and the stain above them faded out at once.
A false-colour render confirmed the site, the band height and the height above the water were all right, so the fix
is in the shading:
- The stain is full up to 70% of the band and darker green-brown (0.3 of the wood).
- The crust is confined to the band's lowest quarter: wet grey shells about 6 cm across, each its own size and off-centre,
  with dark gaps between them.
- The damp wood's roughness is 0.75, not 0.55.

Stills: `pc/bay-piling-kemah.jpg` and its crop `pc/bay-piling-kemah-crop.jpg`, from the packaged game on Ultra, 1 m above
the water, 12 m off a Kemah pier at sim (-683, 517).
