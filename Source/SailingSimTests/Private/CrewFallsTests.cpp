#include "Misc/AutomationTest.h"
#include "CrewFalls.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	constexpr EAutomationTestFlags FallsFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
	constexpr float Dt = 1.f / 60.f;

	/** Runs Seconds of frames with the same inputs; returns the most frames in a row the crew were simulated. */
	void RunFor(FCrewFalls& F, float Seconds, float Tilt, float LatG, float VertG, bool bCapsized)
	{
		for (float T = 0.f; T < Seconds; T += Dt) F.Update(Dt, Tilt, LatG, VertG, bCapsized);
	}
}

/**
 * Crew C5 (CrewFalls.h): when the crew fall and when they are back on their feet.
 *  1. Sailing hard (heeled 25 deg, 0.3 g of slam and roll) never throws them.
 *  2. A knock (a tenth of a second at 1.5 g: a collision) throws them with some grip left, and they are posed again within
 *     the fall's minimum, the steady second, the gather and the hold (about 3.1 s).
 *  3. A capsize keeps them falling, near limp, as long as she lies over; righted, they gather and come back.
 *  4. A second knock while they gather throws them again.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualCrewFallsTest, "SailingSim.Visual.CrewFalls", FallsFlags)
bool FVisualCrewFallsTest::RunTest(const FString& Parameters)
{
	const FCrewFallParams P;
	{
		FCrewFalls F(P);
		RunFor(F, 20.f, 25.f, 0.3f, 0.25f, false);
		TestEqual(TEXT("1: hard sailing doesn't throw the crew"), F.FallCount(), 0);
	}
	{
		FCrewFalls F(P);
		RunFor(F, 1.f, 10.f, 0.1f, 0.f, false);
		RunFor(F, 0.1f, 10.f, 1.5f, 0.f, false);
		TestTrue(TEXT("2: a knock throws them"), F.IsSimulated() && F.FallCount() == 1);
		TestEqual(TEXT("2: with some grip"), F.Strength(), P.KnockStrength);
		float Back = -1.f, LastStrength = F.Strength();
		bool bMonotonic = true;
		for (float T = 0.f; T < 8.f && Back < 0.f; T += Dt)
		{
			F.Update(Dt, 10.f, 0.1f, 0.f, false);
			bMonotonic &= F.Strength() >= LastStrength - 1e-6f;
			LastStrength = F.Strength();
			if (F.JustRecovered()) Back = T;
		}
		const float Expect = P.MinFallSeconds + P.GatherSeconds + P.HoldSeconds;
		AddInfo(FString::Printf(TEXT("2: posed again after %.2f s"), Back));
		TestTrue(FString::Printf(TEXT("2: back on their feet in %.2f s (%.2f-%.2f)"), Back, Expect, Expect + P.SteadySeconds + 0.1f),
			Back >= Expect - 0.05f && Back <= Expect + P.SteadySeconds + 0.1f);
		TestTrue(TEXT("2: the controls only strengthen on the way back"), bMonotonic);
	}
	{
		FCrewFalls F(P);
		RunFor(F, 0.5f, 60.f, 0.2f, 0.f, false);
		RunFor(F, 10.f, 95.f, 0.2f, 0.f, true);
		TestTrue(TEXT("3: capsized, still falling after 10 s"), F.Phase() == ECrewFallPhase::Falling);
		TestEqual(TEXT("3: near limp"), F.Strength(), P.CapsizeStrength);
		RunFor(F, 6.f, 8.f, 0.1f, 0.f, false);
		TestTrue(TEXT("3: righted, posed again within 6 s"), F.Phase() == ECrewFallPhase::Posed && F.FallCount() == 1);
	}
	{
		FCrewFalls F(P);
		RunFor(F, 0.1f, 10.f, 1.5f, 0.f, false);
		RunFor(F, P.MinFallSeconds + P.SteadySeconds + 0.3f, 10.f, 0.1f, 0.f, false);
		TestTrue(TEXT("4: gathering"), F.Phase() == ECrewFallPhase::Gathering && F.Strength() > P.KnockStrength);
		RunFor(F, 0.1f, 10.f, 0.f, 1.4f, false);
		TestTrue(TEXT("4: a slam while gathering throws them again"), F.Phase() == ECrewFallPhase::Falling && F.Strength() == P.KnockStrength);
	}
	return true;
}

#endif
