#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "PolarReference.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FWindField WindFrom(double Knots, double FromDeg)
	{
		FWindParams P;
		P.SpeedKnots = Knots;
		P.FromDegrees = FromDeg;
		return FWindField(P);
	}

	void Run(FBoatModel& Boat, const FBoatControls& Controls, const FWindField& Wind, double Seconds)
	{
		for (int32 I = 0; I < FMath::RoundToInt(Seconds * PhysicsHz); ++I) Boat.Step(PhysicsDt, Controls, Wind);
	}

	/** Sails every point of a boat's reference polar and checks it against the point's tolerance. */
	void CheckPolar(FAutomationTestBase& Test, EBoatType Type)
	{
		const FBoatConfig Config = FBoatConfig::Make(Type);
		Test.AddInfo(FString::Printf(TEXT("%hs: TWS TWA polar model err%% heel leeway"), Config.Name));
		double Worst = 0.0;
		for (const FPolarPoint& P : FleetReferencePolar(Type))
		{
			const FSteadyResult R = SailSteady(P.TrueWindKnots, P.TrueWindAngleDeg, Config, true, P.bSpinnaker);
			const double Err = (R.BoatSpeedKnots - P.BoatSpeedKnots) / P.BoatSpeedKnots;
			Worst = FMath::Max(Worst, FMath::Abs(Err));
			Test.AddInfo(FString::Printf(TEXT("%4.0f %5.1f%s %5.2f %5.2f %+5.1f %4.1f %4.1f  %hs"), P.TrueWindKnots, P.TrueWindAngleDeg, P.bSpinnaker ? TEXT("s") : TEXT(" "),
				P.BoatSpeedKnots, R.BoatSpeedKnots, Err * 100.0, R.HeelDeg, R.LeewayDeg, P.Note));
			Test.TestTrue(FString::Printf(TEXT("%.0f kn at %.0f deg within %.0f%% (%.2f vs %.2f kn)"), P.TrueWindKnots, P.TrueWindAngleDeg, P.Tolerance * 100.0,
				R.BoatSpeedKnots, P.BoatSpeedKnots), FMath::Abs(Err) <= P.Tolerance);
		}
		Test.AddInfo(FString::Printf(TEXT("Worst error %.1f%%"), Worst * 100.0));
	}
}

#define SAILING_FLEET_POLAR_TEST(Class, Name, Type) \
	IMPLEMENT_SIMPLE_AUTOMATION_TEST(Class, "SailingSim.Fleet.Polar." Name, Flags) \
	bool Class::RunTest(const FString& Parameters) { CheckPolar(*this, Type); return true; }

SAILING_FLEET_POLAR_TEST(FSailingPolarJ22, "J22", EBoatType::J22)
SAILING_FLEET_POLAR_TEST(FSailingPolarSunfish, "Sunfish", EBoatType::Sunfish)
SAILING_FLEET_POLAR_TEST(FSailingPolarILCA7, "ILCA7", EBoatType::ILCA7)
SAILING_FLEET_POLAR_TEST(FSailingPolarCatalina22, "Catalina22", EBoatType::Catalina22)
SAILING_FLEET_POLAR_TEST(FSailingPolarCatalina30, "Catalina30", EBoatType::Catalina30)
SAILING_FLEET_POLAR_TEST(FSailingPolarHobie16, "Hobie16", EBoatType::Hobie16)
SAILING_FLEET_POLAR_TEST(FSailingPolarCorsair880, "Corsair880", EBoatType::Corsair880)
SAILING_FLEET_POLAR_TEST(FSailingPolarLagoon42, "Lagoon42", EBoatType::Lagoon42)

/**
 * Each boat's own settings reach its config: #250 had a comment swallow the ILCA's C.TrimMaxEaseDeg and C.Name on the
 * same line, so she sailed with the default 25 deg ease and no name, and every measurement was of that boat. Every
 * Make(type) has its type, a non-empty name of its own, and its trim settings as Fleet.cpp gives them.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFleetConfigsTest, "SailingSim.Fleet.ConfigsComplete", Flags)
bool FSailingFleetConfigsTest::RunTest(const FString& Parameters)
{
	struct FWant { EBoatType Type; const char* Name; double MaxEase, HeelLimit, ReachHeelLimit, Traveler; };
	const FWant Want[] = {
		{ EBoatType::J22, "J/22", 25.0, 13.0, 0.0, 8.0 }, { EBoatType::Sunfish, "Sunfish", 60.0, 8.0, 0.0, 3.0 },
		{ EBoatType::ILCA7, "ILCA 7 (Laser)", 60.0, 8.0, 6.0, 4.0 }, { EBoatType::Catalina22, "Catalina 22", 25.0, 20.0, 0.0, 8.0 },
		{ EBoatType::Catalina30, "Catalina 30", 25.0, 22.0, 0.0, 8.0 }, { EBoatType::Hobie16, "Hobie 16", 45.0, 10.7, 0.0, 22.0 },
		{ EBoatType::Corsair880, "Corsair 880", 40.0, 10.0, 0.0, 15.0 }, { EBoatType::Lagoon42, "Lagoon 42", 35.0, 4.0, 0.0, 12.0 },
		{ EBoatType::Maxi, "Maxi 100", 25.0, 18.0, 0.0, 9.0 },
	};
	TSet<FString> Names;
	for (const FWant& W : Want)
	{
		const FBoatConfig C = FBoatConfig::Make(W.Type);
		const FString Name = UTF8_TO_TCHAR(C.Name ? C.Name : "");
		TestTrue(FString::Printf(TEXT("%hs: its own type"), W.Name), C.Type == W.Type);
		TestEqual(FString::Printf(TEXT("%hs: its name"), W.Name), Name, FString(UTF8_TO_TCHAR(W.Name)));
		TestFalse(FString::Printf(TEXT("%hs: a name no other boat has"), W.Name), Name.IsEmpty() || Names.Contains(Name));
		Names.Add(Name);
		TestEqual(FString::Printf(TEXT("%hs: TrimMaxEaseDeg"), W.Name), C.TrimMaxEaseDeg, W.MaxEase);
		TestEqual(FString::Printf(TEXT("%hs: TrimHeelLimitDeg"), W.Name), C.TrimHeelLimitDeg, W.HeelLimit);
		TestEqual(FString::Printf(TEXT("%hs: TrimReachHeelLimitDeg"), W.Name), C.TrimReachHeelLimitDeg, W.ReachHeelLimit);
		TestEqual(FString::Printf(TEXT("%hs: TravelerRangeDeg"), W.Name), C.TravelerRangeDeg, W.Traveler);
	}
	TestEqual(TEXT("Every boat in the table"), int32(UE_ARRAY_COUNT(Want)), int32(EBoatType::Maxi) + 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingDinghyCapsizeTest, "SailingSim.Fleet.DinghyCapsizeAndRighting", Flags)
bool FSailingDinghyCapsizeTest::RunTest(const FString& Parameters)
{
	// 20 kn on a beam reach, course held, the sheet cleated and the sailor sitting in: she is knocked flat. The ILCA
	// stays over until the sailor climbs onto the daggerboard with the sail let go. (The Sunfish's low lateen tends to
	// lift her back up on its own: a known gap, see the README.)
	for (EBoatType Type : { EBoatType::ILCA7, EBoatType::Sunfish })
	{
		FBoatModel Boat(FBoatConfig::Make(Type));
		const FWindField Wind = WindFrom(20.0, 0.0);
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 2.0);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 90.0;
		FBoatControls C;
		C.MainSheet = 0.05;
		C.Hike = -1.0;
		double MaxHeel = 0.0;
		for (int32 I = 0; I < int32(20 * PhysicsHz); ++I)
		{
			if (FMath::Abs(Boat.GetTelemetry().Heel) < 45.0 * kDegToRad) C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			MaxHeel = FMath::Max(MaxHeel, FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg);
		}
		AddInfo(FString::Printf(TEXT("%hs: knocked to %.0f deg, capsized %d"), BoatTypeName(Type), MaxHeel, Boat.GetTelemetry().bCapsized));
		TestTrue(FString::Printf(TEXT("%hs is knocked flat when overpowered"), BoatTypeName(Type)), MaxHeel > 65.0);
		if (Type != EBoatType::ILCA7) continue;
		TestTrue(TEXT("ILCA 7 stays capsized"), Boat.GetTelemetry().bCapsized);
		C.bRighting = true;
		C.MainSheet = 1.0;
		double Seconds = 0.0;
		while (Seconds < 60.0 && FMath::Abs(Boat.GetTelemetry().Heel) > 30.0 * kDegToRad) { Run(Boat, C, Wind, 0.5); Seconds += 0.5; }
		AddInfo(FString::Printf(TEXT("  righted in %.1f s"), Seconds));
		TestTrue(TEXT("ILCA 7 is righted from the daggerboard"), FMath::Abs(Boat.GetTelemetry().Heel) <= 30.0 * kDegToRad);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingKeelboatKnockdownTest, "SailingSim.Fleet.KeelboatsRecoverFromKnockdown", Flags)
bool FSailingKeelboatKnockdownTest::RunTest(const FString& Parameters)
{
	// Sheets cleated hard on a beam reach in 25 kn: a ballasted keelboat is knocked well over but does not capsize,
	// and comes upright once the sheets are let go.
	for (EBoatType Type : { EBoatType::J22, EBoatType::Catalina22, EBoatType::Catalina30 })
	{
		FBoatModel Boat(FBoatConfig::Make(Type));
		const FWindField Wind = WindFrom(25.0, 0.0);
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 2.0);
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.05;
		double MaxHeel = 0.0;
		bool bCapsized = false;
		for (int32 I = 0; I < int32(40 * PhysicsHz); ++I)
		{
			Boat.Step(PhysicsDt, C, Wind);
			MaxHeel = FMath::Max(MaxHeel, FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg);
			bCapsized |= Boat.GetTelemetry().bCapsized;
		}
		C.MainSheet = C.JibSheet = 1.0;
		Run(Boat, C, Wind, 20.0);
		const double After = FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg;
		AddInfo(FString::Printf(TEXT("%hs: knocked down to %.0f deg, %.0f deg after easing"), BoatTypeName(Type), MaxHeel, After));
		TestTrue(FString::Printf(TEXT("%hs knocked down hard"), BoatTypeName(Type)), MaxHeel > 40.0);
		TestFalse(FString::Printf(TEXT("%hs does not capsize"), BoatTypeName(Type)), bCapsized);
		TestTrue(FString::Printf(TEXT("%hs comes back up"), BoatTypeName(Type)), After < 25.0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingMultihullTest, "SailingSim.Fleet.MultihullFliesAHullAndCapsizes", Flags)
bool FSailingMultihullTest::RunTest(const FString& Parameters)
{
	// Hobie 16, well sailed in 15 kn upwind: the windward hull flies some of the time, and she stays upright.
	const FBoatConfig Config = FBoatConfig::Make(EBoatType::Hobie16);
	{
		FBoatModel Boat(Config);
		const FWindField Wind = WindFrom(15.0, 0.0);
		Boat.Reset(0.0, 0.0, -50.0 * kDegToRad, 4.0);
		Boat.GetMutableState().WindwardSide = 1;
		Boat.GetMutableState().CrewOffset = Config.CrewSitOut;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 50.0;
		FAutoTrim Trim;
		FBoatControls C;
		C.Hike = 1.0;
		double Flying = 0.0;
		bool bCapsized = false;
		for (int32 I = 0; I < int32(60 * PhysicsHz); ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			if (I > 20 * PhysicsHz && Boat.GetTelemetry().bFlyingHull) Flying += PhysicsDt;
			bCapsized |= Boat.GetTelemetry().bCapsized;
		}
		AddInfo(FString::Printf(TEXT("15 kn upwind: flying a hull %.0f%% of the time, %.1f kn"), Flying / 40.0 * 100.0, Boat.GetTelemetry().BoatSpeed / kKnot));
		TestTrue(TEXT("Flies a hull in 15 kn"), Flying > 1.0);
		TestFalse(TEXT("Does not capsize when sailed well"), bCapsized);
	}
	// Sheets cleated, crew sitting in, 20 kn on the beam: past the tipping point she goes over. Crew on the righting
	// line with the sheets free brings her back.
	{
		FBoatModel Boat(Config);
		const FWindField Wind = WindFrom(20.0, 0.0);
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 4.0);
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.0;
		C.Hike = -1.0;
		Run(Boat, C, Wind, 20.0);
		TestTrue(TEXT("Capsizes past the tipping point"), Boat.GetTelemetry().bCapsized);
		C.bRighting = true;
		C.MainSheet = C.JibSheet = 1.0;
		double Seconds = 0.0;
		while (Seconds < 90.0 && FMath::Abs(Boat.GetTelemetry().Heel) > 20.0 * kDegToRad) { Run(Boat, C, Wind, 0.5); Seconds += 0.5; }
		AddInfo(FString::Printf(TEXT("Righted in %.1f s"), Seconds));
		TestTrue(TEXT("Righted on the righting line"), FMath::Abs(Boat.GetTelemetry().Heel) <= 20.0 * kDegToRad);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPlaningTest, "SailingSim.Fleet.DinghyPlanes", Flags)
bool FSailingPlaningTest::RunTest(const FString& Parameters)
{
	// ILCA 7 on a broad reach in 15 kn: up on the plane, well past the displacement hull speed (5.2 kn).
	const FSteadyResult Plane = SailSteady(15.0, 110.0, FBoatConfig::Make(EBoatType::ILCA7), false);
	const FSteadyResult Light = SailSteady(6.0, 110.0, FBoatConfig::Make(EBoatType::ILCA7), false);
	AddInfo(FString::Printf(TEXT("15 kn: %.1f kn; 6 kn: %.1f kn"), Plane.BoatSpeedKnots, Light.BoatSpeedKnots));
	TestTrue(TEXT("Planes past 1.5 x hull speed in 15 kn"), Plane.BoatSpeedKnots > 1.5 * 1.34 * FMath::Sqrt(3.81 / kFoot));
	TestTrue(TEXT("Displacement sailing in 6 kn"), Light.BoatSpeedKnots < 1.34 * FMath::Sqrt(3.81 / kFoot));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSpinnakerReefTest, "SailingSim.Fleet.SpinnakerAndReefing", Flags)
bool FSailingSpinnakerReefTest::RunTest(const FString& Parameters)
{
	// The spinnaker pays downwind; a reef cuts heel in a breeze.
	const FSteadyResult Plain = SailSteady(10.0, 135.0, FBoatConfig::J22(), false, false);
	const FSteadyResult Spin = SailSteady(10.0, 135.0, FBoatConfig::J22(), false, true);
	AddInfo(FString::Printf(TEXT("J/22 10 kn at 135: %.2f kn plain, %.2f kn with the spinnaker"), Plain.BoatSpeedKnots, Spin.BoatSpeedKnots));
	TestTrue(TEXT("Spinnaker is at least 4% faster downwind"), Spin.BoatSpeedKnots > 1.04 * Plain.BoatSpeedKnots);

	double Heel[3] = { 0, 0, 0 };
	double Area[3] = { 0, 0, 0 };
	for (int32 Reef = 0; Reef <= 2; Reef += 2)
	{
		const FBoatConfig Config = FBoatConfig::Make(EBoatType::Catalina30);
		FBoatModel Boat(Config);
		const FWindField Wind = WindFrom(22.0, 0.0);
		Boat.Reset(0.0, 0.0, -60.0 * kDegToRad, 3.0);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 60.0;
		// The boat's own answer to her sail area, trimmed as the polars are (docs/trimmer-hands/): a crew's hands hold her at
		// the heel limit with either sail.
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FBoatControls C;
		int32 N = 0;
		for (int32 I = 0; I < int32(60 * PhysicsHz); ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Reef = Reef;
			C.MainSheet = 0.15; // same sheet both runs: the reef alone makes the difference
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
			if (I > 30 * PhysicsHz) { Heel[Reef] += FMath::Abs(Boat.GetTelemetry().Heel) * kRadToDeg; ++N; }
		}
		Heel[Reef] /= N;
		Area[Reef] = Boat.GetConfig().Main.TotalArea;
	}
	AddInfo(FString::Printf(TEXT("Catalina 30, 22 kn at 60: heel %.1f deg full main (%.1f m^2), %.1f deg with two reefs (%.1f m^2)"), Heel[0], Area[0], Heel[2], Area[2]));
	TestTrue(TEXT("Two reefs shrink the main by a third or more"), Area[2] < 0.67 * Area[0]);
	TestTrue(TEXT("Two reefs cut the heel"), Heel[2] < Heel[0] - 2.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingEngineTest, "SailingSim.Fleet.Engines", Flags)
bool FSailingEngineTest::RunTest(const FString& Parameters)
{
	// Motoring in a calm: realistic speed ahead, slower astern, and twin engines that pivot the Lagoon in place.
	struct FExpect { EBoatType Type; double MinKnots, MaxKnots; };
	for (const FExpect& E : { FExpect{ EBoatType::Catalina22, 4.5, 6.0 }, FExpect{ EBoatType::Catalina30, 5.0, 6.8 }, FExpect{ EBoatType::Corsair880, 5.5, 7.5 },
		FExpect{ EBoatType::Lagoon42, 7.0, 9.0 } })
	{
		FBoatModel Boat(FBoatConfig::Make(E.Type));
		const FWindField Calm = WindFrom(0.01, 0.0);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls C;
		C.MainSheet = C.JibSheet = 1.0;
		C.Throttle = 1.0;
		Run(Boat, C, Calm, 90.0);
		const double Ahead = Boat.GetTelemetry().ForwardSpeed / kKnot;
		C.Throttle = -1.0;
		Run(Boat, C, Calm, 60.0);
		const double Astern = -Boat.GetTelemetry().ForwardSpeed / kKnot;
		AddInfo(FString::Printf(TEXT("%hs: %.1f kn ahead, %.1f kn astern"), BoatTypeName(E.Type), Ahead, Astern));
		TestTrue(FString::Printf(TEXT("%hs motors at a realistic speed"), BoatTypeName(E.Type)), Ahead >= E.MinKnots && Ahead <= E.MaxKnots);
		TestTrue(FString::Printf(TEXT("%hs goes astern, slower than ahead"), BoatTypeName(E.Type)), Astern > 1.0 && Astern < 0.75 * Ahead);
	}
	{
		FBoatModel Boat(FBoatConfig::Make(EBoatType::Lagoon42));
		const FWindField Calm = WindFrom(0.01, 0.0);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		FBoatControls C;
		C.ThrottleSplit = 0.8;
		Run(Boat, C, Calm, 30.0);
		const double Yaw = Boat.GetState().AngularVelocity.Z * kRadToDeg;
		AddInfo(FString::Printf(TEXT("Lagoon 42 split throttle: turning %.1f deg/s at %.2f kn"), Yaw, Boat.GetTelemetry().BoatSpeed / kKnot));
		TestTrue(TEXT("Twin engines pivot the boat"), Yaw > 3.0 && Boat.GetTelemetry().BoatSpeed < 1.5 * kKnot);
	}
	return true;
}

#endif
