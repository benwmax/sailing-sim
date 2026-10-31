# Rush Creek club docks, pass 2 (slice #405 part 2: pc/club-docks-2)

The floating docks' hardware as real meshes, at real size, in place of the marina generator's kit boxes. The layout, the
home slip and the physics obstacles (`FMarina`) are unchanged.

## The kit (`Tools/blender/build_docks.py` -> `/Game/World/Docks`)

| Mesh | Triangles | What it is |
| --- | ---: | --- |
| `SM_Dock_Cleat` | 368 | a 10 in cast cleat: base plate, two splayed feet, the horn tapering to rounded ends |
| `SM_Dock_Pedestal` | 692 | a shore power pedestal: moulded post, meter window and two outlet covers toward the slip, lamp lens, domed cap |
| `SM_Dock_Box` | 460 | a moulded dock box: rounded body, the lid proud with a lip, hinge, hasp, dark toe kick |
| `SM_Dock_PilingCap` | 180 | a conical cap with its skirt over a 0.34 m piling |
| `SM_Dock_Hoop` | 720 | a steel hoop round the piling, two arms to a plate on the dock's edge, two black rollers |
| `SM_Dock_Ladder` | 704 | a stainless swim ladder off a row's end: rails bent onto the deck, four treads down to 1 m under water |
| `SM_Dock_Float` | 540 | a polyethylene float with moulded ribs (unit size, scaled per module) |
| `SM_Dock_Extinguisher` | 444 | a fire extinguisher cabinet on a post: red cabinet, window, label |

They're built by `scripts/make-world-models.sh` (`build_docks` in its generators) and imported by `import_world.py`
(`SM_Dock` -> `Docks`). The slots are `MI_World_*` looks: White, Steel, Dark, LampGlow, and the new `SafetyRed`
(`WORLD_LIBRARY` in `make_materials.py`).

## Placement

`AMarinaActor::DockKitPlacements` puts each mesh where the generator's boxes stood, from the same rows and slips, as
static instances: 780 in all.
- Two cleats per finger.
- A pedestal at every other slip, and an extinguisher cabinet at every other pedestal.
- Dock boxes where the slip's hash gives one.
- A cap on every piling, and a hoop on every row piling.
- A ladder at each row's end.
- Floats under every 2.4 m module and finger.

They draw within 150 m; the floats draw to 600 m. When the kit is in the content (`HasDockKit`), `BuildGeometry` and the
bake leave those boxes out, so they never draw twice. Without the kit, the boxes stay.

## Triangles per 40 m tile

The baked tiles lose the boxes: 4,161 quads in 22 tiles. Counts are each mesh's LOD 0 by `get_num_triangles`, the
Nanite fallback, the same measure for main and here:

| Tile | Main | Pass 2 |
| --- | ---: | ---: |
| SM_Marina_0_3 | 339 | 256 |
| SM_Marina_0_4 | 348 | 306 |
| SM_Marina_m1_2 | 838 | 788 |
| SM_Marina_m1_3 | 663 | 339 |
| SM_Marina_m1_4 | 792 | 364 |
| SM_Marina_m1_5 | 256 | 156 |
| SM_Marina_m2_3 | 724 | 735 |
| SM_Marina_m2_4 | 813 | 374 |
| SM_Marina_m2_5 | 470 | 302 |
| SM_Marina_m3_3 | 164 | 162 |
| SM_Marina_m3_4 | 112 | 60 |
| The other 11 (clubhouse, piers, walkway) | 1,807 | 1,807 |
| **All 22** | **7,326** | **5,649** |

## Cost

The marina view (bench-phase3's camera, 40 m out, High, 1920x1080, 20 s), uncooked on the RTX 4090, in the same session:

| Build | fps | GPU frame | Game thread |
| --- | --- | --- | --- |
| main | 61.3, 62.2 | 6.39 ms | 12.4-12.6 ms |
| pass 2 (after its rebuild) | 62.5 | 6.39 ms | 12.6 ms |

There's no measurable cost. Pass 2's two runs before main's (55.2 and 59.2 fps, the GPU 6.4-6.7 ms) were the first
after a long pause. Uncooked frame rates aren't the packaged game's; the Mac's High 45 gate is the check.

## Stills

High, 11:00, uncooked. Before (main, left) and after (right, the rebaked tiles and the kit):

| | |
| --- | --- |
| The home slip | ![slip](pass2-slip.jpg) |
| At dock level | ![dock level](pass2-docklevel.jpg) |
| The marina from above | ![overview](pass2-overview.jpg) |

## Notes

- `MI_World_SafetyRed` was made with `WORLD_LIBRARY`'s values by a one-off script on the PC, because a stuck editor
  held `M_WorldSurface`. A `make_materials.py -Only build_world_surface` run after the PC restarts makes it the usual way.
- Pass 1 (`pc/club-docks`) and pass 2 both change `BuildGeometry`. When both are in, pass 1's kit boxes for the same
  hardware (caps, hoops, ladders, cleats, pedestal faces) are skipped under `bDockKitMeshes`, and the marina is rebaked.

## Checked

MSVC build clean. `SailingSim.Lake.*` and `SailingSim.Smoke.*`: 36 of 36 pass.
