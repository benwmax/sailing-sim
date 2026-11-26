# Reel fix frames (1080p probes, Nov 25-26 2026)

| Frame | Fix |
|---|---|
| `R12-sunfish-fixed.webp` | **Approved.** The mount moved forward of the mast, 0.4 m to windward of the centreline, looking aft and up: `"pos":[1.9,0.4,0.7]`, `"look":[14,200,0]`, fov 80. It's now in `shots/s12-sunfish-bow.json`. The take still starts at 10 s, so the tack at 14.2 s is in it. |
| `R06-helm-eye-before-nohud.webp` | Before: film and capture takes hide the HUD (`SailHud.cpp`, `IsCaptureMode`). |
| `R06-helm-eye-capturehud-pr838.webp` | With #838's `-SailingCaptureHud -SailingUiMode=helpful`: the Helpful HUD, but the learning-tip box shows. |
| `R06-helm-eye-capturehud-notips.webp` | **The R06 to use.** The same, plus `-SailingUIScript=Wait,L,Wait`. L is ToggleLearning, sent as a Slate key event inside the game; the log reads "UI script: L -> SViewport (handled)". The tip box is gone; the rest of the Helpful HUD stays. A throwaway profile with `learningMode false` didn't do it: measuring runs don't read that setting. |
| `R10-gust-h10-b0.webp`, `R10-gust-h10-b0-7frames.webp` | **R10:** a tripod at 45 m out and 10 m up, hfov 35, bearing 0, with `-SailingGust=0.9` and a 10 s warm-up. The 7 s take covers the 12-18 s gust: true wind about 17 -> 21 kn, heel -5 -> -26 deg, 3.1 -> 4.9 kn. The boat is about a third of the frame and there's only water behind her, so the far-shore trees are out of frame. |

## The R06 learning tip against the telltale panel (for the sim thread)

**At the frame** (about 10 s into the take, 12 kn breeze from the south, TWA 37-42, the demo close-hauled):
- AWA swings 21 -> 37 -> 21 deg and AWS 12.6 -> 21 kn within half a second, in gusts.
- The mainsheet is 0.129-0.133 and the jib sheet 0.159-0.163, both easing slowly.
- Heel is 6.4-7.1 deg and speed 5.0-5.2 kn.

**What disagreed:**
- The tip card said "Trim: the leech telltales are curling behind the main: it is over-trimmed. Ease the mainsheet (S)".
- The telltale panel's line said "Sailing well: inside yarns just lifting". That line is about the **jib**; the panel's
  MAIN box showed red leech yarns at the same moment.
- So the two may not contradict each other. The main tip is judged at one moment and held on screen for seconds, while
  the panel's summary line talks about the jib.
- Worth checking whether the tip should clear, or the panel should mention the main, when the main's leech yarns stall.

## Not changed

- **The R06 sky:** the cloud deck looks lumpy close up. `-SailingSeed` 7, 3 and 11 give the identical deck, so the seed
  doesn't drive the clouds. Hours 13 and 16.5 are being shot now; if neither is softer, R06 stays at hour 15.
- **R10's gust patch:** from 10 m the water shows whitecap flecks and darker breeze, but no distinct dark gust line
  coming in. With these args no visible gust line paints; a front (`-SailingWeather=Thunderstorm`) would be the way to
  paint one.
