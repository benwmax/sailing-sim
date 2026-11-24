// A ship's outside model table (docs/frigate-import/, ShipOutside.h): the export's meshes read into parts with their
// states, the rig groups the running rigging follows, and the frigate's own table where the import has landed.
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "ShipOutside.h"

namespace ShipOutsideTestsLocal
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	const TCHAR* Sample = TEXT("") R"({
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
			"asset": "/Game/Boats/Frigate/Guns/SM_Frigate_Gun24_Barrel", "part": "Gun24_Barrel", "states": null, "frame": "own (guns.json meshes)"}
	}
})";
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
	return true;
}
