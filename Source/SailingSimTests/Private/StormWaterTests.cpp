#include "Misc/AutomationTest.h"
#include "WaterSurface.h"

#if WITH_DEV_AUTOMATION_TESTS

// Feedback #27 (docs/blow-sea/): M_WaterV4's storm water look (StormWater) fades in with the air's mean wind. The
// shading itself lives in make_materials.py (V4_SHADE); this holds when it is on.

namespace
{
	constexpr EAutomationTestFlags StormWaterFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStormWaterTest, "SailingSim.Visual.StormWater", StormWaterFlags)
bool FSailingStormWaterTest::RunTest(const FString& Parameters)
{
	// None to 18 kn (a fresh breeze keeps the water it had), full from 26 kn (the report's storm), rising between.
	for (const double Kn : { 0.0, 10.0, 15.0, 18.0 })
		TestEqual(*FString::Printf(TEXT("%.0f kn: off"), Kn), AWaterSurface::StormWaterStrength(Kn), 0.0, 1e-12);
	TestEqual(TEXT("Half at 22 kn"), AWaterSurface::StormWaterStrength(22.0), 0.5, 1e-12);
	for (const double Kn : { 26.0, 32.0, 40.0 })
		TestEqual(*FString::Printf(TEXT("%.0f kn: full"), Kn), AWaterSurface::StormWaterStrength(Kn), 1.0, 1e-12);
	double Last = -1.0;
	bool bRising = true;
	for (double Kn = 17.0; Kn <= 27.0; Kn += 0.1)
	{
		const double S = AWaterSurface::StormWaterStrength(Kn);
		if (S < Last) bRising = false;
		Last = S;
	}
	TestTrue(TEXT("Never falls as the wind rises"), bRising);
	return true;
}

#endif
