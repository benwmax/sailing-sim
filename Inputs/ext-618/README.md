# #618: the Sunfish's tiller extension, crew on and off

mac/618-ext-double at 448763f0, uncooked (scripts/run-game.sh), High, 10 kn at TWA 60, demo autopilot. The camera is low
over the windward quarter, aimed at the tiller (`-SailingCamTarget=-1.0,0,0.4 -SailingCamDist=1.9 -SailingCamPitch=-12`,
yaw 35 and 65 from the stern).

- Crew on (`-SailingShowCrew=1`): the helm holds the live extension; the tiller is bare (SM_Sunfish_TillerExt hidden).
- Crew off (`-SailingShowCrew=0`): the extension lies stowed along the tiller's top (SM_Sunfish_TillerExt shown); the
  live line collapses into the tiller's end.

One extension in each, never two.
