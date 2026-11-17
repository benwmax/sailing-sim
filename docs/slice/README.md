# The vertical slice: date and gate order

Tracking issue: #399. On Nov 16 2026 Bean moved the slice from Fri Nov 20 to the end of November, so the recent work
lands in it: "we've added a lot of new things lately and made some good improvements and i want them all in the game".
The same evening he added the frigate "Commonwealth" at full quality, with the date moving to fit: "i want to have the
frigate in this slice, so adjust the release date to make that happen, do not sacfrifice frigate quality." Her schedule
is on her plan (Claude artifact 8y6hW8vHjjUPJRovJEuxY7).

| Date (2026, Central time) | What happens |
| --- | --- |
| Fri Nov 20 | Tester build from main as it stands (`scripts/windows/friday.ps1`) |
| **Fri Nov 27, end of day** | **Feature freeze for everything except the frigate** (shore tracks, Catalina 22, J-Class, cameras, UI) |
| Fri Nov 27 | Tester build: the slice without the frigate |
| Nov 25 to Dec 8 | The frigate's Mac and PC work (physics, game wiring, cannon fire, gate views, fix loop) |
| Fri Dec 4 | Tester build with the frigate as far as she is |
| **Tue Dec 8, end of day** | **Frigate freeze**: her last pull request merges |
| Wed Dec 9 to Thu Dec 10 | Fixes only. Full `gate.sh --scope all`, the scripted playthrough, a 2-hour soak, the PC's Ultra bench. Release candidate Thu Dec 10 |
| **Fri Dec 11** | **The slice**: `friday.ps1` on the release candidate. Fallback Fri Dec 18 if her gates show the rigging or sails need rework |

The slice's "done means" list in #399 is unchanged, except that the save check is a Nov 27 save loading in the
Dec 11 build.

## Gate order

The Mac takes one gate at a time and starts nothing from 07:30 to 11:00 UTC (the nightly). Every game-code pull
request also needs the PC's MSVC build and tests; anything outside `Source/` and `docs/` needs Bean's `bean-approved`
label after its last push. A pull request ready earlier than its slot goes earlier.

| Order | Work | Mac | PC |
| --- | --- | --- | --- |
| 1 | J-Class "Bluebonnet" slice 13, Mac half: `EBoatType`, reference polar, tuning (`docs/jclass-13/`) | polar and physics tests | MSVC |
| 2 | Shore foundation in the game: Track A ground textures and Track C edge types | content rebuild, `--scope world` | MSVC, Ultra stills |
| 3 | Catalina 22 rebuild in the game (the slice's third boat) | import, `--scope boats` | MSVC, Ultra stills |
| 4 | J-Class slice 14 in the game | import, `--scope boats` | MSVC, Ultra stills |
| 5 | Shore Track D trees and Track B grass in the game | bake, `--scope world` | MSVC, Ultra bench |
| 6 | Shore Track E building kit and Tracks F and H docks and yard props (Track I placement) | bake, `--scope world` | MSVC, Ultra stills |
| 7 | Camera views slice 3, UI leftovers (transom name and the rest of the brand list) | `--scope ui` | MSVC |
| 8 | Fixes from the Nov 20 and Nov 27 tester builds | as needed | as needed |
| 9 | The frigate, Nov 25 to Dec 8: square-rig physics and polar (Mac ~1 day), game wiring (Mac ~1 day), cannon fire (Mac ~2 days), six gate views, a full sweep and the cost fix loop (Mac ~3 days) | ~7 days | import and materials, below-decks light, 4K Ultra bench, cannon effects (~7 days) |

Frame rate is the main risk: grass, trees and the building kit all land in the same view. Medium 60 and High 45 on the
Mac hold for every gate. Items 1 to 8 finish by Nov 27 so the Mac and PC are the frigate's from Nov 30; a track that breaks a floor goes in with its far band trimmed, or waits.

## Not in this slice

- Shore Track G, the clubhouse: it waits on Bean's photos.
- The close-up rock round (Bean's grey-card photos) and the boat shape loop (the rudder rake photo), unless the photos
  arrive by Nov 27.
- Still out as in #399: the prologue, new places, the physics gap list, replay, online.
