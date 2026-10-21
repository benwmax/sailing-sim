#include "Misc/AutomationTest.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameterCollection.h"

namespace
{
	constexpr EAutomationTestFlags SprayHullFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// Spray hull (docs/spray-hull): MPC_Boat carries SprayWet (the pawn's spray and slam wetting of the topsides, read by
// M_BoatSurface and M_J22HeroSurface), and M_BowWave, the bow wave's curl, is a translucent material (the pawn draws it
// on the waves). Skipped (with a warning) before make_materials.py has built them.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualSprayHullTest, "SailingSim.Visual.SprayHull", SprayHullFlags)
bool FVisualSprayHullTest::RunTest(const FString& Parameters)
{
	const UMaterialParameterCollection* Mpc = LoadObject<UMaterialParameterCollection>(nullptr, TEXT("/Game/Boats/MPC_Boat.MPC_Boat"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Mpc)
	{
		AddWarning(TEXT("No MPC_Boat: run make_materials.py"));
		return true;
	}
	TestNotNull(TEXT("MPC_Boat has SprayWet"), Mpc->GetScalarParameterByName(TEXT("SprayWet")));
	TestNotNull(TEXT("MPC_Boat keeps WaterZ"), Mpc->GetScalarParameterByName(TEXT("WaterZ")));
	const UMaterialInterface* Bow = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BowWave.M_BowWave"), nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (TestNotNull(TEXT("M_BowWave"), Bow))
	{
		TestEqual(TEXT("M_BowWave is translucent"), int32(Bow->GetBlendMode()), int32(BLEND_Translucent));
	}
	return true;
}
