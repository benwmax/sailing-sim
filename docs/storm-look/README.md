# Storm look: whitecaps, green water, rain, torn crests, lens water, camera shake

Bean's go on Nov 15 2026, for the storm look plan (the "Storm look" artifact in the project thread). He asked for items 1
to 3 now, 4 and 5 too, the waves kept realistic, and camera shake and lens water as settings. The budget he picked is
**+3 ms in all for the new effects, at native 4K on Ultra** (BEN-PC's 4K storm was 62 fps, 16.1 ms).

The waves themselves are unchanged. Heights, slopes, the folds the caps are masked by and the cover the tests count
(`Whitecaps`, `WhitecapsSeen`, `-SailingDebugFoam`) stay as they were. Only how the foam, the spray, the rain and the
glass are drawn changes, plus what the camera does.

| Item | What changes | Where | Compare with |
| --- | --- | --- | --- |
| 1. Whitecap life cycle | Caps age into lace and then strings along the wind; groups of breakers; fresh foam has relief | `V4_SHADE` (M_WaterV4) | `-SailingClassicFoam` |
| 2. Green water | Seas over the rail come aboard as sheets, and a film of water runs over the deck | `GreenWater.h`, `UpdateSpray`, `UpdateBoatWetness`, `BOAT_CODE`, hero `DETAIL_CODE` | `-SailingNoCameraShake` for the kick |
| 3. Rain eats the horizon | A downpour is 0.8 km of visibility (1.5 before); drops splash on the sea | `FStormRain::VisibilityKm`, `V4_SHADE` rain loop | none (it is the weather) |
| 4. Torn crests | From about 25 kn the wind tears the lip off the breaking crests | `AWaterSurface::GaleSprayFor` (`Torn`), `UpdateSpray` | wind under 22 kn |
| 5. Lens water | Each drop is a lens: the world upside down inside it, a dark rim, a glint; slams throw splashes and a film | `LENS_CODE` (M_LensWater) | Settings > Water on the lens |
| 6. Camera shake | Slams and seas aboard jolt the camera; it trembles in a gale | `FCameraBuffet`, `ASailboatPawn::UpdateCameraBuffet` | Settings > Camera shake, `-SailingNoCameraShake` |

Details for each are in [whitecaps/](whitecaps/), [green-water/](green-water/), [camera-buffet/](camera-buffet/) and
[lens-water/](lens-water/). Items 3 and 4 are short and are described here.

## 3. Rain eats the horizon, and rain on the sea

**Visibility.** Thunderstorm METARs report heavy rain (+TSRA) at 1/4 to 1 statute mile, which is 0.4 to 1.6 km. The
storm's core used to bottom out at 1.5 km, so the far shore stayed in view through a downpour. Rain's extinction adds to
the clear air's. Visibility is about 3.9 over the extinction, so log visibility moves linearly with the rain.
`FStormRain::VisibilityKm(clear, rain)` is the geometric blend from the clear air's visibility to
`DownpourVisibilityKm` (0.8 km) at full rain:

- moderate rain (0.4) on a 10 km storm day gives about 3.6 km;
- heavy rain (0.7) gives about 1.7 km;
- the core gives 0.8 km.

`FWeatherState::LocalizeStorm`, the real-day radar and the game mode's local rain all use it.
`SailingSim.Weather.DownpourVisibility` holds those numbers and checks the visibility under a storm's core.

**Splashes.** Each rain ring on M_WaterV4 now starts with the splash the drop throws up: a white speck at the ring's
centre for the first 8% of its life. Within 30 m, a finer and denser set of splashes is drawn on its own (15 cm cells,
three a second, as many as the rain squared). They are drawn as foam while a pixel can resolve them, up to a 5 cm
footprint; past that the rain's general greying (0.10 of the rain) takes over. Before this, the sea in a 50 mm/h core
read as wet glass.

## 4. Wind-torn crest spray

The Beaufort scale's force 6 (22 to 27 kn) says "probably some spray", and force 7 says foam is blown in streaks.
`GaleSprayFor(kn).Torn` is a smoothstep from 22 to 30 kn. That share of the breaking crests found by the crest-spray
search (the same search, the same fold test), within 25 m of the camera, also have their lip torn off:

- a short torn sheet off the top, 0.2 to 0.4 m, lasting 0.2 to 0.4 s, carried at 60 to 80% of the wind;
- two to four fine drops (4 to 10 cm quads) streaking downwind with it.

The first cut also threw a mist wisp off every torn crest out to 60 m. Past 25 m the spray draws its drops as mist
too, so BEN-PC's 4K stills showed white puffs like steam all over the sea. Now the torn crests stay near the camera,
where drops are drawn as drops, and add no mist of their own.

The crest search's sample count, the gale's extra crests (24 to 32 kn) and the spindrift (33 to 41 kn) are unchanged.
`SailingSim.Visual.GaleSpray` checks Torn: nothing at 20 kn, some at 26, every crest by 32, and only growing with the
wind.

## Settings

Both default to on and are saved in `profile.json` (`display.lensWater`, `display.cameraShake`; see
[../save/README.md](../save/README.md)).

- **Graphics > Water on the lens** (High and up, where the lens material exists). The blendable stays on the post
  process volume, and its weight follows the setting. A blendable at weight 0 is not drawn.
- **Display > Camera shake.** It never runs in photo mode, the capture mode, a watched replay or a measured run, so
  benches and stills are steady.

## Tuning knobs (make_materials.py environment, defaults in brackets)

- `STORM_FOAM_HOLES` (0.3): how far holes open in ageing foam. 0.3 opens about half of an old patch.
- `STORM_CAP_VARY` (0.8): how much a wave group moves the drawn caps' edge, in e-folds of cover.
- `STORM_FOAM_BUMP` (1.0): the fresh foam's relief. 0 turns it off.
- `STORM_CAP_CORE` (0.3): the share of the hole threshold that opens even in a cap's core.
- `STORM_CAP_RIM` (1.2): how aged a cap's drawn edge is.
- `STORM_CAP_RAG` (0.06): how far the lace moves a cap's drawn edge, in J.
- `LENS_FIELD` (4.0): how wide a view each lens drop shows, in drop sizes.

## What the Mac and the PC still have to do

The cloud session that wrote this has no Unreal editor or shader compiler. The HLSL was reviewed by hand, and
SailingPhysics was built and checked standalone with clang (`-Wall -Wextra -Werror -Wshadow`, polar unchanged). Still
to do:

1. Rebuild the materials: `scripts/make-content.sh` (M_WaterV4, M_LensWater, the M_BoatSurface library, MPC_Boat), then
   `HERO_MATERIALS_ONLY=1` for the hero J/22's material. Commit the assets on the branch.
2. Run the tests and the water gate (Medium 60, High 45).
3. Take storm stills with and without `-SailingClassicFoam` at 20, 28 and 35 kn, a downpour, a knockdown with the lee
   rail under, and a bow-down slam with the lens on.
4. On BEN-PC (when Bean resumes it), take the 4K Ultra storm view, held to +3 ms over main.
