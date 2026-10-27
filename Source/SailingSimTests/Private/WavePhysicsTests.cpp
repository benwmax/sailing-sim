#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "EasyAssists.h"
#include "FixedStepper.h"
#include "SeaTrials.h"
#include "Waves.h"
#include "Wind.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// Wave physics (docs/wave-physics/): added resistance scaled by size, and the waves' slope push (surfing).
namespace WavePhysicsTestsLocal
{
	constexpr EAutomationTestFlags WaveFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	/** ORC's VPP sea: a 5 s wind sea (Hs 1 m here) in 16 kn, no lake chop. */
	FTrialSeaSpec OrcSea()
	{
		FTrialSeaSpec S;
		S.WindKnots = 16.0;
		S.FetchMeters = 1.0;
		S.bOcean = true;
		S.Ocean.WindMs = 16.0 * kKnot;
		S.Ocean.WindFromRad = 0.0;
		S.Ocean.WindSeaHs = 1.0;
		S.Ocean.WindSeaTp = 5.0;
		S.Ocean.SwellHs = 0.0;
		return S;
	}

	/** The Gulf off Galveston in 12 kn from the south: its wind sea and a 1.2 m, 9 s swell from the southeast. */
	FTrialSeaSpec GulfSea(double WindKnots = 12.0)
	{
		FTrialSeaSpec S;
		S.WindKnots = WindKnots;
		S.WindFromDeg = 180.0;
		S.FetchMeters = 1.0;
		S.bOcean = true;
		S.Ocean.WindMs = FMath::Max(WindKnots, 1.0) * kKnot;
		S.Ocean.WindFromRad = kPi;
		S.Ocean.SwellHs = 1.2;
		S.Ocean.SwellTp = 9.0;
		S.Ocean.SwellFromRad = 135.0 * kDegToRad;
		return S;
	}

	FBoatConfig WithPush(EBoatType Type, double Scale)
	{
		FBoatConfig C = FBoatConfig::Make(Type);
		C.WaveSlopeForceScale = Scale;
		return C;
	}
}

/**
 * Added resistance by size: in ORC's sea each keelboat's added resistance against the J/22's is ORC's (VPP 2023 eq. 6.62,
 * its 16 kn sea and length baselines; the log in f(L30) read either way): Catalina 22 0.79, Catalina 30 1.23 to 1.36,
 * a 97 ft maxi 2.78 to 4.12. The J/22's own number is her polar's (SailingSim.Physics.PolarGate).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveAddedResistanceScalingTest, "SailingSim.Physics.WaveAddedResistanceScaling", WavePhysicsTestsLocal::WaveFlags)
bool FSailingWaveAddedResistanceScalingTest::RunTest(const FString&)
{
	using namespace WavePhysicsTestsLocal;
	const FSeaRunResult J22 = RunInSea(FBoatConfig::Make(EBoatType::J22), OrcSea(), 45.0, 0, false, 30.0, 120.0);
	TestTrue(TEXT("The J/22 meets added resistance in ORC's sea"), J22.MeanWaveN > 50.0);
	struct FCase { EBoatType Type; double Low, High; };
	for (const FCase& K : { FCase{ EBoatType::Catalina22, 0.6, 1.05 }, FCase{ EBoatType::Catalina30, 1.1, 1.5 }, FCase{ EBoatType::Maxi, 2.5, 4.5 } })
	{
		const FSeaRunResult R = RunInSea(FBoatConfig::Make(K.Type), OrcSea(), 45.0, 0, false, 30.0, 120.0);
		const double Ratio = R.MeanWaveN / FMath::Max(J22.MeanWaveN, 1.0);
		AddInfo(FString::Printf(TEXT("%hs: %.0f N at %.2f kn, %.2f x the J/22's %.0f N"), BoatTypeName(K.Type), R.MeanWaveN, R.MeanKnots, Ratio, J22.MeanWaveN));
		TestTrue(FString::Printf(TEXT("%hs within ORC's scaling (%.2f in %.2f..%.2f)"), BoatTypeName(K.Type), Ratio, K.Low, K.High), Ratio >= K.Low && Ratio <= K.High);
	}

	// Flat water: no added resistance and no push, step by step.
	FBoatModel Boat(FBoatConfig::Make(EBoatType::J22));
	FWindParams P;
	P.SpeedKnots = 12.0;
	const FWindField Wind(P);
	FWaveField Flat(1);
	Boat.Reset(0.0, 0.0, -45.0 * kDegToRad, 5.0 * kKnot);
	FBoatControls C;
	C.MainSheet = C.JibSheet = 0.25;
	double MaxWave = 0.0, MaxPush = 0.0;
	for (int32 I = 0; I < int32(20.0 * PhysicsHz); ++I)
	{
		Boat.Step(PhysicsDt, C, Wind, &Flat);
		MaxWave = FMath::Max(MaxWave, FMath::Abs(Boat.GetTelemetry().WaveResistance));
		MaxPush = FMath::Max(MaxPush, FMath::Abs(Boat.GetTelemetry().WaveSlopeSurge));
	}
	TestTrue(FString::Printf(TEXT("Flat water: no added resistance (%.3g N)"), MaxWave), MaxWave == 0.0);
	TestTrue(FString::Printf(TEXT("Flat water: no slope push (%.3g N)"), MaxPush), MaxPush == 0.0);
	return true;
}

/**
 * The prologue's gale (step 4: the mistral, Hs 3.5 m at 7 s on the Gulf stand-in, 32 kn, two reefs, the scene's limits):
 * the maxi tacks on the wheel (SailingSim.Prologue.Gale's helm) at least 5 times in 6, and beats 1 to 10% slower than on
 * flat water (before docs/wave-physics/ she made 5.8 kn against 12.3 and tacked 0 of 36). The band is ORC's (docs/surfing/):
 * her coefficient from ORC's length scaling, over this 7 s sea's spectrum, costs her 3.0% alone (1.4 to 3.6% across its log
 * reading); she loses 4% with the slope push and orbital flow (9% before the flow, which carried a false creep downwave).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGaleTackTest, "SailingSim.Physics.GaleTack", WavePhysicsTestsLocal::WaveFlags)
bool FSailingGaleTackTest::RunTest(const FString&)
{
	FBoatConfig Maxi = FBoatConfig::Make(EBoatType::Maxi);
	FSceneLimits::For(true).ApplyTo(Maxi);
	int32 InSea = 0, Flat = 0;
	TArray<FString> Times;
	for (uint32 Seed = 1; Seed <= 6; ++Seed)
	{
		const double W = RunGaleTack(Maxi, 2, Seed, true), F = RunGaleTack(Maxi, 2, Seed, false);
		InSea += W > 0.0;
		Flat += F > 0.0;
		Times.Add(FString::Printf(TEXT("%.1f/%.1f"), W, F));
	}
	AddInfo(FString::Printf(TEXT("Tacks in the gale, seconds in the sea / on flat water (-1: not through in 90 s): %s"), *FString::Join(Times, TEXT(", "))));
	TestTrue(FString::Printf(TEXT("She tacks in the gale's sea (%d of 6)"), InSea), InSea >= 5);
	TestTrue(FString::Printf(TEXT("... and on flat water (%d of 6)"), Flat), Flat == 6);
	const FSeaRunResult Sea = RunInSea(Maxi, FTrialSeaSpec::Gale(1), 50.0, 2, false, 30.0, 120.0);
	const FSeaRunResult Calm = RunInSea(Maxi, FTrialSeaSpec::Gale(1, 32.0, false), 50.0, 2, false, 30.0, 120.0);
	const double Loss = 1.0 - Sea.MeanKnots / Calm.MeanKnots;
	AddInfo(FString::Printf(TEXT("Beating at TWA 50: %.2f kn in the sea (added resistance %.0f N, calm %.0f N), %.2f flat"), Sea.MeanKnots, Sea.MeanWaveN, Sea.MeanCalmN, Calm.MeanKnots));
	// 1 to 10%: under ORC's low reading (1.4%) to about three times its central 3.0% for the push and flow on top.
	TestTrue(FString::Printf(TEXT("The sea costs her 1 to 10%% upwind (%.1f%%)"), Loss * 100.0), Loss > 0.01 && Loss < 0.10);
	return true;
}

/**
 * Surfing: the waves' slope pushes her down a face and holds her on a back, and gives nothing for free. A J/22 running at
 * TWA 150 on the Gulf swell surfs (her best second 1.5 kn over the run without the push, a little faster on average);
 * the maxi running in the gale is faster than on flat water and peaks past 23 kn; the ILCA in 20 kn of lake chop rides
 * it to a higher peak. Adrift on the swell (no wind) the push averages out to nothing and she goes nowhere.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSurfingTest, "SailingSim.Physics.Surfing", WavePhysicsTestsLocal::WaveFlags)
bool FSailingSurfingTest::RunTest(const FString&)
{
	using namespace WavePhysicsTestsLocal;
	const FSeaRunResult J = RunInSea(WithPush(EBoatType::J22, 1.0), GulfSea(), 150.0, 0, false, 30.0, 240.0);
	const FSeaRunResult J0 = RunInSea(WithPush(EBoatType::J22, 0.0), GulfSea(), 150.0, 0, false, 30.0, 240.0);
	AddInfo(FString::Printf(TEXT("J/22 on the Gulf swell, TWA 150: %.2f kn (best second %.2f) with the push, %.2f (%.2f) without; on a face %+.2f m/s2, on a back %+.2f"),
		J.MeanKnots, J.MaxKnots, J0.MeanKnots, J0.MaxKnots, J.FaceAccel, J.BackAccel));
	TestTrue(TEXT("She speeds up on a face"), J.FaceAccel > 0.1);
	TestTrue(TEXT("... and slows on a back"), J.BackAccel < -0.1);
	TestTrue(TEXT("Surfing: her best second 1.5 kn over the run without the push"), J.MaxKnots > J0.MaxKnots + 1.5);
	TestTrue(TEXT("... and no slower on average (within -2% to +15%)"), J.MeanKnots > 0.98 * J0.MeanKnots && J.MeanKnots < 1.15 * J0.MeanKnots);

	FBoatConfig Maxi = FBoatConfig::Make(EBoatType::Maxi);
	FSceneLimits::For(true).ApplyTo(Maxi);
	const FSeaRunResult M = RunInSea(Maxi, FTrialSeaSpec::Gale(1), 150.0, 2, false, 30.0, 120.0);
	const FSeaRunResult M0 = RunInSea(Maxi, FTrialSeaSpec::Gale(1, 32.0, false), 150.0, 2, false, 30.0, 120.0);
	AddInfo(FString::Printf(TEXT("Maxi running in the gale, TWA 150: %.2f kn (seconds %.1f to %.1f) against %.2f flat (%.1f to %.1f); mean push %+.0f N"),
		M.MeanKnots, M.MinKnots, M.MaxKnots, M0.MeanKnots, M0.MinKnots, M0.MaxKnots, M.MeanSurgeN));
	TestTrue(TEXT("The maxi runs faster in the gale's sea than on flat water"), M.MeanKnots > M0.MeanKnots);
	TestTrue(TEXT("... surfing past 23 kn (a 30 m maxi has logged 33 in 30-35 kn and big seas)"), M.MaxKnots > 23.0);

	FTrialSeaSpec Chop;
	Chop.WindKnots = 20.0;
	Chop.bCalibrationSea = true;
	const FSeaRunResult L = RunInSea(WithPush(EBoatType::ILCA7, 1.0), Chop, 150.0, 0, false, 30.0, 240.0);
	const FSeaRunResult L0 = RunInSea(WithPush(EBoatType::ILCA7, 0.0), Chop, 150.0, 0, false, 30.0, 240.0);
	AddInfo(FString::Printf(TEXT("ILCA in 20 kn of lake chop, TWA 150: %.2f kn (best second %.2f) with the push, %.2f (%.2f) without"), L.MeanKnots, L.MaxKnots, L0.MeanKnots, L0.MaxKnots));
	TestTrue(TEXT("The ILCA rides the chop to a higher peak"), L.MaxKnots > L0.MaxKnots + 0.3);

	// Adrift on the swell (no wind): the push oscillates with the waves and averages out. (What she makes good comes from
	// her keel sculling as she rolls, a known gap: docs/wave-physics/.)
	FTrialSeaSpec Swell = GulfSea(0.0);
	Swell.Ocean.WindMs = 0.5;
	const FSeaRunResult D = RunInSea(WithPush(EBoatType::J22, 1.0), Swell, 90.0, 0, false, 30.0, 300.0);
	AddInfo(FString::Printf(TEXT("Adrift on the swell: mean push %+.2f N, she made good %.2f kn"), D.MeanSurgeN, D.NetKnots));
	TestTrue(FString::Printf(TEXT("Adrift, the push averages out (%.2f N)"), D.MeanSurgeN), FMath::Abs(D.MeanSurgeN) < 5.0);
	return true;
}

/**
 * docs/surfing/: the waves' orbital flow past the hull, keels and rudders. The field's horizontal velocity is linear
 * theory's: forward under the crests (in phase with the height along the waves' travel), falling off with depth, and in
 * shallow water reaching the bottom. Then the references: a J/22 on a following 2 m wind sea in 20 kn surfs in bursts of
 * 1.5 to 2 times her hull speed on the steep faces; the maxi reaches past 20 kn on the gale's 3.5 m quartering sea; upwind
 * on flat water nothing changes. With the flow, the rudder meets less water on a face, so she yaws off course more there.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSurfingFlowTest, "SailingSim.Physics.SurfingFlow", WavePhysicsTestsLocal::WaveFlags)
bool FSailingSurfingFlowTest::RunTest(const FString&)
{
	using namespace WavePhysicsTestsLocal;
	auto Statistics = [](const FWaveField& W, double Below, double& OutCorr, double& OutRms)
	{
		const double Dir = W.MeanDirection();
		double HU = 0.0, HH = 0.0, UU = 0.0;
		for (int I = 0; I < 6000; ++I)
		{
			const double T = 0.1 * I;
			double U, V;
			W.OrbitalVelocity(3.0, 7.0, T, Below, U, V);
			const double Along = U * FMath::Cos(Dir) + V * FMath::Sin(Dir);
			const double H = W.Height(3.0, 7.0, T);
			HU += H * Along; HH += H * H; UU += Along * Along;
		}
		OutCorr = HU / FMath::Sqrt(FMath::Max(HH * UU, 1e-12));
		OutRms = FMath::Sqrt(UU / 6000.0);
	};
	FWaveParams P;
	P.WindSpeedKnots = 18.0;
	P.FetchMeters = 15000.0;
	FWaveField Deep;
	Deep.SetWind(P);
	Deep.SnapToTarget();
	FWaveField Shallow;
	Shallow.SetDepth(2.0);
	Shallow.SetWind(P);
	Shallow.SnapToTarget();
	double Corr, Surface, Deep2, ShallowSurface, ShallowBed, Unused;
	Statistics(Deep, 0.0, Corr, Surface);
	Statistics(Deep, 2.0, Unused, Deep2);
	Statistics(Shallow, 0.0, Unused, ShallowSurface);
	Statistics(Shallow, 2.0, Unused, ShallowBed);
	AddInfo(FString::Printf(TEXT("Hs %.2f m: along-wave speed %.2f m/s rms at the surface (correlation with the height %.2f), %.2f at 2 m; 2 m deep water %.2f at the surface, %.2f at the bed"),
		Deep.SignificantHeight(), Surface, Corr, Deep2, ShallowSurface, ShallowBed));
	TestTrue(TEXT("The water moves forward under the crests"), Corr > 0.5);
	TestTrue(TEXT("... and less deep down"), Deep2 < 0.8 * Surface && Deep2 > 0.1 * Surface);
	TestTrue(TEXT("In shallow water the motion reaches the bed"), ShallowBed > 0.5 * ShallowSurface);

	FTrialSeaSpec Run;
	Run.WindKnots = 20.0;
	Run.FetchMeters = 1.0;
	Run.bOcean = true;
	Run.Ocean.WindMs = 20.0 * kKnot;
	Run.Ocean.WindFromRad = 0.0;
	Run.Ocean.WindSeaHs = 2.0;
	Run.Ocean.WindSeaTp = 6.5;
	Run.Ocean.SwellHs = 0.0;
	const FBoatConfig J22 = FBoatConfig::Make(EBoatType::J22);
	FBoatConfig J22Still = J22;
	J22Still.WaveOrbitalFlowScale = 0.0;
	const FSeaRunResult J = RunInSea(J22, Run, 150.0, 0, true, 30.0, 240.0, 0.02);
	AddInfo(FString::Printf(TEXT("J/22 on a following 2 m sea in 20 kn, TWA 150: %.2f kn (best second %.2f), %.2f kn on the steep faces, hull speed %.2f"),
		J.MeanKnots, J.MaxKnots, J.PhaseKnots[4], J.HullSpeedKnots));
	TestTrue(TEXT("She surfs past 1.5 times her hull speed"), J.MaxKnots > 1.5 * J.HullSpeedKnots);
	TestTrue(TEXT("... at 1.5 to 2 times it on the steep faces"), J.PhaseKnots[4] > 1.5 * J.HullSpeedKnots && J.PhaseKnots[4] < 2.0 * J.HullSpeedKnots);
	TestTrue(TEXT("... faster on the faces than on the backs"), J.PhaseKnots[4] > J.PhaseKnots[0] + 1.0);

	const FSeaRunResult Q = RunInSea(J22, Run, 165.0, 0, true, 30.0, 240.0, 0.02);
	const FSeaRunResult Q0 = RunInSea(J22Still, Run, 165.0, 0, true, 30.0, 240.0, 0.02);
	AddInfo(FString::Printf(TEXT("TWA 165: off course on the faces by %.1f deg with the flow, %.1f in still water (backs %.1f, %.1f)"),
		Q.FaceCourseErrDeg, Q0.FaceCourseErrDeg, Q.BackCourseErrDeg, Q0.BackCourseErrDeg));
	TestTrue(TEXT("With the flow the waves yaw her more on a face"), Q.FaceCourseErrDeg > Q0.FaceCourseErrDeg);
	TestFalse(TEXT("... without knocking her down"), Q.bCapsized);

	FBoatConfig Maxi = FBoatConfig::Make(EBoatType::Maxi);
	FSceneLimits::For(true).ApplyTo(Maxi);
	const FSeaRunResult M = RunInSea(Maxi, FTrialSeaSpec::Gale(1), 120.0, 2, false, 30.0, 150.0, 0.03);
	AddInfo(FString::Printf(TEXT("Maxi in the gale, TWA 120: %.2f kn (seconds %.1f to %.1f)"), M.MeanKnots, M.MinKnots, M.MaxKnots));
	TestTrue(TEXT("The maxi reaches past 20 kn on the quartering sea"), M.MeanKnots > 20.0);

	FTrialSeaSpec Flat;
	Flat.WindKnots = 12.0;
	Flat.FetchMeters = 1.0;
	const FSeaRunResult U = RunInSea(J22, Flat, 45.0, 0, false, 25.0, 60.0);
	const FSeaRunResult U0 = RunInSea(J22Still, Flat, 45.0, 0, false, 25.0, 60.0);
	AddInfo(FString::Printf(TEXT("Upwind on flat water: %.3f kn with the flow, %.3f without"), U.MeanKnots, U0.MeanKnots));
	TestTrue(TEXT("Upwind on flat water nothing changes"), FMath::Abs(U.MeanKnots - U0.MeanKnots) < 0.01);
	return true;
}

#endif
