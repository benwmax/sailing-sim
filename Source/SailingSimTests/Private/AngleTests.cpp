#include "Misc/AutomationTest.h"
#include "HAL/PlatformTime.h"
#include "SailingAngles.h"
#include <limits>

#if WITH_DEV_AUTOMATION_TESTS

// The PC's soak 3 hang: FMath::UnwindDegrees on a 1e17 heading never returns. SailingAngles::WrapDegrees always does.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWrapDegreesTest, "SailingSim.Smoke.WrapDegrees",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingWrapDegreesTest::RunTest(const FString&)
{
	const double Start = FPlatformTime::Seconds();
	const double Inf = std::numeric_limits<double>::infinity(), NaN = std::numeric_limits<double>::quiet_NaN();
	for (const double A : { 1e17, -1e17, 1e300, -1e300, Inf, -Inf, NaN })
	{
		const double W = SailingAngles::WrapDegrees(A);
		TestTrue(FString::Printf(TEXT("%g wraps into (-180, 180]: %g"), A, W), W > -180.0 && W <= 180.0);
		const float F = SailingAngles::WrapDegrees(float(A));
		TestTrue(FString::Printf(TEXT("... as a float too: %g"), F), F > -180.f && F <= 180.f);
	}
	TestEqual(TEXT("NaN gives 0"), SailingAngles::WrapDegrees(NaN), 0.0);
	TestEqual(TEXT("Infinity gives 0"), SailingAngles::WrapDegrees(Inf), 0.0);
	// Ordinary angles: what UnwindDegrees gives.
	for (const double A : { 0.0, 179.0, 181.0, -181.0, 540.0, -725.5, 359.9, 3600.25 })
		TestTrue(FString::Printf(TEXT("%g as UnwindDegrees: %g"), A, SailingAngles::WrapDegrees(A)), FMath::IsNearlyEqual(SailingAngles::WrapDegrees(A), FMath::UnwindDegrees(A), 1e-9));
	TestEqual(TEXT("180 stays 180"), SailingAngles::WrapDegrees(180.0), 180.0);
	TestTrue(TEXT("Returns at once (no loop)"), FPlatformTime::Seconds() - Start < 1.0);
	return true;
}

#endif
