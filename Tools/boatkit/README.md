# Boat kit

The studio-style boat pipeline from the plan "Boat modeling pipeline plan" (Claude Doc, Oct 16 2026). Instead of
one script drawing a whole boat, fittings are modelled once at hero quality and placed on every boat from data. Phase 1
(docs/boatkit-1) is the kit, the J/22 layout, character sheets and the photo match loop. Nothing here is imported into
the game yet.

| File | What it does |
| --- | --- |
| `bk_geom.py` | Primitives (lathe, prism, rotation-minimising sweep), angle-limited bevels, weighted normals, sockets |
| `bk_materials.py` | Preview materials read from the game's `MI_Boat_*` table in `scripts/make_materials.py` |
| `bk_parts.py` | The kit: 31 generic, brand-free fittings, each with sockets (`SOCKET_*` empties) |
| `bk_layout.py` | Places parts from `layouts/<boat>.json`: sockets or positions, snapped onto the hull, mirrored, stacked |
| `bk_touches.py` | Owner touches (coiled line, cooler, fenders, stowed winch handle, tiller bungee, bottle) |
| `characters/*.json` | One boat each: registration, seed, story, wear levels, colours, touches |
| `build_kit.py` | Builds every part, exports `SM_Kit_<Part>.fbx` and `kit.json`, renders the catalogue |
| `dress_boat.py` | Dresses a boat (hull with its baked fittings stripped, kit, touches), writes `placements.json`, renders |
| `photomatch/solve_camera.py` | Solves a photo's camera from picked points (DLT + Levenberg-Marquardt, or a fixed lens) |
| `photomatch/compare.py` | Photo, render, blend and outline overlay in one image |

Run everything with `scripts/make-boatkit.sh [--render]` (Blender or the `bpy` module; about 10 s without renders).

## Rules for parts

- Origin on the mounting surface, +Z out of it, +X forward along the part. Metres.
- Material slots are `MI_Boat_*` names that exist in `BOAT_LIBRARY`; `bk_materials.get` fails on any other name.
- Every hard edge gets a chamfer (`G.finish(ob, bevel)`), and the joined part gets weighted normals.
- Name attach points as sockets: where a line leads, where a pin sits, where a hand grips.
- Generic shapes only: no maker's logo or a copied product silhouette (the game may be sold).

## The photo match loop

1. Pick 4 to 8 points in a photo that the model also has (sockets, or `photomatch/landmarks_j22.json`) and write
   `photomatch/matches/<photo>.json` with pixel positions. Only numbers go in the repo; the photo stays in the
   project files or `Data/Reference/raw/` (git-ignored) when it shows people.
2. `python3 Tools/boatkit/photomatch/solve_camera.py <matches> Inputs/j22-hero/J22H_sockets.json Tools/boatkit/photomatch/landmarks_j22.json`
   Phone photos: set `lens_35mm_equiv` (24 for the iPhone main camera) and four points are enough. Points with
   `"solve": false` are checks, reported against the solved camera.
3. `dress_boat.py <layout> <character> <out> --render --camera <photo>.camera.json --photo <photo.jpg>` renders from
   that camera and writes `compare_<photo>.jpg`.
4. Fix the layout or the hull where the outline and the photo disagree, and run it again.
