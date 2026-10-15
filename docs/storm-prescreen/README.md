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

## What it really was (storm-sky-fix)

The first try's diagnosis above was wrong on game-04. Turning the rain curtains off (`-SailingNoRainCurtains`) and the
fog off (`r.Fog 0`, `r.VolumetricFog 0`) left the pale wall where it was. Tinting the layers (`SAILING_DEBUG_LAYERS`)
showed it was the storm layer's own volumetric cloud. Its dark albedo was multiplied by the camera's cloud darkness
(`FrontB.w`), so it only applied with the boat already under the deck. Seen from the sunshine ahead of the front, the
storm stayed white.

The fix is constants and one per-sample term in `CLOUD_CODE`, plus the curtains' shade. No new samples, no new textures:

1. **The storm's cloud is dark wherever the viewer stands.** Albedo `lerp(0.96, (0.19, 0.21, 0.26), wet)`, a blue slate,
   without the `FrontB.w` factor. The low-altitude occlusion floor goes from 0.3 to 0.2.
2. **What counts as wet.** It's the storm's share of the density, or its own density (`dSm * 2`), or the storm's structure
   (`storm * 3`), or the map's storm extent (`w.a * 2`), faded out at 4.5-5.5 km under the anvil (it was 3-4.5 km). Before,
   it was only the share, so any stratus or cumulus inside the storm took the larger share and came out sunlit white.
3. **Rain curtains in the deck's shadow.** Each curtain's colour is multiplied by `lerp(0.2, 1, Shade)`, where `Shade` is
   `FWeatherMap::SunTransmittance` from the curtain toward the sun. It's computed on the game thread with the curtain
   selection, twice a second for up to 32 curtains (16 on Low), and sent as per-instance custom data 3.
4. **The shelf's face.** The billow erosion is cut by 0.85 over the shelf above its base (it was only cut at the lip), and
   the face brightens to 0.8 instead of 1.25 (front boost 1.1, was 1.6).

Not done: scaling the clouds' sun term (`CloudScatteredLuminanceScale`) by the storm's coverage. With the albedo
fixed it wasn't needed for these views.

**game-08's pale band** (the grey towers across the middle of the frame) isn't the shelf. Zeroing the material's albedo
removes it, but none of the storm terms (`dSm`, `storm`, `w.a`) reach it, and neither a higher step depth
(`-SailingCloudStepDepth=2.5`) nor three times the storm's extinction (`-SailingCloudLayerExt=1,1,3,1`) hides it. These
are fair cumulus outside the storm's painted extent, so they aren't seen through the deck, and they're lit by the sun
beside the storm. The cumulus that were inside the extent (the puffs under the deck, top left) are now in its shade. If
game-08 should show no sunlit towers at all, that's a weather-map change (fade cumulus coverage near the front), not a
shading one.

## Where the fix is (as first proposed, before the diagnosis above)

1. **Rain curtains and fog under the deck:** darken their in-scattering by the deck's shadow (`FWeatherMap::
   SunTransmittance` toward the sun) instead of the open-sky light. That is where game-04's pale wall comes from.
2. **The clouds' sun inside a storm:** scale `CloudScatteredLuminanceScale` (or the cloud's sun term in the material)
   by the storm's coverage toward the sun, so a shelf seen with the sun behind the storm is lit by the sky, not the sun.
3. **The shelf's face:** a smoother, denser outline over its tiers. The face's erosion is what speckles on Ultra
   (`edgeS` / `lip` in `CLOUD_CODE`).

Each needs a pre-screen at game-04 and game-08 on High and Ultra, and a bench of the storm view next to main. The Mac's
High is at 46.5-47.5 fps on the sentinels, so none of them may add cloud or fog cost there.
