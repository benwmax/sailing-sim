# Phase 8: reference realism pass

Method: `reference-kit/method.md`. What each step produced:

| Step | Output |
| --- | --- |
| 1. Grade the library | `reference-log.csv`: 190 clips graded A 29 / B 91 / C 70, with venue, wind, sea, sun, camera and what is measurable |
| 2. Capture mode | `-SailingCapture=HelmEye\|ActionCam\|Chase\|Drone\|ShoreTele` (see the README); `reference-scenes.csv` lists the 12 reference scenes, `scripts/capture-scenes.sh` reproduces them into `captures/` (still, `.camera.json`, `.telemetry.csv`) |
| 3. Compare | `compare/index.html` (built by `scripts/make_compare_page.py`): each clip plays from its timestamp through YouTube's privacy-enhanced embed beside the game frame, with 1-5 scores from `compare/scores.csv`. Open it locally. Physics: `scripts/reference-checks.sh`, before `reference-checks-before.txt` (6 of 39 out), after `reference-checks-after.txt` (3 of 46 out, all listed as open) |
| 4. Fix list | `fix-list.md`, ranked by Severity x Visibility x Teaching / Cost, with status. Golden screenshots in `golden/` |
| 5. Blind test | `blind-test/stills/still01..20.jpg` (10 Wikimedia Commons photos, 10 game frames from `blind-test/scenes.csv`), built by `Tools/blindtest/make_blind_pack.py`. Credits in `blind-test/credits.md`; `blind-test/answer-key.csv` holds the answers (don't open before marking). Online marking page: https://claude.ai/artifact/EiTmEiEk4MugbJ9pAQWo3P |
| 6. Bean's own data | Waiting on lessons: phone logger, roll-decay at the dock, tiller video, shot list, scans, sound clips |

No YouTube frames are stored in the repo; the comparison page streams the clips.

## Golden screenshots

| File | Guards |
| --- | --- |
| `whitecaps-06/09/14/22kn.png` (and `whitecaps-14kn-before.png`) | Beaufort whitecap coverage from 7 kn |
| `water-drone-olive.png` | Ray Hubbard's turbid olive water from a drone; the faint wake |
| `storm-grey.png` | Ground light falling and greying under a storm deck |
| `helm-eye.png` | The helm-eye camera on the windward deck, crew beside it hidden |
| `wake-short.png` | A dinghy's foam trail fading within a few lengths |
| `chase-12kn.png` | Scattered whitecaps at 12 kn; the chase camera framing the rig |
