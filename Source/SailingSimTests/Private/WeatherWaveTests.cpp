#include "Misc/AutomationTest.h"
#include "BoatModel.h"
#include "FixedStepper.h"
#include "PolarReference.h"
#include "Waves.h"
#include "Weather.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	FWaveField MakeWaves(double Knots, double FromDeg, double Fetch, uint32 Seed = 3)
	{
		FWaveField Waves(Seed);
		FWaveParams P;
		P.WindSpeedKnots = Knots;
		P.WindFromDegrees = FromDeg;
		P.FetchMeters = Fetch;
		Waves.SetWind(P);
		Waves.SnapToTarget();
		return Waves;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveHeightTest, "SailingSim.Water.FetchLimitedChop", Flags)
bool FSailingWaveHeightTest::RunTest(const FString& Parameters)
{
	// Fetch-limited growth law in the adjusted wind (W3): 10 kn over 5 km gives about 0.19 m, 20 kn about 0.43 m.
	const double Hs10 = FWaveField::TargetSignificantHeight(10.0 * kKnot, 5000.0);
	const double Hs20 = FWaveField::TargetSignificantHeight(20.0 * kKnot, 5000.0);
	AddInfo(FString::Printf(TEXT("Hs: %.2f m at 10 kn, %.2f m at 20 kn over 5 km; Tp %.1f s / %.1f s"), Hs10, Hs20,
		FWaveField::TargetPeakPeriod(10.0 * kKnot, 5000.0), FWaveField::TargetPeakPeriod(20.0 * kKnot, 5000.0)));
	TestEqual(TEXT("Hs at 10 kn, 5 km"), Hs10, 0.192, 0.01);
	TestTrue(TEXT("Waves grow with wind"), Hs20 > 1.8 * Hs10);
	TestTrue(TEXT("Waves grow with fetch"), FWaveField::TargetSignificantHeight(10.0 * kKnot, 10000.0) > Hs10);
	TestEqual(TEXT("Calm water stays calm"), FWaveField::TargetSignificantHeight(0.2, 5000.0), 0.0, 1e-9);

	// The surface itself has that significant height (4 x standard deviation) and a zero mean.
	const FWaveField Waves = MakeWaves(15.0, 0.0, 5000.0);
	TestEqual(TEXT("Components sum to the target Hs"), Waves.SignificantHeight(), FWaveField::TargetSignificantHeight(15.0 * kKnot, 5000.0), 0.005);
	double Sum = 0.0, SumSq = 0.0;
	const int32 N = 20000;
	for (int32 I = 0; I < N; ++I)
	{
		const double X = (I % 200) * 3.7, Y = (I / 200) * 4.1, T = I * 0.013;
		const double H = Waves.Height(X, Y, T);
		Sum += H; SumSq += H * H;
	}
	const double Mean = Sum / N, Std = FMath::Sqrt(SumSq / N - Mean * Mean);
	AddInfo(FString::Printf(TEXT("Sampled surface: mean %.3f m, 4 sigma %.3f m (target %.3f)"), Mean, 4.0 * Std, Waves.SignificantHeight()));
	TestEqual(TEXT("Surface mean is the still-water level"), Mean, 0.0, 0.01);
	TestEqual(TEXT("Sampled Hs matches"), 4.0 * Std, Waves.SignificantHeight(), 0.15 * Waves.SignificantHeight());
	return true;
}

/**
 * W0: each band of the lake sea follows the wind at its own pace (FWaveField::GrowthSeconds, tau = 8 T^2 clamped to
 * 5..300 s). After a step from 6 to 18 kn the 0.5 s ripples reach 90% of their new amplitude long before the 4 s waves,
 * and the steady state is the same sea as before (the targets are unchanged; only the approach is per band).
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveBandGrowthTest, "SailingSim.Physics.WaveBandGrowth", Flags)
bool FSailingWaveBandGrowthTest::RunTest(const FString& Parameters)
{
	FWaveField Waves = MakeWaves(6.0, 0.0, 5000.0);
	// The same field snapped to 18 kn (its directions were laid by the 6 kn wind it started in).
	FWaveField Target = Waves;
	{
		FWaveParams P18 = Target.GetParams();
		P18.WindSpeedKnots = 18.0;
		Target.SetWind(P18);
		Target.SnapToTarget();
	}
	auto BandNear = [&Waves](double Period)
	{
		int32 Best = 0;
		for (int32 B = 1; B < kWaveBands; ++B)
		{
			if (FMath::Abs(Waves.BandPeriod(B) - Period) < FMath::Abs(Waves.BandPeriod(Best) - Period)) Best = B;
		}
		return Best;
	};
	auto BandRms = [](const FWaveField& W, int32 B)
	{
		double E = 0.0;
		for (int32 D = 0; D < kWaveDirectionsPerBand; ++D) E += FMath::Square(W.GetComponents()[B * kWaveDirectionsPerBand + D].Amplitude);
		return FMath::Sqrt(E);
	};
	const int32 Short = BandNear(0.5), Long = BandNear(4.0);
	const double Short0 = BandRms(Waves, Short), Short1 = BandRms(Target, Short);
	const double Long0 = BandRms(Waves, Long), Long1 = BandRms(Target, Long);
	TestTrue(TEXT("Both bands grow with the wind"), Short1 > Short0 * 1.05 && Long1 > Long0 * 1.05);

	FWaveParams P = Waves.GetParams();
	P.WindSpeedKnots = 18.0;
	Waves.SetWind(P);
	constexpr double Dt = 1.0 / 60.0;
	double ShortT90 = -1.0, LongT90 = -1.0;
	// Long enough for the slowest band (300 s) to settle to 1e-6: since W3's adjusted wind the 18 kn sea reaches it.
	for (int32 I = 1; I <= 5000 * 60; ++I)
	{
		Waves.Update(Dt);
		const double T = I * Dt;
		if (ShortT90 < 0.0 && (BandRms(Waves, Short) - Short0) >= 0.9 * (Short1 - Short0)) ShortT90 = T;
		if (LongT90 < 0.0 && (BandRms(Waves, Long) - Long0) >= 0.9 * (Long1 - Long0)) LongT90 = T;
	}
	double MaxDiff = 0.0, MaxAmp = 0.0;
	for (int32 I = 0; I < kWaveComponents; ++I)
	{
		MaxDiff = FMath::Max(MaxDiff, FMath::Abs(Waves.GetComponents()[I].Amplitude - Target.GetComponents()[I].Amplitude));
		MaxAmp = FMath::Max(MaxAmp, Target.GetComponents()[I].Amplitude);
	}
	AddInfo(FString::Printf(TEXT("Band %.2f s (tau %.0f s) reached 90%% in %.1f s, band %.2f s (tau %.0f s) in %.1f s; Hs %.3f m vs %.3f m snapped"),
		Waves.BandPeriod(Short), FWaveField::GrowthSeconds(Waves.BandPeriod(Short)), ShortT90, Waves.BandPeriod(Long),
		FWaveField::GrowthSeconds(Waves.BandPeriod(Long)), LongT90, Waves.SignificantHeight(), Target.SignificantHeight()));
	TestTrue(TEXT("The ripples reach 90% within half a minute"), ShortT90 > 0.0 && ShortT90 < 30.0);
	TestTrue(TEXT("The 4 s waves take minutes"), LongT90 > 120.0);
	TestTrue(TEXT("The ripples get there long before the 4 s waves (5x sooner)"), ShortT90 > 0.0 && LongT90 > 5.0 * ShortT90);
	TestTrue(TEXT("Steady state equals the snapped sea"), MaxDiff < 1e-6 * FMath::Max(MaxAmp, 1e-3));
	TestTrue(TEXT("Growth times clamp to 5..300 s"), FWaveField::GrowthSeconds(0.1) == 5.0 && FWaveField::GrowthSeconds(20.0) == 300.0);
	return true;
}

/**
 * docs/short-wave-spreading: each band's three directions are laid about the wind (-Delta, 0, +Delta, a few degrees of
 * jitter) and weighted by the measured spreading (Donelan, Hamilton and Hui's sech^2, narrowest at the peak), so the sea
 * near the peak is long-crested; the calibration sea keeps the constructor's directions and cos^2; a turn past 45 deg
 * lays them again without moving the surface at the hold point.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveSpreadingTest, "SailingSim.Physics.WaveSpreading", Flags)
bool FSailingWaveSpreadingTest::RunTest(const FString& Parameters)
{
	// DHH at the peak (beta 2.28): 44 deg wide at half height; three directions carry its mean cos at about 37 deg.
	const double PeakSide = FWaveField::SideAngle(2.28) / kDegToRad;
	const double FarSide = FWaveField::SideAngle(FWaveField::SpreadingBeta(3.0, 1.0)) / kDegToRad;
	AddInfo(FString::Printf(TEXT("Side directions: %.1f deg at the peak, %.1f deg at 3 fp"), PeakSide, FarSide));
	TestTrue(TEXT("Near the peak the sides are 30..45 deg off the wind"), PeakSide > 30.0 && PeakSide < 45.0);
	TestTrue(TEXT("Far above the peak they spread wider"), FarSide > PeakSide + 15.0);
	TestEqual(TEXT("The spreading is normalized"), [] { double S = 0.0; for (int32 I = 0; I < 3600; ++I) S += FWaveField::DirectionalSpreading(1.0, 1.0, -UE_DOUBLE_PI + (I + 0.5) * 2.0 * UE_DOUBLE_PI / 3600.0); return S * 2.0 * UE_DOUBLE_PI / 3600.0; }(), 1.0, 1e-6);

	// Wind from 70 deg: the waves travel toward 250 deg.
	FWaveField Waves = MakeWaves(9.0, 70.0, 3000.0);
	const double Travel = 250.0 * kDegToRad;
	double MaxCentre = 0.0, MaxAsym = 0.0;
	for (int32 B = 0; B < kWaveBands; ++B)
	{
		const FWaveComponent* C = Waves.GetComponents() + B * kWaveDirectionsPerBand;
		const double L = WrapAngle(FMath::Atan2(C[0].Ky, C[0].Kx) - Travel), M = WrapAngle(FMath::Atan2(C[1].Ky, C[1].Kx) - Travel), R = WrapAngle(FMath::Atan2(C[2].Ky, C[2].Kx) - Travel);
		MaxCentre = FMath::Max(MaxCentre, FMath::Abs(M));
		MaxAsym = FMath::Max(MaxAsym, FMath::Abs(L + R));
	}
	AddInfo(FString::Printf(TEXT("Anchored: centre directions within %.1f deg of the wind, sides symmetric within %.1f deg"), MaxCentre / kDegToRad, MaxAsym / kDegToRad));
	TestTrue(TEXT("Every band's centre direction is the wind's within 3 deg"), Waves.IsAnchored() && MaxCentre < 3.01 * kDegToRad);
	TestTrue(TEXT("The sides are symmetric about it within 6 deg"), MaxAsym < 6.01 * kDegToRad);
	TestEqual(TEXT("The anchored sea keeps its Hs"), Waves.SignificantHeight(), FWaveField::TargetSignificantHeight(9.0 * kKnot, 3000.0), 0.002);

	// Energy-weighted mean cos(theta) about the wind, the sea's directional width: the old fields' was cos^2's or wider.
	auto MeanCos = [Travel](const FWaveField& W)
	{
		double E = 0.0, EC = 0.0;
		for (int32 I = 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& C = W.GetComponents()[I];
			E += C.Amplitude * C.Amplitude;
			EC += C.Amplitude * C.Amplitude * FMath::Cos(FMath::Atan2(C.Ky, C.Kx) - Travel);
		}
		return EC / FMath::Max(E, 1e-12);
	};
	FWaveField Calib(3);
	FWaveParams PC;
	PC.WindSpeedKnots = 9.0;
	PC.WindFromDegrees = 70.0;
	PC.FetchMeters = 3000.0;
	PC.bCalibrationSea = true;
	Calib.SetWind(PC);
	Calib.SnapToTarget();
	const FWaveField Fresh(3);
	bool bSame = !Calib.IsAnchored();
	for (int32 I = 0; I < kWaveComponents; ++I) bSame &= Calib.GetComponents()[I].Kx == Fresh.GetComponents()[I].Kx && Calib.GetComponents()[I].Phase == Fresh.GetComponents()[I].Phase;
	AddInfo(FString::Printf(TEXT("Mean cos about the wind: %.3f measured spreading, %.3f calibration sea (cos^2 over the old directions)"), MeanCos(Waves), MeanCos(Calib)));
	TestTrue(TEXT("The calibration sea keeps the constructor's directions"), bSame);
	TestTrue(TEXT("The measured sea is longer-crested than the calibration sea"), MeanCos(Waves) > MeanCos(Calib) + 0.03);

	// A 30 deg shift only reweights; a 60 deg one lays the directions again, the surface unmoved at the hold point.
	const uint32 Gen = Waves.GetDirectionGeneration();
	FWaveParams P = Waves.GetParams();
	P.WindFromDegrees = 100.0;
	Waves.SetWind(P);
	TestEqual(TEXT("A 30 deg shift keeps the directions"), Waves.GetDirectionGeneration(), Gen);
	P.WindFromDegrees = 130.0;
	P.HoldX = 812.0;
	P.HoldY = -455.0;
	double Before[3], After[3];
	for (int32 K = 0; K < 3; ++K) Before[K] = Waves.Height(P.HoldX, P.HoldY, 40.0 + 1.7 * K);
	const double Away = Waves.Height(P.HoldX + 300.0, P.HoldY, 40.0);
	Waves.SetWind(P);
	for (int32 K = 0; K < 3; ++K) After[K] = Waves.Height(P.HoldX, P.HoldY, 40.0 + 1.7 * K);
	TestTrue(TEXT("A 60 deg shift lays them again"), Waves.GetDirectionGeneration() == Gen + 1 && FMath::IsNearlyEqual(Waves.GetAnchorDirection(), 310.0 * kDegToRad, 1e-9));
	TestTrue(TEXT("The surface at the hold point doesn't move"), FMath::Abs(Before[0] - After[0]) < 1e-6 && FMath::Abs(Before[1] - After[1]) < 1e-6 && FMath::Abs(Before[2] - After[2]) < 1e-6);
	TestTrue(TEXT("Away from it the surface did change (the new directions are in use)"), FMath::Abs(Away - Waves.Height(P.HoldX + 300.0, P.HoldY, 40.0)) > 1e-4);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveDirectionTest, "SailingSim.Water.FollowsTheWind", Flags)
bool FSailingWaveDirectionTest::RunTest(const FString& Parameters)
{
	FWaveField Waves = MakeWaves(12.0, 0.0, 5000.0); // wind from +X: waves travel toward -X
	TestTrue(TEXT("Waves travel downwind"), FMath::Abs(WrapAngle(Waves.MeanDirection() - kPi)) < 25.0 * kDegToRad);

	// The wind backs 90 degrees: the sea follows over a few minutes without the surface jumping.
	FWaveParams P = Waves.GetParams();
	P.WindFromDegrees = 90.0;
	Waves.SetWind(P);
	double Prev = Waves.Height(3.0, 4.0, 0.0), MaxStep = 0.0;
	for (int32 I = 1; I <= 300 * 60; ++I)
	{
		Waves.Update(1.0 / 60.0);
		const double H = Waves.Height(3.0, 4.0, I / 60.0);
		MaxStep = FMath::Max(MaxStep, FMath::Abs(H - Prev));
		Prev = H;
	}
	TestTrue(TEXT("Sea turned with the wind"), FMath::Abs(WrapAngle(Waves.MeanDirection() - (90.0 * kDegToRad + kPi))) < 25.0 * kDegToRad);
	TestTrue(TEXT("No jumps in the surface (max 3 cm per frame at 60 fps)"), MaxStep < 0.03);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingBoatInWavesTest, "SailingSim.Water.BoatRidesTheWaves", Flags)
bool FSailingBoatInWavesTest::RunTest(const FString& Parameters)
{
	FWindParams WP;
	WP.SpeedKnots = 15.0;
	const FWindField Wind(WP);
	const FWaveField Waves = MakeWaves(15.0, 0.0, 8000.0);

	auto Sail = [&](const FWaveField* W, double& OutPitchRms, double& OutHeaveRms, double& OutSpeed)
	{
		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -50.0 * kDegToRad, 5.0 * kKnot);
		FAutopilot Pilot; Pilot.TargetTWADeg = 50.0;
		FAutoTrim Trim;
		FBoatControls C; C.MainSheet = C.JibSheet = 0.2;
		double P2 = 0.0, Z = 0.0, Z2 = 0.0, S = 0.0; int32 N = 0;
		for (int32 I = 0; I < int32(60 * PhysicsHz); ++I)
		{
			C = Trim.Update(Boat, C, PhysicsDt);
			C.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, C, Wind, W);
			if (I > int32(30 * PhysicsHz))
			{
				const double Pitch = Boat.GetTelemetry().Pitch, Heave = Boat.OriginPosition().Z;
				P2 += Pitch * Pitch; Z += Heave; Z2 += Heave * Heave; S += Boat.GetTelemetry().BoatSpeed; ++N;
			}
		}
		OutPitchRms = FMath::Sqrt(P2 / N) * kRadToDeg;
		OutHeaveRms = FMath::Sqrt(FMath::Max(0.0, Z2 / N - (Z / N) * (Z / N)));
		OutSpeed = S / N / kKnot;
	};
	double FlatPitch, FlatHeave, FlatSpeed, WavePitch, WaveHeave, WaveSpeed;
	Sail(nullptr, FlatPitch, FlatHeave, FlatSpeed);
	Sail(&Waves, WavePitch, WaveHeave, WaveSpeed);
	AddInfo(FString::Printf(TEXT("Hs %.2f m. Flat: pitch %.2f deg rms, heave %.3f m, %.2f kn. Chop: pitch %.2f deg rms, heave %.3f m, %.2f kn"),
		Waves.SignificantHeight(), FlatPitch, FlatHeave, FlatSpeed, WavePitch, WaveHeave, WaveSpeed));
	TestTrue(TEXT("Pitches in the chop"), WavePitch > FlatPitch + 0.3);
	TestTrue(TEXT("Heaves in the chop"), WaveHeave > 0.02);
	TestTrue(TEXT("Chop slows her down upwind"), WaveSpeed < FlatSpeed - 0.05);
	TestTrue(TEXT("...but not absurdly"), WaveSpeed > 0.8 * FlatSpeed);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingStormTest, "SailingSim.Weather.ThunderstormSequence", Flags)
bool FSailingStormTest::RunTest(const FString& Parameters)
{
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Thunderstorm, 11, 16.0);
	FWindField Wind;

	TArray<EStormPhase> Order;
	double MaxGustKnots = 0.0, MeanAfter = 0.0, SpeedBefore = 0.0, RainStart = -1.0, FrontAtBoat = -1.0, MinVis = 1e9;
	double DirBefore = 0.0, DirAfter = 0.0;
	int32 AfterSamples = 0;
	for (int32 I = 0; I <= 650 * 10; ++I)
	{
		const double T = I * 0.1;
		const FWeatherState S = Weather.Evaluate(T);
		FWeatherSystem::ApplyToWind(S, Wind, T);
		if (Order.Num() == 0 || Order.Last() != S.Storm) Order.Add(S.Storm);
		const Vec3 V = Wind.VelocityAt(Vec3(0, 0, 10), T);
		const double Knots = V.LengthXY() / kKnot;
		if (T < 100.0) { SpeedBefore = FMath::Max(SpeedBefore, Knots); DirBefore = std::atan2(-V.Y, -V.X); }
		if (FrontAtBoat < 0.0 && Knots > 18.0) FrontAtBoat = T;
		if (T > FWeatherSystem::kFrontArrives + 15.0 && T < FWeatherSystem::kOutflowDecays)
		{
			MaxGustKnots = FMath::Max(MaxGustKnots, Knots);
			MeanAfter += Knots; ++AfterSamples;
			DirAfter = std::atan2(-V.Y, -V.X);
		}
		if (RainStart < 0.0 && S.Rain > 0.05) RainStart = T;
		MinVis = FMath::Min(MinVis, S.VisibilityKm);
	}
	MeanAfter /= FMath::Max(AfterSamples, 1);
	const FWeatherState End = Weather.Evaluate(650.0);
	AddInfo(FString::Printf(TEXT("Before %.1f kn; front reached the boat at %.0f s; outflow mean %.1f kn, gusts to %.1f kn; shift %.0f deg; rain from %.0f s; min visibility %.1f km; %d strikes"),
		SpeedBefore, FrontAtBoat, MeanAfter, MaxGustKnots, FMath::Abs(WrapAngle(DirAfter - DirBefore)) * kRadToDeg, RainStart, MinVis, int32(Weather.GetStrikes().size())));

	const TArray<EStormPhase> Expected = { EStormPhase::Building, EStormPhase::GustFront, EStormPhase::Rain, EStormPhase::Clearing, EStormPhase::Clear };
	TestTrue(TEXT("Phases play in order: building, gust front, rain, clearing, clear"), Order == Expected);
	TestTrue(TEXT("Light before the storm"), SpeedBefore < 15.0);
	TestTrue(TEXT("Gust front arrives on schedule"), FMath::Abs(FrontAtBoat - FWeatherSystem::kFrontArrives) < 30.0);
	// W5b: the outflow is the cold pool's density current (1.2 x the front's speed) and a moderate microburst: a strong
	// storm's gusts (Love Field 41 kn on the replayed 11 June 2023 storm), short of the severe 50 kn.
	TestTrue(TEXT("Outflow gusts 30 to 50 kn"), MaxGustKnots >= 30.0 && MaxGustKnots <= 50.0 && MeanAfter > 18.0);
	TestTrue(TEXT("Sharp wind shift with the front"), FMath::Abs(WrapAngle(DirAfter - DirBefore)) > 60.0 * kDegToRad);
	// (W5b: the rain foot reaches the water a few hundred metres behind the front: half a minute later at this speed.)
	TestTrue(TEXT("The rain comes after the gust front"), RainStart > FrontAtBoat + 15.0);
	TestTrue(TEXT("Visibility drops in the downpour"), MinVis < 3.0);
	TestTrue(TEXT("It clears: no rain, light sky at the end"), End.Rain < 0.01 && End.CloudDarkness < 0.3);

	TestTrue(TEXT("Lightning during the storm"), Weather.GetStrikes().size() >= 15u);
	const FLightningStrike& Strike = Weather.GetStrikes()[0];
	const double Distance = FMath::Sqrt(Strike.X * Strike.X + Strike.Y * Strike.Y + 1.0e6);
	TestEqual(TEXT("Thunder arrives at the speed of sound"), FWeatherSystem::ThunderDelaySeconds(Strike, 0.0, 0.0), Distance / 343.0, 1e-6);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingVisibleGustsTest, "SailingSim.Weather.GustsVisibleBeforeTheyArrive", Flags)
bool FSailingVisibleGustsTest::RunTest(const FString& Parameters)
{
	// W1: puffs are seen on the water before they arrive. A puff 400 m up its track (it drifts at the wind aloft, a few
	// degrees veered) is the puff the boat feels when it gets there; the water's roughness there now foretells the
	// boat's wind then (the fine turbulence moves at the surface wind, so not exactly).
	FWindParams WP;
	WP.SpeedKnots = 12.0;
	WP.FromDegrees = 0.0;
	WP.GustIntensity = 0.12;
	WP.PuffIntensity = 0.1;
	WP.Seed = 5;
	const FWindField Gusty(WP);
	const Vec3 Drift = Gusty.PuffDrift();
	const double Vp = Drift.LengthXY();
	const Vec3 Ahead = Drift / Vp * -400.0; // up the puffs' track
	double PuffError = 0.0, SA = 0.0, SB = 0.0, SAA = 0.0, SBB = 0.0, SAB = 0.0;
	const int32 N = 300;
	for (int32 I = 0; I < N; ++I)
	{
		const double T = 60.0 + I * 7.0;
		double F0, S0, F1, S1;
		Gusty.PuffAt(Ahead.X, Ahead.Y, T, F0, S0);
		Gusty.PuffAt(0.0, 0.0, T + 400.0 / Vp, F1, S1);
		PuffError += FMath::Abs(F0 - F1) / N;
		// What the eye takes in: the roughness over a patch of water 150 m across up there now; what the boat feels: her
		// wind over the 20 s it takes to cross it.
		double A = 0.0, B = 0.0;
		for (int32 K = -2; K <= 2; ++K) for (int32 L = -2; L <= 2; ++L) A += Gusty.SurfaceRoughnessAt(Ahead.X + K * 35.0, Ahead.Y + L * 35.0, T) / 25.0;
		for (int32 K = -10; K <= 10; ++K) B += Gusty.SurfaceRoughnessAt(0.0, 0.0, T + 400.0 / Vp + K) / 21.0;
		SA += A; SB += B; SAA += A * A; SBB += B * B; SAB += A * B;
	}
	const double Cov = SAB / N - SA * SB / (N * N), Corr = Cov / FMath::Sqrt((SAA / N - SA * SA / (N * N)) * (SBB / N - SB * SB / (N * N)));
	AddInfo(FString::Printf(TEXT("A puff 400 m up its track arrives %.0f s later within %.3f of its strength on average; the water there now (a 150 m patch) and the wind here then (20 s) correlate %.2f"),
		400.0 / Vp, PuffError, Corr));
	TestTrue(TEXT("A puff seen 400 m upwind reaches the boat (a few land or fade on the way)"), PuffError < 0.03);
	TestTrue(TEXT("The rough water upwind foretells the wind"), Corr > 0.5);

	// The storm's gust front shows as a band of rough water closing in before the wind at the boat changes.
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::Thunderstorm, 11, 16.0);
	FWindField Wind;
	const double T0 = FWeatherSystem::kFrontArrives - 30.0;
	FWeatherSystem::ApplyToWind(Weather.Evaluate(T0), Wind, T0);
	const double Here = Wind.SurfaceRoughnessAt(0.0, 0.0, T0);
	double Best = 0.0, BestDist = 0.0;
	const double From = 290.0 * kDegToRad;
	for (double D = 50.0; D <= 800.0; D += 25.0)
	{
		const double R = Wind.SurfaceRoughnessAt(std::cos(From) * D, std::sin(From) * D, T0);
		if (R > Best) { Best = R; BestDist = D; }
	}
	AddInfo(FString::Printf(TEXT("30 s before the front: roughness %.2f at the boat, %.2f at %.0f m toward the storm"), Here, Best, BestDist));
	TestTrue(TEXT("Gust front visible upwind 30 s before it arrives"), Best > 2.0 * Here && BestDist > 200.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWeatherPresetsTest, "SailingSim.Weather.PresetsAndRepeatability", Flags)
bool FSailingWeatherPresetsTest::RunTest(const FString& Parameters)
{
	auto KnotsAt = [](EWeatherPreset Preset, double Hour, uint32 Seed = 1)
	{
		FWeatherSystem W;
		W.Configure(Preset, Seed, Hour);
		return W.Evaluate(0.0).Wind.SpeedKnots;
	};
	TestTrue(TEXT("Calm morning is light"), KnotsAt(EWeatherPreset::CalmMorning, 7.5) < 4.0);
	TestTrue(TEXT("The breeze builds through the afternoon"), KnotsAt(EWeatherPreset::AfternoonBreeze, 15.0) > 1.8 * KnotsAt(EWeatherPreset::AfternoonBreeze, 8.0));
	FWeatherSystem Rain;
	Rain.Configure(EWeatherPreset::Rain, 1, 12.0);
	TestTrue(TEXT("Rain preset rains with poor visibility"), Rain.Evaluate(0.0).Rain > 0.3 && Rain.Evaluate(0.0).VisibilityKm < 6.0);

	// Same seed, same day; a different seed, a different random day.
	FWeatherSystem A, B, C;
	A.Configure(EWeatherPreset::Thunderstorm, 99, 16.0);
	B.Configure(EWeatherPreset::Thunderstorm, 99, 16.0);
	TestTrue(TEXT("Same seed, same lightning"), A.GetStrikes().size() == B.GetStrikes().size() && A.GetStrikes()[3].Time == B.GetStrikes()[3].Time);
	bool bAnyDifferent = false;
	for (uint32 Seed = 2; Seed < 12; ++Seed)
	{
		bAnyDifferent |= FMath::Abs(KnotsAt(EWeatherPreset::RandomDay, 15.0, Seed) - KnotsAt(EWeatherPreset::RandomDay, 15.0, 1)) > 0.5;
	}
	TestTrue(TEXT("Random day varies with the seed"), bAnyDifferent);
	TestEqual(TEXT("Random day repeats for a seed"), KnotsAt(EWeatherPreset::RandomDay, 15.0, 7), KnotsAt(EWeatherPreset::RandomDay, 15.0, 7));
	return true;
}

#endif
