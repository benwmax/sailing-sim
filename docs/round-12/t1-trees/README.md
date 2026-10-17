# T1: tree lighting and variety (round 12, `Inputs/clouds-trees/plan.md`)

The second item of the clouds and trees plan. In round 12 the shore trees looked flat: "lit evenly, the shoreline looks
flat", every tree the same green.

## The lighting

Lumen's scene had no trees at all. Capturing the leaf cards into its surface cache had cost 10 ms (Visual V6), so every
tree component was kept out of it, out of ray tracing and out of the distance fields. Nothing shaded a crown's inside or
the ground under it beyond the shadow maps' direct sun.

- **The opaque mid and far crowns** (`SM_*_Far`: 250 m to 1 km with shadows, beyond 1 km without) are cheap, closed
  meshes. They now affect indirect lighting, ray tracing (Lumen on High and Ultra) and the distance fields (Medium's
  software Lumen).
- **The near leaf-card trees** get a lighting-only stand-in: the same tree's opaque crown, at 85% of its size so the sunny
  outer leaves stay lit. It is hidden in game but kept in the indirect lighting (`bAffectIndirectLightingWhileHidden`),
  and casts no shadow, since the leaf cards cast that. A crown kept out of the main pass instead (`bRenderInMainPass =
  false`) was left out of Lumen too, and made no difference.
- **Ambient occlusion in the leaf cards.** The cards' vertex red says how far out they sit. The sky and Lumen's indirect
  light reach the inside of a crown a third as much as its outside.
- The leaf cards themselves stay out of Lumen's scene.

At the north lake shore (`shore150`, below), the near trees' insides and the ground under them darken: by about 4 of 255
on the ground under the near trees, more in the crowns' hollows.

## The variety

`TreeLookFor` (`TreePlacement.h`) gives each tree its own look. It is a pure function of the tree's position, through the
shared portable hash, so it is the same after every regroup and on the Mac and the PC. It goes to per-instance custom
data 0-2, read by `M_TreeLeaves` and `M_TreeCrown` (`TREE_LOOK` in `make_materials.py`):

- **Its green**, from yellow-green to blue-green, and its brightness, plus or minus 25%.
- **How much it turns in autumn.** The deciduous post oaks and cedar elms each turn their own amount; the live oaks and
  eastern red cedars keep their green.
- **Its autumn colour.** Russet-brown for the post oaks, which keep their brown leaves through the winter; yellow for
  the cedar elms.
- **A lean** of up to 3 degrees either way, so a stand isn't ruler-straight.

**The season** follows the session's date (`AutumnAmount`, `SpringAmount`, through `MPC_World.Autumn` and `.Spring`):

| | Day | Amount |
|---|---|---|
| Green in summer | | 0 |
| Turning, mid-October | Oct 17 | 0.2: the early turners show colour |
| Peak, near Thanksgiving | Nov 25 | 1 |
| Post oaks still brown, until leaf-out in late March | Jan 10 | 1 |
| Spring's fresh yellow-green, early April | Apr 5 | 1 (spring) |

`-SailingNoTreeLight` and `-SailingNoTreeLooks` compare (both off = before).

## Stills (packaged, the PC)

- `shore150-high.jpg`: the north lake shore 150 m off, High. Before (top) and after (bottom).
- `<scene>-high.jpg` and `<scene>-ultra.jpg` for the saved round 12 cameras. Each is before (main) and after, side by
  side. The trees show in lake-towers (along the bottom) and lake-north-shore (far shore). The Galveston cameras have few
  near trees.

The real photos to compare against, real-03 and real-10 from the G5 blind pack, are only on the Mac.

## Cost (GPU frame, ms, 1080p, before / after in the same build)

| View | High | Ultra |
|---|---|---|
| slip | 6.17 / 6.43 (+0.26) | 8.85 / 9.10 (+0.25) |
| lake-towers | 5.03 / 5.34 (+0.31) | 8.33 / 8.65 (+0.32) |
| shore150 | 5.45 / 5.73 (+0.28) | 8.33 / 8.61 (+0.28) |

The cost is +0.25 to 0.32 ms, within the plan's 0.5 ms on High. Most of it is the base pass (the trees' materials); the
Lumen slice is unchanged within the noise.

## Tests

`SailingSim.Visual.TreeLooks` checks the following:
- The look is deterministic.
- The greens span their range.
- The leans are a few degrees.
- The evergreens never turn.
- The season curve, from July to April.
