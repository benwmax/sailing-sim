# Graphics, UI and levels: G1 to G5

The second plan after the Visual phases (V1-V7, `visual-summary.md`). Each phase has its own branch and README.

| Phase | Branch | What it did |
|---|---|---|
| G1 the sky | `graphics-1-sky` | Our own baked cloud noise (no repeats), the cloud grain traced to aliasing and fixed, Nubis-style cumulus, a 1024² weather map, the Ultra tier for the RTX 4090 PC. `graphics-1/README.md` |
| G2 the shore | `graphics-2-shore` | The USGS 3DEP 1 m lidar baked into 64 m shore tiles around Ray Hubbard: the physics and the placement of trees, houses and riprap follow it, meshed at 1 m within 300 m. |
| G3 boats and crew | `graphics-3-boats` | Liveries and wear from a catalogue of real schemes, per-boat sail numbers, published fleet dimensions, MetaHumans at High with hair, scripted polos, shoes, life jackets and caps over CC0 fabric scans. `graphics-3/README.md` |
| G4 front end and HUD | `graphics-4-ui` | The front end (world, launch spot, boat, conditions, mode), level select by session, a loading screen with real readiness stages, pause, five-tab settings, rebinding, and a new Slate HUD. `graphics-4/README.md` |
| G5 the blind test | `graphics-5-blind` | 15 Commons photos against 15 matched frames, my read of every pair, then fixes: the haze lit by the metered light, exposure into a low sun, the sun's disc through the haze, fibrous cirrus. `graphics-5/README.md` |

## Where it stands

- **Gates:** packaged on the M5 Pro, Medium holds 60 fps and High 45 on every bench view. The tightest is helm-eye on
  High at 45.0-45.1, about where it has been since G3.
- **Tests:** 92 automation tests pass, including `SailingSim.UI.SessionFlow`.
- **Blind tests:**
  - [Real or Game: The Whole Game](https://claude.ai/artifact/3vCD1d83vfZx21tXNuGZzY), 30 stills.
  - Round 7 (`graphics-5/game/`).
  - The G3 boats round and the G1 skies pack.
- **What still gives the game away** (graphics-5/README.md, Open):
  - the cumulus: frosted edges and marbled overhead decks;
  - the shelf cloud's form;
  - the ship and shore building models;
  - the Gulf's colour under overcast.
- **Not checked yet:** the Windows build on the 4090 (Ultra and strand hair).

## Pull requests

One per phase against `main`, opened one at a time as the previous one merges. When this was written, #15 (V5) was open,
with V6, V7 and G1-G5 queued behind it.
