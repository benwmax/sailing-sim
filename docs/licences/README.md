# Licence audit

Bean may sell the game (Oct 15 2026). From now on only commercially usable assets, data and code go in. This page
lists every third-party asset, dataset and piece of code the repo contains or its scripts fetch or build. Each one is
in `assets.csv` with its source, licence, commercial use (yes, no or conditions), conditions and where it is used.
`scripts/licence-check.sh` fails if any file under `Content/` or `Audio/` has no row. That covers tracked files, new
untracked ones and the git-ignored local builds such as the MetaHumans. It also fails if any row says "no".

Audited on Oct 15 2026 against main 7149d537 and the local builds on Bean's Mac.

## Flagged

No asset in the repo or the builds is under a non-commercial, research-only or no-derivatives licence. No NC Commons
photo, no LAFAN1, Bandai, AMASS or CMU motion, and no Mixamo or Fab content was found. Nine things need attention.
Five are actions before release (item 1 is now fixed):

| # | What | Problem | Recommended fix |
|---|---|---|---|
| 1 | `Content/Materials/T_SailMarks` (`scripts/make_sail_marks.py`) and the J22Hero sail and bow lettering (`Inputs/j22-hero`) | Were rasterized from Apple's bundled Arial and Helvetica (or Arial/Liberation on other machines). | **Fixed (Oct 15 2026, sail-font):** both now draw from Saira Condensed Bold (OFL, `Content/UI/Fonts`); the insignia is sheared for its slant, the bow registration widened 1.3x to block proportions. The atlas and the hero (sail textures, hull bake, FBX) were regenerated and reimported. |
| 2 | The J/22 sail insignia (red "J" + "/22") and the class and brand names (J/22, J/Boats, Catalina, Hobie, Corsair, Lagoon, ILCA, Sunfish) | These are trademarks, not copyright licences. Naming the boats descriptively is normally fine. A maker's logo drawn on the sails, or the names in store art, can need permission. | Ask J/Boats (and the others named in store text) for permission, or replace the drawn insignia with a generic class mark. This needs a lawyer's view before release, not a code change. **In the game (Oct 21 2026, boat fidelity 4):** the sails' insignia is now a made-up emblem (`scripts/make_sail_marks.py`); the J22Hero's own sail maps (`Inputs/j22-hero`, Blender renders only, not used by the game's sails) still draw the old mark. The names remain. |
| 3 | "ASA 101" (drills, quiz) | This is a trademark of the American Sailing Association. The quiz is our own text: no question copies the Study Kit. | Use the name only descriptively ("prepares you for the ASA 101 exam"), with no logo, and no endorsement claim without the ASA's agreement. |
| 4 | "Larus atricilla.ogg" by Tony Phillips (`Content/Audio/Pack/Birds/laughing_gull_01`) | This is CC BY 3.0, which is commercial-OK with attribution. The game shows no credit: the settings text only points at a repo path (`SailFrontEnd.cpp:1090`). | **Fixed (Oct 17 2026, licence-closure):** Settings > Sound now credits it by title, author and licence, with the two public-domain recordings. A full credits screen (with the Unreal notice) was added on Oct 18 2026 (see the end of this page). |
| 5 | OpenStreetMap and Overture Maps building footprints (`Content/TerrainData/*.houses`, `.piers`, the shore and marina data, the baked world tiles) | Both are ODbL 1.0, which is commercial-OK. Two conditions: attribution in the game and its documentation, and share-alike on the derived database (the bake files, not the game). The in-game credit names only OSM and USGS (`SailingHUD.cpp:1134`), and Overture was missing from CREDITS.md. | I added Overture to CREDITS.md in this PR. **Fixed (Oct 17 2026):** the in-game map credit names Overture Maps Foundation too. Keep offering the bake files under ODbL (CREDITS.md says so) and be ready to provide them on request. |

Checks with no change needed now:

| # | What | Status |
|---|---|---|
| 6 | MetaHuman crew (git-ignored, cooked into the package) | The MetaHuman licence allows commercial use in Unreal Engine products. The source characters, their FBX exports (`Artifacts/crew`) and `pack-metahumans.sh`'s zip must never be redistributed outside the cooked game, for example in a public repo, a Fab upload or a mod kit. The crew clothing tailored over MetaHuman garments counts as MetaHuman content. |
| 7 | MetaHumanBodyTracker / MetaHumanCharacter (#53, Win64 editor only) | These are editor tools and are not shipped. The animations they solve from Bean's footage are ours. Confirm on its Fab page that the plugin carries only the Fab Standard Licence / Unreal EULA. |
| 8 | Iowa Environmental Mesonet ASOS (`Tools/weather/fetch_day.py`, real days) | IEM relays public-domain NWS observations and states no licence of its own. Low risk. Credit IEM as a courtesy (added to CREDITS.md), or fetch the same ASOS data from NCEI if a stated licence is wanted. |
| 9 | Unreal Engine itself | The EULA allows commercial release. It takes a 5% royalty on gross revenue above USD 1M per product, and the packaged build's `NOTICES.txt` must ship with the game. |

## Clear for commercial use

| Group | Licence | Notes |
|---|---|---|
| Everything generated by the repo's scripts: boats, world kit, crew bodies and gear, materials, cloud noise, UI art, maps, learning text, the sound pack's 43 synthesized sounds, `Wind.mann` (Hipersim, MIT) | Own work | Most of `Content/` |
| ambientCG fabrics (Fabric036, 048, 070, Leather038) | CC0 | No attribution needed (credited anyway) |
| Saira, Source Sans 3 | SIL OFL 1.1 | The OFL texts are staged with the fonts; the fonts are never sold on their own |
| Commons recordings "Gull 1" and "Rain on a veranda and t" | Public domain | |
| USGS 3DEP (DEM, 1 m lidar, point clouds), USDA NAIP, NOAA C-CAP, NOAA ENC charts, CO-OPS tides and currents, NCEI ASOS, HRRR and MRMS | US federal public domain | The chart is not for navigation |
| TWDB survey and Water Data for Texas | Texas public information | |
| Fleet particulars and reference polars (ORC, keelindex.com, builders, papers) | Facts | Cited in CREDITS.md and `docs/phase-4/fleet-data.json`; don't copy whole tables into the shipped UI |
| All C++ in `Source/` | Own work | No vendored third-party code; methods after cited papers |

## Tools (not shipped)

Blender (GPL; its output is ours), SWAN (GPL; outputs are data), the Python packages in `Tools/venv` and system zlib are
used only for tooling, and nothing from them is linked into the game. The packages are numpy, scipy, pandas, h5py and
numba (BSD); Pillow (MIT-CMU); shapely; pyproj, pyogrio, pyshp, netCDF4 and hipersim (MIT); matplotlib (PSF-style);
tifffile; xarray and eccodes (Apache 2.0); and wetb (GPL v3).

## Repo-only material

The blind-test packs and compare pages in `docs/` hold cropped Wikimedia Commons photos under CC0, CC BY and CC BY-SA
2.0-4.0. Each pack has its `credits.md`. They are never in `Content/`. The repo is public now (Oct 2026):
keep those credits, and the BY-SA images stay BY-SA. Bean's lesson photos (`Data/Reference/raw`) stay git-ignored and
are never published (faces).

## Rules from now on

- Commercially usable only: CC0, public domain, CC BY (with attribution), OFL, MIT/BSD/Apache, ODbL (attribution and
  share-alike on the data), and the Unreal EULA, Fab Standard and MetaHuman licences inside the UE game. Nothing NC, ND
  or "personal / research use".
- Animation data: our own capture, procedural motion, Epic's Game Animation Sample (Unreal EULA, inside UE), the CMU
  Graphics Lab mocap database (free for any use, credit asked) and Mixamo (royalty-free in a game; never redistribute
  the raw files). LAFAN1 (CC BY-NC), Bandai Namco's dataset (CC BY-NC-ND), AMASS (non-commercial) and anything else
  NC are out. None of these is used today.
- A new file under `Content/` or `Audio/` needs a row in `assets.csv`, or `scripts/licence-check.sh` fails. Add a
  credit to `CREDITS.md` whenever the licence asks for one.

```bash
scripts/licence-check.sh
```

## Closure (Oct 17 2026, main df0ba7b5)

- `scripts/licence-check.sh` now covers `Inputs/` too (the generators' sources and the sample pack's WAVs) and fails on
  a malformed row (the `Content/Look` row had an unquoted comma). Rows added for `Inputs/` (audio, j22-hero, rope,
  boat-detail, look, drills, g2, g3, g4), the docs compare-page photos, the photo-match pixel picks and the game captures.
- Every Commons photo in `docs/` now has a `credits.md` beside it (new: `docs/graphics-5/compare/real`,
  `docs/visual-6/compare`, `docs/visual-7/compare`) and all 34 are listed in CREDITS.md.
- No file in git history ever lived under `Data/Reference`, no image was ever deleted (what is in the tree is all there
  ever was), and none of the images in `docs/` or `Inputs/` is one of Bean's lesson photos: `Inputs/j22-hero/renders` and
  `docs/boatkit-*` are Cycles renders and game captures. The photo-match JSON keeps only pixel numbers.
- Nothing from MetaHuman or Fab is tracked under `Content/` (`git ls-files Content | grep -i -e metahuman -e fab` finds
  only the ambientCG `Crew/Fabric`).

Closed (Oct 18 2026, Bean's choice): the hero J/22 now carries a made-up registration, TX 1288 ZX, in its style
(`Inputs/j22-hero/j22_style.py`), its character sheet (`Tools/boatkit/characters/tx1288zx.json`) and the rebaked hull
(`hero-registration`); the lesson boat's number stays only in source comments and older renders under `docs/`, as the
photographed reference. In the game (reimported on the Mac, boats gate passed): [hero-registration-game.jpg](hero-registration-game.jpg),
the starboard bow in the home slip on High. Overture's buildings theme mixes OSM, Microsoft and Esri footprints. Closed Oct 18 2026 (Bean: "yes include them
in the credits"): Overture's attribution page (docs.overturemaps.org/attribution, buildings theme) asks for "© OpenStreetMap
contributors. Available under the Open Database License.", "Esri Community Maps contributors. Available under CC BY 4.0." and
"Global ML Building Footprints. Licensed by Microsoft under the Open Database License." (Google Open Buildings and the
East Asia and Spain sources do not cover Texas). CREDITS.md, the Credits screen (which shows CREDITS.md) and the in-game
map credit line carry all three.

Credits screen (Oct 18 2026, `credits-screen`): the front end has a Credits screen (Title > Credits, and Settings > Credits
and licences on every tab). It leads with the Unreal Engine trademark notice and then shows all of CREDITS.md, which it
reads at runtime: `SailingSim.Build.cs` stages the repo's own file into the pak, so CREDITS.md stays the only source.
`SailingSim.UI.Credits` checks the notice and every heading. Still: [Credits.jpg](../graphics-4/screens/Credits.jpg).
