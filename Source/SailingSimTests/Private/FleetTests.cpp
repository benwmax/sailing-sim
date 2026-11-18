#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "PolarReference.h"
#include "AutoTrim.h"
#include "ShipHandling.h"
#include "ShipSailPlans.h"
#include "Waves.h"
#include "Async/ParallelFor.h"

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
// Bluebonnet's polar is estimated (Tools/shipkit/jclass/polar_bluebonnet.py: docs/jclass-13/), 20% at every point.
SAILING_FLEET_POLAR_TEST(FSailingPolarBluebonnet, "Bluebonnet", EBoatType::Bluebonnet)

/**
 * docs/frigate-physics/: the frigate Commonwealth against her estimated polar (polar_commonwealth.json), sailed as her
 * trial sails her: the fastest sail plan her officers would carry under the heel cap (ShipSailPlans.h), three minutes to
 * settle (she is slow to gather way) and 40 s averaged. The points run in parallel (each is a few plans of 220 s).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPolarCommonwealth, "SailingSim.Fleet.Polar.Commonwealth", Flags)
bool FSailingPolarCommonwealth::RunTest(const FString& Parameters)
{
	const FBoatConfig Config = FBoatConfig::Make(EBoatType::Commonwealth);
	TestTrue(TEXT("Commonwealth is square-rigged"), Config.HasSquareRig() && IsSquareRigged(EBoatType::Commonwealth));
	TestEqual(TEXT("Her eleven square sails (the frigate wiring's rig table keeps sails.json's order)"), int32(Config.Square.Sails.size()), 11);
	const std::vector<FPolarPoint>& Points = FleetReferencePolar(EBoatType::Commonwealth);
	TArray<FShipSteadyResult> Results;
	Results.SetNum(int32(Points.size()));
	ParallelFor(Results.Num(), [&](int32 I) { Results[I] = SailShipSteady(Config, Points[I].TrueWindKnots, Points[I].TrueWindAngleDeg); });
	AddInfo(TEXT("Commonwealth: TWS TWA polar model err% heel leeway plan"));
	double Worst = 0.0;
	for (int32 I = 0; I < Results.Num(); ++I)
	{
		const FPolarPoint& P = Points[I];
		const FSteadyResult& R = Results[I].R;
		const double Err = (R.BoatSpeedKnots - P.BoatSpeedKnots) / P.BoatSpeedKnots;
		Worst = FMath::Max(Worst, FMath::Abs(Err));
		AddInfo(FString::Printf(TEXT("%4.0f %5.1f %5.2f %5.2f %+5.1f %4.1f %4.1f  %hs"), P.TrueWindKnots, P.TrueWindAngleDeg, P.BoatSpeedKnots, R.BoatSpeedKnots,
			Err * 100.0, R.HeelDeg, R.LeewayDeg, ShipSailPlan(Results[I].Plan).Name));
		TestTrue(FString::Printf(TEXT("%.0f kn at %.0f deg within %.0f%% (%.2f vs %.2f kn)"), P.TrueWindKnots, P.TrueWindAngleDeg, P.Tolerance * 100.0,
			R.BoatSpeedKnots, P.BoatSpeedKnots), FMath::Abs(Err) <= P.Tolerance);
		TestTrue(FString::Printf(TEXT("%.0f kn at %.0f deg: under the heel cap"), P.TrueWindKnots, P.TrueWindAngleDeg), R.HeelDeg <= ShipHeelCapDeg(Config));
	}
	AddInfo(FString::Printf(TEXT("Worst error %.1f%%"), Worst * 100.0));
	return true;
}

namespace
{
	struct FShipOrderRun { double Done = -1.0, SpeedBefore = 0.0, SpeedAfter = 0.0, FinalTwa = 0.0; bool bMissed = false; EShipManoeuvre Ended = EShipManoeuvre::None; };

	/** docs/frigate-physics/: Commonwealth close-hauled on the starboard tack under all plain sail in the polar's lake chop,
	 *  settled three minutes, then the order; she is followed to a minute after Done (or 5 minutes hove to). */
	FShipOrderRun SailShipOrder(EShipManoeuvre What, double Tws)
	{
		const FBoatConfig C = FBoatConfig::Make(EBoatType::Commonwealth);
		const FWindField Wind = WindFrom(Tws, 0.0);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = Tws;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		const double Twa = 67.5;
		FBoatModel Boat(C);
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, FMath::Min(0.4 * Tws, 9.0) * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		Trim.Settings.bHike = false;
		FBoatControls Ctl;
		Ctl.MainSheet = Ctl.JibSheet = Twa / 180.0;
		ApplyShipSailPlan(C, 0, Ctl, false);
		for (int32 M = 0; M < kMaxMasts; ++M) Ctl.Brace[M] = 1.0;
		for (int32 I = 0; I < int32(C.Square.Sails.size()); ++I)
		{
			Boat.GetMutableState().YardAngle[I] = YardAngleFor(C.Square, I, 1.0);
			Boat.GetMutableState().SquareOut[I] = Ctl.SquareSet[I] == ESailSet::Set ? 1.0 : 0.0;
		}
		FShipHandling H;
		FShipOrderRun Out;
		const double Settle = 180.0, Limit = 1300.0;
		double SpeedSum = 0.0;
		int32 SpeedN = 0;
		bool bStarted = false;
		for (int32 I = 0; I < int32((Settle + Limit) * PhysicsHz); ++I)
		{
			const double Tm = I * PhysicsDt;
			if (!bStarted && Tm >= Settle)
			{
				H.Start(What, Boat);
				bStarted = true;
				Out.SpeedBefore = SpeedSum / FMath::Max(SpeedN, 1);
			}
			Ctl = Trim.Update(Boat, Ctl, PhysicsDt);
			const bool bHeld = bStarted && H.Update(Boat, Ctl, PhysicsDt);
			if (!bHeld)
			{
				if (bStarted) Pilot.TargetTWADeg = H.CourseAfterDeg();
				Ctl.Tiller = Pilot.Update(Boat);
			}
			Boat.Step(PhysicsDt, Ctl, Wind, &Waves);
			const double Kn = Boat.GetTelemetry().ForwardSpeed / kKnot;
			if (!bStarted)
			{
				if (Tm > Settle - 30.0) { SpeedSum += Kn; ++SpeedN; }
				continue;
			}
			const double Ts = Tm - Settle;
			if (H.Step() == EShipManoeuvreStep::MissedStays) Out.bMissed = true;
			const bool bHoveTo = What == EShipManoeuvre::HeaveTo && Ts >= 300.0;
			if (Out.Done < 0.0 && !H.IsActive() && What != EShipManoeuvre::HeaveTo) Out.Done = Ts;
			if (bHoveTo || (Out.Done >= 0.0 && Ts >= Out.Done + 60.0))
			{
				if (bHoveTo) Out.Done = Ts;
				Out.SpeedAfter = Kn;
				break;
			}
		}
		Out.FinalTwa = Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
		Out.Ended = H.Manoeuvre();
		return Out;
	}
}

/**
 * docs/frigate-physics/: Commonwealth's manoeuvres by orders (ShipHandling.h) on her own config, as the trial measured them
 * (Nov 17 2026): she tacks in 16 kn inside 6 minutes and in 24 kn inside 4; in 8 kn she misses stays, is boxed off and
 * wears instead, ending on the new tack inside 20 minutes (17.4 in the trial); she wears in 16 kn inside 4 minutes; hove to in 12 kn she lies near-stopped (under 1.5 kn).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShipManoeuvresTest, "SailingSim.Fleet.Ship.Manoeuvres", Flags)
bool FSailingShipManoeuvresTest::RunTest(const FString& Parameters)
{
	struct FCase { EShipManoeuvre What; double Tws; double MaxSeconds; bool bMayMiss; const TCHAR* Name; };
	const FCase Cases[] = {
		{ EShipManoeuvre::Tack, 16.0, 360.0, false, TEXT("tack, 16 kn") }, { EShipManoeuvre::Tack, 24.0, 240.0, false, TEXT("tack, 24 kn") },
		{ EShipManoeuvre::Tack, 8.0, 1200.0, true, TEXT("tack, 8 kn (missed stays: boxed off and wore)") }, { EShipManoeuvre::Wear, 16.0, 240.0, false, TEXT("wear, 16 kn") },
		{ EShipManoeuvre::HeaveTo, 12.0, 300.0, false, TEXT("heave to, 12 kn") },
	};
	TArray<FShipOrderRun> Runs;
	Runs.SetNum(UE_ARRAY_COUNT(Cases));
	ParallelFor(Runs.Num(), [&](int32 I) { Runs[I] = SailShipOrder(Cases[I].What, Cases[I].Tws); });
	for (int32 I = 0; I < Runs.Num(); ++I)
	{
		const FCase& K = Cases[I];
		const FShipOrderRun& R = Runs[I];
		AddInfo(FString::Printf(TEXT("%s: done %.0f s, %.2f kn before, %.2f a minute after, TWA %.1f%s"), K.Name, R.Done, R.SpeedBefore, R.SpeedAfter, R.FinalTwa,
			R.bMissed ? TEXT(" (missed stays: wore)") : TEXT("")));
		if (K.What == EShipManoeuvre::HeaveTo)
		{
			TestTrue(FString::Printf(TEXT("%s: lying near-stopped"), K.Name), FMath::Abs(R.SpeedAfter) < 1.5);
			TestTrue(FString::Printf(TEXT("%s: still on the starboard tack"), K.Name), R.FinalTwa > 0.0);
			continue;
		}
		TestTrue(FString::Printf(TEXT("%s: done inside %.0f s"), K.Name, K.MaxSeconds), R.Done >= 0.0 && R.Done <= K.MaxSeconds);
		TestTrue(FString::Printf(TEXT("%s: on the port tack after"), K.Name), R.FinalTwa < 0.0);
		TestTrue(FString::Printf(TEXT("%s: way on again"), K.Name), R.SpeedAfter > 0.5 * R.SpeedBefore);
		if (!K.bMayMiss) TestFalse(FString::Printf(TEXT("%s: without missing stays"), K.Name), R.bMissed);
		else TestTrue(FString::Printf(TEXT("%s: missed stays and wore"), K.Name), R.bMissed && R.Ended == EShipManoeuvre::Wear);
	}
	return true;
}

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
		{ EBoatType::Maxi, "Maxi 100", 25.0, 18.0, 0.0, 9.0 }, { EBoatType::Bluebonnet, "Bluebonnet", 25.0, 22.0, 0.0, 4.0 },
		{ EBoatType::Commonwealth, "Commonwealth", 25.0, 12.0, 0.0, 0.0 },
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
	TestEqual(TEXT("Every boat in the table"), int32(UE_ARRAY_COUNT(Want)), int32(EBoatType::Count));
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCapsizeTiltTest, "SailingSim.Fleet.KnockdownIsNotACapsize", Flags)
bool FSailingCapsizeTiltTest::RunTest(const FString& Parameters)
{
	// A ballasted keelboat counts as capsized only past her angle of vanishing stability (the J/22's ORC certificate
	// gives 104 deg light); dinghies and multihulls past 70 deg are over.
	for (EBoatType Type : { EBoatType::J22, EBoatType::Catalina22, EBoatType::Catalina30 })
	{
		const FBoatModel Boat(FBoatConfig::Make(Type));
		const double Deg = Boat.CapsizeTilt() * kRadToDeg;
		AddInfo(FString::Printf(TEXT("%hs: capsized past %.0f deg"), BoatTypeName(Type), Deg));
		TestTrue(FString::Printf(TEXT("%hs: a knockdown to 100 deg is not a capsize"), BoatTypeName(Type)), Deg > 100.0);
		TestTrue(FString::Printf(TEXT("%hs: still positive righting moment at the capsize tilt"), BoatTypeName(Type)), Boat.RightingMomentAt(Boat.CapsizeTilt()) > 0.0);
		TestTrue(FString::Printf(TEXT("%hs: gone just past it"), BoatTypeName(Type)), Boat.RightingMomentAt(Boat.CapsizeTilt() + 0.2 * kDegToRad) <= 0.0);
	}
	for (EBoatType Type : { EBoatType::Sunfish, EBoatType::ILCA7, EBoatType::Hobie16, EBoatType::Corsair880, EBoatType::Lagoon42 })
	{
		TestEqual(FString::Printf(TEXT("%hs: capsized past 70 deg"), BoatTypeName(Type)), FBoatModel(FBoatConfig::Make(Type)).CapsizeTilt() * kRadToDeg, 70.0, 1e-6);
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
