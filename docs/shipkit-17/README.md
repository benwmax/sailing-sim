# Shipkit 17: the frigate Commonwealth's Unreal export

Slice 17 of *Commonwealth*, our own 36-gun frigate of 1797 (the plan: <https://claude.ai/artifact/8y6hW8vHjjUPJRovJEuxY7>;
her hull, rig, sails, guns and decks are slices 1 to 14, [docs/shipkit-1](../shipkit-1/README.md) onward, her textures
and wear slice 15, [docs/shipkit-15](../shipkit-15/README.md), her light copy slice 16,
[docs/shipkit-16](../shipkit-16/README.md)). Until now she lived in one Blender file. This slice writes her out for
the game: **475 FBX files** (one per part above the gun deck, the decks below merged, the guns' shared meshes once
each, every moving part on its own pivot), each with its light twin for the import to make LOD 1, a sockets file that
says where every copy goes and in which state it shows, and a materials table for the PC to build her material
instances from. It is tools and docs only, like slices 1 to 16: the PC lane imports her (plan: Nov 25 to 30) with
`scripts/import_boats.py`'s conventions (FBX axes as the maxi's, `MI_<Tag>_*` slot names, a `<Tag>_sockets.json` in
centimetres), and the wiring thread's game code reads the sockets file's `states`, `placed`, `guns` and `lights`.

## What is written

`Tools/shipkit/frigate/export.py <build>/frigate_light.blend <out> --build <build>` (the light copy's merged
file; `export_1797.json` says what goes where). Every mesh is in the ship's frame (origin midships on the load
waterline, X forward, Y starboard, Z up: the build's frame, which is Unreal's) unless it is a part that moves, which is
in its own frame and placed by the sockets file. On the slice 13 build (the berth deck, `docs/shipkit-13`):

| group | files | detailed triangles | what |
| --- | ---: | ---: | --- |
| `Outside/SM_Frigate_<Part>` | 246 | 2,720,009 | one per part above the gun deck: hull, decks, fittings, spars, standing and running rigging, sails in each set, boats, the lid lanyards and the carronades' chocks (modelled in the ship's frame, so they go here: `ship_frame_parts`); the wheel and the capstan's drumhead on their own pivots (`deck.json` `frames`) |
| `Decks/SM_Frigate_<Deck>` | 11 | 529,329 | `GunDeck` (with its twin `SM_Frigate_GunDeck_Light`: seen through the waist and the ports), `BerthDeck`, its day and night sets `BerthDeck_Hammocks` and `BerthDeck_Messes` merged apart, the berth deck's six instanced meshes (hammock, hook, mess table, bench, kid, sea chest) once each, and the gun deck's turning parts on their pivots (`gundeck.json` `frames`: the capstan's head, the two cabin doors; the tiller and its six rope parts once the tiller build merges) |
| `Guns/SM_Frigate_<Mesh>` | 218 | 3,520,600 | the shared meshes once each in their own frames (`Gun24_Barrel`, `_Carriage`, `_Quoin`, `_TruckFore`, `_TruckHind`, `_Tompion`, `_Apron`; `Carr32_Barrel`, `_Bed`, `_Slide`), each gun's gear for each pose and its irons in its port's frame (`Gun24_S01_GearHoused`, `_GearRunIn`, `_GearRunOut`, `_Irons`; `Carr32_S01_GearRunOut`, `_GearRecoil`, `_Irons`), the 30 port lids in their hinges' frames (`Lid_01_S` to `Lid_15_P`: origin on the hinge, +X along it) |

Every mesh above the berth deck has its twin beside it, `<file>_Light.fbx` (468 of the 475; the berth deck's seven
have none: drawn only from inside, close to). 241 MB in all. The detailed triangles above are every file's once; what
the game draws in a state is the sockets file's `states` and slice 16's budget (959,776 light triangles under sail,
982,638 cleared for action).

**`Frigate_sockets.json`** (centimetres, the ship's frame):

- `meshes`: for every file its group, asset path (`/Game/Boats/Frigate/<Group>/SM_Frigate_<Name>`), triangles, slots,
  its twin's file and triangles, the part or parts in it, the frame it is in (`ship`, `port`, `hinge`, `its own`), the
  states it shows in (`underway`, `action`, `clewed`, `anchored`: a part in none of the pose collections shows in all
  four), and for a part that turns the build's `turns` note (the axis and sense: the wheel about its own +X, a positive
  turn taking the ship's head to port; the capstans about +Z).
- `placed`: 1,345 placings of the shared and framed meshes: each gun part in each pose (`Guns_Housed` 252,
  `Guns_RunIn` 224, `Guns_RunOut` 224, `Carronades_RunOut` and `_Recoil` 66 each, and from the `Guns` collection
  the 50 irons and 22 slides that every pose shares), the 30 lids, the berth deck's
  236 hooks, hammocks (112, by night) and mess things (58, by day), and the five framed parts, each as `mesh`,
  `location_cm`, `rotation_xyzw` (a quaternion), `scale`, its collection and deck, and its `owner`: `battery` for
  what the cannon-fire code spawns and moves itself (every gun's parts in each pose, its gear, irons, tompion and
  apron, and the 28 lids with a gun behind them: 932 placings), `ship` for the static placement (the two bridle
  ports' lids `Lid_15_S`/`_P`, shut always, the framed parts, the berth deck's copies). The battery places one set of
  gun parts and moves it between the poses' placings; the ship must not place the battery's, or they draw twice.
- `guns`: `guns.json`'s port frames, poses, elevations and the lids' hinge frames (metres there), for the cannon-fire
  thread's recoil and the lids' opening, with `frames_note` (a port frame: origin on the deck where the port's middle line meets
  the side's inner face, +X out through the port, +Z the deck's normal; a hinge frame: origin on the hinge, +X along it) and `meshes`: the frame each shared mesh's vertices
  are in (the gun parts in their port's, the lids in their hinge's).
- `lights`: the 27 lanterns below (15 on the gun deck, 12 on the berth deck) with zone, colour, kelvin, lumens,
  `cast_shadows`, `location_cm`, `radius_cm`, and each deck's `light_budget` (16 lights) from the build.
- `states`: the four states' collections (slice 16's `light_1797.json`), `root`, `twins`, `parts_without_twin` (empty).

**`Frigate_materials.json`**: the five wear levels (age and care) and, for each of the 43 materials, its slot
(`MI_Frigate_<Material>`), the undressed base colour and roughness, its surface and kind on slice 15's cards, and the
wear terms at each level (`weathering.amounts`, the same numbers the Blender dressing uses), for the PC to build the
material instances (`MI_Frigate_*` over `M_BoatSurface`'s kinds, or a frigate master: the PC lane's call).

## The tiller build

Re-run on the model thread's tiller build (PR #799, `docs/frigate-tiller`, which carries slice 14's orlop and hold too)
after its twins: the 30 parts that build changed or added above the berth deck (the tiller's nine, the cabin's bulkhead,
doors, skylights, window seat, stanchions, the wheel's standards, the gun deck itself, eight tackles near the stern)
got new twins by `light.py --only`, merged over slice 16's (first given wins), and every state stays under the budget:
underway 962,170, cleared for action 985,222, courses clewed 971,531, at anchor 943,121 light triangles, worst error
15.03 mm, nothing failing. The export is then **484 files, 254 MB**: Outside 246 (the tiller rope's still legs among
them), Decks 20 (the tiller and its six rope parts on their own frames, `Decks/SM_Frigate_Orlop` 178,612 and `_Hold`
372,048 triangles, no twins: both below), Guns 218; 1,352 placings; 29 lanterns (the orlop's two from `orlop.json`,
which slice 14 writes for the orlop and the hold together: `export_1797.json` names it for both and the export reads it
once; those two give only a place and colour, so `lights_note` says what to assume until the model thread adds kelvin,
lumens and radius). New in the sockets file: **`helm`**, the tiller's turn (about its own +Z, hard over 35 degrees, 5.02
wheel turns lock to lock) and, at each whole degree of helm, the frame each rope part takes (`poses`: 71 rows of
`location_cm`, `rotation_xyzw` and a run's X scale, from `gundeck.json`'s `tiller_ropes`; the amidships row equals the
parts' `placed` frames). It is at `/mnt/project-files/tall-ship/export-tiller/` for the PC import.

## Checks

An independent review of the export found three labelling faults, fixed before this page's numbers: the lid lanyards
(in two pose collections) and the carronades' chocks were sorted into Guns/ and handed to the battery though they are
modelled in the ship's frame (now `ship_frame_parts`, Outside/, owner `ship`); 78 gear meshes were labelled `its own`
frame instead of `port`; and the first real export had no lanterns or turning frames because the build's json files
were read only beside the blend (now `--build`).

- Every exported mesh above the berth deck has a twin (`parts_without_twin: []`), and the twins' triangles per state
  are slice 16's.
- Round trip: `SM_Frigate_Wheel.fbx` read back into Blender has its 4,488 triangles, its pivot at the axle (bounds
  symmetric about the origin, ±0.673 along the axle, ±1.067 across, ±1.018 up) and slots `MI_Frigate_Iron`,
  `MI_Frigate_Oak`; its twin 1,138 triangles in the same box; `SM_Frigate_Lid_01_S.fbx` has its origin on the hinge
  (0 to 0.81 m across the lid from it); `SM_Frigate_GunDeck_Light.fbx` carries the deck's `Planking` and `Margin` UVs
  and `SM_Frigate_Skin_Light.fbx` the hull's three slots.
- The moving parts' frames agree with the wiring thread's expectation (its `docs/ship-frames`): vertices in the frame's
  own axes, the frame in `placed` under the part's name, Decks/ for the gun deck's, Outside/ for the wheel and capstan.

## Running it

    python -I Tools/shipkit/frigate/light.py ...                     # slice 16: the twins, merged into frigate_light.blend
    python -I Tools/shipkit/frigate/export.py <out16>/frigate_light.blend <out17> --build <build>   # about 4 minutes
    python -I Tools/shipkit/frigate/export.py <build>/frigate.blend <out17> --dry                   # the two json files and the counts, no FBX

with bpy 5.3 in a Python 3.13 venv. `--only Outside,Decks,Guns` exports some groups. `--build` names the build's
folder (by default the blend's own): `guns.json` and `deck.json` are required, and each built deck's json
(`gundeck.json`, `berthdeck.json`) too, since those give the port frames, the turning parts' frames and the lanterns;
without one it stops and says which.

## Files

| file | what |
| --- | --- |
| `Tools/shipkit/frigate/export.py` | the export above; the tiller build's `helm` table and slice 14's lantern format |
| `Tools/shipkit/frigate/export_1797.json` | the groups, the decks' collections, properties, poses and build files (the hold's is `orlop.json`), the gun parts, the lids' frame rule, the asset root |
| `docs/shipkit-17/` | this page |

The export itself (241 MB of FBX) is not in git: the PC lane runs the export on the model thread's build (or takes it
from `/mnt/project-files/tall-ship/`) and imports it; the cooked game carries the meshes.

## Still to do

- The orlop's two lanterns' kelvin, lumens and radius, once the model thread adds them to `orlop.json`.
- The PC import (`scripts/import_boats.py` or a frigate importer): LOD 1 from each `_Light.fbx` at slice 16's switch
  sizes (`docs/shipkit-16/light.json`'s `ue_screen_size`), the material instances from `Frigate_materials.json`.
