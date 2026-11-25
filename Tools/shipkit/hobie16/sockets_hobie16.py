"""The Hobie 16's game sockets (slice 8, docs/hobie16-9): every point the game's boat code reads from a boat's parts
(Source/SailingSim/Private/BoatModelVisuals.cpp), from the rebuild's own geometry, for the import in slice 10.

The game hangs a boat on four parts (ASailboatPawn::ModelMeshesFor): the hull with everything fixed to it, the mast
(stood on the hull's MastStep), the boom (on the physics' gooseneck) and a rudder (one mesh, turned about each
RudderPivot). From the sockets it draws the live rig: the forestay from ForestayTack to the mast's Hounds, a shroud a
side from ChainplateUpper_S/P to Hounds, a trapeze wire a crew member from Hounds, the jib sheets from the clew to
JibLead_S/P and on to JibWinch_S/P (the lazy one by LazySheetVia), the mainsheet from the boom's Boom_Mainsheet to the
traveller car between Traveler_C and Traveler_S. The fleet's Hobie 16 (Tools/blender/build_fleet.py) has the same
names, so the rebuild draws every line today's does.

Written into the build's hobie16_sockets.json beside slice 4's rig sockets: "sockets" (Unreal's frame, X forward,
Y to starboard, Z up, cm, the body frame: origin on the design waterline), "owner" (the part each lies on, by the
fleet's mesh names SM_Hobie16_*; slice 10's export renames them and moves each to its part's origin), "near" (the
build object a socket sits on and how close, which sockets_check_hobie16.py holds) and "from" (where each comes from).
"""
import numpy as np

import hardware_hobie16 as HWR
import platform_hobie16 as PL
import rig_hobie16 as RG
import rudder_hobie16 as RU
import sails_hobie16 as SL

Z = np.array([0.0, 0.0, 1.0])
HULL, MAST, BOOM, RUDDER = "SM_Hobie16_Hull", "SM_Hobie16_Mast", "SM_Hobie16_Boom", "SM_Hobie16_Rudder"

# what the game reads from her parts (BoatModelVisuals.cpp; the fleet's Hobie16 set): the build stops if one is missing
REQUIRED = {
    HULL: ["MastStep", "RudderPivot", "RudderPivot_1", "ForestayTack", "ChainplateUpper_S", "ChainplateUpper_P",
           "JibLead_S", "JibLead_P", "JibWinch_S", "JibWinch_P", "LazySheetVia", "Traveler_C", "Traveler_S"],
    MAST: ["Hounds", "MastheadAft"],
    BOOM: ["Boom_Mainsheet", "Boom_Clew"],
    RUDDER: [],
}


def ue(p):
    """Blender's frame (Y to port, metres) to the game's (Y to starboard, cm)."""
    return [round(100 * float(p[0]), 2), round(-100 * float(p[1]), 2), round(100 * float(p[2]), 2)]


def game_sockets(S, Sv, K):
    """The sockets from the solved rig S (rig_hobie16.solve), sails Sv (sails_hobie16) and the hardware's layout K
    (hardware_hobie16.build's, with the jib cars' blocks and cams). Returns {sockets, owner, near, from}."""
    out, owner, near, frm = {}, {}, {}, {}

    def put(name, p, part, obj, within, why):
        out[name], owner[name], near[name], frm[name] = ue(p), part, {"object": obj, "within_m": within}, why

    TR, JS = HWR.HW["traveller"], HWR.HW["jib_sheet"]
    # ---- the hull
    put("MastStep", S["heel"], HULL, "H16Platform_Frame", 0.01,
        "the mast's heel on the step's ball (rig_hobie16: the mast part's origin, about which it rotates)")
    put("ForestayTack", S["junction"], HULL, "H16Platform_Bridle", 0.03,
        "the bridle plate on the forestay's line, where the forestay and both bridle wires meet (rig_hobie16)")
    for side, tag in ((1, "P"), (-1, "S")):
        put(f"ChainplateUpper_{tag}", RG.chainplate(side), HULL, "H16Rig_Stays", 0.03,
            "the shroud's pin in its chainplate at the hull's deck edge (rig_hobie16.chainplate); she has no lowers "
            "and no spreaders, so there is no ChainplateLower or SpreaderTip (the game then draws one shroud a side)")
    R = RU.layout()
    for k, (side, hull) in enumerate(((1, "port"), (-1, "starboard"))):
        put("RudderPivot" if k == 0 else f"RudderPivot_{k}", (R["ax"], side * R["yr"], 0.0), HULL,
            "H16Rudder_P" if side == 1 else "H16Rudder_S", 0.06,
            f"the {hull} rudder's pintles' axis at the design waterline (rudder_hobie16.layout: the part's origin, "
            "about which the game turns it; the first is the port one, as on the fleet's model)")
    for side, tag in ((1, "P"), (-1, "S")):
        put(f"JibLead_{tag}", K["jib_lead"][side], HULL, "H16Hw_JibSheet", 0.02,
            "the jib car's ratchet block's sheave on the front crossbar's track, where the sheet comes down from the "
            "clew (hardware_hobie16: the 2:1's lower sheave)")
        put(f"JibWinch_{tag}", K["jib_cam"][side], HULL, "H16Hw_JibSheet", 0.02,
            "the fairlead of the cam over that block, where the tail leaves for the crew's hand: no winch, as the J/22's "
            "JibWinch is its cam's fairlead (the game wraps no drum on a boat without sheet winches)")
    h = S["heel"][2] + JS["lazy_on_mast_above_heel_m"]
    via = HWR.mast_aft(S, h)
    put("LazySheetVia", (via[0], 0.0, via[2]), HULL, "H16Mast", 0.02,
        "where the lazy sheet bears on the mast's aft face on its way from the clew to the other car "
        "(hardware_hobie16: lazy_on_mast_above_heel_m over the heel); the game slides it aft to the clew's station "
        "when the clew is aft of it, as hers is")
    car_top = K["eye"] + HWR.HW["mainsheet"]["eye_m"] * Z
    put("Traveler_C", (K["car"][0], 0.0, car_top[2]), HULL, "H16Hw_Mainsheet", 0.02,
        "the top of the eye on the traveller car's swivel post, the car centred: the mainsheet's lower block hangs "
        "from it (hardware_hobie16)")
    reach = TR["stop_y_m"] - 0.015 - TR["car"][1] / 2
    put("Traveler_S", (K["car"][0], -reach, car_top[2]), HULL, "H16Platform_Frame", 0.12,
        "the same eye with the car run out to starboard against its stop on the rear crossbar (stop_y_m less the "
        "stop's and the car's half widths): the end of the car's travel")
    put("Gooseneck", Sv["main"]["tack"], HULL, "H16Boom", 0.02,
        "the boom's pivot at the main's tack (sails_hobie16: the boom part's origin). The game hangs the boom on the "
        "physics' gooseneck (MainLuffX, BoomZ); slice 10's test holds the two together")
    strap = HWR.HW["hiking_straps"]
    for side, tag in ((1, "P"), (-1, "S")):
        x = (strap["front_x_m"] + (K["L"]["rx"] + PL.P["rear_crossbar"]["width_m"] / 2)) / 2
        y = side * (strap["front_y_m"] + strap["rear_y_m"]) / 2
        put(f"FootBrace_{tag}", (x, y, PL.tramp_top(K["L"], x, y) + strap["thick_m"] + 0.004), HULL, "H16Hw_Straps",
            0.03, "the middle of the hiking strap on that side, on its top: where a crew member sitting out hooks a "
            "foot (the game's crew read FootBrace_S/P where a model has it; not required, since the fleet's has none)")
    # ---- the mast
    L = RG.G["mast"]["length_m"]
    top = np.asarray(S["heel"], float) + L * RG.axis(S["rake"])
    put("Hounds", S["hounds"], MAST, "H16Mast", 0.05,
        "the hounds on the mast's axis inside its cast band (rig_hobie16), the point slice 4 solved the wires' "
        "pin-to-pin lengths to: the game draws the forestay, both shrouds and the trapeze wires to it, so their last "
        "few centimetres run inside the mast, past the built tangs, where they don't show")
    put("Masthead", top, MAST, "H16Mast", 0.03, "the mast's top on its axis (the check's mast length)")
    put("MastheadAft", HWR.mast_aft(S, top[2] - 0.03), MAST, "H16Mast", 0.03,
        "the masthead's aft face: she has no backstay, so the game draws nothing from it, but the fleet's set has it")
    put("MastBase", S["heel"], MAST, "H16Mast", 0.03,
        "the mast's heel (the check's mast length; no vang reads it: she has none)")
    # ---- the boom
    put("Boom_Mainsheet", K["up_c"], BOOM, "H16Hw_Mainsheet", 0.02,
        "the mainsheet's upper block's sheaves under the boom (hardware_hobie16: hung from its bail), where the "
        "game's mainsheet starts")
    put("Boom_Clew", K["mclew"], BOOM, "H16Sail_Main", 0.03, "the main's clew at the boom's end (sails_hobie16)")
    # ---- the rudder (the port one: the game turns the same mesh on each pivot)
    ub, ut = R["uc"]
    put("RudderStock", (R["ax"], R["yr"], ut), RUDDER, "H16Rudder_P", 0.03,
        "the rudder head's top on its pivot line (rudder_hobie16.layout)")
    put("RudderBolt", (R["ax"] - 0.02, R["yr"], ub + 0.01), RUDDER, "H16Rudder_P", 0.01,
        "the kick-up pin through the castings, about which the blade swings up (rudder_hobie16)")
    missing = [f"{part}: {n}" for part, names in REQUIRED.items() for n in names if owner.get(n) != part]
    if missing:
        raise SystemExit("sockets the game reads are missing:\n  " + "\n  ".join(missing))
    return {"sockets": out, "owner": owner, "near": near, "from": frm,
            "required": REQUIRED,
            "not_written": {"TillerEnd": "the game holds a tiller extension from the rudder's TillerEnd; hers hangs "
                                         "from the middle of the tiller crossbar, which joins both rudders and is "
                                         "built on the hull (H16Tiller_Crossbar, with the extension laid along it), "
                                         "as the fleet's model does: slice 10 decides how the game draws it",
                            "ChainplateLower_S/P, LowerTang, SpreaderTip_S/P": "no lowers and no spreaders",
                            "BackstayPlate": "no backstay", "Boom_Vang": "no vang"}}
