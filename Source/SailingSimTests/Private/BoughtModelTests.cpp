#include "Misc/AutomationTest.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "BoatModel.h"

namespace
{
	constexpr EAutomationTestFlags BoughtModelFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	// A bought hull scaled to its class: its length within this share of the config's published LOA (less a bowsprit).
	constexpr double BoughtLoaTolerance = 0.03;
}

// Bought-model test (docs/bought-yacht): a purchased model fitted to a class (Tools/blender/prep_bought.py, imported by
// import_boats.py `bought <Tag>` to the git-ignored /Game/Boats/Bought/<Tag>) stands in for that class's model on the
// player's boat. It rides the class's physics, so it is held only to the config's length and to the sockets the rig and
// sails are drawn from (not to the physics hull underwater, as SailingSim.Visual.FleetMesh holds the shipped fleet).
// Skipped, with a note, where no bought model is imported (every checkout but the PC that has one).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualBoughtModelTest, "SailingSim.Visual.BoughtModel", BoughtModelFlags)
bool FVisualBoughtModelTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	static const TCHAR* Tags[] = { TEXT("J22"), TEXT("Sunfish"), TEXT("ILCA7"), TEXT("Catalina22"), TEXT("Catalina30"), TEXT("Hobie16"), TEXT("Corsair880"), TEXT("Lagoon42"), TEXT("Maxi") };
	int32 Found = 0;
	for (int32 Type = 1; Type < int32(UE_ARRAY_COUNT(Tags)); ++Type)
	{
		const TCHAR* Tag = Tags[Type];
		auto Load = [Tag](const TCHAR* Part)
		{
			return Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr,
				*FString::Printf(TEXT("/Game/Boats/Bought/%s/SM_%sB_%s.SM_%sB_%s"), Tag, Tag, Part, Tag, Part), nullptr, LOAD_NoWarn | LOAD_Quiet));
		};
		UStaticMesh* Hull = Load(TEXT("Hull"));
		if (!Hull) continue;
		++Found;
		UStaticMesh* Mast = Load(TEXT("Mast"));
		UStaticMesh* Boom = Load(TEXT("Boom"));
		UStaticMesh* Rudder = Load(TEXT("Rudder"));
		if (!TestTrue(FString::Printf(TEXT("%s: the bought set has its mast, boom and rudder"), Tag), Mast && Boom && Rudder)) continue;
		const FBoatConfig C = FBoatConfig::Make(EBoatType(Type));
		const FBox B = Hull->GetBoundingBox();
		const double Length = (B.Max.X - B.Min.X) / 100.0;
		const double Target = C.LengthOverall - C.Bowsprit;
		TestTrue(FString::Printf(TEXT("%s: bought hull %.2f m long against the class's %.2f"), Tag, Length, Target),
			FMath::Abs(Length - Target) <= BoughtLoaTolerance * Target);
		for (const TCHAR* Name : { TEXT("MastStep"), TEXT("ForestayTack"), TEXT("Traveler_C"), TEXT("RudderPivot") })
		{
			TestNotNull(FString::Printf(TEXT("%s: hull socket %s"), Tag, Name), Hull->FindSocket(Name));
		}
		for (const TCHAR* Name : { TEXT("MastBase"), TEXT("Hounds") })
		{
			TestNotNull(FString::Printf(TEXT("%s: mast socket %s"), Tag, Name), Mast->FindSocket(Name));
		}
		TestNotNull(FString::Printf(TEXT("%s: boom socket Boom_Clew"), Tag), Boom->FindSocket(TEXT("Boom_Clew")));
	}
	if (Found == 0) AddInfo(TEXT("No bought model imported (/Game/Boats/Bought): nothing to check"));
	return true;
}
