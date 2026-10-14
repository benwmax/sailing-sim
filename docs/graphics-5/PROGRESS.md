# Graphics G5: the whole-game blind test (working notes)

Bean asked (2026-10-14, 02:48 UTC) for the work to keep going overnight without stalling. This file is the plan and
the place to resume from. Branch `graphics-5-blind` (from `graphics-4-ui`). No PRs until #15 merges; no purchases.

## Steps

- [x] 1. Scene list: 12 kinds of view that span G1-G4 (lake sailing, marina, close-hauled chase, shelf cloud, fair
      cumulus, Galveston ship, Hobie, dusk, I-30 bridge, crew close up, Gulf swell, lakeshore houses); `scenes.csv`.
- [x] 2. Commons photos for each (CC0 / CC BY / CC BY-SA only), downloaded with credits (`Tools/blindtest/fetch_commons.py`).
- [x] 3. Game stills matched to each photo (capture mode, High), `docs/graphics-5/blind/game/`.
- [x] 4. The pack (`Tools/blindtest/make_blind_pack.py`), 24 stills, answer key.
- [x] 5. Publish "Real or Game: The Whole Game" (db answers), link in README.
- [x] 6. My own read, pair by pair: what gives each game frame away; the fix list.
- [ ] 7. Fix the cheapest high-impact tells from step 6 (one commit each, tests and bench after).
- [ ] 8. Recapture the affected stills, before/after page, bench, README; G1-G5 summary (`docs/graphics-summary.md`).

## Log

- Steps 1-5 (03:45 UTC): 15 Commons photos (5 from Lake Tawakoni, Texas), 15 matched captures, pack of 30 (seed 55),
  page https://claude.ai/artifact/3vCD1d83vfZx21tXNuGZzY (answers save to its db). Fixed on the way: `-SailingNoHud` stills
  no longer show the canvas hint line ("H: show instruments..."), which gave away a marina frame.
- Step 6 and fixes 1-3 (05:00 UTC): haze lit by the metered light, exposure into a low sun, fog max opacity 0.9,
  fibrous cirrus (commits 1cee19e, 37bf61a). Read and fix list in README.md.
- GPU turns: session "sailing-sim-d7" (round 7 of the blind test, docs/graphics-5/game/) shares this checkout and holds
  the GPU until it sends "GPU free". Stage explicit paths only.
- Next (step 7-8, after "GPU free"): rebuild, recapture all 15 (scenes.csv), rebuild the pack (seed 55) and republish
  the page with the fixed frames? No: the published pack is the "before" test; publish an "after" compare page instead
  (before/after per scene), bench-visual High/Medium against G4, tests.
