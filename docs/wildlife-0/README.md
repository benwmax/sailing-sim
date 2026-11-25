# Wildlife Phase 0: who lives where, and when (Nov 25 2026)

Phase 0 of the wildlife plan (Bean's plan doc "Wildlife plan: accurate animals for each sailing area",
https://claude.ai/artifact/CZNpXuF7h14SXZxj6j6MCY). Post-slice: nothing here merges before the Dec 11 release, and
nothing in the game reads these tables yet (Phase 1 adds the distant birds).

## What it is

A table per world, `Content/TerrainData/<World>.wildlife.json`, built from GBIF sighting records:

- **Who**: 14 to 16 animals or groups of look-alikes per world (`Tools/wildlife/species.json`, the same cast as the
  plan doc's tables): their kind, fresh or salt water, flight or swim style, typical size, flush distance, habitats
  (keys the game will map to depth, shore, chart and pier data) and when in the day they're about.
- **When**: twelve monthly weights. Zero outside the animal's season, a trickle (at most 0.1) in its rare months, and
  inside the season the month's share of the records, divided by all bird records that month in the same area
  (birdwatchers go out far more in spring), floored at 0.15. Animals with fewer than 50 records get flat seasons, and
  up to 300 records the records' shape is blended with flat in proportion (one June bioblitz isn't a season).
- **How many together**: the usual count and the count 9 in 10 groups stay under, from the records' counts when there
  are at least 30, otherwise the catalogue's rough range (the plan's words, checked against video in Phase 1).
- **Where** (dolphins and sharks): record places on a 0.02 degree grid (about 2 km).
- **Credits**: every dataset the table draws on, with its record count and licence.

`TexasCoast` has its own table over the Galveston Bay and Gulf passage boxes together, with the same cast.

## Rules (Bean, Nov 24 2026)

- **No eBird.** Cornell's eBird terms need written permission for commercial use, so eBird's GBIF dataset
  (`4fa7b334-ce0d-4e88-aaae-2e0c138d049e`) is subtracted from every count and never paged. The GBIF search API has no
  "not this dataset", so every facet is fetched twice: all records, and eBird's alone.
- **Only CC0 and CC BY 4.0 records**, present (not absence records), without geospatial issues, inside the world's box.
  GBIF filters on each record's own licence. iNaturalist and Happywhale are CC BY-NC as datasets because some of their
  records are; only their CC0 and CC BY records are counted (`per_record_licences` in `species.json`).
- **Birda left out too** (`left_out_datasets`): every Birda record says CC BY 4.0 but the dataset says CC BY-NC 4.0, so
  with the licence unclear it's subtracted like eBird. That took about 6,000 records from Galveston Bay's birds and with
  them the only bird counts on the coast: every bird group is now the plan's rough range.
- **Birds, dolphins and whales: sightings since 2000 only** (no museum specimens: 362 of Galveston's 433 dolphin records
  were Smithsonian strandings, peaking in March).
- Sharks in, rare. Marseille's pilot whales, Risso's dolphins and sperm whales left out. No whales in Texas.

## Tools

```
python3 Tools/wildlife/fetch_gbif.py             # fetch what the cache (Data/Wildlife/raw/cache, git-ignored) lacks
python3 Tools/wildlife/build_tables.py           # write Content/TerrainData/<World>.wildlife.json
python3 Tools/wildlife/test_wildlife.py          # realism rules; with the cache here, also checks the tables match it
```

Cloud sessions can't reach api.gbif.org. There, `fetch_gbif.py --offline` writes the missing URLs to
`Data/Wildlife/raw/missing.json`; `Tools/wildlife/browser_fetch.js`, pasted into a browser tab on
https://api.gbif.org, fetches them (and makes the record-page and dataset URLs from the facets, as `fetch_gbif.py`
does); `fetch_gbif.py --ingest results.json` stores the answers. Repeat until `--offline` reports nothing missing.
That's how these tables were made, through the Mac's built-in browser.

## Results (fetched Nov 25 2026)

| World | Animals | Bird records used | eBird left out | Birda left out | Months from records | Credited datasets |
|---|---|---|---|---|---|---|
| RayHubbard | 14 | 3,441 | 191,078 | 240 | 4 of 14 | 4 |
| GalvestonBay | 15 | 12,911 | 2,687,298 | 6,058 | 11 of 15 | 16 |
| GulfPassage | 15 | 9,334 | 2,359,395 | 1,608 | 12 of 15 | 22 |
| Marseille | 16 | 265,133 | 16,351 | 106 | 11 of 16 | 115 |
| TexasCoast | 15 | 29,644 | 4,322,712 | 7,309 | 13 of 15 | 23 |

What it means for Phase 1:

- **Ray Hubbard is thin.** Without eBird the lake has 3,441 bird records, so most of its birds have flat seasons inside
  the plan's months (Forster's tern has none at all). The seasons are the plan's; the records only confirm them.
- **Group sizes are all the plan's rough ranges.** Texas bird counts came almost only from Birda, and the Marseille
  networks rarely record a count. Phase 1 checks them against video.
- **Texas coast seasons read well**: laughing gulls and brown pelicans peak in June, white pelicans are November to
  March, frigatebirds April to October, menhaden schools peak in July.
- **Dolphins are placed**: Galveston Bay 57 sightings over 49 cells, the Gulf passage 58 over 52, Marseille's bottlenose
  93 over 36; sharks 41 and 63 records. Marseille's striped dolphins (82 sightings) come all year, offshore.
- **Marseille** draws mostly on the SILENE-FAUNE-PACA, CEN PACA, LPO PACA and Calanques National Park datasets; the
  gannet's summer records stay a trickle, Scopoli's shearwaters peak in August, swifts April to August.

## Tests

`python3 Tools/wildlife/test_wildlife.py`: every cast animal is in the catalogue and every catalogue animal is cast;
nothing from the sea (or a dolphin, whale, shark or ray) on Ray Hubbard and no freshwater-only animal on the coast; no
whale in any Texas world; Marseille's deep-water rarities out; sharks marked rare; whales rare and far offshore; every
animal only in its months, every season month at least 0.15, rare months at most 0.1; groups sane; eBird never among
the credits, in a page's URL or in a cached record; Birda left out and never credited; every credited dataset CC0 or
CC BY or licensed record by record; only CC0 and CC BY 4.0 queried; and, with the cache, the committed tables are
exactly what the cache builds.

## Next

Phase 1 (after Dec 11, Mac): the distant birds read these tables. Before then, a cloud session can draft the Blender
bird silhouettes and reference cards.
