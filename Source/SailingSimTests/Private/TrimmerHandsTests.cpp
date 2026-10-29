#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "SeaTrials.h"
#include "AutoTrim.h"
#include "WindClimate.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

/**
 * docs/trimmer-hands/: the crew trim like people. The J/22 upwind in 15 kn: on flat water in a steady wind nobody touches a
 * sheet; in the lake's chop (5 km) the hands make a few adjustments a minute (under 20 across main, traveller and jib) and
 * the mainsheet travels under 3 times its length a minute, where the polar's ideal trim chases every roll (over 10); in
 * gusty air they adjust more than in a steady breeze; and the boat is as fast as with ideal trim within 3%.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingTrimmerHandsTest, "SailingSim.Physics.TrimmerHands",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingTrimmerHandsTest::RunTest(const FString&)
{
	const FBoatConfig J22 = FBoatConfig::Make(EBoatType::J22);
	const double Gust = GustIntensityForFactor(ClimateGustFactor(7, 15.0, false));
	const FTrimHandsResult Flat = MeasureTrimHands(J22, 15.0, 45.0, 1.0, 0.0, 300.0);
	const FTrimHandsResult Chop = MeasureTrimHands(J22, 15.0, 45.0, 5000.0, 0.0, 300.0);
	const FTrimHandsResult Gusty = MeasureTrimHands(J22, 15.0, 45.0, 5000.0, Gust, 300.0);
	const FTrimHandsResult Ideal = MeasureTrimHands(J22, 15.0, 45.0, 5000.0, 0.0, 300.0, false);
	auto Line = [](const TCHAR* What, const FTrimHandsResult& R)
	{
		return FString::Printf(TEXT("%s: main %.2f, traveller %.2f, jib %.2f travels/min, %.1f adjustments/min, %.2f kn"), What, R.MainTravelPerMin,
			R.TravelerTravelPerMin, R.JibTravelPerMin, R.AdjustmentsPerMin, R.MeanKnots);
	};
	AddInfo(Line(TEXT("Flat, steady"), Flat));
	AddInfo(Line(TEXT("Lake chop, steady"), Chop));
	AddInfo(Line(TEXT("Lake chop, gusty"), Gusty));
	AddInfo(Line(TEXT("Lake chop, ideal trim"), Ideal));
	TestTrue(TEXT("Flat water, steady wind: the sheets are left alone"), Flat.AdjustmentsPerMin < 1.0 && Flat.MainTravelPerMin < 0.1);
	TestTrue(TEXT("In the chop: a few adjustments a minute, not every roll"), Chop.AdjustmentsPerMin > 1.0 && Chop.AdjustmentsPerMin < 20.0);
	TestTrue(TEXT("... the mainsheet under 3 travels a minute"), Chop.MainTravelPerMin < 3.0 && Chop.JibTravelPerMin < 3.0);
	TestTrue(TEXT("... the traveller under 6"), Chop.TravelerTravelPerMin < 6.0);
	TestTrue(TEXT("... where ideal trim chases every roll"), Ideal.MainTravelPerMin > 10.0);
	TestTrue(TEXT("More adjustments in gusty air"), Gusty.AdjustmentsPerMin > Chop.AdjustmentsPerMin);
	TestTrue(FString::Printf(TEXT("As fast as ideal trim within 3%% (%.2f against %.2f kn)"), Chop.MeanKnots, Ideal.MeanKnots),
		FMath::Abs(Chop.MeanKnots / Ideal.MeanKnots - 1.0) < 0.03);
	return true;
}

/**
 * docs/j22-crew-tack/: the J/22's crew hold the main through a tack the player calls on the helm. On main the player's tack
 * already went through at every wind (14 to 28 kn, full helm or not); in a blow she nearly stopped head to wind. With a
 * gentle helm (0.6) in 28 kn, over 24 tacks, the hold gets more of them through and quicker, keeping more speed; and the
 * crew never read a luff in the gusts as a call. Off by default (the scenarios, polars and AI sail as before), and nothing
 * changes on a dinghy.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCrewTackTest, "SailingSim.Physics.CrewTack",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingCrewTackTest::RunTest(const FString&)
{
	TestFalse(TEXT("Off by default"), FAutoTrimSettings().bCrewTacks);
	const FBoatConfig J22 = FBoatConfig::Make(EBoatType::J22);
	int32 ThroughOwn = 0, ThroughCrew = 0, FalseCalls = 0;
	double KeptOwn = 0.0, KeptCrew = 0.0;
	TArray<double> SecondsOwn, SecondsCrew;
	constexpr int32 Seeds = 24;
	for (uint32 Seed = 1; Seed <= uint32(Seeds); ++Seed)
	{
		const FPlayerTackResult Own = RunPlayerTack(J22, 28.0, Seed, 0.6, false), Crew = RunPlayerTack(J22, 28.0, Seed, 0.6, true);
		ThroughOwn += Own.bThrough;
		ThroughCrew += Crew.bThrough;
		KeptOwn += Own.KeptShare / Seeds;
		KeptCrew += Crew.KeptShare / Seeds;
		SecondsOwn.Add(Own.bThrough ? Own.Seconds : 999.0);
		SecondsCrew.Add(Crew.bThrough ? Crew.Seconds : 999.0);
		FalseCalls += Crew.FalseCalls;
	}
	SecondsOwn.Sort();
	SecondsCrew.Sort();
	const double MedianOwn = 0.5 * (SecondsOwn[11] + SecondsOwn[12]), MedianCrew = 0.5 * (SecondsCrew[11] + SecondsCrew[12]);
	AddInfo(FString::Printf(TEXT("28 kn, tiller 0.6, 24 tacks: on her own %d through, median %.1f s, %.0f%% of her speed kept; with the crew %d, %.1f s, %.0f%%"),
		ThroughOwn, MedianOwn, 100.0 * KeptOwn, ThroughCrew, MedianCrew, 100.0 * KeptCrew));
	TestTrue(FString::Printf(TEXT("More tacks through with the crew (%d against %d)"), ThroughCrew, ThroughOwn), ThroughCrew > ThroughOwn);
	TestTrue(FString::Printf(TEXT("... quicker (median %.1f s against %.1f)"), MedianCrew, MedianOwn), MedianCrew < MedianOwn);
	TestTrue(FString::Printf(TEXT("... keeping more of her speed (%.0f%% against %.0f%%)"), 100.0 * KeptCrew, 100.0 * KeptOwn), KeptCrew > KeptOwn + 0.05);
	// The minute's gusty beat before each call, and a full-helm tack at 20 kn: no luff read as a tack.
	for (uint32 Seed = 1; Seed <= 8; ++Seed) FalseCalls += RunPlayerTack(J22, 20.0, Seed, 1.0, true).FalseCalls;
	TestEqual(TEXT("No false calls in a gusty beat"), FalseCalls, 0);
	// A dinghy is sailed as before.
	const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
	const FPlayerTackResult A = RunPlayerTack(Ilca, 14.0, 1, 1.0, false), B = RunPlayerTack(Ilca, 14.0, 1, 1.0, true);
	TestTrue(TEXT("The ILCA's tack is unchanged"), A.bThrough == B.bThrough && A.Seconds == B.Seconds && A.MinSpeedKnots == B.MinSpeedKnots);
	return true;
}

#endif
