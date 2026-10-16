#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "PolarReference.h"
#include "Scenarios.h"
#include "Wind.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags PhysicsTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	void Run(FBoatModel& Boat, const FBoatControls& Controls, const FWindField& Wind, double Seconds)
	{
		for (int32 I = 0; I < FMath::RoundToInt(Seconds * PhysicsHz); ++I)
		{
			Boat.Step(PhysicsDt, Controls, Wind);
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFixedStepperTest, "SailingSim.Physics.FixedStepRate", PhysicsTestFlags)
bool FSailingFixedStepperTest::RunTest(const FString& Parameters)
{
	FFixedStepper Stepper;
	TestEqual(TEXT("Step rate is 120 Hz"), Stepper.GetStepDt(), 1.0 / 120.0);
	int32 Total = 0;
	for (int32 I = 0; I < 60; ++I) Total += Stepper.Advance(1.0 / 60.0);
	TestEqual(TEXT("One second at 60 fps runs 120 steps"), Total, 120);
	FFixedStepper Hitch;
	TestEqual(TEXT("A 2 s hitch is capped at 12 steps"), Hitch.Advance(2.0), 12);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingDeterminismTest, "SailingSim.Physics.DeterministicAndFrameRateIndependent", PhysicsTestFlags)
bool FSailingDeterminismTest::RunTest(const FString& Parameters)
{
	// Same seeded W1 wind (puffs, fine turbulence, shifts, an unstable afternoon), same controls, rendered at 30 fps and
	// 120 fps with the weather re-applied every frame as the game does: identical boat.
	auto Simulate = [](double Fps)
	{
		FWindParams WP;
		WP.SpeedKnots = 12.0;
		WP.GustIntensity = 0.14;
		WP.PuffIntensity = 0.1;
		WP.ShiftDegrees = 8.0;
		WP.PersistentShiftDegrees = 6.0;
		WP.AirMinusWaterC = -3.0;
		WP.MixedLayerMeters = 1500.0;
		WP.Seed = 42;
		FWindField Wind(WP);
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -50.0 * kDegToRad, 2.0);
		FFixedStepper Stepper;
		FBoatControls Controls;
		Controls.MainSheet = 0.2;
		Controls.JibSheet = 0.25;
		Controls.Tiller = 0.1;
		for (int32 F = 0; F < FMath::RoundToInt(10.0 * Fps); ++F)
		{
			Wind.SetParamsAt(WP, F / Fps, Boat.GetState().Position.X, Boat.GetState().Position.Y);
			const int32 Steps = Stepper.Advance(1.0 / Fps);
			for (int32 S = 0; S < Steps; ++S) Boat.Step(PhysicsDt, Controls, Wind);
		}
		return Boat.GetState();
	};
	const FBoatState A = Simulate(30.0);
	const FBoatState B = Simulate(120.0);
	TestEqual(TEXT("Position X matches"), A.Position.X, B.Position.X, 1e-9);
	TestEqual(TEXT("Position Y matches"), A.Position.Y, B.Position.Y, 1e-9);
	TestEqual(TEXT("Orientation matches"), A.Orientation.Z, B.Orientation.Z, 1e-12);
	TestTrue(TEXT("Boat actually sailed somewhere"), A.Position.LengthXY() > 10.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWindTest, "SailingSim.Physics.WindField", PhysicsTestFlags)
bool FSailingWindTest::RunTest(const FString& Parameters)
{
	FWindParams WP;
	WP.SpeedKnots = 10.0;
	WP.FromDegrees = 90.0; // from +Y
	const FWindField Steady(WP);
	const Vec3 At10 = Steady.VelocityAt(Vec3(0, 0, 10), 0.0);
	TestEqual(TEXT("10 kn at 10 m"), At10.Length() / kKnot, 10.0, 1e-6);
	TestTrue(TEXT("Blows toward -Y when coming from +Y"), At10.Y < 0.0 && FMath::Abs(At10.X) < 1e-9);
	TestTrue(TEXT("Less wind near the water (log profile)"), Steady.VelocityAt(Vec3(0, 0, 2), 0.0).Length() < 0.9 * At10.Length());
	TestTrue(TEXT("More wind aloft"), Steady.VelocityAt(Vec3(0, 0, 20), 0.0).Length() > At10.Length());

	// W1: stability bends the profile. Warm air over cool water: more wind aloft for the same 10 m wind; cold over warm
	// (well mixed): less.
	FWindParams Warm = WP, Cold = WP;
	Warm.AirMinusWaterC = 4.0;
	Cold.AirMinusWaterC = -6.0;
	const double Neutral20 = Steady.MeanSpeedAtHeight(20.0) / Steady.MeanSpeedAtHeight(10.0);
	const double Warm20 = FWindField(Warm).MeanSpeedAtHeight(20.0) / FWindField(Warm).MeanSpeedAtHeight(10.0);
	const double Cold20 = FWindField(Cold).MeanSpeedAtHeight(20.0) / FWindField(Cold).MeanSpeedAtHeight(10.0);
	AddInfo(FString::Printf(TEXT("20 m over 10 m: neutral %.3f, warm over cool %.3f, cold over warm %.3f"), Neutral20, Warm20, Cold20));
	TestTrue(TEXT("Stable air: steeper profile"), Warm20 > Neutral20 + 0.01);
	TestTrue(TEXT("Unstable air: flatter profile"), Cold20 < Neutral20 - 0.005);
	TestEqual(TEXT("10 m speed is the reference whatever the stability"), FWindField(Warm).MeanSpeedAtHeight(10.0) / kKnot, 10.0, 1e-9);

	WP.GustIntensity = 0.25;
	WP.ShiftDegrees = 10.0;
	WP.Seed = 7;
	const FWindField Gusty(WP);
	const FWindField Same(WP);
	double Sum = 0.0, Min = 1e9, Max = 0.0, MaxShift = 0.0;
	int32 N = 0;
	// Over the water at one time (the field's spatial mean is the mean wind), and in time at a point.
	for (int32 I = 0; I < 60; ++I)
	{
		for (int32 J = 0; J < 60; ++J)
		{
			const double G = Gusty.GustFactorAt(Vec3(I * 97.0, J * 113.0, 10), 500.0 + 3.0 * J);
			Sum += G; ++N;
			Min = FMath::Min(Min, G); Max = FMath::Max(Max, G);
		}
	}
	for (int32 I = 0; I < 2000; ++I)
	{
		const double T = I * 0.5;
		MaxShift = FMath::Max(MaxShift, FMath::Abs(Gusty.ShiftAt(Vec3(0, 0, 10), T)));
		if (I % 100 == 0)
		{
			TestEqual(TEXT("Same seed gives the same wind"), Gusty.VelocityAt(Vec3(5, 3, 6), T).X, Same.VelocityAt(Vec3(5, 3, 6), T).X, 1e-12);
		}
	}
	AddInfo(FString::Printf(TEXT("Gust factor over the water: mean %.3f, %.2f to %.2f; largest shift at a point %.1f deg"), Sum / N, Min, Max, MaxShift * kRadToDeg));
	TestEqual(TEXT("Gusts average out to the mean speed"), Sum / N, 1.0, 0.03);
	TestTrue(TEXT("Gusts and lulls of about +/-25%"), Max > 1.25 && Min < 0.8);
	TestTrue(TEXT("Shifts: the slow ones plus the puffs' veer and fan"), MaxShift * kRadToDeg > 10.0 && MaxShift * kRadToDeg < 60.0);

	// Frozen flow: the fine turbulence drifts downwind at the mean speed (puffs off), so a gust upwind arrives here later.
	FWindParams Fine = WP;
	Fine.PuffIntensity = 0.0;
	const FWindField FineOnly(Fine);
	const double Speed = 10.0 * kKnot;
	const Vec3 Upwind(0.0, 100.0, 10.0); // wind from +Y
	TestEqual(TEXT("Fine turbulence drifts downwind with the air"), FineOnly.GustFactorAt(Upwind, 0.0), FineOnly.GustFactorAt(Vec3(0, 0, 10), 100.0 / Speed), 1e-9);
	TestTrue(TEXT("It is there to drift"), FMath::Abs(FineOnly.GustFactorAt(Upwind, 0.0) - FineOnly.GustFactorAt(Vec3(0, 0, 10), 0.0)) > 1e-4);
	// The puffs drift faster, at the wind aloft, and a little veered.
	const Vec3 Drift = Gusty.PuffDrift();
	const double Aloft = Drift.LengthXY() / Speed;
	const double Veer = WrapAngle(std::atan2(Drift.Y, Drift.X) - std::atan2(-1.0, 0.0)) * kRadToDeg;
	AddInfo(FString::Printf(TEXT("Puffs drift at %.2f x the 10 m wind, %.1f deg veered"), Aloft, Veer));
	TestTrue(TEXT("Puffs drift faster than the surface wind"), Aloft > 1.1 && Aloft < 1.7);
	TestTrue(TEXT("... a few degrees to its right"), Veer > 3.0 && Veer < 15.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingFloatTest, "SailingSim.Physics.FloatsAndRights", PhysicsTestFlags)
bool FSailingFloatTest::RunTest(const FString& Parameters)
{
	FWindParams Calm;
	Calm.SpeedKnots = 0.0;
	const FWindField Wind(Calm);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, 0.0, 0.0);
	FBoatControls Controls;
	Controls.Hike = -0.5; // crew on the centerline
	Boat.GetMutableState().Position.Z += 0.2; // dropped 20 cm
	Run(Boat, Controls, Wind, 20.0);
	TestEqual(TEXT("Floats at its design waterline (within 2 cm)"), Boat.OriginPosition().Z, 0.0, 0.02);
	TestEqual(TEXT("Floats level in heel (within 0.5 deg)"), Boat.GetTelemetry().Heel * kRadToDeg, 0.0, 0.5);
	TestEqual(TEXT("Floats level in pitch (within 1 deg)"), Boat.GetTelemetry().Pitch * kRadToDeg, 0.0, 1.0);

	// Righting moment rises with heel, peaks well past 30 degrees, and is still positive on its side (ballasted keelboat).
	const double RM10 = Boat.RightingMomentAt(10.0 * kDegToRad);
	const double RM30 = Boat.RightingMomentAt(30.0 * kDegToRad);
	const double RM90 = Boat.RightingMomentAt(90.0 * kDegToRad);
	AddInfo(FString::Printf(TEXT("Righting moment: %.0f N m at 10 deg, %.0f at 30, %.0f at 90"), RM10, RM30, RM90));
	TestTrue(TEXT("Righting moment at 10 deg is plausible for a 22 ft keelboat (1.5 to 4 kN m)"), RM10 > 1500.0 && RM10 < 4000.0);
	TestTrue(TEXT("More righting moment at 30 deg than 10"), RM30 > RM10);
	TestTrue(TEXT("Still self-righting at 90 deg"), RM90 > 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPolarTest, "SailingSim.Physics.PolarGate", PhysicsTestFlags)
bool FSailingPolarTest::RunTest(const FString& Parameters)
{
	// Phase 1 gate: within 10 percent of the reference polar at every tested point (see PolarReference.h for sources).
	AddInfo(TEXT(" TWS   TWA  polar  model   err%  heel  leeway  helm  source"));
	double Worst = 0.0;
	for (const FPolarPoint& P : J22ReferencePolar())
	{
		const FSteadyResult R = SailSteady(P.TrueWindKnots, P.TrueWindAngleDeg);
		const double Err = (R.BoatSpeedKnots - P.BoatSpeedKnots) / P.BoatSpeedKnots * 100.0;
		Worst = FMath::Max(Worst, FMath::Abs(Err));
		AddInfo(FString::Printf(TEXT("%4.0f %5.1f  %5.2f  %5.2f  %+5.1f  %4.1f  %5.1f  %4.1f  %hs"), P.TrueWindKnots, P.TrueWindAngleDeg,
			P.BoatSpeedKnots, R.BoatSpeedKnots, Err, R.HeelDeg, R.LeewayDeg, R.RudderDeg, P.Note));
		TestTrue(FString::Printf(TEXT("%.0f kn at %.1f deg within 10%% of polar (%.2f vs %.2f kn)"), P.TrueWindKnots, P.TrueWindAngleDeg, R.BoatSpeedKnots, P.BoatSpeedKnots),
			FMath::Abs(Err) <= 10.0);
		// Plausible heel: under 25 degrees everywhere with a competent crew, and a keelboat never heels to windward much.
		TestTrue(FString::Printf(TEXT("Plausible heel at %.0f kn, %.1f deg (%.1f deg)"), P.TrueWindKnots, P.TrueWindAngleDeg, R.HeelDeg), R.HeelDeg >= 0.0 && R.HeelDeg < 25.0);
		// Leeway: a few degrees upwind, near zero downwind.
		TestTrue(FString::Printf(TEXT("Plausible leeway at %.0f kn, %.1f deg (%.1f deg)"), P.TrueWindKnots, P.TrueWindAngleDeg, R.LeewayDeg),
			R.LeewayDeg < (P.TrueWindAngleDeg < 70.0 ? 8.0 : 4.0));
		// Pointing too close to the wind is slower than the beat angle.
	}
	AddInfo(FString::Printf(TEXT("Worst error %.1f%%"), Worst));

	const FSteadyResult Pinching = SailSteady(10.0, 32.0);
	const FSteadyResult Beat = SailSteady(10.0, 40.9);
	TestTrue(TEXT("Pinching at 32 deg is slower than the beat angle"), Pinching.BoatSpeedKnots < Beat.BoatSpeedKnots);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingJ22RigTest, "SailingSim.Physics.J22RigPosition", PhysicsTestFlags)
bool FSailingJ22RigTest::RunTest(const FString& Parameters)
{
	// Boat kit phase 2: the J/22's mast stands where the class puts it, J = 8.8 ft (2.68 m) from the forestay tack to
	// the mast's front face, and both sails hang off it: the jib's tack at the stem, the main's luff on the mast's aft face.
	// The hero model's MastStep socket (Inputs/j22-hero) follows MastX.
	const Sailing::FBoatConfig C = Sailing::FBoatConfig::J22();
	const Sailing::FSailStripGeometry& J0 = C.Jib.Strips[0];
	const Sailing::FSailStripGeometry& J1 = C.Jib.Strips[1];
	const double Tack = J0.LuffX - 0.5 * (J1.LuffX - J0.LuffX);   // the luff carried down to the foot
	const double J = Tack - (C.MastX + 0.5 * C.MastDiameter);
	TestTrue(FString::Printf(TEXT("J %.3f m within 4 cm of the class's 2.682 m"), J), FMath::Abs(J - 2.682) < 0.04);
	const double MainLuff = C.Main.Strips[0].LuffX;
	TestTrue(FString::Printf(TEXT("Main luff %.3f m on the mast's aft face %.3f m"), MainLuff, C.MastX - 0.5 * C.MastDiameter),
		FMath::Abs(MainLuff - (C.MastX - 0.5 * C.MastDiameter)) < 0.03);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingJ22KeelContactTest, "SailingSim.Physics.J22KeelContact", PhysicsTestFlags)
bool FSailingJ22KeelContactTest::RunTest(const FString& Parameters)
{
	// Boat kit phase 3: the J/22 touches bottom under the drawn fin (the class keel template's foot, x -0.49 to +0.11 at
	// full draft), not under the keel's Center, which is a balance knob 45 cm further forward. The other boats' feet
	// stay under their foil centres.
	Sailing::FBoatModel Boat;
	const Sailing::FBoatConfig& C = Boat.GetConfig();
	const Sailing::FFoilDef* Keel = nullptr;
	for (const Sailing::FFoilDef& F : C.Foils) if (F.Role == Sailing::EFoilRole::Keel) Keel = &F;
	if (!TestNotNull(TEXT("The J/22 has a keel"), Keel)) return false;
	double MinX = 100.0, MaxX = -100.0, FootZ = 0.0;
	for (const Sailing::Vec3& P : Boat.GetBottomPoints())
	{
		if (P.Z > -C.Draft + 0.01) continue; // only the keel's foot reaches full draft
		MinX = FMath::Min(MinX, P.X); MaxX = FMath::Max(MaxX, P.X); FootZ = P.Z;
	}
	AddInfo(FString::Printf(TEXT("Keel foot x %.2f to %.2f m at z %.2f m; keel Center x %.2f m"), MinX, MaxX, FootZ, Keel->Params.Center.X));
	TestTrue(TEXT("Foot trailing edge at x -0.49 m"), FMath::Abs(MinX + 0.49) < 0.01);
	TestTrue(TEXT("Foot leading edge at x 0.11 m"), FMath::Abs(MaxX - 0.11) < 0.01);
	TestTrue(TEXT("Foot at full draft"), FMath::Abs(FootZ + C.Draft) < 0.01);
	TestTrue(TEXT("The balance knob is not where the boat touches bottom"), Keel->Params.Center.X > MaxX + 0.3);

	Sailing::FBoatModel Cat(Sailing::FBoatConfig::Make(Sailing::EBoatType::Catalina22));
	for (const Sailing::FFoilDef& F : Cat.GetConfig().Foils)
		TestFalse(TEXT("Other boats keep their feet under the foil centre"), F.HasContactFootprint());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHelmTest, "SailingSim.Physics.LeewayAndWeatherHelm", PhysicsTestFlags)
bool FSailingHelmTest::RunTest(const FString& Parameters)
{
	// Upwind in a breeze the boat makes leeway and carries weather helm; both come out of the forces, not a script.
	const FSteadyResult R = SailSteady(15.0, 45.0);
	AddInfo(FString::Printf(TEXT("15 kn, 45 deg: leeway %.1f deg, heel %.1f deg, helm %.1f N"), R.LeewayDeg, R.HeelDeg, R.HelmForceN));
	TestTrue(TEXT("Leeway 2 to 8 degrees close-hauled"), R.LeewayDeg > 2.0 && R.LeewayDeg < 8.0);
	TestTrue(TEXT("Weather helm: the tiller pulls toward rounding up"), R.HelmForceN > 0.0);

	// Let go of the tiller close-hauled in a breeze: weather helm rounds the boat up toward the wind.
	FWindParams WP;
	WP.SpeedKnots = 15.0;
	const FWindField Wind(WP);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 5.0 * kKnot);
	FAutopilot Pilot;
	Pilot.TargetTWADeg = 45.0;
	FAutoTrim Trim;
	FBoatControls C;
	C.MainSheet = C.JibSheet = 0.2;
	for (int32 I = 0; I < int32(30 * PhysicsHz); ++I)
	{
		C = Trim.Update(Boat, C, PhysicsDt);
		C.Tiller = Pilot.Update(Boat);
		Boat.Step(PhysicsDt, C, Wind);
	}
	const double Before = Boat.GetTelemetry().TrueWindAngle;
	// Let go: no hand on the tiller, so the rudder trails with the flow and stops holding the bow down.
	Boat.GetMutableConfig().HelmStiffness = 2.0;
	C.Tiller = 0.0;
	Run(Boat, C, Wind, 4.0);
	AddInfo(FString::Printf(TEXT("Tiller released: TWA %.1f -> %.1f deg"), Before * kRadToDeg, Boat.GetTelemetry().TrueWindAngle * kRadToDeg));
	TestTrue(TEXT("Released tiller: boat rounds up"), Boat.GetTelemetry().TrueWindAngle < Before - 3.0 * kDegToRad);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingTackTest, "SailingSim.Physics.TackTime", PhysicsTestFlags)
bool FSailingTackTest::RunTest(const FString& Parameters)
{
	for (const double Tws : { 6.0, 10.0, 15.0 })
	{
		const FTackResult R = RunTack(Tws);
		AddInfo(FString::Printf(TEXT("%.0f kn: tack %.1f s, %.2f -> min %.2f -> %.2f kn after 10 s"), Tws, R.TackSeconds, R.SpeedBeforeKnots, R.MinSpeedKnots, R.SpeedAfter10sKnots));
		TestTrue(FString::Printf(TEXT("Tack completes in %.0f kn"), Tws), R.bCompleted);
		// A J/22 tacks from close-hauled to close-hauled in roughly 4 to 10 seconds and keeps way through the turn.
		TestTrue(FString::Printf(TEXT("Tack time in a realistic range in %.0f kn (%.1f s)"), Tws, R.TackSeconds), R.TackSeconds > 4.0 && R.TackSeconds < 10.0);
		TestTrue(FString::Printf(TEXT("Keeps way through the tack in %.0f kn"), Tws), R.MinSpeedKnots > 0.4 * R.SpeedBeforeKnots);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingIronsTest, "SailingSim.Physics.InIrons", PhysicsTestFlags)
bool FSailingIronsTest::RunTest(const FString& Parameters)
{
	// Stopped head to wind with no way on: the sails luff, the boat drifts backward and the rudder can't help yet.
	const FIronsResult R = RunIrons(10.0, 8.0);
	AddInfo(FString::Printf(TEXT("After 8 s: TWA %.1f deg, forward speed %.2f kn"), R.FinalTWADeg, R.FinalForwardSpeedKnots));
	TestTrue(TEXT("Still pointing near the wind"), FMath::Abs(R.FinalTWADeg) < 25.0);
	TestTrue(TEXT("No forward way (drifting back)"), R.FinalForwardSpeedKnots <= 0.05 && R.MaxForwardSpeedKnots < 0.2);
	TestTrue(TEXT("Telemetry says in irons"), R.bInIronsAtEnd);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSailFlowTest, "SailingSim.Physics.LuffAndStall", PhysicsTestFlags)
bool FSailingSailFlowTest::RunTest(const FString& Parameters)
{
	// On a beam reach in 10 kn: sheets hard in stalls the sails; sheets all the way out luffs them.
	FWindParams WP;
	WP.SpeedKnots = 10.0;
	const FWindField Wind(WP);
	auto FlowWith = [&](double Sheet, ESailFlow Expect)
	{
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 5.0 * kKnot);
		FBoatControls C;
		C.MainSheet = C.JibSheet = Sheet;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 90.0;
		for (int32 I = 0; I < int32(10 * PhysicsHz); ++I)
		{
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind);
		}
		int32 Count = 0;
		const FBoatTelemetry& T = Boat.GetTelemetry();
		for (int32 I = 0; I < T.NumMainStrips; ++I) Count += T.MainStrips[I].Flow == Expect;
		for (int32 I = 0; I < T.NumJibStrips; ++I) Count += T.JibStrips[I].Flow == Expect;
		return Count;
	};
	TestTrue(TEXT("Over-trimmed on a reach: most strips stalled"), FlowWith(0.0, ESailFlow::Stalled) >= 5);
	TestTrue(TEXT("Fully eased on a reach: most strips luffing"), FlowWith(1.0, ESailFlow::Luffing) >= 5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingHullSpeedTest, "SailingSim.Physics.HullSpeedWall", PhysicsTestFlags)
bool FSailingHullSpeedTest::RunTest(const FString& Parameters)
{
	// J/22 LWL 19 ft: 1.34 * sqrt(19) = 5.84 kn. Reaching in 15 kn the boat goes a little past it but hits the wall:
	// doubling the wind to 30 kn on a beam reach adds well under a knot... check resistance rises steeply past it.
	FBoatModel Boat;
	const double HullSpeed = 1.34 * std::sqrt(Boat.GetConfig().WaterlineLength / kFoot);
	TestEqual(TEXT("J/22 hull speed"), HullSpeed, 5.84, 0.02);
	const FSteadyResult R15 = SailSteady(15.0, 90.0, FBoatConfig::J22(), false);
	const FSteadyResult R25 = SailSteady(25.0, 90.0, FBoatConfig::J22(), false);
	AddInfo(FString::Printf(TEXT("Beam reach: %.2f kn in 15 kn of wind, %.2f kn in 25"), R15.BoatSpeedKnots, R25.BoatSpeedKnots));
	TestTrue(TEXT("Past hull speed only modestly on a breezy reach"), R15.BoatSpeedKnots < HullSpeed * 1.25);
	TestTrue(TEXT("Hull-speed wall: 67% more wind gives under 15% more speed"), R25.BoatSpeedKnots < R15.BoatSpeedKnots * 1.15);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCalmStaysPutTest, "SailingSim.Physics.CalmDoesNotRockTheBoat", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FSailingCalmStaysPutTest::RunTest(const FString& Parameters)
{
	// No wind, no waves, sheets slack: she should lie still. (The crew used to follow the masthead's apparent wind,
	// which swings with the roll, and rocked her up to two knots.)
	FWindParams P;
	P.SpeedKnots = 0.0;
	const FWindField Calm(P);
	FBoatModel Boat;
	Boat.Reset(0.0, 0.0, 0.0, 0.0);
	FBoatControls C;
	C.MainSheet = 1.0;
	C.JibSheet = 1.0;
	// The crew's weight to one side gives her a steady list; rocking is the heel swinging, so measure its range
	// over the second half minute.
	double MinHeel = 1e9, MaxHeel = -1e9;
	for (int32 I = 0; I < int32(60.0 * PhysicsHz); ++I)
	{
		Boat.Step(PhysicsDt, C, Calm);
		if (I > int32(30.0 * PhysicsHz))
		{
			MinHeel = FMath::Min(MinHeel, Boat.GetTelemetry().Heel);
			MaxHeel = FMath::Max(MaxHeel, Boat.GetTelemetry().Heel);
		}
	}
	const double Speed = Boat.GetState().Velocity.LengthXY();
	const double Swing = FMath::RadiansToDegrees(MaxHeel - MinHeel);
	AddInfo(FString::Printf(TEXT("After a minute: %.3f m/s, heel %.1f to %.1f deg"), Speed, FMath::RadiansToDegrees(MinHeel), FMath::RadiansToDegrees(MaxHeel)));
	TestTrue(TEXT("Lies still (under 0.05 m/s)"), Speed < 0.05);
	TestTrue(TEXT("Does not rock (heel swings under 1 deg)"), Swing < 1.0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
