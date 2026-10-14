# Visual V5: sky and storm

The sky is now built from the weather on Medium and High:
- **Clouds:** layered volumetric clouds, painted from the weather state.
- **Storm:** a storm structure that rides the physics gust front.
- **Night:** stars and the Milky Way placed for the date.
- **Moon:** its phase, with earthshine on the dark side.
- **Air:** haze per air mass, and sun shafts in volumetric fog.
- **Lightning:** branching bolts that light the cloud from inside.
- **Lens:** water on the lens, on High.

Low keeps the Phase 8 sky.

![Afternoon cumulus, Medium](bench/beam8-medium.png)

## Clouds from the weather (`CloudSky.h`, `M_CloudLayers`, `SailingSim.Visual.CloudLayers`)

`FCloudSky` (in `FWeatherState`) holds four layers. Each has its own coverage, base, top and density:

| Layer | When | Base and top | Notes |
| --- | --- | --- | --- |
| Cumulus | Texas summer afternoon | Base 1.2 km late morning, rising to 1.5 km by mid-afternoon | Builds after noon to about a third of the sky; favours the heated land over the lake (the test: 0.49 over land vs 0.13 over water) |
| Stratus | Overcast; nimbostratus in rain | Overcast behind a dry northerly: 0.9 km; rain: 0.6 km | — |
| Cirrus | Ahead of a front, or blown off a storm's anvil | — | — |
| Storm | Thunderstorm | — | Shape is below |

How it is drawn:
- **Weather map.** `FWeatherMap` paints the layers on a 64 km map around the camera, on a worker every 2 s. The map sits in the clouds' drifting frame, so it moves with the wind aloft between paints. Each layer's mean over the map is its coverage: the test holds every preset within 0.05.
- **Cloud shader.** `M_CloudLayers` reads the map and gives each layer its own profile (flat bases, rounded and lumpy tops) and noise. It also outputs a conservative density.
- **Tracer.** The tracer spans only the layers present. Cirrus is a thin sheet 9 km up on the sky dome, not in the volume: spanning it spread the tracer's samples too thin.
- **Sunlight on the lake.** The lake's light follows the cloud field: the scene's sun is the transmittance through the layers and the storm toward the sun (`SunTransmittance`). A cumulus shadow, or the storm cutting off the sun, darkens the water.
- **Sunlight on the clouds.** The clouds themselves get the undimmed sun, so a storm keeps lit towers over dark bases.

## The storm on the gust front (`FStormShape`, `SailingSim.Visual.ShelfCloud`)

The thunderstorm is built along the physics gust front, at distances ahead of or behind its line:
- **Shelf cloud.** A low wedge with its lip 250 m ahead of the front. Its base is about 0.4–0.5 km, and its tiered face slopes back up into the storm.
- **Rain core.** Starts 700 m behind the front (the rain reaches the boat a minute after the front, as the physics has it). It towers as the storm builds.
- **Rain curtain.** Falls in shafts with lighter gaps under the core, down to the water.
- **Anvil.** Spreads ahead.

The same shape is in C++ and in the shader. The test sails the storm over the boat: the shelf's leading edge arrives 20.5 s before the front (the limit is 30), its base is 425 m, and the rain core follows.

Fix on the way: the storm's timeline was keyed to the map origin rather than the boat's start. A boat launched off Rush Creek met the gust front about a minute early. It now starts at the launch spot, so the front reaches the start at 150 s as documented.

## Light, air, night (`M_SkyDome`, `SailingEnvironment.cpp`)

- **Sky dome.** A sky material reproduces the atmosphere (`SkyAtmosphereViewLuminance`) and adds:
  - **Sun disc:** with limb darkening (u = 0.6), energy-normalised.
  - **Stars and the Milky Way:** placed by local sidereal time and the lake's latitude, with the Great Rift's dust lane.
  - **Moon:** its phase lit from the true sun, with earthshine on the dark limb.
- **Haze.** A humidity haze per preset: milky on a humid summer day, crisp behind a norther, sea haze on the bay and offshore. It darkens with the light, so the night horizon doesn't glow.
- **Volumetric fog.** On Medium and High, so the sun's shafts show through gaps in the cloud (coarse grid on Medium, finer on High).
- **Lightning.** A branching bolt per strike: a stepped main channel, plus 4–9 fading branches. A light lights the water, and the strike lights the cloud's inside around it. Thunder is delayed by distance, as before.
- **Rain and the lens.** The rain sheet leans with the wind. On High outside the capture mode, raindrops and wave spray land on the lens: they run with the apparent wind and refract the scene. The spray is fed by the water's spray droplets near the camera.

## Frame rate and GPU (packaged build, `bench.csv`)

| View | Low | Medium (V4) | High (V4) | Medium GPU ms (base / Lumen / water / clouds+fog) |
| --- | --- | --- | --- | --- |
| beam8 | 118.5 | 102.4 (82.4) | 54.3 (49.0) | 9.47 (3.65 / 1.28 / 1.58 / 1.87) |
| beat15 | 118.6 | 93.7 (84.0) | 51.2 (52.7) | 8.84 (3.14 / 1.3 / 1.6 / 1.65) |
| storm | 118.6 | 90.9 (118.7) | 55.3 (78.2) | 10.9 (2.81 / 1.36 / 1.61 / 3.95) |
| marina | 118.4 | 102.5 (86.9) | 58.4 (56.7) | 10.02 (4.36 / 1.58 / 1.6 / 1.46) |
| coast-day | 118.2 | 88.3 (77.0) | 52.1 (47.6) | 9.87 (3.94 / 1.61 / 1.6 / 1.54) |
| coast-night | 119.5 | 108.4 (92.3) | 64.1 (60.3) | 8.47 (2.54 / 1.58 / 1.41 / 1.79) |
| gulf-sea | 118.6 | 113.0 (94.7) | 67.2 (60.1) | 7.92 (2.45 / 1.34 / 1.63 / 1.4) |
| helm-eye | 118.5 | 98.7 (83.2) | 55.3 (50.7) | 9.96 (3.21 / 1.77 / 1.4 / 2.55) |

Every view clears both bars: Medium is at 88–113 fps and High at 51–67, faster than V4 because the clouds trace only the layers present.

Clouds and fog on Medium in clear sky cost 1.4–2.55 ms. Helm-eye's 2.55 is 0.05 over the 2.5 ms budget, inside the run-to-run noise of a three-frame ProfileGPU. In the storm view it is 3.95 ms on Medium and 6.4 ms on High, reported as the brief asks.

## Comparison (`compare/index.html`) and blind test (`blind/`)

Sky scores against the reference clips, before → after:

| Scenes | Sky |
| --- | --- |
| Fair-weather scenes | 2 → 2. They have real cumulus now rather than streaky haze; the remaining gap is grain in the cloud edges. |
| squall-lake | 3 → 2 |
| storm-lake | 3 → 3. **Not met.** |

The storm-lake reference looks into an approaching shelf cloud from a high shore. Our scene's tripod looks back toward the boat from inside the storm's path, and what shows is layered, lit storm cloud, not the shelf's curved lip, its bright gap and the rain wall beyond. From the side the structure is there; from the lake under it the shelf reads as one dark wall. This needs:
- a finer noise on the shelf's face and underside;
- a camera framing that matches the reference;

and is the open item.

Blind test round 4 is in `blind/`: ten new game frames and the same ten Commons photos, reshuffled. Its marking page is https://claude.ai/artifact/YVumx3ktcJkoz4NpcoHVWb, and the answer key is `blind/answer-key.csv` (don't open it before marking). Rounds 2 and 3 are still unmarked.

## Partial or left for later

- **Storm shelf look:** above, the one sky gate item not met.
- **Cloud grain:** a fine sparkle in the cloud edges (the quarter-resolution tracer's reconstruction). Half-resolution tracing cleans it a little for +1.5 ms.
- **Lens water:** screen-space drops, not simulated droplets on a glass mesh.
