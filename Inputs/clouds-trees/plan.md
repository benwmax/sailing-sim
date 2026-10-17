# Clouds and trees: a plan for changes you can see

Written Oct 17 2026 for Bean, after blind round 12 (clouds named on 4 of 20 frames, trees on 1).
Clouds have been the top tell in every round since round 7. Small tweaks have not moved the score, so this plan
changes how the clouds and trees are made, not just their settings.

## What you will see change

| Now (round 12 stills) | After this plan |
|---|---|
| Cloud edges look spray-painted: a fuzzy, grainy fringe all the way round. | Sunlit tops have crisp, cauliflower-like edges; only the bases and far clouds go soft. |
| The insides look like stacked pancakes or contour lines (lake towers still). | Rounded billows that build upward, with a flat grey base underneath. |
| Clouds are huge and close, filling half the frame. | Fair-weather clouds are mostly small and far: a row of puffs over the shore, lots of blue sky (like real photo 05). |
| Each cloud's base sits at its own height. | All the bases on a given day line up at one height, as they do in real Texas cumulus. |
| The storm sky is streaky and speckled. | A smooth dark base with a bright band under it (like real photo 08). |
| Shore trees are round dark-green balls, all the same size and colour. | Mixed species and heights, yellow-green to blue-green, trunks and sky showing through gaps, willows leaning over the water (like real photo 10). |
| Trees are lit evenly, so the shoreline looks flat ("lighting feels off"). | Shady insides to the crowns and dark ground under them, so the tree line has depth. |

Real photos to compare against are the ones you already marked as real:
[real-05 cumulus over a far shore](../sailing-sim-g5/real/real-05.jpg),
[real-08 storm base](../sailing-sim-g5/real/real-08.jpg),
[real-10 lake shore with willows](../sailing-sim-g5/real/real-10.jpg),
[real-03 White Rock Lake wooded shore](../sailing-sim-g5/real/real-03.jpg).
Our stills are in the repo under `docs/round-12/game/`: `r12-lake-towers`, `r12-galv-kemah`, `r12-galv-texascity`, `r12-storm-shelf`.

## Why ours look fake

I looked at the four round 12 cloud and tree stills next to the real photos, and at the code.

- **Clouds are drawn in one quick pass with too few samples.** The game looks through the sky in about 80 steps
  (roughly every 190 m on the Mac). Anything finer than a step turns into speckle, so earlier fixes blurred the
  detail away. That is the trade-off between "noisy" and "cartoonish" that Bean has been catching on both sides.
  The clouds already cost 5.0 ms of the Mac's 13.5 ms frame at the lake towers, so we can't just add more steps.
- **The shapes come from generic noise.** Nothing in the shape knows how a cumulus grows: rising bubbles, a flat base
  where the air condenses, and towers that billow out at the top. Clouds are also too big: the cells go up to 4 km
  across, but most fair-weather cumulus are 0.2 to 1.5 km.
- **The leaves are drawn by a script, not photographed.** The leaf texture is painted by a small Python program, and
  there are only 8 tree models in the whole game.
- **Trees past 250 m are solid green balls.** To save time, trees beyond 250 m (on High) switch to plain crowns, and
  every lake-shore view sees them at that range.
- **Trees are left out of the lighting system's model of the scene** (it cost 10 ms with leaf cards). So nothing
  darkens the inside of a crown or the ground under it, and the whole tree line is lit evenly.

## How other games do it

| Game | Clouds | Trees |
|---|---|---|
| Horizon Forbidden West (Guerrilla, "Nubis" talks 2015, 2022, 2023) | Cloud shapes built from real weather types: a height profile per cloud type with billows eaten into it. Later, whole 3D cloud models made in a simulation and stored as a "voxel" grid. | |
| Red Dead Redemption 2, Microsoft Flight Simulator, Frostbite games | Far sky rendered slowly over many frames and then reused, because distant clouds barely change frame to frame. Close clouds are drawn live. | |
| Unreal Engine 5.7+ (Epic, our engine) | Our current approach, the engine's volumetric clouds. | **Procedural Vegetation Editor** grows trees inside the editor. **Nanite Foliage** draws far tree canopies as tiny voxels instead of blobs or flat cards. Both are free and built in, and both are marked experimental. |
| Most AAA open worlds (Fortnite, Forza Horizon, Far Cry) | Forza uses photographed real skies. | Photo-scanned leaves and bark; "impostors" (pictures of a real tree from many angles) for distant trees; colour and size varied per tree. |

The common thread is that realistic games don't draw the sky from scratch every frame. They put the expensive work
somewhere else: into the shape (made ahead of time from real cloud physics) or into time (rendered slowly, then
reused). Trees work the same way. They start from photographed leaves and use a proper far-distance version of the
same tree, not a stand-in shape.

## Do we need to add something to the engine?

**We don't have to change Unreal itself.** A custom engine build would mean rebuilding Unreal on both machines at every
update, and that isn't worth it here. What we do need:

1. **Two built-in Unreal features switched on:** the Procedural Vegetation Editor and Nanite Foliage. Both are free and
   come with 5.7 and later. Because they are experimental, the first step is checking that Nanite Foliage works on the
   Mac's graphics (Metal). If it doesn't, we fall back to impostors, which work everywhere.
2. **One new piece of our own rendering code, a "sky cache."** It renders the far clouds carefully, a slice at a
   time, into a panorama that gets refreshed every few seconds (faster in storms). Only nearby clouds are drawn live.
   This is game code in our repo, not an engine change. It's the single biggest fix for grain, and it should also
   give the Mac frame time back.

## The steps

One PR each. The PC builds them (graphics is its side), and the Mac checks frame rate (Medium 60 / High 45 fps)
before anything merges. All of them count as round 12 tell fixes, so they fit under the v1 freeze, except C3, which
is marked below. Frame costs are my estimates until each PR measures them.

### C1. Cloud shape and size (material only, quickest win)
- **You'll see:** smaller, farther fair-weather clouds with flat bases at one height and rounded tops that build
  upward. No pancake layers or contour bands, and crisp sunlit edges on top with soft ones only underneath.
- **How:** use the per-cloud-type height profile and upward billow erosion from the Horizon talks. Base height comes
  from the day's temperature and dew point (about 125 m per degree of spread). Cap cell size near 1.5 km on
  fair-weather days and keep the big ones for building days. Make the edge sharp on the sunlit side and soft on the
  base. These are changes to `make_materials.py` (CLOUD_CODE) and `CloudSky.cpp` (sizes).
- **Check:** re-shoot the four round 12 cloud stills from their saved cameras, side by side with the old ones and
  with real-05.
- **Cost:** about 0 ms. Same steps, different shape.

### C2. Sky cache (new code, fixes the grain)
- **You'll see:** the speckle under the bases (Kemah, storm shelf) and the streaks in the storm sky go away, and far
  clouds keep their detail.
- **How:** clouds beyond about 4 km are rendered into a panorama with many more samples per pixel, a slice per frame,
  refreshed every few seconds (every second or so in a storm). The live pass only draws the near clouds, so it can use
  short, fine steps. The boat moves too slowly for the far sky to shift visibly.
- **Check:** the same stills, plus a 60-second video at the storm shelf to make sure there's no visible pop when the
  panorama refreshes.
- **Cost:** should be cheaper than today. The target is clouds and fog at 3 ms or less on Mac High, down from 5.0.

### T1. Tree lighting and variety (quick)
- **You'll see:** crowns with shady insides, darker ground under the trees, and every tree a slightly different size
  and green, including yellow-greens and some autumn colour, since the season follows the game date.
- **How:** give the far crowns a cheap shadow shape the lighting can use, so they count again without the 10 ms leaf
  cost. Add a per-tree tint, size and lean.
- **Check:** re-shoot the lake towers and north shore, side by side with real-03 and real-10.
- **Cost:** 0.3 to 0.5 ms on High (estimate).

### T2. Real leaves and real Texas species
- **You'll see:** leaves that look photographed, trunks and branches visible near the water, and sky showing through
  gaps in the crowns.
- **How:** replace the script-drawn leaf atlas with photo-scanned leaves and bark, then grow our shore species in
  the Procedural Vegetation Editor. For the lake: post oak, cedar elm, sugarberry, eastern red cedar, and black
  willow and cottonwood at the waterline. For Galveston: live oak and salt cedar. Several variants of each.
  - **Assets:** CC0 first (Poly Haven, ambientCG), because those can go in git and reach the Mac. Free Megascans
    from Fab only where CC0 has no match. Fab files can't go in git, so you would need to copy them to the Mac.
- **Check:** close and mid shots of Rush Creek and the north shore; the model viewer gets the new trees.
- **Cost:** up to 1.0 ms on High. That is the plants budget already set in the environment plan (E4), which this
  starts early.

### T3. Far trees that look like trees
- **You'll see:** the far tree line stops being green balls. Each tree has its own silhouette, with gaps and trunks
  at the shore line.
- **How:** use Nanite Foliage for distant canopies if it passes on the Mac. Otherwise use impostors baked from the T2
  trees.
- **Check:** the Texas City, Kemah and lake towers stills.
- **Cost:** about the same as the current blobs or less (estimate). This gets measured first, on both machines.

### C3. Real cumulus shapes from a simulation (bigger; after v1 unless C1 and C2 fall short)
- **You'll see:** cauliflower detail at the right scale, with towers that look like the ones over the lake on a July
  afternoon.
- **How:** this is the Horizon "Nubis Cubed" approach. Simulate a field of cumulus on the PC's 4090 with the free
  physics model already planned in the weather plan (W6 pilot, MicroHH). Then store 30 to 60 cloud shapes as small 3D
  textures and place them from our weather map.
- **Cost:** GPU about the same as C2. Roughly 30 to 60 MB more memory (estimate).

## Order and the target

The PC's order after the Kemah towers fix: **C1, T1, C2, T2, T3**, then C3 after v1. The cheap, visible ones come
first, so you'll see changes early.

**Target for the next blind round:** clouds named on 1 frame or fewer (4 now) and trees on none (1 now), at the same
scenes. Each PR posts its side-by-side stills before merging, so you can judge them yourself along the way.

This builds on, rather than replaces, the existing plans: weather plan W5 (cloud fixes) and W6 (simulation pilot),
and the environment plan E4 (plants). Everything uses free tools and free, commercial-OK assets.
