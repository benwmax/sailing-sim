#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "Waves.h"
#include "WaterSurface.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// Feedback #27 (docs/blow-sea/): from 20 kn the game builds the lake's sea in a stronger wind than the mean
// (FWaveField::BlowSeaKnots). The growth laws themselves (and the SWAN tests on them) are unchanged.

namespace
{
	constexpr EAutomationTestFlags BlowSeaFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	double PeakWavelength(double Tp) { return kGravity * Tp * Tp / (2.0 * kPi); }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBlowSeaTest, "SailingSim.Physics.BlowSea", BlowSeaFlags)
bool FSailingBlowSeaTest::RunTest(const FString& Parameters)
{
	// Nothing changes up to 20 kn, or with the lift off.
	for (const double Kn : { 0.0, 5.0, 12.0, 15.0, 19.9, 20.0 })
		TestEqual(*FString::Printf(TEXT("%.1f kn: the sea's wind is the wind"), Kn), FWaveField::BlowSeaKnots(Kn), Kn, 1e-12);
	TestEqual(TEXT("Lift 0 is off at 30 kn"), FWaveField::BlowSeaKnots(30.0, 0.0), 30.0, 1e-12);

	// The ramp: 20 to 28 kn on a smoothstep, then held at 1 + lift; continuous and rising.
	TestEqual(TEXT("26 kn builds a 29.3 kn sea"), FWaveField::BlowSeaKnots(26.0), 26.0 * (1.0 + 0.15 * 0.84375), 1e-9);
	TestEqual(TEXT("28 kn and up: 1.15 times the wind"), FWaveField::BlowSeaKnots(35.0) / 35.0, 1.0 + FWaveField::kBlowLift, 1e-12);
	double Last = 0.0;
	bool bRising = true, bContinuous = true;
	for (double Kn = 18.0; Kn <= 40.0; Kn += 0.05)
	{
		const double S = FWaveField::BlowSeaKnots(Kn);
		if (Last > 0.0 && S <= Last) bRising = false;
		if (Last > 0.0 && S - Last > 0.05 * 2.5) bContinuous = false;
		Last = S;
	}
	TestTrue(TEXT("The sea's wind rises with the wind"), bRising);
	TestTrue(TEXT("... without a step"), bContinuous);

	// The report's spot (north lake below the SH-66 causeway, 26 kn from 157.5 deg): the sea the game builds there now
	// stands at the same law's height over the straight-line fetch (within 10%), a little steeper than before (Hs over the peak's
	// wavelength), and its whitecap target (Monahan, U^3.41) rises by half.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const double X = 8917.0, Y = 240.0, From = 157.5 * kDegToRad, U = 26.0 * kKnot;
	const double Effective = FMath::Clamp(Lake.Terrain.EffectiveFetch(X, Y, From), 200.0, 15000.0);
	const double Straight = FMath::Clamp(Lake.Terrain.FetchToward(X, Y, From), 200.0, 15000.0);
	const double Ub = FWaveField::BlowSeaKnots(26.0) * kKnot;
	const double Hs0 = FWaveField::TargetSignificantHeight(U, Effective), Hs1 = FWaveField::TargetSignificantHeight(Ub, Effective);
	const double Tp0 = FWaveField::TargetPeakPeriod(U, Effective), Tp1 = FWaveField::TargetPeakPeriod(Ub, Effective);
	const double StraightHs = FWaveField::TargetSignificantHeight(U, Straight);
	AddInfo(FString::Printf(TEXT("Report spot, 26 kn: fetch %.0f m effective, %.0f m straight; Hs %.2f -> %.2f m (law over the straight fetch %.2f), Tp %.2f -> %.2f s"),
		Effective, Straight, Hs0, Hs1, StraightHs, Tp0, Tp1));
	TestTrue(TEXT("Taller: at least 15% over the SWAN-fitted sea"), Hs1 > 1.15 * Hs0);
	TestTrue(TEXT("... at the straight-line fetch's height within 10%"), FMath::Abs(Hs1 / StraightHs - 1.0) < 0.10);
	TestTrue(TEXT("... and no less steep"), Hs1 / PeakWavelength(Tp1) >= Hs0 / PeakWavelength(Tp0));

	// The storm water look (M_WaterV4's StormWater) by the air's wind: none to 18 kn, full from 26, rising between.
	TestEqual(TEXT("Storm water: none at 18 kn"), AWaterSurface::StormWaterStrength(18.0), 0.0, 1e-12);
	TestEqual(TEXT("Storm water: half at 22 kn"), AWaterSurface::StormWaterStrength(22.0), 0.5, 1e-12);
	TestEqual(TEXT("Storm water: full at 26 kn"), AWaterSurface::StormWaterStrength(26.0), 1.0, 1e-12);
	TestEqual(TEXT("Storm water: full at 40 kn"), AWaterSurface::StormWaterStrength(40.0), 1.0, 1e-12);
	return true;
}

#endif
