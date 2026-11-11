# Bow wave at the J/22's stem: before and after

mac/bowwave-stem e54dbfd0. Uncooked (scripts/run-game.sh), High, 16 kn at TWA 45, demo autopilot. Camera on the bow:
`-SailingCamTarget=2.4,0,0 -SailingCamDist=3.8 -SailingCamYaw=100 -SailingCamPitch=-6`.

- `bowwave_main_before` / `_after`: main 7c78a9be without and with the fix.
- `bowwave_s615_before` / `_after`: #615's class hull (7fd1b239, merged locally with the fix for the after shot).
- `bowwave_strip.jpg`: the waterline crops, top to bottom in that order.

Before, a flat white blob or a long white streak stands off the stem. After, the sheet hugs the hull at the waterline, and
the crest starts a little aft of the stem as a broken lip. The chop's phase differs between runs, so compare the stem.
