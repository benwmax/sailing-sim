# Fleet sweep: the first minute on every boat

The J/22's first-minute check, repeated for the Sunfish, ILCA 7, Catalina 22, Catalina 30, Hobie 16, Corsair 880,
Lagoon 42 and the maxi. All on High, lake, AfternoonBreeze, 12 kn (dinghies 10). Each sheet
(`sheet-<boat>.jpg`) has, top row then bottom row:
- chase on a beat, a reach and a run;
- helm eye on a beat, a reach and a run;
- cockpit view on a beat, a reach and a run;
- a tack (chase, the autopilot tacking);
- the boat at her berth or launch, in chase and from the cockpit.

## Fixed here

**Catalina 30: a leg raised onto the cabin top across the helm's view.** Her crew spread along the cockpit from its
forward end less 0.3 m. On the rail, legs inboard, the forward hand's feet came up against the cabin face, as the
J/22's did (`docs/crew-leg/`). Her row now starts 0.55 m aft of the well's end:
- the four rail crew sit at -1.87 to -3.22;
- the helm stays at -4.15, still 0.93 m clear.

See `catalina30-helm-beat-*`, `catalina30-cockpit-reach-*`. The Catalina 22 at 0.3 is fine and unchanged.

## Passed on (model, for the PC)

**Lagoon 42: the helm sees only the wheel and a white wall.** The helm-eye and cockpit views on every point of sail are
filled by the wheel, half a metre ahead, and the saloon's aft bulkhead. In `build_fleet.py`'s `lagoon_detail` the wheel
is on that bulkhead, its centre 1 m above the bridgedeck, and the seat cushion 0.45 m up behind it. The bulkhead is
opaque white, with the saloon's glazing on the sides only. On the real boat the helm looks forward through the saloon's
aft and front windows.

## Checked, fine

- **Rocking at rest** (berth telemetry after 4 s, heel range):
  - Catalinas, Corsair, Lagoon: under 1.4 deg;
  - Sunfish, ILCA, Hobie: 2.5-4.5 deg, irregular, crew centred: their sails stay up at the dock and flog in the gusts.
- **The maxi:** she has no berth on the lake (the prologue boat); the drill starts her sailing.
- **Crew:**
  - the Corsair's crew sit knees-up on the net (the flat-deck pose, `docs/crew-hull-clip/`);
  - the Hobie's crew sits close ahead of the helm on the same hull, so the cockpit view shows a back, as on the real boat;
  - the dinghy sailors hike and sit as before.
- **Sails, rigging and sheets:** nothing through the deck or the sails on any boat in these frames.
