# Boat kit

The studio-style boat pipeline from the plan "Boat modeling pipeline plan" (Claude Doc, Oct 16 2026). Instead of
one script drawing a whole boat, fittings are modelled once at hero quality and placed on every boat from data. Phase 1
(docs/boatkit-1) is the kit, the J/22 layout, character sheets and the photo match loop. Boat fidelity 2
(docs/boat-fidelity-2) adds catalogue sizes, the lifeline and rigging parts, a shared 10 px/cm trim sheet, a light version of
every part and the import into the game (`/Game/Boats/Kit`, `scripts/import_hardware_kit.py`); fitting it to a boat is phase 3.

| File | What it does |
| --- | --- |
| `bk_geom.py` | Primitives (lathe, prism, rotation-minimising sweep), angle-limited bevels, weighted normals, sockets |
| `bk_materials.py` | Preview materials read from the game's `MI_Boat_*` table in `scripts/make_materials.py` |
| `bk_parts.py` | The kit: 43 generic, brand-free fittings, each with sockets (`SOCKET_*` empties), catalogue sizes (`SIZES`) and maker's plates (`badge`, the made-up TERNWAY) |
| `bk_trim.py` | Trim-sheet UVs: each face on its surface kind's band at 10 px/cm, badges fitted whole into their plate cell |
| `make_trim_sheet.py` | The shared trim sheet (`Inputs/boat-kit/T_KitTrim_N/_M`, `trim.json`), numpy and Pillow |
| `make_review_sheet.py` | Lays the review renders out as sheets (a system Python with Pillow) |
| `bk_layout.py` | Places parts from `layouts/<boat>.json`: sockets or positions, snapped onto the hull, mirrored, stacked |
| `bk_touches.py` | Owner touches (coiled line, cooler, fenders, stowed winch handle, tiller bungee, bottle) |
| `characters/*.json` | One boat each: registration, seed, story, wear levels, colours, touches |
| `build_kit.py` | Builds every part, exports `SM_Kit_<Part>.fbx` (hero) and `SM_Kit_<Part>_Light.fbx` (decimated) and `kit.json`, renders the catalogue and the size rows |
| `dress_boat.py` | Dresses a boat (hull with its baked fittings stripped, kit, touches), writes `placements.json`, renders |
| `photomatch/solve_camera.py` | Solves a photo's camera from picked points (DLT + Levenberg-Marquardt, or a fixed lens) |
| `photomatch/match_blend.py` | Renders any saved .blend (the hero J/22) from a solved camera and writes the compare image |
| `photomatch/profile_match.py` | Lays the hero's side outline over a square-on broadside photo from two picked points (stem top, transom top) and prints the picked stations in hero metres (`matches/<photo>.profile.json`) |
| `photomatch/compare.py` | Photo, render, blend and outline overlay in one image |
| `partloop/render_views.py` | Part detail loop: one part from the same views every round (six turntable, two in use for blocks and cleats, clay, side, edge and top outlines) and its `stats.json` |
| `partloop/score.py` | Part detail loop: the scorecard (sizes, outline overlap, features, budget, blind review) against the part's card in `partloop/parts/<part>.json` |
| `partloop/render_assembly.py` | Part detail loop: parts in place on the J/22 before and after (the 4:1 vang: Fiddle40, FiddleCam, the line reeved through them) |
| `partloop/render_marks.py` | Part detail loop: the course marks and the crew-overboard buoy floating on a lake from a helm's eye, before (the game's engine shapes) and after |
| `partloop/make_sheet.py` | Part detail loop: the before/after sheet for Bean (reference photo, both rounds' views, scorecards, outline overlap) |

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
   `"solve": false` are checks, reported against the solved camera. Spread the points in depth: when they lie near one
   plane (all along the sheer) the camera's height and distance trade off freely and the fit still looks good; the
   solver warns when `flatness` is under 0.08 (docs/boatkit-2).
3. `dress_boat.py <layout> <character> <out> --render --camera <photo>.camera.json --photo <photo.jpg>` renders from
   that camera and writes `compare_<photo>.jpg`. For the hero hull itself, `blender -b -P
   Tools/boatkit/photomatch/match_blend.py -- <model.blend> <photo>.camera.json <photo.jpg> <out>`.
4. Fix the layout or the hull where the outline and the photo disagree, and run it again.

## The part detail loop

One part at a time, to raise the hardware's detail against real references (docs/part-detail-loop, plan "Boat part detail
loop", Nov 8 2026): a card per part (`partloop/parts/<part>.json`: references as links, sizes, the feature list, budget),
the reference photos and their outline masks in a git-ignored folder (`Data/Reference/raw/parts/<Part>/`), then rounds of
build, `render_views.py`, `score.py` and a blind side-by-side review until every check passes.

    python3 Tools/boatkit/partloop/render_views.py Block40 Artifacts/partloop/Block40/r1      # or blender -b -P ... --
    python3 Tools/boatkit/partloop/score.py Tools/boatkit/partloop/parts/block40.json Data/Reference/raw/parts/Block40 Artifacts/partloop/Block40/r1
    python3 Tools/boatkit/partloop/make_sheet.py <ref photo> Artifacts/partloop/Block40/before Artifacts/partloop/Block40/r3 sheet.jpg --title "..." --credit "..."

score.py and make_sheet.py need numpy, scipy and Pillow. Sheets that show a third party's photo stay out of the repo.
