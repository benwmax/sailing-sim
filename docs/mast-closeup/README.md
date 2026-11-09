# Square blocks on a mast close up (Nov 9 2026)

**Symptom.** The PC lane's slip still (fleet-slip-fenders-high: J/22, LeavetheDock, CamTarget 0,0,0.5, yaw 90, pitch -35,
CamDist 9, High) showed a white column in the left foreground. It was broken into large grey square blocks in stair-step
clusters (`slip-diag-1-baseline.jpg`). Pulled 2 m back, the column leaves the lens and the blocks go.

**What it is.** The PC ran the same view many ways (frames on the `inputs` branch, `Inputs/slip-diag/`, notes in its
`fleet-status.txt`):

| Run | Blocks |
| --- | --- |
| `-SailingNoBoatDetail`, `r.TextureStreaming 0`, `r.Lumen.Reflections.Allow 0`, `r.Shadow.Virtual.Enable 0`, `r.Nanite 0`, `ShowFlag.AmbientOcclusion 0`, `r.Lumen.DiffuseIndirect.Allow 0` | still there |
| `ShowFlag.InstancedStaticMeshes 0` | gone, with every berthed neighbour |
| Base colour buffer (`r.BufferVisualizationTarget BaseColor`) | there, unlit (`slip-diag-10-basecolor.jpg`) |
| #579's rebuilt dresses | still there |

So the column is a berthed neighbour's mast (a marina ISM instance) beside the lens, and the blocks are in its material's
colour. The neighbour's livery has painted spars (`FBoatLivery::bSparPainted`, `PaintSpars`), so its mast is surface
kind 5, painted aluminium. Its chips came from one hashed value per 1.3 cm cell in the part's x and z (`floor(LP.xz / 1.3)`,
then a hard `step`). A chipped cell was a 1.3 cm square of grey metal, and neighbouring cells joined into stair-step
clusters. From 2 m they are a few pixels. From a few centimetres they are the blocks in the still. The player's own mast
is anodised (kind 4), which has no such term.

**Fix.** `BOAT_CODE`'s painted-aluminium chips are now small, sparse flakes: two octaves of rotated value noise at 0.5 and
0.17 cm across the face (`cpN`, on the rust lane's projection `hwP`), cut at a narrow band (`chipT = 0.80 - 0.10 ageK`).
They cover 3% of the paint at ageK 0.2, 5% at 0.5 and 10% at 1 (measured on a numpy port), still masked by the grime noise
`vn`. Past a metre a flake is about a pixel, so the term fades to that mean cover between 1 and 3 m and doesn't shimmer.

A first cut reused the rust lane's 1.3 cm noise at the old coverage (16 to 26%). The PC's rerun (`slip-diag-14-pr580.jpg`)
had no squares, but a few centimetres from the lens the patches read as camouflage, so the flakes are now smaller and the
cover lower. `chips_compare.png` shows main, that first cut and the fix, 8 cm and 60 cm across, at the oldest paint (numpy
port of the lines).

Cost: a two-octave noise on painted spars only (surface kind 5), a few dozen ALU ops.

## Check

Rerun the slip still on High. The mast in the left foreground should show soft-edged flakes, not squares.
`scripts/gate.sh --scope world` covers the marina views.
