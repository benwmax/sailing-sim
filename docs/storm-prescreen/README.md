# Storm sky: PC pre-screen (Oct 15 2026)

The Mac found the storm sky only marginally better after #50, and the phase-8 fix list still has it open. Fix-list item
7 says the storm sky is too light, with the note "the shelf structure itself still reads soft (open)". This is a
pre-screen on the PC at main e36585fe: stills of the storm views on High and Ultra, one cheap change tried, and what it
showed.

![main, storm views: bench storm, blind-test game-04, game-08 and game-10; High left, Ultra right](storm-main.jpg)

## What reads wrong (main)

- **game-04 (Catalina 30, front behind, Chase):** what lies behind the boat is a pale grey-white sheet, lighter than the
  sea, with vertical streaks. The references (STORM-001, STORM-005) are dark slate under the deck, with the rain wall
  darker still.
- **game-08 (Galveston, the shelf over open bay):** the shelf's face is bright white, and speckled where its tiers break
  up. The dark band under it is right, but the face reads like a fair-weather cumulus skin, not a shelf. Ultra is grainier
  than High.
- **game-10 and the bench storm view:** fair-weather-bright cumulus towers ahead of the front, and a flat grey overcast
  over the boat. Not wrong as such, but nothing in either view reads threatening.

## Tried: a darker storm cloud (constants only, cost-neutral)

The storm deck's albedo was taken from 0.74-0.80 to 0.42-0.50, its low-altitude occlusion floor from 0.3 to 0.18, and
the shelf face's brightening from 1.6x to 1.25x (`CLOUD_CODE` in make_materials.py).

![main left, darker storm cloud right: game-04 and game-08, High then Ultra](storm-dark1.jpg)

The pictures barely move:

- In game-04 the pale sheet isn't the cloud at all. It's the rain curtains (`M_RainCurtain`) and the volumetric fog in
  front of it.
- In game-08 the albedo only reaches samples where storm density dominates. The shelf's bright face is lit by the
  clouds' undimmed sun (`CloudScatteredLuminanceScale`), and its outline is still cumulus-like erosion.

Reverted: it doesn't earn a gate.

## Where the fix is (a scoped change, cost-neutral on Mac High)

1. **Rain curtains and fog under the deck:** darken their in-scattering by the deck's shadow (`FWeatherMap::
   SunTransmittance` toward the sun) instead of the open-sky light. That is where game-04's pale wall comes from.
2. **The clouds' sun inside a storm:** scale `CloudScatteredLuminanceScale` (or the cloud's sun term in the material)
   by the storm's coverage toward the sun, so a shelf seen with the sun behind the storm is lit by the sky, not the sun.
3. **The shelf's face:** a smoother, denser outline over its tiers. The face's erosion is what speckles on Ultra
   (`edgeS` / `lip` in `CLOUD_CODE`).

Each needs a pre-screen at game-04 and game-08 on High and Ultra, and a bench of the storm view next to main. The Mac's
High is at 46.5-47.5 fps on the sentinels, so none of them may add cloud or fog cost there.
