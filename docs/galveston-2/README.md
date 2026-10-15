# Galveston 2: moored boats off the land, the Gulf front

The Galveston round deferred from Graphics G7. The bay map now grows south to take the Gulf front pack
(`Inputs/g2/gulf-front`, from the `inputs` branch; README there). The moored boats now have to float at low water.

![The Seawall and the Pleasure Pier from the Gulf, High](seawall.png)

![Chart view off the Seawall](chart-gulf-front.png)

## The grid grows south

`Tools/coast/build_galveston.py`'s Galveston box now starts at 29.19 N instead of 29.295 N. The 10 m grid runs from
sim north -39,240 to 8,910 (4,356 x 4,815 cells, 11.8 million of them water) and holds everything in the pack. The pack
said about -38,200 would do. The ENC cells the bake already had (US4TX1MI/MJ/MK, 29.1-29.4 N) chart the whole strip, so
no new charts were needed. The 3DEP DEM was fetched again over the wider box. The OpenStreetMap land use, buildings and
piers got a fourth tile, 29.18-29.29 N. `Tools/coast/fetch_galveston.sh` now fetches the wider box. Cells, coordinates
and everything north of the old edge are unchanged; the map frame keeps its origin at Kemah.

## The Gulf front (`Tools/coast/build_piers.py`)

| Piece | Source | Drawn as |
|---|---|---|
| Galveston Seawall, 10,959 m, crest +4.72 m MLLW | gulf-front `landmarks.geojson` (replaces the bay pack's end of it) | seawall (concrete), an obstacle |
| North Jetty 5,981 m to Light 6A, South Jetty 3,552 m to Light 5A | the same, replacing the bay pack's traces | jetty rock (riprap with boulders) |
| Pleasure Pier (deck +10.05 m), 90th St pier (+5.21 m), 61st St pier (+4.80 m) | `gulf_piers.geojson`, named | pier decks on piles |
| 16 groins (15 Gulf lidar groins and one more) | `groins.geojson` and the pack's narrow structures | riprap |
| 16 more groins and breakwaters | `charted_structures.geojson`, where no lidar groin lies within 15 m | low rock lines (crest +1.0 m, the chart has no height) |
| 3 piers | `charted_structures.geojson`, where the lidar had no deck (low walkways) | pier decks at +3.0 m (the chart has no height) |
| 498 decks, 26 marinas, the island's boats | gulf-front `piers/` (the piers pack's layers for the island) | as the bay's |
| 13,883 buildings, 57,556 trees | gulf-front `shore/` | houses (`build_houses.py`) and crowns (`build_crowns.py`) |

The jetty head lights come from the chart, as before (the navaids bake). I didn't model the beach profiles (398 lines):
the 10 m grid takes its beach from the DEM, and the profiles are a check for a finer beach later. The 0.5 m cover tiles
(`shore/cover.tar.gz`, 39 MB) aren't used, so I left them out of the repo copy.

Rebuilt from the bakes: the shore kit's Nanite tiles (`scripts/bake-shore.sh GalvestonBay`, 509 tiles), the houses
(`scripts/make-houses.sh`: 61,091 houses), the crowns (470,243), the launch map and minimap (`make_ui_art.py`, imported
with `UI_ART_ONLY`), the chart and the tidal current field.

## Moored boats

The brief said about 6,000 moored boats sit on land. In the current bake they don't: G7 had already left out the
6,184 boats whose 10 m cell is land (narrow canals, boat yards). But it kept boats over anything up to 0.1 m above
MLLW. That puts 212 of the 1,447 boats on mud at low water, and many more aground in less water than they draw.

Now a boat is kept only where the grid has water under her keel at MLLW, the chart datum and the lowest normal tide. The
water must be deeper than her draft, which is estimated from her length: 0.3 + 0.13 L for a keelboat, 0.2 + 0.07 L for a
power boat. The one exception is a boat inside a marina polygon, where wet at MLLW is enough: dredged basins get
averaged with their banks in 10 m cells. With the Gulf front's boats added:

| | Boats |
|---|---|
| In both packs | 9,754 |
| On land at MLLW in the 10 m grid | 7,614 left out |
| Wet but shallower than their draft, outside a marina | 622 left out |
| Through a dock (the 2018 boat and a later dock disagree) | 355 left out |
| **Drawn** | **1,163** (1,039 in marinas, 214 south of the old grid edge) |

`SailingSim.Coast.MooredBoatsAfloat` checks that no boat has land under her at MLLW and that none outside a marina has less
water than her draft. `SailingSim.Coast.GulfFront` checks that the grid reaches past the 90th St pier and that there is
Gulf water off the Pleasure Pier with the island behind the wall. It also checks the Seawall's length, both jetties
ending at their head lights, the Gulf groins, and the three named piers on their lidar decks.

## Not done
- **The Gulf front has no swell in the Galveston world.** It is the bay's fetch-limited chop, because the FFT ocean is
  the Gulf passage world's. The Gulf passage world itself is unchanged.
- **The brief's `SailingSim.Gulf` filter matches no tests**, because the Gulf passage's tests sit under `SailingSim.Coast`
  (`LongPassageStable`) and `SailingSim.Physics` (ocean). I ran the full suite.
- The beach profiles (above).

## Gate

- `scripts/build.sh`, `scripts/test.sh`: 125 passed, 0 failed (new: `SailingSim.Coast.MooredBoatsAfloat`, `SailingSim.Coast.GulfFront`;
  every `SailingSim.Coast` test passes, including the Gulf passage's `LongPassageStable`).
- `scripts/package-mac.sh`: succeeded.
- `bench-phase5.sh` and `bench-phase7.sh` (packaged, Medium, 12 s, `NO_DOCS=1` so their published stills stay; `phase5-bench.csv`, `phase7-bench.csv`):

| View | fps | p99 |
|---|---|---|
| coast-day | 87.3 | 12.08 ms |
| coast-bay | 80.7 | 13.34 ms |
| coast-night | 103.1 | 10.66 ms |
| coast-dusk | 114.1 | 9.66 ms |
| chart | 119.8 | 9.39 ms |
| chart-bay | 119.6 | 8.71 ms |

| View | fps | p99 |
|---|---|---|
| gulf-sea | 113.0 | 9.32 ms |
| gulf-swell | 117.3 | 9.06 ms |
| gulf-dusk | 118.5 | 8.65 ms |
| gulf-entrance | 107.5 | 9.92 ms |
| gulf-chart | 119.8 | 8.68 ms |
| logbook | 78.7 | 13.56 ms |
| ghost | 89.0 | 12.34 ms |

- bench-visual, Medium and High (`bench-visual.csv`, screenshots in `bench/`). Every view holds Medium 60 and High 45. The
  coast views on High are 1.5-4 fps lower than in the W3 prep run a few hours earlier (no Gulf front): coast-day goes from 51.3 to 49.4 and
  coast-night from 55.9 to 51.5, because of the island's houses, trees and piers.

| View | Medium fps | p99 | High fps | p99 |
|---|---|---|---|---|
| beam8 | 93.2 | 11.42 ms | 56.3 | 19.63 ms |
| beat15 | 90.3 | 12.23 ms | 55.0 | 22.32 ms |
| storm | 69.0 | 16.21 ms | 48.1 | 23.87 ms |
| marina | 88.6 | 12.48 ms | 52.2 | 21.12 ms |
| coast-day | 86.9 | 12.11 ms | 49.4 | 21.57 ms |
| coast-night | 104.3 | 10.58 ms | 51.5 | 20.98 ms |
| gulf-sea | 109.9 | 9.55 ms | 61.2 | 17.43 ms |
| helm-eye | 92.2 | 11.75 ms | 54.9 | 20.14 ms |
| slip | 74.2 | 15.39 ms | 47.1 | 23.62 ms |
| bridge | 98.0 | 10.97 ms | 56.5 | 19.07 ms |
| crew | 118.6 | 8.58 ms | 68.9 | 15.74 ms |
| marina-night | 90.0 | 12.75 ms | 59.0 | 18.89 ms |
