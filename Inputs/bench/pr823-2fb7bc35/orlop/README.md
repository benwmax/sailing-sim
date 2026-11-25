# #823 at 2fb7bc35: orlop runs (4K Ultra), Nov 25 2026

Package `Windows-pr823-2fb7bc35`: `-SailingBoat=Comm -SailingWorld=Gulf -SailingLaunch=2 -SailingWind=12`, 3840x2160 at
100%, 20 s benches.

| Run | `-SailingWalkAt` | fps | p99 ms | max ms | GPU ms (base / Lumen) | Where she stood |
|---|---|---|---|---|---|---|
| orlop-m4-0 | Orlop,-4,0,0 | 42.8 | 28.16 | 30.5 | 22.89 (9.39 / 2.25) | **Not on the orlop**: "nowhere to stand there", so she stayed at the helm on the upper deck |
| orlop-m12-180 | Orlop,-12,0,180 | **42.5** | 28.09 | **146.3** | 22.94 (9.76 / 2.86) | Orlop, facing aft: a panelled space with chairs, a table and one lantern |
| orlop-ladder-m8 | Orlop,-8,1,0 | **40.1** | 30.31 | 31.6 | 24.49 (10.53 / 3.36) | "Walking on Orlop at (-8, 1)" |

**Log:** both runs that reached the orlop log the expected line, plus the berth line:
- "Ship decks Orlop: 0 copies, 2 lanterns (unshadowed)"
- "Ship decks Berth: 406 copies, 12 lanterns (unshadowed)"

The Gun line again appears only at frame 2, on the upper deck before the walk.

**orlop-m12-180:**
- Beams and planking overhead.
- Lit by the orlop's own lantern, with no berth-lantern light coming down.
- One frame hit 146 ms. It's a single spike; the p99 is 28 ms.

**orlop-ladder-m8:**
- The view shows hammocks hung just above eye height, with long mess tables and benches. It reads more like the berth
  deck seen through an open hatch than the orlop.
- Worth a look on the Mac to confirm whether -8,1 is under an open hatch.

**4K fps on the decks (2fb7bc35):**

| Deck | fps |
|---|---|
| berth | 42.1 / 43.0 |
| gun | 46.1 |
| orlop | 42.5 / 40.1 |

There was no DXGI hang or GPU crash in any run. Bean's Saved was held aside and restored (7B5CA7BE).

## Orlop,-8,1,180 (facing aft, away from the ladderway)

- **41.8 fps** at 4K, p99 27.8 ms, max 29.4 ms, GPU 23.47 ms (base 9.67, Lumen 2.92).
- **Log:** "-SailingWalkAt: walking on Orlop at (-8.00, 1.00) facing 180", then "Ship decks Orlop: 0 copies, 2 lanterns
  (unshadowed)" and the Berth line. There was **no "nowhere to stand" warning**.
- **Feet Z isn't logged.** The game writes no height for the walker, so I can't confirm the -1.95 m from the log.
- **In view, he's on the orlop:**
  - No hammocks or mess benches.
  - A low panelled bulkhead with a doorway, and a pillar on its step on the right.
  - A grating on the floor beyond the door, and a low-beamed space aft with chairs, a table and the orlop lantern.
  - So the earlier ladder-foot still facing forward was looking up the ladderway into the berth deck.
- **Flag:** the floor planking shows a strong zigzag moiré across the lower third of the frame (`orlop-ladder-m8-aft.png`).
  It also shows faintly in the -12,0,180 still. It's a texture or mip problem on the orlop deck's planks at 4K.
