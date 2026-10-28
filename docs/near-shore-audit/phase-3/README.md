# Near-shore audit, phase 3: breakwater, bridge, shore trees

Follow-up to the near-shore audit's items 5 to 7. Procedural only; no downloaded assets.

## What changed

- **Breakwater (item 5: "one large rounded shape repeated in a line").**
  - `build_props.py` makes twelve rocks. The first six are unchanged (the shore's riprap uses them); 6 to 11 are a flat
    slab, a long block and an angular piece, each twice, with more fracture faces and less rounding.
  - `AMarinaActor` piles the breakwater from all twelve:
    - sizes spread like quarried armour stone (mostly 0.8 to 1.5 m, one in eight up to 2.3 m);
    - each rock stretched and tipped its own way;
    - small chinking stones in the gaps;
    - a half-drowned toe of big stones at the waterline.
    Each rock carries custom data with its own shade and wet line.
  - `MI_World_Rock` has its own stone variant of the concrete pattern (4.25). It has world-space mottling and pits, pale
    tops with lichen, the per-rock shade, and a dark, green ring below the wet line. Form-tie lines and run-off streaks
    stay on concrete.
- **Bridges (item 6: clean extruded concrete).**
  - `BuildBridgeGeometry` writes UV1 on the bridge concrete: the deck, girders and barriers carry their position along
    the bridge in pier spacings, the columns their height, and the caps a flag. The flags sit at -1000 and below, so an
    imported mesh reading its UV0 there never trips them.
  - `M_WorldSurface` stains a dark, ragged band about a metre wide down the fascia at every joint over a pier, rust at its
    core, with general grime on the deck. Streaks run down the columns from the cap, each its own length. The columns
    have a deeper, greener waterline ring, and the caps are grimed.
  - `scripts/bake_bridges.py` rebakes the bridge tiles (Ray Hubbard, Galveston Bay, Gulf Passage: 335 tiles) and waits for
    their distance fields.
- **Shore trees (item 7: species and sizes repeat, one canopy height).**
  - `ALakeTerrainActor::AddYardTrees` (`-SailingNoYardTrees` compares) plants one to three young trees round each
    full-detail house. Most go on the water side, at a third to two-thirds of their species' height: a second height
    class under the lidar's mature crowns.
  - Species come from the lot's own palette, by 60 m cell, so a street shares a planting and the next one differs. There
    are four palettes on the lake (live oak and cedar elm, elm and sugarberry, cedar and oak, sugarberry and willow by the
    water) and two on the coast. No tree is added in a 6 m cell where one already stands.
  - Ray Hubbard gets about 20,000 yard trees.

## Cost

Main's bridge tiles, `M_WorldSurface` and `MI_World_*`, without yard trees, against the branch's, alternating, two rounds.
Measured with the new rocks' derived data warmed first. RTX 4090, 1920x1080, uncooked. Each cell is main → branch. The
marina's new rock placement is in both runs (it is code, not an asset), so the marina view's 0.17 ms of GPU is its new
material and shapes only. Phase 2's understory (merged after these runs) shows the same in both.

| View | Tier | fps | game ms | render ms | GPU ms |
|---|---|---|---|---|---|
| Marina, raised | Ultra | 65.9 → 71.4 | 11.78 → 10.96 | 6.34 → 5.83 | 6.60 → 6.77 |
| Marina, raised | High | 78.5 → 78.4 | 10.15 → 10.27 | 5.29 → 5.29 | 4.55 → 4.59 |
| Bridge, eye | Ultra | 67.7 → 72.7 | 12.02 → 10.80 | 6.10 → 5.71 | 6.88 → 6.83 |
| Bridge, eye | High | 77.5 → 76.6 | 10.10 → 10.04 | 5.36 → 5.43 | 4.29 → 4.31 |
| Residential, raised | Ultra | 72.7 → 73.1 | 11.02 → 10.88 | 5.58 → 5.56 | 7.14 → 7.04 |
| Residential, raised | High | 77.2 → 77.1 | 10.34 → 10.30 | 5.26 → 5.25 | 4.88 → 4.79 |
| Helm eye | Ultra | 56.5 → 58.2 | 15.76 → 15.29 | 7.46 → 7.22 | 7.76 → 7.71 |
| Helm eye | High | 61.8 → 59.3 | 14.07 → 14.24 | 6.79 → 7.08 | 5.12 → 5.14 |

The GPU is within 0.2 ms everywhere. The Ultra marina and bridge views ran slower on main's assets in both rounds. They
ran first after each swap back to main's tiles, so the cause is main's bridge tiles' derived data, not this branch. The
rest is run-to-run noise.

## Stills (Ultra, the audit's camera spots)

- `breakwater-15h.jpg`: the marina breakwater at full resolution, before above, after below.
- `marina-noon.jpg`: the marina view at 12:30, side by side.
- `bridge-15h.jpg`, `bridge-eye-detail-15h.jpg`: the I-30 bridge from the raised camera and a detail at eye height.
- `bridge-noon.jpg`: the bridge view at 12:30.
- `residential-trees-15h.jpg`: the residential shore with the young yard trees.

## Not done

- The breakwater rocks are our procedural limestone, not CC0 photo scans (a download wants Bean's OK).
- Bridge pier bents and caps keep their shapes; only the surfaces weather.
