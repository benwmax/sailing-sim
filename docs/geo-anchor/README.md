# The geo anchor

Online-readiness rule 6: things that persist are placed by a stable id or by latitude and longitude, never by map
metres. A world's map frame (metres, +X north, +Y east) is a local projection that a rebake can move (a new grid origin,
a spot nudged onto deeper water); an id or a lat/lon means the same place whatever the bake did.

Code: `Sailing::FGeoAnchor` and `Sailing::ResolvePlacement` in `Source/SailingPhysics/Public/GeoAnchor.h` (plain C++,
SI units, builds standalone). `FLakeData::Anchor` is the loaded world's; `SailCatalog::Anchor(world)` reads it from the
bake header alone (no terrain). The Unreal side converts through `SailingNav::LatLonAt` / `SailingNav::MapAt`
(`Navigation.h`, taking the `FVector2D` map points everything else uses). Tests: `SailingSim.Geo.*` in
`Source/SailingSimTests/Private/GeoTests.cpp`.

## The projection

Every bake projects its sources with pyproj and the string in its header's `"projection"`:

| World | Header | lat_0 | lon_0 | The origin |
| --- | --- | --- | --- | --- |
| Lake Ray Hubbard | `RayHubbard.json` | 32.8233 | -96.5 | Rush Creek Yacht Club |
| Galveston Bay | `GalvestonBay.json` | 29.5446 | -95.0193 | Kemah / Clear Lake |
| Gulf passage | `GulfPassage.json` | 29.33 | -94.69 | Galveston entrance |

`+proj=tmerc +lat_0=.. +lon_0=.. +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m`: transverse Mercator on the GRS80
ellipsoid with the world's origin at map (0, 0); map north is the northing and map east the easting. The inputs are
WGS84 (`EPSG:4326`: OSM, NOAA ENC, CO-OPS stations) and PROJ applies no datum shift from WGS84 to NAD83 here (checked:
the transform equals a bare GRS80 tmerc to the last digit), so a lat/lon from any of those sources goes straight in.

`FGeoAnchor` parses the string (`ParseProj4`: lat_0, lon_0, k, x_0, y_0; a header without one falls back to the build
scripts' constants, `ForWorld`) and computes the projection with Krueger's series to n^6 (Karney 2011, the algorithm
PROJ's tmerc uses), forward and inverse; the inverse solves the conformal latitude by Newton. Agreement:

| Check (`SailingSim.Geo.*`) | Result |
| --- | --- |
| map -> lat/lon -> map and back, origin, four corners, edge midpoints and centre of each world's grid | worst 2.5e-9 m |
| against pyproj 3.8 (PROJ 9.8.1) at the origin and four corners of each grid, both ways | worst 3.0e-9 m |
| Galveston grid's south edge (the Gulf front, -39,240 m north) | 29.1906 N |
| Rush Creek Yacht Club at the lake's origin | 32.8233 N 96.5000 W exactly |
| the club's launch spot: the bake's own lat/lon beside its metres | 0.063 m |
| Houston Ship Channel Lighted Buoy 34, NOAA ENC US5HOUAI 29.4082353 N 94.8202819 W, against the baked navaid | 0.001 m |
| every Galveston navaid, metres -> lat/lon -> metres | under 1 cm |

The pyproj values in the test came from:

```python
from pyproj import Transformer
L = "+proj=tmerc +lat_0=29.5446 +lon_0=-95.0193 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m +no_defs"
lon, lat = Transformer.from_crs(L, "EPSG:4326", always_xy=True).transform(east, north)
```

## Placing something that persists

`ResolvePlacement(anchor, things, placement, snap)`: a placement carries an id and, optionally, a lat/lon. The thing
with that id wins; failing that (renamed or removed in a rebake) the thing nearest the lat/lon within `snap` metres;
failing that, -1, with the lat/lon itself as the landing point. Ids first, lat/lon second.

The save file is the first user (`docs/save/README.md`): `settings.start` and `lastSession` gain an optional
`"launchSpotAt": {"lat": .., "lon": ..}` beside `"launchSpot"`. `FSailSave::SpotIndex` resolves a spot by id, else the
spot nearest the lat/lon within `FSailSave::SpotSnapMeters` (500 m: spots are 800 m apart or more), else the world's
first spot. The save's version stays 1: the field is optional, a file without it reads exactly as before, and an
older game keeps it as an unknown field (it never changed what an existing field means, which is what a version bump is
for). The catalogue's spots carry `Lat`/`Lon` computed from their metres through the anchor (rounded to 1e-8 degrees,
about a millimetre); nothing shows them yet.

"Last position" is the last session's launch spot: Continue starts a session there and nothing saves a position
mid-sail yet. A save of the boat's position mid-sail would add a lat/lon beside it the same way.

## What persists, and in what

| Data | Where | Placed by | Note |
| --- | --- | --- | --- |
| Save: world, launch spot, boat, drill, presets | `Saved/SaveGames/profile.json` | string ids, plus the spot's lat/lon | this PR |
| Logbook entries | `Saved/Logbook/*.json` | lat/lon | now the bake's projection inverted (it was a flat-earth guess about `FLakeData::Latitude`, which on the lake is 32.82, 370 m south of the true origin) |
| Launch spots | bake header `launch_spots` (`xy`; the lake's also `lat`/`lon`) | metres, with a stable id (`"id"` or the name) | the lake's `lat`/`lon` fields are the hand-picked ones before the spot was moved onto water; the metres are the position (up to 509 m apart, the SH-66 spot) |
| Navaids, landmarks, tide stations | bake header | metres, projected from the chart's lat/lon | generated content: rebaking reprojects them |
| Marina rows, slips, piers, clubhouse | `<World>.marina.json` | metres, with ids (`rcyc.dock.a`) | laid out in the map frame by hand; `Content/World/Scans.json` keys scans by those ids |
| Docks, decks, moored boats, houses, crowns, bridges | bake files | metres | generated |
| Replay and ghost | memory only | metres | not saved |
| Capture telemetry, camera json, bench | `Saved/Bench` | metres | developer output, not game state |
| Launch args (`-SailingStartAt`, `-SailingCamWorld`) | the command line | metres | developer tools |

The bakes stay in metres: they are generated content and a rebake regenerates every position from its lat/lon
sources consistently. What is converted is what outlives a bake: a player's save, a logbook, and later anything shared
between players (a race course, a mark, a meeting place), which should carry an id where the world has one and a lat/lon
always.

## Converting

- In SailingPhysics: `FGeoAnchor::ToMap({lat, lon})` gives `{North, East}`; `ToLatLon({North, East})` the reverse.
- In SailingSim: `SailingNav::MapAt(Lake.Anchor, {lat, lon})` gives an `FVector2D` (X north, Y east);
  `SailingNav::LatLonAt(Lake.Anchor, P)` the reverse. Bearings, fixes and dead reckoning stay in the map frame (their
  results are unchanged).
- Without loading a world: `SailCatalog::Anchor(settingsWorld)` (0 lake, 1 Galveston Bay, 2 the Gulf passage).
