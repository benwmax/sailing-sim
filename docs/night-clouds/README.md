# Night clouds: lit from below by the towns, gone after sunset

The night sky over the lake (`*-before.jpg` / `*-after.jpg`, 22 Oct 2026, AfternoonBreeze unless named, High):
- `dusk-*` (18:54);
- `evening-chase` (19:45);
- `night-*` (21:30);
- `overcast-night-*` (21:30, Overcast).

**Before.** At night the cumulus were dark, flat silhouettes against a bright beige sky that glowed 30 deg up. Under
an overcast the deck was dark navy, with a bright rim where the live clouds met the far cache. Fair-weather cumulus
stayed at 40% of the afternoon's cover all night.

## What changed

1. **Cloud bases lit by the city glow.**
   - `CLOUD_CODE` emits the glow in proportion to the extinction, like the shelf's face, so an opaque base reads the
     glow and a thin edge its share: the clouds keep their shape.
   - The glow dies 600 m into each layer above its base, and is strongest toward each city dome (`GLOW_TOWARD`, the
     domes' azimuth and strength as the sky draws them).
   - Its scale is `GlowLum` from the domes' total (`ASailingEnvironment`, `kCloudGlow` 0.35 per unit, times 0.1 in the
     shader against the sky material's units).
   - The far clouds (the C2 sky cache, past 5 km) get the same glow where `M_SkyDome` composites them: their opacity,
     shaped by the cache's own height shade, so bases glow more than tops.
   - Under a stratus deck at night the cache steps aside, as it does for a storm, so the deck is all one surface (no rim).
   - Stars sit behind both, attenuated by the clouds' transmittance.
   - `-SailingCloudGlow=<scale>` measures.
2. **The clouds in colour.** `M_CloudLayers` was built with the volumetric "grayscale material" option, which keeps
   only the red channel of the albedo, extinction and emission. So no glow could be warm, and the storm's slate albedo
   lost its blue. It is off now. Packaged High, grayscale on → off:

   | view | fps | clouds ms |
   |---|---|---|
   | storm | 46.8 → 47.0 | 7.96 → 7.86 |
   | beat15 | 60.1 → 60.0 | 1.44 → 1.44 |
   | helm-eye | 59.7 → 60.2 | 0.91 → 0.98 |
   | marina-night | 60.9 → 60.8 | 1.18 → 1.03 |

   No cost measured.
3. **The domes hug the horizon.** The beige sky overhead was the city domes themselves, not haze (`-SailingClassicHaze`
   and `-SailingNoMoon` left it unchanged). They now fall off as `exp(-11 h)`, not `exp(-7 h)`: half by 4 deg, 6% at
   15 deg, under 1% past 25 deg.
4. **Under the deck at night the light is warm.** The storm's grey cut (post saturation, by `CloudDarkness`) now
   fades out with the night.
5. **Fair-weather cumulus dies after sunset.**
   - The game mode works out the day's sunset from the date and latitude (sun's upper limb at -0.83 deg; 18:45 on
     22 Oct at the lake) and hands it to `FWeatherSystem::SetSunset`.
   - CalmMorning, AfternoonBreeze and ClearMistral cumulus (RandomDay through its base) fade from a quarter of an hour
     before sunset over two hours to 15% of the day's cover. They stay down through the night and build again after
     6-8 h.
   - Thunderstorm, Mistral, Overcast and Rain keep their skies.
   - `SailingSim.Visual.CumulusAfterSunset` holds this for an October and a June sunset.
6. **Dusk is dusk.** The dusk and night bench views (`coast-dusk`, `gulf-dusk` at 18.9, and the night views) now pin
   `-SailingDate=2026-10-22`. On today's date they drifted with the season: 18.9 h is ten minutes after an October
   sunset but an hour and a half before a June one. The Windows views are kept in step.
