# W4: foam that reads as foam (water-4)

The Mac's #85 fixed how much whitecap there is and how big the caps are (the mask, held by `Whitecaps`, `WhitecapsSeen`
and `WhitecapSize`). This pass changes only how the caps are drawn: none of it changes `caps`, the mask the tests and
`-SailingDebugFoam` measure. Low (`M_Water`) is unchanged.

## Step 1: tone, opacity, cells (M_WaterV4)

- **What was wrong:** the cover went straight into opacity over a foam albedo of 0.85. A pixel at 0.3-0.5 cover read
  nearly as white as a solid cap, flat to its hard edge: the decal look (Mac, `docs/water-8/capshape-mac`).
- **FoamTone** (a new output of the shading node) scales the foam's white:
  - 1 on an active crest, 0.5 on the residue it leaves. A dense active whitecap reflects about 0.5-0.6
    (Frouin, Schwindling and Deschamps 1996); Koepke 1984's effective albedo across a whitecap's life is 0.22, so
    aged foam is much dimmer.
  - Broken by bubble cells, 0.7-1.
- **Opacity** follows cover to the power 1.5, with interior bubble cells (0.4-1). The edge feathers over a wider fold
  ramp (0.15 of J against the mask's 0.05): a cap thins out at its edge instead of stopping.

![Lake, High, 12/16/20 kn (rows): main left, this pass right](caps-before-after.jpg)

![Nearest caps at 20 kn, full resolution: main left, this pass right](cap-near-20kn-before-after.png)

Tests: `Whitecaps`, `WhitecapsSeen`, `WhitecapSize`, `WaveMatch` pass. The cost is a few ALU in the pixel shader, no
new texture.

## Next

- Foam persistence and streaks: a worker foam grid round the camera, fed by the caps, decaying with Monahan's residue
  timescale and drawn along the wind.
- Wake foam that lingers (from #84): feed the boats' wake foam into the grid.
- Cost on Mac High: one texture fetch and a few ALU (the PC water gate is running).
