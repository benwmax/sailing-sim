# Region packs

Everything about the shore that belongs to one part of the world is data in a **region pack**, not code: which ground
surfaces, grasses and trees grow there, which bank types and docks the lots get, the house styles, the props in the
yards, the seasons and their colours. The tools and the game read a pack by name, so a second region is a new pack
folder and a few new assets, not new code. The first pack is `north-texas-lake` (Lake Ray Hubbard).

Three rules every track keeps (the shore plan, "Built to work for other locations"):

1. **Region content is in the pack.** A track's builders make assets; the pack says which of them a region uses and
   where. Nothing North Texas–specific goes in a script.
2. **Placement is by rule from map data.** A pack entry's `where` may only use the inputs in `pack.py RULES` (distance and
   height to the water, depth, slope, tree cover, crown height, land use, house lot, bank type, boathouse, street side,
   distance to a house, footprint, storeys, roof shape, commercial). The only hand placement is the home club (`hand_placed`).
3. **Buildings are parts plus recipes.** A house style picks one part per slot (wall, roof finish, window, door, garage
   door, chimney, porch, trim) by weight. The roof shape is not picked: it comes from the house's lidar fit.

## Layout

```
Tools/envloop/packs/<pack id>/
  pack.json        where it applies, climate, seasons, the map data its rules read, sizes, material slots and tints
  ground.json      Track A: ground surfaces
  grass.json       Track B: grasses and ground plants
  shoreline.json   Track C: bank and edge types, and the lot edge shares
  trees.json       Track D: tree and shrub species
  buildings.json   Track E: parts by slot, and house-style recipes
  docks.json       Track F: docks, boathouses, marina sheds, boats in their sockets
  yard.json        Track H: yard and shore props
```

`tracks.json` names each track's file (`pack_file`) and where the track keeps its asset ids (`assets`). Track G (the
clubhouse) is hand built for the home club and has no pack file; Track I (rollout) reads them all.

### pack.json

| Field | What |
| --- | --- |
| `id`, `name` | the folder name, and a name for people |
| `extends` | another pack to start from, or null |
| `applies_to` | the worlds (bake names) and a lat/lon box |
| `place` | lat, lon, UTC offset, elevation, a line on the climate, the reference day and hour for stills |
| `seasons`, `required_seasons` | season names with their months and a note on what changes; the ones every asset with seasons must have |
| `map_data` | which bake files the rules read |
| `sizes` | the size card it uses (`base`) and rows it changes (`overrides`: a metric region's doors and windows) |
| `hand_placed` | where hand placement is allowed (the home club only) |
| `material_slots` | shared slot names (MetalRoof, Galv, Canvas, Plastic, Vinyl, Carpet, Paint) and their tints, linear RGB |

### A track file

```json
{"pack": "north-texas-lake", "track": "F", "note": "...",
 "entries": [
  {"id": "shore-dock-a", "asset": "SM_ShoreDock_A", "group": "dock", "weight": 3,
   "where": {"lot_edge": ["bulkhead"], "depth_m": [1.0, 99], "boathouse": false},
   "sockets": ["boat_0"]},
  {"id": "shore-boat-pwc", "asset": "SM_ShoreBoat_PWC", "group": "boat", "weight": 3, "fills": ["pwc_N"]}
 ]}
```

| Field | What |
| --- | --- |
| `id` | lower-case words joined by `-`, unique in the file |
| `asset` | the track's own asset id (a mesh name, a card name), or null until it is made |
| `group`, `weight` | entries in one group are alternatives; one is picked per place by weight (seeded by the place) |
| `seasons` | which of the pack's seasons it has |
| `where` | the placement rule: ranges are `[min, max]`, sets are lists of names, flags true or false; all must hold |
| `sockets` | named attach points it carries (`boat_0`, `pwc_port_0`, `kayak_1`, `umbrella_0`, `chairs_0`) |
| `fills` | the sockets it can fill instead of a `where`, `N` meaning any number (`boat_N`) |
| `latin`, `note`, `where_text` | for people |

Extra keys a track needs stay in its file (`lot_edge_shares` in shoreline, `per_lot` in yard, `slots` and `parts` in
buildings). Tracks keep their own card formats; the pack only points at their assets.

### Buildings

`buildings.json` adds `slots`, `parts` (per slot: `id`, `asset`, optional `tint` or `slot_material`) and, on each style
entry, a `recipe`: for every slot, the parts it may use with their weights. The style's `where` picks it by storeys,
roof shape, footprint and distance to the water. Today: ranch brick 1970s, traditional two-storey brick, lake cottage,
craftsman, modern farmhouse, Mediterranean stucco.

## A new region

1. Make `packs/<id>/pack.json` with `"extends": "north-texas-lake"` if most of it carries over, or null.
2. In each track file list only what changes: an entry with an inherited id replaces it, `"drop": true` removes it,
   new ids add. For buildings, add parts to a slot and new recipes.
3. Make the new assets in their tracks, with `"packs": ["<id>"]` on their cards.
4. `python3 Tools/envloop/pack.py check` and `python3 Tools/envloop/test_envloop.py`.

## Tools

- `pack.py check [pack]` checks every pack: fields, ids, groups and weights, seasons, that rules use map data only,
  that assets exist in their track (once the track has made some), socket names, the lot edge shares, every recipe part.
- `pack.py show <pack> <track>` prints a track's file with its parents folded in; `pack.load(id)` in Python.
- `render_bands.py --pack <id>` lights the midday renders with the pack's sun at solar noon on its reference day
  (80.5 deg on Ray Hubbard on 15 June).
- `check_card.py` checks a card's `packs`.

Shares and species in `trees.json` and the style weights in `buildings.json` are first guesses for the tracks to confirm.
`shoreline.json`'s lot edge shares are what HouseKit.cpp does today (0.55, 0.30, 0.15); the game reads none of this yet
(Track I wires it after the slice).
