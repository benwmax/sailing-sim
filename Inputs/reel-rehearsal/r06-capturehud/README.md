# R06 capture-mode test take on main 02eea166 (#838 merged), PC, Nov 26 2026

**Package:** new Development package `Packaged\Windows-02eea166`. MSVC build succeeded, 0 project warnings.

**Take:**
- `reel-saturday.ps1 -Package Windows-02eea166 -Only R06-helm-eye -Res 1080p`, the script at inputs 1f204911.
- The args: `-SailingCapture=HelmEye -SailingCaptureHud -SailingUiMode=helpful`, the lake, 12 kn, 13:00, demo at TWA 45,
  and `-SailingUIScript=Wait,L,Wait`.
- Result: 360 of 360 frames (6 s at 60). The stills are frames 53, 197 and 323, as webp.

**Result: as wanted.**
- **The HUD shows in the take,** helpful mode, as a player sees it:
  - time, wind and sky;
  - compass tape;
  - minimap;
  - wind dial;
  - speed with VMG and target;
  - depth;
  - telltales panel;
  - key hints.
- **No learning tip box** at any point.
- **The telltales panel's own status line stays.** That's part of the helpful HUD, not a learning tip: "Jib too tight"
  early, "Sailing well" once she settles.
- No crew (`-SailingShowCrew=0`), as for every reel take.

**Note for the Saturday script:** the capture takes write their frames to `<take>\rec\frame_NNNN.png`.

Bean's Saved was held aside and restored (7B5CA7BE).
