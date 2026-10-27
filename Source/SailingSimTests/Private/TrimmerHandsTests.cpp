#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "SeaTrials.h"
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

#endif
