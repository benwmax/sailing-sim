# Far whitecaps as upright sprites (option B of `docs/far-caps/`)

**What:** on High and Ultra, the whitecaps from 300 m to 1.25 km are small upright quads standing on the crests
(`AWaterSurface::UpdateFarCaps`, `M_FarCap`) instead of `M_WaterV4`'s flat flecks (option A). Medium keeps A alone.

## How

- **Placement.** The ring is cut into 400 m tiles. A tile is held when it reaches into 300 m to 1.25 km, the eye is
  low over it (height under 0.14 of its far distance: from above, A's flecks read better), and it lies within the half
  field of view plus 25 deg. It is dropped once it is 40 deg out, so tiles appear and go off screen. The plan runs every
  0.5 s, and at once when the view turns more than 8 deg.
- **Mesh.** Each tile is one Static ISM of slots placed from the tile's own seed. A rebuilt tile keeps its places.
  There are no slots on land or within a hop (7 m) of the shore. The ISM has no collision, shadow, distance field, ray
  tracing or captures, following the spray pool's pattern.
- **Cover, same as A.** The tile's cover is `FarCapCover`, the same Monahan cover the fleck cells carry: wind from
  `FWindField::ReadableAt` and the mean surface roughness, times `WhitecapScaleFor` and the breaking onset, so there
  are none on glassy water or under the breaking onset.
  - The caps alive at once are cover × tile area ÷ (cap area 1.5 m² × the life's mean 0.7937).
  - The slots number 1.3 × that + 1, at a live probability that makes the mean exact (`FarCapTilePlan`).
  - Over 30,000 slots in view (a storm), the caps get fewer and bigger in quarter steps (`Size`), with the same foam.
- **Handover.** The sprites' share is `FarCapSpriteWeight`, mirrored by M_FarCap and by M_WaterV4's `FCS_W`. Its
  terms:
  - smoothstep 300–400 m in;
  - smoothstep 1.1–1.25 km out;
  - smoothstep 0.05–0.14 on height over distance.

  The flecks are multiplied by 1 − that, so the two never stack: sprites stand in for flecks.
- **Life.** Each cap lives 4 s, as 1.6 sin clamped at 1, hops up to 6 m between lives, and rides at 0.6 Hs.
- **Popping.** A cap's life is decided as it starts. Lives begun before `SwitchT` keep `ProbA`; later ones take
  `ProbB`. A slot added by a rebuild (`Born`, custom data 1) stays dark until its next life. Tiles grow, never shrink in
  place.
- **Material.** Masked with a temporal-AA dither (translucent, the caps over the water were hidden behind the single
  layer water at a low eye). Lit as foam lying on the water, with the normal mostly up and leaning to the eye.

## Budget (packaged High, Mac, two or three runs each)

| view | fps off → on | GPU frame (stat unit) | game thread | farcap_cpu_ms | slots |
|---|---|---|---|---|---|
| helm-eye 20 kn | 59.7 → 59.7 | +0.01 ms | +0.02 ms | 0.021 | 19,175 |
| beat15 | 61.05 → 60.2 | +0.23 ms | +0.03 ms | 0.024 | 7,985 |
| storm | 47.35 → 46.7 | +0.29 ms | +0.12 ms | 0.10 | 29,000–31,000 |

Limits:
- GPU: 0.4 ms on High. Met in all three views.
- Game thread: 0.2 ms. Met (0.12 ms at most, in the storm).
- Storm on High: at least 46 fps. Met at 46.7.

The first build cost 3 fps everywhere and the storm went to 44.2. It held all 38 tiles of the ring, about 110,000 slots
in the storm, and each moving tile was dynamic ray-tracing geometry (0.5–1.5 ms of render thread). The view cone, the
slot budget and dropping them from ray tracing brought it to the table above.

## What it looks like

`helm{12,16,20}-before.jpg` / `-after.jpg` are the helm's eye at 12, 16 and 20 kn (before: `-SailingNoFarCaps`).
`helm*-far-band.jpg` shows the far water 3× (top before, bottom after).

**Honest result.** From the helm's 2 m eye, a cap at 600 m is about 2 px wide and 0.7 px tall at 1440×1080. At A's
cover there are only 0.08% (12 kn) to 0.44% (20 kn) of them, and most of the far lake there reflects a bright sky. So
over the open far water the sprites hardly change the picture.

They do show where the water behind them is dark: under the far shore, and as a scatter of specks along the water's
edge at the horizon (`motion-diff.jpg`: on minus off, ×4). B therefore delivers what it promised (caps with height at
the horizon, at the right cover, inside the budget). It is less visible than `docs/far-caps/` hoped, because the cover
the coordinator fixed is small.

Ways to make them read more, each a change of what "right" means and not done here:
- a brighter crest (spray lit against the sun);
- a larger cap area on the lake (fewer, bigger);
- the cover not tied to A.

## Popping (recorded run)

The recorded run is `-SailingSlowMo=0.1` with `RECORD=3 RECORD_INTERVAL=0.1`: screenshots 0.15 s of game time apart,
since a screenshot takes about 0.8 s on this Mac. The settings were helm-eye, 20 kn, the autopilot sailing (`DEMO=1`),
once on and once with `-SailingNoFarCaps`.

`motion-strip.jpg` is the horizon band 3× over six frames, and `motion-diff.jpg` is on minus off. The sprites' specks
hold from frame to frame. None appears or vanishes outside the run-to-run noise of the water, which is about 1.5
levels: the two runs are not bit-identical, so no exact pop count is possible. The tile and probability changes that
could pop are handled by construction, as above.

## Args and tests

- `-SailingNoFarCaps` compares.
- `-SailingDebugFarCaps` makes every slot live and ten times as tall, and logs the tiles.
- `-SailingSlowMo=<f>` dilates the world's time.
- bench.json has `farcap_cpu_ms` and `farcap_slots`.
- `SailingSim.Visual.FarCapSprites` holds:
  - the tiles carry the cover exactly, bigger caps included;
  - no caps under the onset;
  - the weight's range and its limits (none near the boat, none from above, none past 1.25 km).
