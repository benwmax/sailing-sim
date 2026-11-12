// docs/rope-lay/ (rope realism phase 1): the rope lay's checks (RopeLayChecks.h), the same the standalone
// scripts/rope-check.sh runs.
#include "Misc/AutomationTest.h"
#include "RopeLayChecks.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags RopeFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	bool ReportRope(FAutomationTestBase& Test, const Sailing::FRopeLayCheck& Check)
	{
		for (const std::string& Line : Check.Lines) Test.AddInfo(UTF8_TO_TCHAR(Line.c_str()));
		Test.TestTrue(UTF8_TO_TCHAR(Check.Name.c_str()), Check.bPass);
		return true;
	}
}

#define ROPE_LAY_TEST(Name) \
	IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRopeLay##Name##Test, "SailingSim.Visual.RopeLay." #Name, RopeFlags) \
	bool FRopeLay##Name##Test::RunTest(const FString& Parameters) { return ReportRope(*this, Sailing::RopeLayChecks::Name()); }

ROPE_LAY_TEST(FreeLine)
ROPE_LAY_TEST(DrapeOverTrunk)
ROPE_LAY_TEST(NoShimmer)
ROPE_LAY_TEST(Deterministic)
ROPE_LAY_TEST(BlockTangent)
ROPE_LAY_TEST(WinchTurns)
ROPE_LAY_TEST(ManyCases)
ROPE_LAY_TEST(OverASailor)
ROPE_LAY_TEST(OverALifeline)

#undef ROPE_LAY_TEST

#endif
