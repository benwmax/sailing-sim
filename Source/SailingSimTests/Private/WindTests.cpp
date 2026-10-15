// W1: Wind 2.0. The puffs against the stations they were calibrated on, the puffs at two scales, the puffs' veer and fan,
// the same field at any frame rate, and the shore's lee band (docs/w1/README.md).
#include "Misc/AutomationTest.h"
#include "LakeTerrain.h"
#include "Weather.h"
#include "Wind.h"
#include "WindClimate.h"

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

namespace
{
	constexpr EAutomationTestFlags WindTestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWindPuffStatisticsTest, "SailingSim.Physics.WindPuffStatistics", WindTestFlags)
bool FWindPuffStatisticsTest::RunTest(const FString& Parameters)
{
	// The weather's wind, measured at fixed points the way ASOS and CO-OPS measure (5 s peaks in each minute over the
	// 2-minute mean; the 2-minute means around their half-hour mean; the time between puffs), against the fitted table.
	TestNotNull(TEXT("The Mann tile is loaded (Content/TerrainData/Wind.mann)"), FTurbulenceTile::Shared());
	struct FCase { int Month; double Hour; bool bCoast; const TCHAR* Name; };
	const FCase Cases[] = { { 7, 15.0, false, TEXT("Lake, July afternoon") }, { 1, 10.0, false, TEXT("Lake, January morning") }, { 4, 13.0, true, TEXT("Bay, April midday") } };
	for (const FCase& C : Cases)
	{
		FWeatherSystem Weather;
		Weather.Configure(EWeatherPreset::AfternoonBreeze, 5, C.Hour);
		Weather.SetClimate(C.Month, C.bCoast);
		FWeatherState S = Weather.Evaluate(0.0);
		S.Wind.SpeedKnots = 12.0; // the calibration is for winds of 8 kn and up
		const FWindField Wind(S.Wind);
		const FGustStats G = MeasureGustStats(Wind, 6.0, 6);
		const double WantGust = ClimateGustFactor(C.Month, C.Hour, C.bCoast), WantSlow = ClimatePuffStrength(C.Month, C.Hour, C.bCoast);
		const double WantMinutes = ClimatePuffMinutes(C.Month, C.Hour, C.bCoast);
		AddInfo(FString::Printf(TEXT("%s (air - water %+.1f C, mixed layer %.0f m): gust factor %.3f (stations %.3f), 2-min spread %.3f (%.3f), puffs every %.0f min (%.0f), mean %.3f"),
			C.Name, S.Wind.AirMinusWaterC, S.Wind.MixedLayerMeters, G.GustFactor, WantGust, G.SlowRms, WantSlow, G.PuffMinutes, WantMinutes, G.MeanFactor));
		TestTrue(FString::Printf(TEXT("%s: gust factor within 0.03 of the stations'"), C.Name), FMath::Abs(G.GustFactor - WantGust) < 0.03);
		TestTrue(FString::Printf(TEXT("%s: puff strength within a factor 1.6 of the stations'"), C.Name), G.SlowRms > WantSlow / 1.6 && G.SlowRms < WantSlow * 1.6);
		TestTrue(FString::Printf(TEXT("%s: puffs every 4 to 14 minutes"), C.Name), G.PuffMinutes >= 4.0 && G.PuffMinutes <= 14.0);
		TestEqual(FString::Printf(TEXT("%s: the mean is the mean"), C.Name), G.MeanFactor, 1.0, 0.05);
	}
	// Stability: cold air over warm water makes bigger puffs than warm air over cool water, same day otherwise.
	FWindParams P;
	P.SpeedKnots = 10.0;
	P.GustIntensity = 0.14;
	P.PuffIntensity = 0.09;
	P.MixedLayerMeters = 1200.0;
	P.AirMinusWaterC = -5.0;
	const FWindField Cold(P);
	P.AirMinusWaterC = 4.0;
	const FWindField Warm(P);
	AddInfo(FString::Printf(TEXT("Puff amplitude: cold over warm %.2f, warm over cool %.2f"), Cold.GetDerived().PuffAmplitude, Warm.GetDerived().PuffAmplitude));
	TestTrue(TEXT("Unstable air is puffier"), Cold.GetDerived().PuffAmplitude > 1.3 * Warm.GetDerived().PuffAmplitude);
	// Streets in a breeze, open cells in light air.
	P.AirMinusWaterC = 0.0;
	P.SpeedKnots = 18.0;
	const FWindField Breeze(P);
	P.SpeedKnots = 6.0;
	const FWindField Light(P);
	TestTrue(TEXT("Streets of puffs along a breeze"), Breeze.GetDerived().PuffAlong > 1.8 * Breeze.GetDerived().PuffAcross);
	TestTrue(TEXT("Round open cells in light air"), FMath::Abs(Light.GetDerived().PuffAlong / Light.GetDerived().PuffAcross - 1.0) < 0.1);
	TestTrue(TEXT("Puffs 0.3 to 3 km across"), Breeze.GetDerived().PuffAcross >= 300.0 && Light.GetDerived().PuffAcross <= 3000.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWindTwoScalesTest, "SailingSim.Physics.WindPuffsAtTwoScales", WindTestFlags)
bool FWindTwoScalesTest::RunTest(const FString& Parameters)
{
	// The W6 LES pilot (a North Texas summer afternoon) puts most of the gust energy in lulls and puffs 2 to 5 km across,
	// with 250 to 500 m streaks inside them. The puff layer's spectrum along the wind must have both: the kilometre cells
	// and the streaks, where the W1 field (CellShare 0) had one scale.
	auto Bands = [](const FWindField& Wind, double& Kilometre, double& Streaks)
	{
		const int32 N = 1600;
		const double Step = 25.0; // 40 km lines
		double Total = 0.0;
		Kilometre = Streaks = 0.0;
		for (int32 Line = 0; Line < 8; ++Line)
		{
			TArray<double> S;
			S.SetNum(N);
			double Mean = 0.0;
			for (int32 I = 0; I < N; ++I)
			{
				double F, Shift;
				Wind.PuffAt(-I * Step, Line * 3100.0, 1800.0 + Line * 900.0, F, Shift);
				S[I] = F;
				Mean += F / N;
			}
			for (double& V : S) { V -= Mean; Total += V * V / N; }
			for (int32 K = 1; K < N / 2; ++K)
			{
				const double Lambda = N * Step / K;
				const bool bKm = Lambda >= 2000.0 && Lambda <= 8000.0, bStreak = Lambda >= 250.0 && Lambda < 1000.0;
				if (!bKm && !bStreak) continue;
				double Re = 0.0, Im = 0.0;
				for (int32 I = 0; I < N; ++I)
				{
					const double A = 2.0 * kPi * K * I / N;
					Re += S[I] * std::cos(A);
					Im += S[I] * std::sin(A);
				}
				(bKm ? Kilometre : Streaks) += 2.0 * (Re * Re + Im * Im) / (double(N) * N);
			}
		}
		Kilometre /= Total;
		Streaks /= Total;
	};
	FWeatherSystem Weather;
	Weather.Configure(EWeatherPreset::AfternoonBreeze, 5, 15.0);
	Weather.SetClimate(7, false);
	FWeatherState S = Weather.Evaluate(0.0);
	S.Wind.SpeedKnots = 12.0;
	const FWindField Wind(S.Wind);
	double Km, Streaks;
	Bands(Wind, Km, Streaks);
	S.Wind.CellShare = 0.0;
	const FWindField OneScale(S.Wind);
	double Km1, Streaks1;
	Bands(OneScale, Km1, Streaks1);
	const FWindField::FDerived& D = Wind.GetDerived();
	AddInfo(FString::Printf(TEXT("July afternoon (mixed layer %.0f m): cells %.1f to %.1f km waves, puffs %.0f m; puff variance at 2-8 km %.0f%%, at 250-1000 m %.0f%% (one scale: %.0f%%, %.0f%%)"),
		S.Wind.MixedLayerMeters, D.CellWaveMin / 1000.0, D.CellWaveMax / 1000.0, D.PuffAcross, Km * 100.0, Streaks * 100.0, Km1 * 100.0, Streaks1 * 100.0));
	TestTrue(TEXT("Cells within 2 to 5 km"), D.CellWaveMin >= 2000.0 && D.CellWaveMax <= 5000.0);
	TestTrue(TEXT("Most of the puffs' energy at kilometres"), Km > 0.45);
	TestTrue(TEXT("Streaks inside them"), Streaks > 0.08 && D.PuffAcross <= 1000.0);
	TestTrue(TEXT("The one-scale field had no streaks"), Streaks1 < 0.03);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWindPuffVeerTest, "SailingSim.Physics.WindPuffVeersAndFans", WindTestFlags)
bool FWindPuffVeerTest::RunTest(const FString& Parameters)
{
	// Puffs only (no fine turbulence, no slow shifts), wind from the north. Find the strongest puff on the water.
	FWindParams P;
	P.SpeedKnots = 10.0;
	P.FromDegrees = 0.0;
	P.GustIntensity = 0.0;
	P.PuffIntensity = 0.1;
	P.MixedLayerMeters = 1000.0;
	P.Seed = 3;
	const FWindField Wind(P);
	const double T = 1800.0;
	double Best = 0.0, BX = 0.0, BY = 0.0;
	for (int32 I = -60; I <= 60; ++I)
	{
		for (int32 J = -60; J <= 60; ++J)
		{
			double F, S;
			Wind.PuffAt(I * 50.0, J * 50.0, T, F, S);
			if (F > Best) { Best = F; BX = I * 50.0; BY = J * 50.0; }
		}
	}
	// Refine to the centre.
	for (int32 Pass = 0; Pass < 3; ++Pass)
	{
		const double Step = 20.0 / (1 << Pass);
		for (int32 I = -5; I <= 5; ++I) for (int32 J = -5; J <= 5; ++J)
		{
			double F, S;
			Wind.PuffAt(BX + I * Step, BY + J * Step, T, F, S);
			if (F > Best) { Best = F; BX += I * Step; BY += J * Step; I = J = -6; }
		}
	}
	double CF, CS;
	Wind.PuffAt(BX, BY, T, CF, CS);
	// Across the puff's track: to the right of the drift (Unreal: +90 degrees from it).
	const Vec3 Drift = Wind.PuffDrift();
	const double A = std::atan2(Drift.Y, Drift.X) + 0.5 * kPi;
	double Right = -1e9, Left = 1e9;
	const double R = 0.5 * Wind.GetDerived().PuffAcross;
	for (double D = 0.1 * R; D <= 0.9 * R; D += 0.05 * R)
	{
		double F, S;
		Wind.PuffAt(BX + std::cos(A) * D, BY + std::sin(A) * D, T, F, S);
		Right = FMath::Max(Right, S);
		Wind.PuffAt(BX - std::cos(A) * D, BY - std::sin(A) * D, T, F, S);
		Left = FMath::Min(Left, S);
	}
	// Lulls: where there is no puff, the wind is lighter and backed.
	double LullShift = 0.0;
	int32 Lulls = 0;
	for (int32 I = -40; I <= 40; ++I) for (int32 J = -40; J <= 40; ++J)
	{
		double F, S;
		Wind.PuffAt(I * 77.0, J * 83.0, T, F, S);
		if (F < 1.0) { LullShift += S; ++Lulls; }
	}
	LullShift /= FMath::Max(Lulls, 1);
	AddInfo(FString::Printf(TEXT("Strongest puff %.0f%% over the mean, veered %.1f deg at its centre; %.1f deg on its right, %.1f deg on its left; lulls %.1f deg"),
		(CF - 1.0) * 100.0, CS * kRadToDeg, Right * kRadToDeg, Left * kRadToDeg, LullShift * kRadToDeg));
	TestTrue(TEXT("A real puff"), CF > 1.15);
	TestTrue(TEXT("It veers about the puff veer (7 deg)"), CS * kRadToDeg > 4.0 && CS * kRadToDeg < 12.0);
	TestTrue(TEXT("Fans out to the right on its right side"), (Right - CS) * kRadToDeg > 10.0);
	TestTrue(TEXT("... and to the left on its left side"), (CS - Left) * kRadToDeg > 10.0 && Left < 0.0);
	TestTrue(TEXT("Lulls back"), LullShift < 0.0);
	// The veer is tunable.
	P.PuffVeerDegrees = 14.0;
	const FWindField Twice(P);
	double TF, TS;
	Twice.PuffAt(BX, BY, T, TF, TS);
	TestEqual(TEXT("Twice the veer, twice the turn"), TS, 2.0 * CS, 0.25 * FMath::Abs(CS));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWindFrameRateTest, "SailingSim.Physics.WindSameAtAnyFrameRate", WindTestFlags)
bool FWindFrameRateTest::RunTest(const FString& Parameters)
{
	// The game re-applies the weather's wind every frame, anchored at the boat. The same seed and time give the same field
	// at 30 and 144 fps: exactly while nothing changes, within a hair while the breeze builds and veers.
	auto Run = [](double Fps, bool bChanging, double Seconds)
	{
		FWindParams P;
		P.SpeedKnots = 11.0;
		P.FromDegrees = 200.0;
		P.GustIntensity = 0.14;
		P.PuffIntensity = 0.09;
		P.ShiftDegrees = 8.0;
		P.PersistentShiftDegrees = 8.0;
		P.Seed = 77;
		FWindField Wind(P);
		for (int32 F = 0; F <= FMath::RoundToInt(Seconds * Fps); ++F)
		{
			const double T = F / Fps;
			if (bChanging)
			{
				P.SpeedKnots = 11.0 + 3.0 * T / Seconds;
				P.FromDegrees = 200.0 + 10.0 * T / Seconds;
			}
			// A boat 2 km out sailing north at 3 m/s.
			Wind.SetParamsAt(P, T, 2000.0 + 3.0 * T, 500.0);
		}
		return Wind;
	};
	const double Seconds = 120.0;
	for (const bool bChanging : { false, true })
	{
		const FWindField A = Run(30.0, bChanging, Seconds), B = Run(144.0, bChanging, Seconds);
		double MaxSpeed = 0.0, MaxDir = 0.0;
		for (int32 I = 0; I < 200; ++I)
		{
			const Vec3 Pos(2000.0 + 360.0 + (I % 20) * 37.0, 500.0 + (I / 20) * 41.0, 10.0);
			const Vec3 VA = A.VelocityAt(Pos, Seconds), VB = B.VelocityAt(Pos, Seconds);
			MaxSpeed = FMath::Max(MaxSpeed, FMath::Abs(VA.LengthXY() - VB.LengthXY()) / VA.LengthXY());
			MaxDir = FMath::Max(MaxDir, FMath::Abs(WrapAngle(std::atan2(VA.Y, VA.X) - std::atan2(VB.Y, VB.X))));
		}
		AddInfo(FString::Printf(TEXT("%s: 30 vs 144 fps differ by %.2g in speed, %.2g deg"), bChanging ? TEXT("Building and veering") : TEXT("Steady"), MaxSpeed, MaxDir * kRadToDeg));
		if (bChanging)
		{
			TestTrue(TEXT("Building and veering: the same field within 1% and half a degree"), MaxSpeed < 0.01 && MaxDir < 0.5 * kDegToRad);
		}
		else
		{
			TestTrue(TEXT("Steady: the same field exactly"), MaxSpeed < 1e-12 && MaxDir < 1e-12);
		}
	}
	// A change of direction turns the patterns about the anchor (the boat), not the map origin: 10 km out, a 10-degree
	// swing leaves the puff at the boat where it was.
	FWindParams P;
	P.SpeedKnots = 10.0;
	P.GustIntensity = 0.14;
	P.PuffIntensity = 0.09;
	P.Seed = 4;
	FWindField Wind(P);
	const Vec3 Boat(10000.0, -7000.0, 10.0);
	Wind.SetParamsAt(P, 100.0, Boat.X, Boat.Y);
	double F0, S0;
	Wind.PuffAt(Boat.X, Boat.Y, 100.0, F0, S0);
	P.FromDegrees = 10.0;
	Wind.SetParamsAt(P, 100.0, Boat.X, Boat.Y);
	double F1, S1;
	Wind.PuffAt(Boat.X, Boat.Y, 100.0, F1, S1);
	TestEqual(TEXT("A wind swing does not move the puff at the boat"), F1, F0, 1e-9);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWindShelterBandTest, "SailingSim.Lake.ShelterBandBehindTrees", WindTestFlags)
bool FWindShelterBandTest::RunTest(const FString& Parameters)
{
	// A low bank (1 m) along the north shore (X > 1200) with a 40 m belt of 12 m trees on it; water to the south; wind
	// from the north. The lee is deepest close in, still there at 10 tree heights, mostly gone at 20 and gone by 30;
	// the open-water wind builds with fetch. Houses shelter too.
	const int Rows = 800, Cols = 100;
	std::vector<float> H(Rows * Cols);
	for (int R = 0; R < Rows; ++R) for (int C = 0; C < Cols; ++C) H[R * Cols + C] = R * 2.0 > 1200.0 ? 1.0f : -6.0f;
	FLakeTerrain Lake;
	Lake.InitSynthetic(Rows, Cols, 2.0, 0.0, 0.0, H);
	std::vector<uint8_t> Trees(80 * 10, 0);
	for (int R = 0; R < 80; ++R) for (int C = 0; C < 10; ++C) Trees[R * 10 + C] = (R * 20.0 >= 1200.0 && R * 20.0 < 1240.0) ? 255 : 0;
	Lake.InitSyntheticTrees(80, 10, 20.0, 0.0, 0.0, Trees);
	FShelterMap Shelter;
	Shelter.Build(Lake, 0.0, 10.0);
	const double Top = 13.0; // bank and canopy
	auto LeeAtHeights = [&](double N) { return Shelter.LeeAt(1200.0 - N * Top, 100.0); };
	AddInfo(FString::Printf(TEXT("Lee of a 12 m treeline: %.2f at 3 heights, %.2f at 10, %.2f at 20, %.2f at 32; open-water build %.2f at 40 m, %.2f at 1.2 km"),
		LeeAtHeights(3), LeeAtHeights(10), LeeAtHeights(20), LeeAtHeights(32), Shelter.BuildAt(1160.0, 100.0), Shelter.BuildAt(20.0, 100.0)));
	TestTrue(TEXT("Deep lee right behind the trees"), LeeAtHeights(3) < 0.45);
	TestTrue(TEXT("Still sheltered 10 heights downwind"), LeeAtHeights(10) < 0.6);
	TestTrue(TEXT("Mostly recovered by 20 heights"), LeeAtHeights(20) > 0.65 && LeeAtHeights(20) < 0.92);
	TestTrue(TEXT("Gone by 30 heights"), LeeAtHeights(32) > 0.98);
	// W6's LES: 0.91 of the open-water wind at the shore, full by about a kilometre.
	TestTrue(TEXT("The wind builds over open water"), Shelter.BuildAt(1160.0, 100.0) < 0.94 && Shelter.BuildAt(20.0, 100.0) > 0.99);
	TestEqual(TEXT("Factor is lee times build"), Shelter.FactorAt(800.0, 100.0), Shelter.LeeAt(800.0, 100.0) * Shelter.BuildAt(800.0, 100.0), 1e-9);

	// Without the trees a 1 m bank hardly shelters; a row of 9 m houses on it does.
	FLakeTerrain Bare;
	Bare.InitSynthetic(Rows, Cols, 2.0, 0.0, 0.0, H);
	FShelterMap Open, Houses;
	Open.Build(Bare, 0.0, 10.0);
	std::vector<FShelterObstacle> Row;
	for (double Y = 0.0; Y <= 200.0; Y += 15.0) Row.push_back({ 1215.0, Y, 6.0, 1.0 + 9.0 });
	Houses.Build(Bare, 0.0, 10.0, &Row);
	AddInfo(FString::Printf(TEXT("100 m downwind of the bank: %.2f bare, %.2f behind houses"), Open.LeeAt(1100.0, 100.0), Houses.LeeAt(1100.0, 100.0)));
	TestTrue(TEXT("A bare bank barely shelters 100 m out"), Open.LeeAt(1100.0, 100.0) > 0.98);
	TestTrue(TEXT("Houses do"), Houses.LeeAt(1100.0, 100.0) < 0.7);
	return true;
}

#endif
