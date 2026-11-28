# Florida to the Bahamas, stage 1: Miami to Bimini

The first big map (Bean, Nov 27 2026): "somewhere in Florida all the way to the Bahamas". Stage 1 is Biscayne Bay to
Bimini across the Gulf Stream, about 50 nm. Stage 2 goes on across the Great Bahama Bank to the Berry Islands and
Nassau, about 170 nm more. The plan it follows is the doc "Huge maps without memory growth": the world is cut into
tiles that load near the boat and drop behind it, so a bigger map costs disk, not memory.

This is draft work for after the Dec 11 release. Nothing here changes the game yet: the tools bake files the game does
not read until the follow-up PRs below land.

## The world, in three bakes and one composed map

| Bake | What | Cells | Chart | Land | Tides |
|---|---|---|---|---|---|
| `MiamiBiscayne` (the frame) | Biscayne Bay, Key Biscayne, Government Cut, out past Fowey Rocks | 10 m | NOAA ENC | USGS 3DEP | CO-OPS, Virginia Key |
| `FloridaStraits` | The open water between, to about 900 m deep | 200 m, 5 cm height steps | NOAA ENC (overview, approach) | none | Virginia Key |
| `Bimini` | North and South Bimini, Gun Cay, Cat Cay, the bank edge | 10 m | NOAA ENC (chart 11469 reaches Bimini) | flat low land | Virginia Key until FES2022 |
| `MiamiBimini` | All three as one streamed world, plus the Gulf Stream | 6.4 km tiles | merged | | |

World files: `Tools/coast/worlds/MiamiBiscayne.json`, `FloridaStraits.json`, `Bimini.json`, `MiamiBimini.json`.
Sources and licences: [data-sources.md](data-sources.md).

## Running it (on the Mac, after the release)

```
Tools/venv/bin/python -I Tools/coast/fetch_miami_bimini.py --list # the ENC cells and tide stations it would fetch
Tools/venv/bin/python -I Tools/coast/fetch_miami_bimini.py        # into Data/<World>/raw (git-ignored)
Tools/venv/bin/python Tools/coast/build_coast.py MiamiBiscayne
Tools/venv/bin/python Tools/coast/build_coast.py FloridaStraits
Tools/venv/bin/python Tools/coast/build_coast.py Bimini
Tools/venv/bin/python Tools/coast/build_coast.py MiamiBimini  # compose_world.py: the tiles
Tools/venv/bin/python -I Tools/coast/gulf_stream.py MiamiBimini [--nc <monthly means>.nc]
scripts/make-far-ring.sh MiamiBimini
```

Check after the first bake: each bake's checkpoints line (chart shoreline against the terrain), the coverage line
("covered N% of the grid": how much of Bimini the US ENC really charts), the previews in this folder, and that
`build_coast.py TexasCoast` still writes byte-identical `TexasCoast.tiles` (the compose changes below keep it so).

## The Gulf Stream (`Tools/coast/gulf_stream.py`)

The Florida Current runs north through the Straits at up to about 2 m/s (4 knots) all day, every day. The tidal
current file a world already has (`.current`) can't hold that: it is one station's tide scaled per cell. So the stream
is its own file, `<World>.stream`: a north and east surface speed per 1 km cell for each month (format in the script's
header).

- With model data (`--nc`): Copernicus Marine monthly means (commercial use allowed with credit) or HYCOM, fetched on
  the Mac (commands below), interpolated onto the world and kept only where the water is 10 m deep or more.
- Without it: an analytic stream fitted to the published section. Its core is a quarter of the way across from the
  Florida side (about 20-25 km off Miami), 1.8 m/s at the core (a little more in July, a little less in winter, after
  NOAA's 27 N cable record), falling off fast toward Florida and slowly toward Bimini, and nothing on the bank or in the
  bay. `--self-test` checks it on a made-up strait.

The game does not read the file yet. Wiring it in is a Source/ PR: add it to the water velocity the boats feel (the
same place `FTideModel`'s current goes), show it on the chart as arrows, and give the wind-against-current sea its
steeper, shorter waves (the Gulf Stream's famous "elephants" in a norther).

Fetching the monthly means on the Mac (free Copernicus Marine account; the toolbox is `pip install copernicusmarine`):

```
copernicusmarine subset -i cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m -v uo -v vo \
  -x -80.4 -X -79.1 -y 25.3 -Y 26.1 -z 0.4 -Z 0.6 -o Data/MiamiBimini/raw -f stream_monthly.nc
```

(The dataset id is a best guess written from the cloud, which can't reach Copernicus Marine; if it is wrong, `copernicusmarine describe -c GLOBAL_MULTIYEAR_PHY_001_030` lists the datasets; a
monthly series works too, the bake averages each calendar month.)

## Changes to the existing tools

`Tools/coast/compose_world.py`:
- Off the frame grid a tile now takes the spacing of the finest bake it overlaps, so Bimini keeps its 10 m instead of
  being resampled to the Straits' 200 m. Where two bakes overlap, the finer one's heights win.
- Each tile picks its own height unit: centimetres, or 5 cm steps for a tile deeper than about 320 m (the Straits). The
  game already reads each tile's unit (`FTileIndex`).
- With one other bake (TexasCoast) both rules give exactly what they gave before.

## What needs hand work (the Bahamas side is coarse)

- **Bimini Harbour and the marinas.** The US chart's harbour detail is thin. The channel, the docks at Alice Town and the
  Bimini Big Game Club need placing from photos and OSM, the way the Galveston piers were.
- **Reefs and the bank edge.** The Great Bahama Bank rises from hundreds of metres to a few metres in under a kilometre
  just west of the islands. The ENC contours give the shape; the reef flats, coral heads and sand bores need the Allen
  Coral Atlas (once its licence is confirmed) or hand-drawn areas.
- **Bimini's houses.** 1,530 footprints, almost none with heights: storeys and roofs need a Bahamas house style, like
  Marseille's `house_style`. They also only stream in once world objects go into tiles (plan step 5); until then the
  composed world carries only the frame member's houses.
- **Tides at Bimini.** FES2022 constituents for Bimini replace Virginia Key's.
- **Seam at Bimini's edge.** Only the frame grid blends into its neighbours; Bimini's 10 m edge meets the 200 m Straits
  without a blend. Its edge sits in deep water or on the flat bank, so the step should be small; check it in the
  preview.

## Follow-up PRs, in order

1. (Mac) First fetch and bake of the three members and the composed world; previews and the coverage numbers here.
2. (Source/) The game reads `<World>.stream`: boats feel it, the chart shows it, `SailingSim.Coast.GulfStream` test.
3. (Tools/) Bimini hand work: harbour, reefs, house style, FES2022 tides.
4. After plan steps 5 and 6 (world objects in tiles, tide moves the water): the long-sail soak on MiamiBimini.
5. Stage 2: the Berry Islands and Nassau, mostly global grids plus hand work.
