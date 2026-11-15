# PR #703 (storm look) on BEN-PC: 4K Ultra, native, no DLSS

**Head c6a0e6ab** (branch `claude/project-thread-blitx3`, which contains main 6f44708f).

## Step 1: build and the first DXC compile of the new HLSL

- **MSVC build:** Succeeded, 0 errors, 0 warnings in our Source.
- **`run-python.ps1 make_materials.py -Only build_water_v4,build_lens_water,build_boat_library`:** exit 0, no Python
  errors. It saved M_WaterV4, M_LensWater, MPC_Boat (with `Wash` and `WashSide` added), M_BoatSurface, M_BoatMast,
  M_BoatPacked and the MI_Boat_* library.
- **`import_j22_hero.py` with `HERO_MATERIALS_ONLY=1`:** exit 0. It saved M_J22HeroSurface, M_J22HeroGlass and the
  MI_J22H_* instances.
- **Not committed.** The regenerated assets were used only to package; the Mac owns the asset commit. I kept a copy on
  the PC, and the checkout is back to clean main.
- **No shaders in the commandlet.** It saves without compiling, so the real DXC compile was the cook. The cook compiled
  M_WaterV4, M_LensWater, M_BoatSurface and M_J22HeroSurface for PCD3D_SM6 ("Missing cached shadermap ... compiling")
  with **no shader or material errors**.
- **Warm-up game log:** no shader errors and no default material.

## Step 2: 4K Ultra storm, 30 s, A/B/A back to back

Setup: `views.ps1` storm view (Thunderstorm, weather time 200 s, 37 kn at the end, in the rain), `-SailingBenchTrace`.
Camera shake is off in measured runs.

| run | fps | frame ms | p99 ms | GPU ms (frames.csv) | game ms | frames > 40 ms | GPU slices total | water | post | base | lumen | clouds/fog |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a 6f44708f | 36.2 | 27.60 | 32.34 | 27.49 | 17.21 | 13 | 21.69 | 1.62 | 2.51 | 5.54 | 1.02 | 9.80 |
| b #703 | 36.3 | 27.54 | 32.07 | 27.41 | 16.96 | 12 | 21.96 | 1.55 | 2.53 | 5.81 | 1.10 | 9.79 |
| c 6f44708f | 36.0 | 27.79 | 32.74 | 27.76 | 15.23 | 14 | 22.29 | 1.59 | 2.48 | 5.53 | 1.14 | 10.37 |

**#703 costs nothing measurable here.**
- **Frame time:** 27.54 ms against main's 27.60-27.79 ms, about -0.15 ms.
- **Water slice:** 1.55 ms against 1.59-1.62.
- **Post slice:** 2.53 ms against 2.48-2.51.
- **Base pass:** about +0.27 ms (5.81 against 5.53-5.54), within A's own spread on the other slices.

That is well inside Bean's +3 ms. The slices come from three `ProfileGPU` frames after the window, so read them to
about ±0.3 ms.

The look is plainly different in the end screenshots (`storm/b-c6a0e6ab/storm-ultra.png` against `a-6f44708f`):
- the lens drops are refracting lenses, showing the scene inverted, with a dark rim and a glint;
- the horizon is greyer in the rain;
- the foam on the near sea reads more broken up.

## Step 3: stills from the #703 package (`stills/`)

**Wind pairs.** In the storm the gust front sets the wind, so `-SailingWind=28/35` does not hold. The stills are named
by the wind the HUD shows:

| still | HUD wind | notes |
|---|---|---|
| `storm-29kn` / `storm-28kn-classicfoam` | 29 and 28 kn | `-SailingWind=28` |
| `storm-28kn-b` / `storm-28kn-b-classicfoam` | 28 kn | asked as `-SailingWind=35`; it did not take |
| `storm-30kn` / `storm-30kn-classicfoam` | 30 kn | the storm view as is, 10 s in |

- **37 kn:** the wind reaches 37 kn only about 30 s in, which is where the A/B/A end screenshots are. B there is #703 at
  37 kn; A and C are main.
- **No 35 kn pair with and without `-SailingClassicFoam`.** A 35 kn+ pair needs a 30 s run or a later
  `-SailingWeatherTime`.
- **New foam against classic:** at the same camera and moment the difference is subtle in these stills. The new caps are
  a little more broken, with lace and strings, and the classic ones are more solid patches.

**`downpour-shore` against `before-storm-shore`** (same camera toward the near shore, weather time 200 s against 0 s):
- Before the storm, the far shore line is clearly on the horizon.
- In the downpour (30 kn), the far shore is gone into grey. The sea shows the new torn crests and spume: white puffs of
  mist sitting over the breaking crests, quite dense over the whole sea at this distance, and worth a look for whether
  they read too much like steam.

**`slam-cockpit-rain`** (Gulf, swell 2.5 m, 38 kn, `-SailingCockpit`, 20 s):
- The refractive lens drops show well, and the deck is wet.
- The end frame caught her heeled 38° on a close reach, not a bow-down slam, so neither the slam splash nor the film on
  the lens is in this frame.
- No arg forces a slam. It needs a timed capture, or a still taken at a slam from the replay.

**Banding.** The `before-storm-shore` still, the clear one, shows heavy colour banding (posterised sky, sails and water).
The same banding shows in main's Sunfish stills (main-check-7cfcaae2 and main-check-6f44708f, clouds and HUD panels), so
it is not #703. It looks like an older issue on the PC's PNG path or in post at Ultra, worth its own look.

Bean's Saved was held aside and restored (F6458EAB) around every packaged run.
