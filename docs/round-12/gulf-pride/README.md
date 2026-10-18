# The Gulf Pride gets a tanker hull (round 12 follow-up)

The traffic's first ship is the "Tanker Gulf Pride", but she was drawn with the container ship's model
(`SM_Vessel_Container`, stacks and all). She now has her own model, `SM_Vessel_Tanker`, built by
`Tools/blender/build_vessels.py` (`tanker()`) from the same hull generator as the other vessels:

- a 228 m hull laden in the channel (6 m of freeboard), black topsides over the red bottom paint, bulbous bow;
- the flush main deck with seven cargo and vapour pipes on saddles and the raised catwalk from the house to the
  forecastle;
- ullage domes and hatches over twelve pairs of tanks, eight vent risers with their pressure/vacuum heads;
- the midships manifold with its crossover pipes, valves, drip trays and a hose crane each side;
- the forecastle with its breakwater, foremast, windlasses, bollards and anchors;
- a five-tier house aft with the bridge wings, radar mast, funnel and the freefall lifeboat.

`APowerVesselActor::Build(Kind, bTanker)` draws a ship named "Tanker..." with it (the container ship, the Bayport
Star, keeps hers), with her lights moved to the model: masthead lights on the foremast (26 m) and higher on the radar
mast (33 m, Rule 23(a)), sidelights on the bridge wings, the sternlight, three reds and the cylinder (Rule 28). Low and
a missing model keep the box shapes. No downloaded assets: the model is generated, and `Content/World/*` already has
its licence row.

## Still (packaged, High, Windows; left main, right this branch; below, the ship cropped)

`gp-abeam-high.jpg`, camera in `scenes.csv` (`-SailingTraffic=1` puts only the tanker in the channel,
`-SailingNearShip=350` starts the boat 350 m off her). The boat's sail hides her house from this camera.
