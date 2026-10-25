# The G5 shore scene's site (Oct 25 2026)

The G5 shore photo (a Lake Tawakoni shore, `docs/graphics-5/blind/stills/still23.jpg`) shows long, regular, parallel
crests crossing water that is otherwise almost glassy. Our g5-shore scene never showed them. Narrower spreading
(`docs/short-wave-spreading`) didn't change that: the up-down reflection ratio stayed at 0.70, against the photo's 3.40.

## Cause: the site, not the waves

- **The photo:** it looks out through a bay's mouth to open water (the horizon is in the frame). Its crests are waves
  grown out on the lake, travelling into the calm inshore water. They are not a local wind sea.
- **Our camera:** g5-shore stood at map (-1190, 1150), inside a nearly enclosed cove.
  - The sea map's Saville fetch there is 230 m or less in every direction, and 68 m upwind of the scene's northerly.
  - The model gives it Hs 0.02 m against 0.29 m outside, with no long components at all: only the local chop. Nothing
    there could draw the photo's crests.
- **An open shore:** a shallow cell facing 4 km of water to the north, map (-2070, -1710), 1.5 m deep.
  - The same 9 kn northerly gives Hs 0.145 m there.
  - Its long components are 8 to 12 m waves arriving head-on, 2 to 5 mm in amplitude each.

`cove-open.jpg` (High, overcast, noon, the camera 1.6 m up):

| | |
|---|---|
| The old cove at 9 kn | The photo |
| The open shore at 9 kn | The open shore at 6 kn |

The open shore draws crests rolling straight in. At 6 kn they are regular rows of wavelets across the view, the closest to
the photo.

## The change

`docs/graphics-5/blind/scenes.csv`: g5-shore is now the open shore at 6 kn from the north. The camera
(`-SailingCamWorld=-920,-2860,1.6,0,-4`, relative to the start at the cove) is at map (-2070, -1710), looking north.

The old cove view is still what the shore-plant passes (`docs/weed-tops`, `docs/shore-margin` and others) compare. To
reproduce it:

```
-SailingWorld=Lake -SailingStartAt=-1150,1150,0 -SailingKeepStart -SailingWeather=Overcast -SailingWind=9 -SailingHour=12 -SailingCamWorld=-40,0,1.6,40,-4 -SailingQuality=High
```

The game doesn't change.

## Known limits

- **The glassy water between the photo's crests.** That is a breeze that has dropped: long waves outlast the ripples. In
  play the sea does this already, since each band decays over 8 T^2 (`FWaveField::GrowthSeconds`). A capture starts at
  the steady sea for its wind, so a still can't show it. Showing it needs a "wind dropped" start for captures. Done
  properly, that also has to hold the short-wave detail's development to the new wind (it follows the field's variance),
  so it is not a two-line arg. Left out.
- **No propagation into shelter.** Each point grows only the waves its own fetch allows (FSeaMap). Waves don't diffract
  through a cove's mouth or round a headland. Inside a narrow-mouthed cove the model's sea is smaller and broader than a
  real one fed from outside.
