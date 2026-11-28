#include "Misc/AutomationTest.h"
#include "SoakMemory.h"

#if WITH_DEV_AUTOMATION_TESTS

// docs/long-sail-soak: the long-sail memory test's fit (SailingSoak::Fit).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSoakMemoryFitTest, "SailingSim.Smoke.SoakMemory.Fit",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingSoakMemoryFitTest::RunTest(const FString&)
{
	// Two hours, a row a minute, sailing 5 m/s: 30 MB of warm-up in the first 10 minutes, then flat with a 4 MB wobble.
	TArray<SailingSoak::FMemRow> Flat;
	for (int32 M = 0; M <= 120; ++M)
	{
		SailingSoak::FMemRow Row;
		Row.T = M * 60.0;
		Row.TravelledM = M * 300.0;
		Row.UsedMB = 3000.0 + (M < 10 ? 3.0 * M : 30.0) + ((M % 2) ? 2.0 : -2.0);
		Flat.Add(Row);
	}
	const SailingSoak::FMemFit F = SailingSoak::Fit(Flat);
	TestEqual(TEXT("The warm-up's rows are left out"), F.Rows, 111);
	TestTrue(FString::Printf(TEXT("Flat after the warm-up (%.2f MB/h)"), F.MBPerHour), FMath::Abs(F.MBPerHour) < 1.0);
	TestTrue(FString::Printf(TEXT("... and per distance (%.2f MB/100 km)"), F.MBPer100Km), FMath::Abs(F.MBPer100Km) < 1.0);
	TestEqual(TEXT("Peak"), F.PeakMB, 3032.0, 1e-9);

	// The same run with 1 MB a minute on top: 60 MB/h, and 60 MB per 18 km = 333 MB per 100 km.
	TArray<SailingSoak::FMemRow> Growing = Flat;
	for (int32 I = 0; I < Growing.Num(); ++I) Growing[I].UsedMB += I;
	const SailingSoak::FMemFit G = SailingSoak::Fit(Growing);
	TestEqual(TEXT("A steady climb, an hour"), G.MBPerHour, 60.0, 0.5);
	TestEqual(TEXT("... per 100 km"), G.MBPer100Km, 333.33, 2.0);

	// Parked: no distance, so no per-distance figure.
	TArray<SailingSoak::FMemRow> Parked = Growing;
	for (SailingSoak::FMemRow& Row : Parked) Row.TravelledM = 0.0;
	TestEqual(TEXT("Parked: no per-distance growth"), SailingSoak::Fit(Parked).MBPer100Km, 0.0, 1e-12);

	// A short hop (2 km after the warm-up, as on the lake): no per-distance figure, only the hourly one.
	TArray<SailingSoak::FMemRow> Hop = Growing;
	for (SailingSoak::FMemRow& Row : Hop) Row.TravelledM *= 2000.0 / 33000.0;
	const SailingSoak::FMemFit H = SailingSoak::Fit(Hop);
	TestEqual(TEXT("A 2 km hop: no per-distance growth"), H.MBPer100Km, 0.0, 1e-12);
	TestEqual(TEXT("... but the hourly figure stands"), H.MBPerHour, 60.0, 0.5);

	// Too short to say.
	TArray<SailingSoak::FMemRow> Short;
	Short.Add({ 30.0, 0.0, 3000.0 });
	TestEqual(TEXT("Nothing after the warm-up"), SailingSoak::Fit(Short).Rows, 0);
	return true;
}

#endif
