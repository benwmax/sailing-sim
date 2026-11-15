# Colour banding (Nov 15): not in the game's frames

## Result

**There is no banding in the game's screenshots.** The "heavy colour banding" I reported in #703 round 1 (the clear
before-storm still) and in main's Sunfish stills came from how I viewed them, not from the game. I looked at the
3840x2160 PNGs through a downscaled preview, and that preview posterised the gradients. The PNG files themselves are
smooth. I'm sorry for the false lead.

## Evidence

**1. The PNG format.** The bench screenshot (`FScreenshotRequest::RequestScreenshot` in `SailingGameMode.cpp:1400`,
the engine's back-buffer readback) is 8-bit RGBA, not interlaced, with no gAMA, sRGB or palette chunks. The bench path
applies no quantisation of its own: it is the engine's standard screenshot of the presented frame, UI included.

**2. Sky columns, read straight from the PNGs** (`steps.py`):

| still | column | levels changed by 1 | larger steps |
|---|---|---|---|
| before-storm-shore | x=3300, y 150-900 | 345 of 364 | 17 of 2-5 levels; none bigger |
| sunfish-lake-day (main 6f44708f) | x=600, sky | most | the big jumps are cloud edges |

Runs are 1 to 19 px long. That is a smooth gradient dithered to 8 bits, not posterised.

**3. Colour counts** (`patch.py`). There are thousands of distinct colours per 600x300 sky or cloud patch (1,261 to
6,946), and no single colour covers more than 7% of a patch. A posterised image would have a handful of colours with
large flat shares.

**4. 1:1 crops** (`before-storm-crop-1to1.png`, `sunfish-crop-1to1.png`). Viewed without downscaling, the sky
gradients and clouds are smooth.

**5. The worst case, a clear dusk sky** (`dusk-Ultra.png`, `dusk-High.png`). Settings: main a9514c07, which has #703;
lake, 21 June, 19:36, the camera pitched up into the low sky, 4K, no HUD. Args are in the JSONs and below.
- Down the gradient (x=1920 and x=3600): Ultra steps 1 level 384 and 447 times; High 395 and 481 times.
- The bigger steps are cloud edges.
- The 1:1 crops (`dusk-*-crop-1to1.png`) show no contour bands on either tier, and High and Ultra look the same.
- Args: `-SailingWorld=Lake -SailingLaunch=1 -SailingWeather=AfternoonBreeze -SailingHour=19.6 -SailingDate=2026-06-21
  -SailingWind=6 -SailingTWA=90 -SailingHoldTWA=90 -SailingCamYaw=0 -SailingCamPitch=12 -SailingCamDist=12
  -SailingNoHud -SailingCloudScale=0,0`. `-SailingCloudScale=0,0` did not remove the clouds.

## What I could not establish

I could not compare against an independent capture of the live window. PrintScreen and other synthetic routes are not
allowed, and no capture tool is installed. The bench PNG is the back-buffer readback, so it is the frame the game
presented; what the OS and monitor do after that is untested.

## What I did not do

- **The cvar sweep** (tonemapper, grain quantisation, scene colour format, sky LUT sizes, exposure band): there was no
  banding to remove.
- **A new package** (`Windows-75ed143f`): the existing a9514c07 package, which has #703, was enough.

## One thing seen in passing

In the dusk crop, the top right cloud's lit edge shows a grainy, speckled fringe. That is the volumetric clouds'
sampling noise at sunset, not banding. It may be worth a look by whoever owns the clouds at dusk.

**Proposed fix:** none needed for banding.
