#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "FarLights.h"
#include "FarLightsActor.h"

#if WITH_DEV_AUTOMATION_TESTS

// Wide World Rendering PR 3 (docs/world-far-lights): far lights by Allard's law and the horizon, city domes from the
// world files, and no light drawn twice inside the near pool.

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags FarLightsFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	const FLakeData& MarseilleForFarLights()
	{
		static FLakeData Lake;
		static bool bLoaded = Lake.Load(FLakeData::DefaultDirectory(), TEXT("Marseille"));
		return Lake;
	}

	int32 FindFarLight(const FFarLightsData& Data, const TCHAR* Name)
	{
		return Data.Lights.IndexOfByPredicate([&](const FFarLightsData::FLight& L) { return L.Name.Contains(Name); });
	}

	/** Whether the light shows at any moment of one of its cycles (it flashes: sample its rhythm). */
	bool ShowsWithinCycle(const FFarLightsData& Data, int32 Index, const FVector& CameraCm, bool bDark, double VisibilityKm, bool* OutLoom = nullptr)
	{
		const double Cycle = FMath::Max(Data.Lights[Index].Light.CycleLength(), 1.0);
		for (double T = 0.0; T < Cycle; T += 0.05)
		{
			if (AFarLightsActor::IsLightShown(Data, Index, CameraCm, bDark, VisibilityKm, 1.0e9 + T, nullptr, OutLoom)) return true;
		}
		return false;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWorldFarLightsTest, "SailingSim.World.FarLights", FarLightsFlags)
bool FWorldFarLightsTest::RunTest(const FString& Parameters)
{
	// Allard's law on its own: a nominal range is, by definition, where the light meets the night threshold at 10 nm of
	// visibility; at 12 km of visibility a 23-mile light is gone well inside 20 nm.
	const double I23 = FFarLightMath::IntensityForNominalRange(23.0);
	const double AtRange = FFarLightMath::IlluminanceLux(I23, 23.0 * 1852.0, 10.0 * 1.852);
	TestTrue(TEXT("A 23-mile light meets the night threshold at 23 nm and 10 nm visibility"), FMath::Abs(AtRange / FFarLightMath::NightThresholdLux - 1.0) < 1e-6);
	TestTrue(TEXT("...is plain at 20 nm on a 25 km night"), FFarLightMath::IlluminanceLux(I23, 20.0 * 1852.0, 25.0) > 5.0 * FFarLightMath::NightThresholdLux);
	TestTrue(TEXT("...and gone at 20 nm in 12 km of visibility"), FFarLightMath::IlluminanceLux(I23, 20.0 * 1852.0, 12.0) < FFarLightMath::NightThresholdLux);
	TestTrue(TEXT("Planier's 68 m lantern dips under a 2.5 m eye's horizon at about 20 nm"),
		FMath::Abs(FFarLightMath::GeographicRangeM(68.0, 2.5) / 1852.0 - 20.4) < 0.3);

	const FLakeData& Lake = MarseilleForFarLights();
	const FFarLightsData& Data = Lake.FarLights;
	if (!TestTrue(TEXT("Marseille's far lights load"), Data.Lights.Num() > 60)) return false;

	// Planier: from 18 nm out on its north-east bearing (toward the Vieux-Port), at the helm's eye height.
	const int32 Planier = FindFarLight(Data, TEXT("Planier"));
	if (TestTrue(TEXT("Planier is in the far lights"), Planier != INDEX_NONE))
	{
		const FFarLightsData::FLight& P = Data.Lights[Planier];
		const FVector2D Toward = (FVector2D::ZeroVector - P.XY).GetSafeNormal();
		const FVector2D At18 = P.XY + Toward * 18.0 * 1852.0;
		const FVector Eye(At18.X * 100.0, At18.Y * 100.0, 250.0);
		bool bLoom = true;
		TestTrue(TEXT("Planier shows at 18 nm on a clear night (25 km)"), ShowsWithinCycle(Data, Planier, Eye, true, 25.0, &bLoom));
		TestFalse(TEXT("...above the horizon, not as a loom"), bLoom);
		TestFalse(TEXT("Planier is gone by day"), ShowsWithinCycle(Data, Planier, Eye, false, 25.0));
		TestFalse(TEXT("Planier is gone at 18 nm in 12 km of visibility"), ShowsWithinCycle(Data, Planier, Eye, true, 12.0));
		const FVector2D At22 = P.XY + Toward * 22.0 * 1852.0;
		bool bLoom22 = false;
		const bool bShows22 = ShowsWithinCycle(Data, Planier, FVector(At22.X * 100.0, At22.Y * 100.0, 250.0), true, 40.0, &bLoom22);
		TestTrue(TEXT("At 22 nm on a mistral night Planier is under the horizon: only its loom"), bShows22 && bLoom22);
		AddInfo(FString::Printf(TEXT("Planier: %s, %.0f m, %.0f nm"), UTF8_TO_TCHAR(P.Light.Label().c_str()), P.Z, P.Light.RangeNm));
	}

	// Characters match Lights.h: each far light that is a navaid here carries the navaid's own rhythm and colour.
	int32 Matched = 0, Navaids = 0;
	for (const FFarLightsData::FLight& L : Data.Lights)
	{
		if (L.Navaid == INDEX_NONE) continue;
		++Navaids;
		if (!Lake.Navaids.IsValidIndex(L.Navaid)) continue;
		const FLightCharacter& N = Lake.Navaids[L.Navaid].Light;
		Matched += N.Litchr == L.Light.Litchr && N.Groups == L.Light.Groups && N.Morse == L.Light.Morse && FMath::Abs(N.Period - L.Light.Period) < 1e-6
			&& (N.Colours.empty() ? 1 : N.Colours[0]) == L.Light.Colours[0] && FMath::IsNearlyEqual(N.CycleLength(), L.Light.CycleLength());
	}
	AddInfo(FString::Printf(TEXT("%d far lights: %d this world's navaids, %d from beyond"), Data.Lights.Num(), Navaids, Data.Lights.Num() - Navaids));
	TestEqual(TEXT("Every navaid's far light has its character"), Matched, Navaids);
	TestTrue(TEXT("Lights from beyond the map (Cap Couronne)"), FindFarLight(Data, TEXT("Couronne")) != INDEX_NONE);

	// No light doubled inside the near pool: from the Vieux-Port's entrance, every navaid within 6 km is ANavaidsActor's.
	const FVector Entrance(0.0, 0.0, 300.0);
	int32 Doubled = 0, Near = 0;
	for (int32 I = 0; I < Data.Lights.Num(); ++I)
	{
		const FFarLightsData::FLight& L = Data.Lights[I];
		if (L.Navaid == INDEX_NONE || L.XY.Size() >= AFarLightsActor::NearPoolM) continue;
		++Near;
		Doubled += ShowsWithinCycle(Data, I, Entrance, true, 40.0);
	}
	AddInfo(FString::Printf(TEXT("%d navaid lights inside the near pool at the entrance"), Near));
	TestTrue(TEXT("The near pool holds the harbour's lights"), Near > 20);
	TestEqual(TEXT("None of them is drawn by the far lights too"), Doubled, 0);

	// City domes and the lit shore come from the world's files.
	TestTrue(TEXT("Marseille has city domes (Marseille, Aubagne, Cassis, La Ciotat...)"), Data.Cities.Num() >= 4
		&& Data.Cities.ContainsByPredicate([](const FFarLightsData::FCity& C) { return C.Name == TEXT("Marseille"); }));
	TestTrue(TEXT("Marseille's shore lights its towns"), Data.Shore.Num() > 1000);
	TestTrue(TEXT("Ships on Marseille's lanes"), Data.Lanes.Num() >= 2);
	FFarLightsData Galveston;
	TestTrue(TEXT("Galveston's far lights load, its domes moved from the code (Houston, Texas City)"),
		Galveston.Load(FLakeData::DefaultDirectory() / TEXT("GalvestonBay.farlights.json"))
		&& Galveston.Cities.ContainsByPredicate([](const FFarLightsData::FCity& C) { return C.Name == TEXT("Houston"); }));
	return true;
}

#endif
