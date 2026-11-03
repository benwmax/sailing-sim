#include "Misc/AutomationTest.h"
#include "AutoTrim.h"
#include "BoatModel.h"
#include "EasyAssists.h"
#include "FixedStepper.h"
#include "LakeTerrain.h"
#include "Wind.h"
#include <cmath>
#include <vector>

using namespace Sailing;

// Easy mode (docs/easy-mode/README.md): the assists on a J/22 (and a dinghy) do what they say, and off they change nothing.
// The same checks run standalone in scripts/polar.sh --easy.
namespace EasyModeTestsLocal
{
	constexpr EAutomationTestFlags EasyFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingEasyModeTest, "SailingSim.Physics.EasyMode", EasyModeTestsLocal::EasyFlags)
bool FSailingEasyModeTest::RunTest(const FString&)
{
	// Off: every knob is the boat's own, the trim's settings their defaults, and a boat steps bit for bit as before.
	{
		const FBoatConfig Own = FBoatConfig::J22();
		FBoatConfig Off = Own;
		const FEasyAssists Realistic = FEasyAssists::For(Off, false);
		Realistic.ApplyTo(Off, 1052.0);
		TestTrue(TEXT("Realistic leaves the J/22's helm, damping and weather helm"), Off.HelmStiffness == Own.HelmStiffness && Off.ExtraRollDamping == Own.ExtraRollDamping
			&& Off.HeelYawCoef == Own.HeelYawCoef && Off.YawDampingLinear == Own.YawDampingLinear);
		TestEqual(TEXT("... and no heel cap"), Off.HeelCapDeg, 0.0);
		FAutoTrimSettings Trim;
		Realistic.ApplyTo(Trim);
		const FAutoTrimSettings OwnTrim;
		TestTrue(TEXT("... and the trim's settings"), Trim.RateScale == OwnTrim.RateScale && Trim.HeelLimitDeg == OwnTrim.HeelLimitDeg && Trim.bEasePuffs == OwnTrim.bEasePuffs);
		TestEqual(TEXT("Realistic no-go cue: the boat's own 35 degrees"), Realistic.NoGoDeg(), 35.0);
		TestEqual(TEXT("... no early warning"), Realistic.NoGoWarnDeg(), 35.0);
		FWindParams WP;
		WP.SpeedKnots = 12.0;
		WP.GustIntensity = 0.15;
		const FWindField Wind(WP);
		FBoatModel A(Own), B(Off);
		A.Reset(0.0, 0.0, -0.9, 2.0);
		B.Reset(0.0, 0.0, -0.9, 2.0);
		FAutoTrim TA, TB;
		Realistic.ApplyTo(TB.Settings);
		FEasyHelm Helm;
		FBoatControls CA, CB;
		for (int32 I = 0; I < 20 * 120; ++I)
		{
			CA = TA.Update(A, CA, PhysicsDt);
			CB = TB.Update(B, CB, PhysicsDt);
			A.Step(PhysicsDt, CA, Wind);
			B.Step(PhysicsDt, Helm.Update(B, CB, Realistic, PhysicsDt), Wind);
		}
		TestTrue(TEXT("Realistic: the same 20 s, bit for bit"), A.GetState().Position.X == B.GetState().Position.X && A.GetState().Position.Y == B.GetState().Position.Y
			&& A.GetTelemetry().Heel == B.GetTelemetry().Heel);
	}

	const FEasyAssists Easy = FEasyAssists::For(FBoatConfig::J22(), true);
	TestEqual(TEXT("Easy no-go cue: 45 degrees"), Easy.NoGoDeg(), 45.0);
	TestEqual(TEXT("... warned from 55"), Easy.NoGoWarnDeg(), 55.0);
	FBoatTelemetry T;
	T.ForwardSpeed = 2.5;
	T.TrueWindAngle = FMath::DegreesToRadians(40.0);
	TestTrue(TEXT("At 40 degrees: inside the Easy cue, clear of the Realistic one"), NoGoCueFor(T, Easy) == ENoGoCue::Inside && NoGoCueFor(T, FEasyAssists()) == ENoGoCue::Clear);
	T.TrueWindAngle = FMath::DegreesToRadians(50.0);
	TestTrue(TEXT("At 50: the Easy warning"), NoGoCueFor(T, Easy) == ENoGoCue::Near);

	// No capsize: a J/22 on a 15 kn beam reach in gusts holds her course under the cap; at 22 kn with 30% gusts the
	// Realistic boat goes past it and the Easy one doesn't.
	const FEasyReachResult Reach = RunEasyReach(EBoatType::J22, true, 15.0, 90.0, 120.0);
	AddInfo(FString::Printf(TEXT("Easy 15 kn beam reach: max heel %.1f (cap %.1f), course within %.1f deg, %.2f kn"), Reach.MaxHeelDeg, Reach.HeelCapDeg, Reach.MaxCourseErrorDeg, Reach.MeanSpeedKnots));
	TestTrue(TEXT("15 kn reach: under the heel cap"), Reach.HeelCapDeg > 20.0 && Reach.MaxHeelDeg <= Reach.HeelCapDeg && !Reach.bCapsized);
	TestTrue(TEXT("... holds her course within 8 degrees"), Reach.MaxCourseErrorDeg < 8.0);
	TestTrue(TEXT("... and still sails (over 5.5 kn)"), Reach.MeanSpeedKnots > 5.5);
	const FEasyReachResult Hard = RunEasyReach(EBoatType::J22, true, 22.0, 70.0, 120.0, 0.3);
	const FEasyReachResult HardRealistic = RunEasyReach(EBoatType::J22, false, 22.0, 70.0, 120.0, 0.3);
	AddInfo(FString::Printf(TEXT("22 kn, 30%% gusts: Easy max heel %.1f, Realistic %.1f"), Hard.MaxHeelDeg, HardRealistic.MaxHeelDeg));
	TestTrue(TEXT("22 kn gusty: Easy under the cap"), Hard.MaxHeelDeg <= Hard.HeelCapDeg && !Hard.bCapsized);
	TestTrue(TEXT("... where Realistic goes past it"), HardRealistic.MaxHeelDeg > Hard.HeelCapDeg);
	const FEasyReachResult Dinghy = RunEasyReach(EBoatType::ILCA7, true, 22.0, 70.0, 120.0, 0.3);
	AddInfo(FString::Printf(TEXT("ILCA 7 22 kn gusty on Easy: max heel %.1f (cap %.1f)"), Dinghy.MaxHeelDeg, Dinghy.HeelCapDeg));
	TestTrue(TEXT("A dinghy on Easy: under her cap, upright"), Dinghy.MaxHeelDeg <= Dinghy.HeelCapDeg && !Dinghy.bCapsized);

	// Irons: head to wind with no way on and the tiller centred, Easy has her sailing within 25 s; Realistic doesn't.
	const FEasyIronsResult Irons = RunEasyIrons(EBoatType::J22, true, 10.0, 40.0);
	const FEasyIronsResult IronsRealistic = RunEasyIrons(EBoatType::J22, false, 10.0, 40.0);
	AddInfo(FString::Printf(TEXT("Irons 10 kn: Easy sailing after %.1f s (TWA %.0f, %.1f kn); Realistic TWA %.0f, %.1f kn"), Irons.FilledSeconds, Irons.FinalTwaDeg,
		Irons.FinalSpeedKnots, IronsRealistic.FinalTwaDeg, IronsRealistic.FinalSpeedKnots));
	TestTrue(TEXT("Irons: Easy falls off and fills within 25 s"), Irons.FilledSeconds > 0.0 && Irons.FilledSeconds < 25.0);
	TestTrue(TEXT("... and is sailing at the end"), FMath::Abs(Irons.FinalTwaDeg) > 35.0 && Irons.FinalSpeedKnots > 3.0);
	TestTrue(TEXT("Realistic stays in irons"), IronsRealistic.FilledSeconds < 0.0);

	// A beginner's tack (tiller hard over 4 s, then let go): Easy ends on the new tack and sailing in 6, 10 and 15 kn.
	for (const double Tws : { 6.0, 10.0, 15.0 })
	{
		const FEasyTackResult Tack = RunEasyTack(EBoatType::J22, true, Tws);
		AddInfo(FString::Printf(TEXT("Crude tack %.0f kn on Easy: TWA %.0f, %.1f kn, max heel %.1f"), Tws, Tack.FinalTwaDeg, Tack.FinalSpeedKnots, Tack.MaxHeelDeg));
		TestTrue(FString::Printf(TEXT("Crude tack %.0f kn: tacked"), Tws), Tack.bTacked);
	}
	return true;
}

// The Sunfish blow-up (docs/easy-mode/README.md): Easy's heel cap read the tilt, which counts pitch, and pushed on the heel's
// sign. A Sunfish head to wind put down bow first on a bank read past her cap with the heel near zero, the push flipped
// every step and she ran off to 1e17 m in under a second. Here she starts 0.6 m into a sloping bank with the shore astern,
// in irons on 13 kn, nobody on the helm: the state stays finite and on the map for a minute.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingEasyHeelCapAgroundTest, "SailingSim.Physics.EasyHeelCapAground", EasyModeTestsLocal::EasyFlags)
bool FSailingEasyHeelCapAgroundTest::RunTest(const FString&)
{
	const int Rows = 200, Cols = 100;
	std::vector<float> Heights(Rows * Cols);
	for (int R = 0; R < Rows; ++R)
	{
		const double D = -2.0 - (-300.0 + R * 2.0);   // metres past the bank's foot, downwind
		const float H = float(D < -10.0 ? -3.0 : (D > 0.0 ? 1.0 + 0.1 * D : -3.0 + 0.3 * (D + 10.0)));
		for (int Col = 0; Col < Cols; ++Col)
			Heights[R * Cols + Col] = H;
	}
	FLakeTerrain Terrain;
	Terrain.InitSynthetic(Rows, Cols, 2.0, -300.0, -100.0, Heights);
	FWindParams WP;
	WP.SpeedKnots = 13.0;
	WP.FromDegrees = 0.0;
	const FWindField Wind(WP);
	for (const bool bEasy : {false, true})
	{
		FBoatModel Boat(FBoatConfig::Make(EBoatType::Sunfish));
		Boat.SetTerrain(&Terrain);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FEasyAssists Easy;
		Easy.bEnabled = bEasy;
		Easy.ApplyTo(Boat.GetMutableConfig(), Boat.TotalMass());
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		Easy.ApplyTo(Trim.Settings);
		FEasyHelm Helm;
		FBoatControls Controls;
		bool bSane = true;
		double DivergedAt = -1.0;
		for (int I = 0; I < 60 * 120 && bSane; ++I)
		{
			const double Tiller = Controls.Tiller;
			Controls = Trim.Update(Boat, Controls, 1.0 / 120.0);
			Controls.Tiller = Tiller;
			Boat.Step(1.0 / 120.0, bEasy ? Helm.Update(Boat, Controls, Easy, 1.0 / 120.0) : Controls, Wind);
			const Vec3 O = Boat.OriginPosition();
			const Vec3 V = Boat.GetState().Velocity;
			bSane = std::isfinite(O.X) && std::isfinite(O.Y) && std::isfinite(O.Z) && std::isfinite(V.X) && V.Length() < 100.0
				&& std::fabs(O.X) < 1000.0 && std::fabs(O.Y) < 1000.0;
			if (!bSane)
				DivergedAt = I / 120.0;
		}
		TestTrue(FString::Printf(TEXT("%s Sunfish aground in irons stays finite and on the map for 60 s (went off at %.2f s)"),
			bEasy ? TEXT("Easy") : TEXT("Realistic"), DivergedAt), bSane);
	}
	return true;
}
