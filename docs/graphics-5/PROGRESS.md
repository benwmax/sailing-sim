# Graphics G5: the whole-game blind test (working notes)

Bean asked (2026-10-14, 02:48 UTC) for the work to keep going overnight without stalling. This file is the plan and
the place to resume from. Branch `graphics-5-blind` (from `graphics-4-ui`). No PRs until #15 merges; no purchases.

## Steps

- [ ] 1. Scene list: 12 kinds of view that span G1-G4 (lake sailing, marina, close-hauled chase, shelf cloud, fair
      cumulus, Galveston ship, Hobie, dusk, I-30 bridge, crew close up, Gulf swell, lakeshore houses); `scenes.csv`.
- [ ] 2. Commons photos for each (CC0 / CC BY / CC BY-SA only), downloaded with credits (`Tools/blindtest/fetch_commons.py`).
- [ ] 3. Game stills matched to each photo (capture mode, High), `docs/graphics-5/blind/game/`.
- [ ] 4. The pack (`Tools/blindtest/make_blind_pack.py`), 24 stills, answer key.
- [ ] 5. Publish "Real or Game: The Whole Game" (db answers), link in README.
- [ ] 6. My own read, pair by pair: what gives each game frame away; the fix list.
- [ ] 7. Fix the cheapest high-impact tells from step 6 (one commit each, tests and bench after).
- [ ] 8. Recapture the affected stills, before/after page, bench, README; G1-G5 summary (`docs/graphics-summary.md`).
