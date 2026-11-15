# Bow-wave curl on Windows (Development package with #704's cook fix)

**Package:** `Packaged\Windows-7bacf98e-704` (#704 on 6f44708f; the same cook fix as main 75ed143f). M_BowWave is cooked
and loads, with no SkipPackage.

**Run:** Gulf, offshore launch 2, Afternoon breeze, 15 kn, TWA 90 held by the autopilot (`-SailingDemo` with
`-SailingHoldTWA=90`), Ultra, 3840x2160, no HUD. 75 s, with the still at the end. The same run with
`-SailingNoBowWave` gives the compare. Bean's Saved was held aside and restored (F6458EAB).

**Speed at the still** (bench JSON `final_kn`): **6.4 kn** at TWA 86, heel up to 17.5 deg, in all four runs.

**The curl draws.** In `bowwave-bow.png` against `bowwave-bow-nobowwave.png` (low camera abeam of the bow: yaw 70,
pitch -2, 6 m, target 2.8 m forward), and at 1:1 in `crop-bow-curl.png` against `crop-bow-nocurl.png`:
- **With the bow wave:** a translucent, glassy sheet of water climbs the stem and runs aft along the topsides, well above
  the waterline.
- **With `-SailingNoBowWave`:** the sheet is gone and the water meets the hull at the plain waterline.
- **It is subtle in these frames.** That side of the hull is in the sails' shadow and the sheet is clear water, not foam.
  A sunlit side, or 20+ kn, would show it better.

`bowwave-reach*.png` uses the suggested camera (yaw 60, pitch -5, 8 m). It looks down from aft with the bow in shadow,
so the curl does not read there.

**Two earlier tries were not usable:**
- **Without `-SailingDemo`:** nothing steered, and she luffed head to wind at 1.7 kn.
- **On the lake:** after 75 s on the reach she was aground on the shore.
