// docs/long-wave-fft/ (storm water step 5, phase 1): the long-wave FFT engine's checks (LongWaveChecks.h), the same the
// standalone scripts/long-wave-check.sh runs. SeaMapSwan needs SWAN's points from another branch: the script only.
#include "Misc/AutomationTest.h"
#include "LongWaveChecks.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	bool Report(FAutomationTestBase& Test, const FLongWaveCheck& Check)
	{
		for (const std::string& Line : Check.Lines) Test.AddInfo(UTF8_TO_TCHAR(Line.c_str()));
		Test.TestTrue(UTF8_TO_TCHAR(Check.Name.c_str()), Check.bPass);
		return true;
	}
}

#define LONG_WAVE_TEST(Name) \
	IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLongWaves##Name##Test, "SailingSim.Physics.LongWaves." #Name, Flags) \
	bool FLongWaves##Name##Test::RunTest(const FString& Parameters) { return Report(*this, LongWaveChecks::Name()); }

LONG_WAVE_TEST(Spectrum)
LONG_WAVE_TEST(MatchesDirectSum)
LONG_WAVE_TEST(TimeBlend)
LONG_WAVE_TEST(Spreading)
LONG_WAVE_TEST(Growth)
LONG_WAVE_TEST(WindShift)
LONG_WAVE_TEST(FrameRateFree)
LONG_WAVE_TEST(Determinism)
LONG_WAVE_TEST(LongClock)
LONG_WAVE_TEST(Golden)
LONG_WAVE_TEST(NoWeave)
LONG_WAVE_TEST(FieldWiring)

#undef LONG_WAVE_TEST

#endif
