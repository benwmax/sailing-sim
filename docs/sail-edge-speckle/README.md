# The speckled sail edge (Oct 25 2026)

Against a bright sky, the main's and jib's leeches showed a dotted fringe of dark pixels.
- It wasn't the leech flutter or the opacity dither (`docs/sail-aliasing`).
- It wasn't the leech telltales: #324 faced them to the camera, and the fringe was the same before and after.

## Not the anti-aliasing

`aa.jpg` shows the jib's leech at 3x, in four modes: AA off, TAA, TSR, SMAA (`-SailingAA=0|2|4|5`). With AA off the dark
pixels sit right on the silhouette. The AA modes only smear them into the fringe.

## The cause: curvature from screen derivatives at the silhouette

M_SailCloth estimates the cloth's curvature from the screen-space change of its normal (`kc`, from `ddx`/`ddy`). It uses
`kc` for two terms that darken the cloth:
- the belly seen from its hollow side, up to 16%;
- #322's wrinkle valleys, up to 25%.

Where the cloth turns edge-on to the eye, a pixel's footprint runs a long way across the curved surface. The derivatives
there span the curve and the silhouette, so `kc` is noise, and it darkened single edge pixels.

Both terms now fade out as the cloth turns edge-on, by `smoothstep(0.08, 0.25, facingV)`, the facing the shader already
computes for the draft.

`edges.jpg` shows two before/after pairs, main on the left of each:
- **Left pair, the jib's luff with AA off:** the dark silhouette pixels are mostly gone.
- **Right pair, the main and jib with TAA:** the fringe is softer.

## What is left

With TAA a light fringe remains along a moving silhouette. The boat and her cloth move every frame, and TAA resolves a
high-contrast moving edge that way. It isn't shading. Native-resolution TAA on High is the trade made in Visual V1. TSR
or a sharper history clamp would change it, at a cost.
