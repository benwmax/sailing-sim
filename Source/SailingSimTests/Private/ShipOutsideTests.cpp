// A ship's outside model table (docs/frigate-import/, ShipOutside.h): the export's meshes read into parts with their
// states, the rig groups the running rigging follows, and the frigate's own table where the import has landed.
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "ShipOutside.h"

namespace ShipOutsideTestsLocal
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	const TCHAR* Sample = TEXT("") R"json({
	"root": "/Game/Boats/Frigate",
	"meshes": {
		"SM_Frigate_Skin": {"triangles": 267740, "slots": ["MI_Frigate_HullBlack"], "file": "Outside/SM_Frigate_Skin.fbx", "group": "Outside",
			"asset": "/Game/Boats/Frigate/Outside/SM_Frigate_Skin", "light": {"file": "Outside/SM_Frigate_Skin_Light.fbx", "triangles": 108000},
			"part": "Skin", "states": ["action", "anchored", "clewed", "underway"], "frame": "ship"},
		"SM_Frigate_Running_Fore_Set": {"triangles": 9000, "slots": ["MI_Frigate_Hemp"], "file": "Outside/SM_Frigate_Running_Fore_Set.fbx",
			"group": "Outside", "asset": "/Game/Boats/Frigate/Outside/SM_Frigate_Running_Fore_Set", "light": {"file": "x", "triangles": 1},
			"part": "Running_Fore_Set", "states": ["action", "underway"], "frame": "ship"},
		"SM_Frigate_LidLanyards_Open": {"triangles": 900, "slots": ["MI_Frigate_Hemp"], "file": "Outside/SM_Frigate_LidLanyards_Open.fbx",
			"group": "Outside", "asset": "/Game/Boats/Frigate/Outside/SM_Frigate_LidLanyards_Open", "part": "LidLanyards_Open", "states": ["action"], "frame": "ship"},
		"SM_Frigate_Wheel": {"triangles": 4488, "slots": ["MI_Frigate_Oak"], "file": "Outside/SM_Frigate_Wheel.fbx", "group": "Outside",
			"asset": "/Game/Boats/Frigate/Outside/SM_Frigate_Wheel", "part": "Wheel", "states": null, "frame": "its own (deck.json frames)"},
		"SM_Frigate_GunDeck": {"triangles": 405685, "slots": ["MI_Frigate_GunDeckPlanks"], "file": "Decks/SM_Frigate_GunDeck.fbx", "group": "Decks",
			"asset": "/Game/Boats/Frigate/Decks/SM_Frigate_GunDeck", "part": "GunDeck", "states": null, "frame": "ship", "deck": "GunDeck"},
		"SM_Frigate_Gun24_Barrel": {"triangles": 3000, "slots": ["MI_Frigate_Iron"], "file": "Guns/SM_Frigate_Gun24_Barrel.fbx", "group": "Guns",
			"asset": "/Game/Boats/Frigate/Guns/SM_Frigate_Gun24_Barrel", "part": "Gun24_Barrel", "states": null, "frame": "own (guns.json meshes)"},
		"SM_Frigate_BerthHammock": {"triangles": 2632, "slots": ["MI_Frigate_Canvas"], "file": "Decks/SM_Frigate_BerthHammock.fbx", "group": "Decks",
			"asset": "/Game/Boats/Frigate/Decks/SM_Frigate_BerthHammock", "part": "BerthHammock", "states": null, "frame": "ship"}
	},
	"placed": {
		"Wheel": {"mesh": "SM_Frigate_Wheel", "location_cm": [-2225.0, 0.0, 549.57], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1], "collection": null, "owner": "ship"},
		"Hammock_01": {"mesh": "SM_Frigate_BerthHammock", "location_cm": [-1200.0, 300.0, 250.0], "rotation_xyzw": [0, 0, 0.7071068, 0.7071068], "scale": [1, 1, 1],
			"collection": "BerthDeck_Hammocks", "owner": "ship"},
		"Hammock_02": {"mesh": "SM_Frigate_BerthHammock", "location_cm": [-1100.0, 300.0, 250.0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1],
			"collection": "BerthDeck_Hammocks", "owner": "ship"},
		"Gun_01_Barrel": {"mesh": "SM_Frigate_Gun24_Barrel", "location_cm": [100.0, 300.0, 400.0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1],
			"collection": "Guns_RunOut", "owner": "battery"}
	},
	"lights": [
		{"name": "Lantern_01_02_S", "zone": "gun_deck", "colour_rgb": [1.0, 0.62, 0.3], "kelvin": 2200, "lumens": 180.0, "cast_shadows": false,
			"deck": "GunDeck", "location_cm": [-1959.67, 338.1, 375.58], "radius_cm": 307.2},
		{"name": "Lantern_LightRoomAft", "colour_rgb": [1.0, 0.62, 0.3], "cast_shadows": true, "deck": "Orlop", "zone": "orlop",
			"location_cm": [-2042.1, 0.0, -51.0], "radius_cm": 0.0}
	]
})json";
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOutsideTableTest, "SailingSim.ShipOutside.Table", ShipOutsideTestsLocal::TestFlags)
bool FShipOutsideTableTest::RunTest(const FString& Parameters)
{
	using namespace ShipOutside;
	TArray<FPart> Parts;
	FString Error;
	TestTrue(TEXT("the sample parses"), ParseTable(ShipOutsideTestsLocal::Sample, Parts, &Error));
	TestEqual(TEXT("three outside parts in the ship's frame (not the wheel on its pivot, the deck below or a gun)"), Parts.Num(), 3);
	if (Parts.Num() != 3) return false;
	// Sorted by name: LidLanyards_Open, Running_Fore_Set, Skin.
	TestEqual(TEXT("the lanyards"), Parts[0].Name, FString(TEXT("LidLanyards_Open")));
	TestEqual(TEXT("shown in action only"), int32(Parts[0].States), int32(Action));
	TestTrue(TEXT("no twin: no light asset"), Parts[0].LightAsset.IsEmpty());
	TestEqual(TEXT("the fore's running rigging set"), Parts[1].Name, FString(TEXT("Running_Fore_Set")));
	TestEqual(TEXT("shown underway and in action"), int32(Parts[1].States), int32(Underway | Action));
	TestEqual(TEXT("the skin"), Parts[2].Name, FString(TEXT("Skin")));
	TestEqual(TEXT("in every state"), int32(Parts[2].States), int32(AllStates));
	TestEqual(TEXT("its object path"), Parts[2].Asset, FString(TEXT("/Game/Boats/Frigate/Outside/SM_Frigate_Skin.SM_Frigate_Skin")));
	TestEqual(TEXT("its twin's object path"), Parts[2].LightAsset, FString(TEXT("/Game/Boats/Frigate/Outside/SM_Frigate_Skin_Light.SM_Frigate_Skin_Light")));
	TestEqual(TEXT("its triangles"), Parts[2].Triangles, 267740);

	TestFalse(TEXT("not json"), ParseTable(TEXT("{ not json"), Parts, &Error));
	TestFalse(TEXT("no meshes"), ParseTable(TEXT("{\"root\": \"/Game/Boats/Frigate\"}"), Parts, &Error));
	TestEqual(TEXT("the reason"), Error, FString(TEXT("no meshes")));

	TestEqual(TEXT("state bits"), int32(StateBit(TEXT("underway")) | StateBit(TEXT("action")) | StateBit(TEXT("clewed")) | StateBit(TEXT("anchored"))), int32(AllStates));
	TestEqual(TEXT("an unknown state"), int32(StateBit(TEXT("sinking"))), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOutsideDecksTest, "SailingSim.ShipOutside.Decks", ShipOutsideTestsLocal::TestFlags)
bool FShipOutsideDecksTest::RunTest(const FString& Parameters)
{
	using namespace ShipOutside;
	FDeckTable Table;
	FString Error;
	TestTrue(TEXT("the sample parses"), ParseDecks(ShipOutsideTestsLocal::Sample, Table, &Error));
	// The two hammocks on the berth deck: not the wheel (no deck's collection), not the battery's gun.
	TestEqual(TEXT("two placed copies"), Table.Copies.Num(), 2);
	if (Table.Copies.Num() == 2)
	{
		TestEqual(TEXT("the hammock"), Table.Copies[0].Part, FString(TEXT("BerthHammock")));
		TestEqual(TEXT("on the berth deck"), Table.Copies[0].Deck, FString(TEXT("Berth")));
		TestEqual(TEXT("its object path"), Table.Copies[0].Asset, FString(TEXT("/Game/Boats/Frigate/Decks/SM_Frigate_BerthHammock.SM_Frigate_BerthHammock")));
		TestTrue(TEXT("where it hangs"), Table.Copies[0].Transform.GetLocation().Equals(FVector(-1200.0, 300.0, 250.0), 1e-3));
		// A quarter turn about Z: the copy's X points to starboard (+Y), as the export's frame and the game's agree.
		const FVector X = Table.Copies[0].Transform.GetRotation().RotateVector(FVector::ForwardVector);
		TestTrue(TEXT("its quarter turn is to starboard"), X.Equals(FVector::RightVector, 1e-3));
	}
	TestEqual(TEXT("two lanterns"), Table.Lanterns.Num(), 2);
	if (Table.Lanterns.Num() == 2)
	{
		TestEqual(TEXT("on the gun deck"), Table.Lanterns[0].Deck, FString(TEXT("Gun")));
		TestEqual(TEXT("its lumens"), Table.Lanterns[0].Lumens, 180.f);
		TestEqual(TEXT("its reach"), Table.Lanterns[0].RadiusCm, 307.2f);
		TestFalse(TEXT("no shadows"), Table.Lanterns[0].bCastShadows);
		TestEqual(TEXT("the light room's, on the orlop"), Table.Lanterns[1].Deck, FString(TEXT("Orlop")));
		TestEqual(TEXT("no reach given: 0, the deck lamps' default"), Table.Lanterns[1].RadiusCm, 0.f);
		TestTrue(TEXT("shadowed"), Table.Lanterns[1].bCastShadows);
	}
	TestEqual(TEXT("the berth deck's collections"), WalkDeckOf(TEXT("BerthDeck_Messes")), FString(TEXT("Berth")));
	TestEqual(TEXT("the gun deck"), WalkDeckOf(TEXT("GunDeck")), FString(TEXT("Gun")));
	TestEqual(TEXT("the lids are no deck's"), WalkDeckOf(TEXT("Scene Collection")), FString());
	TestTrue(TEXT("a table without placed copies or lights parses to none"), ParseDecks(TEXT("{\"meshes\": {}}"), Table, &Error) && Table.Copies.Num() == 0 && Table.Lanterns.Num() == 0);
	TestFalse(TEXT("no meshes"), ParseDecks(TEXT("{\"root\": \"x\"}"), Table, &Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOutsideGroupsTest, "SailingSim.ShipOutside.Groups", ShipOutsideTestsLocal::TestFlags)
bool FShipOutsideGroupsTest::RunTest(const FString& Parameters)
{
	using namespace ShipOutside;
	TestEqual(TEXT("running rigging by group"), GroupOf(TEXT("Running_Fore_Set")), FString(TEXT("Fore")));
	TestEqual(TEXT("blocks by group"), GroupOf(TEXT("Blocks_Staysails_Clewed")), FString(TEXT("Staysails")));
	TestEqual(TEXT("the spritsail's"), GroupOf(TEXT("Running_Spritsail_Furled")), FString(TEXT("Spritsail")));
	TestEqual(TEXT("a sail is the rig's"), GroupOf(TEXT("Sail_ForeCourse_Set")), FString());
	TestEqual(TEXT("the lanyards follow the ship"), GroupOf(TEXT("LidLanyards_Open")), FString());
	TestEqual(TEXT("the skin follows the ship"), GroupOf(TEXT("Skin")), FString());

	TestEqual(TEXT("fore course"), GroupOfSail(TEXT("fore_course")), FString(TEXT("Fore")));
	TestEqual(TEXT("fore royal"), GroupOfSail(TEXT("fore_royal")), FString(TEXT("Fore")));
	TestEqual(TEXT("main topgallant"), GroupOfSail(TEXT("main_topgallant")), FString(TEXT("Main")));
	TestEqual(TEXT("mizzen topsail"), GroupOfSail(TEXT("mizzen_topsail")), FString(TEXT("Mizzen")));
	TestEqual(TEXT("spanker"), GroupOfSail(TEXT("spanker")), FString(TEXT("Spanker")));
	TestEqual(TEXT("jib"), GroupOfSail(TEXT("jib")), FString(TEXT("Headsails")));
	TestEqual(TEXT("flying jib"), GroupOfSail(TEXT("flying_jib")), FString(TEXT("Headsails")));
	TestEqual(TEXT("fore topmast staysail is a headsail"), GroupOfSail(TEXT("fore_topmast_staysail")), FString(TEXT("Headsails")));
	TestEqual(TEXT("main staysail"), GroupOfSail(TEXT("main_staysail")), FString(TEXT("Staysails")));
	TestEqual(TEXT("mizzen topmast staysail"), GroupOfSail(TEXT("mizzen_topmast_staysail")), FString(TEXT("Staysails")));
	TestEqual(TEXT("nothing else"), GroupOfSail(TEXT("genoa")), FString());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOutsideCommonwealthTest, "SailingSim.ShipOutside.Commonwealth", ShipOutsideTestsLocal::TestFlags)
bool FShipOutsideCommonwealthTest::RunTest(const FString& Parameters)
{
	// Her table, once the import has committed it (Content/TerrainData/Ships/Commonwealth.sockets.json): the 246 parts
	// above the gun deck less the two on their own pivots, every one with its twin, the hull among them.
	using namespace ShipOutside;
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *TablePath(TEXT("Commonwealth"))))
	{
		AddInfo(TEXT("Commonwealth.sockets.json is not in Content yet (the PC's import commits it): nothing to check"));
		return true;
	}
	TArray<FPart> Parts;
	FString Error;
	TestTrue(FString::Printf(TEXT("her table parses: %s"), *Error), ParseTable(Text, Parts, &Error));
	TestEqual(TEXT("244 parts in her frame"), Parts.Num(), 244);
	int32 Twins = 0, Always = 0;
	bool bSkin = false, bWheel = false;
	for (const FPart& P : Parts)
	{
		if (!P.LightAsset.IsEmpty()) ++Twins;
		if (P.States == AllStates) ++Always;
		bSkin |= P.Name == TEXT("Skin");
		bWheel |= P.Name == TEXT("Wheel");
		TestTrue(FString::Printf(TEXT("%s is in some state"), *P.Name), P.States != 0);
		TestTrue(FString::Printf(TEXT("%s is under Outside/"), *P.Name), P.Asset.StartsWith(TEXT("/Game/Boats/Frigate/Outside/SM_Frigate_")));
	}
	TestEqual(TEXT("every part has its twin"), Twins, Parts.Num());
	TestEqual(TEXT("144 parts in every state"), Always, 144);
	TestTrue(TEXT("the hull's skin"), bSkin);
	TestFalse(TEXT("the wheel is the frames' (its own pivot)"), bWheel);
	// Her decks: the berth deck's 406 copies (236 hammock hooks, 112 hammocks, the messes' 24 benches, 12 tables, 12 kids
	// and 10 sea chests) and 29 lanterns (15 on the gun deck with the great cabin's, 12 on the berth deck with the sick
	// bay's and the wardroom's, 2 on the orlop), every copy on a deck whose mesh is in the Decks folder.
	FDeckTable Decks;
	TestTrue(FString::Printf(TEXT("her decks parse: %s"), *Error), ParseDecks(Text, Decks, &Error));
	int32 Berth = 0, Hooks = 0, Hammocks = 0;
	for (const FDeckCopy& C : Decks.Copies)
	{
		if (C.Deck == TEXT("Berth")) ++Berth;
		if (C.Part == TEXT("HammockHook")) ++Hooks;
		if (C.Part == TEXT("BerthHammock")) ++Hammocks;
		TestTrue(FString::Printf(TEXT("%s is under Decks/"), *C.Part), C.Asset.StartsWith(TEXT("/Game/Boats/Frigate/Decks/SM_Frigate_")));
	}
	TestEqual(TEXT("406 copies on the berth deck"), Berth, 406);
	TestEqual(TEXT("236 hammock hooks"), Hooks, 236);
	TestEqual(TEXT("112 hammocks"), Hammocks, 112);
	int32 Gun = 0, BerthLights = 0, Orlop = 0;
	for (const FLantern& L : Decks.Lanterns)
	{
		if (L.Deck == TEXT("Gun")) ++Gun;
		if (L.Deck == TEXT("Berth")) ++BerthLights;
		if (L.Deck == TEXT("Orlop")) ++Orlop;
	}
	TestEqual(TEXT("29 lanterns"), Decks.Lanterns.Num(), 29);
	TestEqual(TEXT("15 on the gun deck"), Gun, 15);
	TestEqual(TEXT("12 on the berth deck"), BerthLights, 12);
	TestEqual(TEXT("2 on the orlop"), Orlop, 2);
	return true;
}
