#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "Waves.h"
#include "Wind.h"
#include <algorithm>
#include <vector>

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// W3 prep (docs/w3-prep): the lake's sea against the PC's SWAN bake of Ray Hubbard (docs/water-3/swan-bake.md), and the
// wind over the water against W6's LES of the lake's outline (docs/water-6/les-pilot.md).

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	double Median(std::vector<double> V)
	{
		if (V.empty()) return 0.0;
		std::nth_element(V.begin(), V.begin() + V.size() / 2, V.end());
		return V[V.size() / 2];
	}

	/** The fetch the game grows the sea on at a point (ASailingGameMode: the effective fetch, 200 m to 15 km). */
	double GameFetch(const FLakeTerrain& T, double X, double Y, double FromRadians)
	{
		return std::clamp(T.EffectiveFetch(X, Y, FromRadians), 200.0, 15000.0);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingWaveGrowthSwanTest, "SailingSim.Physics.WaveGrowthSwan", Flags)
bool FSailingWaveGrowthSwanTest::RunTest(const FString& Parameters)
{
	// The adjusted wind (SPM 1984 eq. 3-28, as the CEM keeps it for these laws): U_A = 0.71 U^1.23.
	TestEqual(TEXT("U_A at 10 m/s"), FWaveField::AdjustedWindSpeed(10.0), 0.71 * FMath::Pow(10.0, 1.23), 1e-9);
	TestTrue(TEXT("U_A is about U at 8.6 kn"), FMath::Abs(FWaveField::AdjustedWindSpeed(4.43) / 4.43 - 1.0) < 0.01);

	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;

	// The bake's statistic: per wind direction (16), the median Hs over the lake's wet cells; then the median over the
	// directions. Here every 250 m of water.
	TArray<FVector2D> Cells;
	for (double X = T.GetOriginX(); X < T.GetOriginX() + T.GetRows() * T.GetCell(); X += 250.0)
		for (double Y = T.GetOriginY(); Y < T.GetOriginY() + T.GetCols() * T.GetCell(); Y += 250.0)
			if (T.HeightAt(X, Y) < 0.0) Cells.Add(FVector2D(X, Y));
	if (!TestTrue(TEXT("Enough water cells"), Cells.Num() > 1000)) return false;
	std::vector<std::vector<double>> Fetch(16);
	for (int D = 0; D < 16; ++D)
		for (const FVector2D& C : Cells) Fetch[D].push_back(GameFetch(T, C.X, C.Y, D * 22.5 * kDegToRad));

	// Physics gaps: above 18 kn the targets grow in U_A steepened by (U / 18 kn)^0.43, continuous at 18 kn.
	TestEqual(TEXT("The stress wind is U_A up to 18 kn"), FWaveField::GrowthStressWind(17.9 * kKnot), FWaveField::AdjustedWindSpeed(17.9 * kKnot), 1e-12);
	TestEqual(TEXT("... continuous at 18 kn"), FWaveField::GrowthStressWind(18.0001 * kKnot), FWaveField::AdjustedWindSpeed(18.0001 * kKnot), 1e-4);
	TestEqual(TEXT("... and (U / 18 kn)^0.43 over it at 28 kn"), FWaveField::GrowthStressWind(28.0 * kKnot) / FWaveField::AdjustedWindSpeed(28.0 * kKnot),
		FMath::Pow(28.0 / 18.0, 0.43), 1e-9);

	// SWAN's lake medians (docs/water-3/swan-compare.csv, the median over directions); 10 kn between 8 and 11 kn on the
	// growth's own power (Hs ~ U^1.2 between them).
	// Mac polish: SWAN's median peak period, the bake's SWAN / game period ratio times the period of the game it compared
	// against (scripts/wave-check.sh); none at 10 kn, which the bake didn't run.
	struct FCase { double Knots, Swan, Tolerance, SwanTp; };
	const double Swan10 = 0.084 * FMath::Pow(10.0 / 8.0, FMath::Loge(0.123 / 0.084) / FMath::Loge(11.0 / 8.0));
	const FCase Cases[] = { { 5.0, 0.047, 0.10, 0.91 }, { 8.0, 0.084, 0.10, 1.14 }, { 10.0, Swan10, 0.10, 0.0 }, { 11.0, 0.123, 0.10, 1.33 },
		{ 14.0, 0.164, 0.10, 1.49 }, { 18.0, 0.232, 0.10, 1.70 }, { 22.0, 0.325, 0.10, 1.99 }, { 28.0, 0.485, 0.10, 2.38 } };
	for (const FCase& Case : Cases)
	{
		std::vector<double> PerDirection, TpPerDirection;
		for (int D = 0; D < 16; ++D)
		{
			std::vector<double> Hs, Tp;
			for (double F : Fetch[D])
			{
				Hs.push_back(FWaveField::TargetSignificantHeight(Case.Knots * kKnot, F));
				Tp.push_back(FWaveField::TargetPeakPeriod(Case.Knots * kKnot, F));
			}
			PerDirection.push_back(Median(Hs));
			TpPerDirection.push_back(Median(Tp));
		}
		const double Game = Median(PerDirection), GameTp = Median(TpPerDirection);
		AddInfo(FString::Printf(TEXT("%.0f kn: game %.3f m, SWAN %.3f m (%+.0f%%); Tp %.2f s"), Case.Knots, Game, Case.Swan, 100.0 * (Game / Case.Swan - 1.0), GameTp));
		TestTrue(*FString::Printf(TEXT("Lake median Hs at %.0f kn within %.0f%% of SWAN"), Case.Knots, 100.0 * Case.Tolerance),
			FMath::Abs(Game / Case.Swan - 1.0) < Case.Tolerance);
		if (Case.SwanTp > 0.0)
		{
			// (Before the Toba period, 22 kn was 7% short and 28 kn 11%.)
			TestTrue(*FString::Printf(TEXT("Lake median Tp at %.0f kn within 10%% of SWAN's %.2f s"), Case.Knots, Case.SwanTp),
				FMath::Abs(GameTp / Case.SwanTp - 1.0) < 0.10);
		}
	}
	// The period follows Toba's 3/2 law in U_A from the steepened height: at 28 kn (Hs / Hs in U_A)^(2/3) = (28 / 18)^0.287.
	const double Ua28 = FWaveField::AdjustedWindSpeed(28.0 * kKnot);
	// (Times docs/lake-periods/' short-fetch factor, fitted to SWAN's points: 1.04 at 2 km.)
	TestEqual(TEXT("Tp at 28 kn over 2 km is Toba's from the steepened Hs"), FWaveField::TargetPeakPeriod(28.0 * kKnot, 2000.0) / FWaveField::GrowthLawPeriod(Ua28, 2000.0),
		FMath::Pow(28.0 / 18.0, 0.43 * 2.0 / 3.0) * FWaveField::ShortFetchPeriodFactor(28.0 * kKnot, 2000.0), 1e-9);
	TestEqual(TEXT("... and U_A's own up to 18 kn"), FWaveField::TargetPeakPeriod(15.0 * kKnot, 2000.0),
		FWaveField::GrowthLawPeriod(FWaveField::AdjustedWindSpeed(15.0 * kKnot), 2000.0) * FWaveField::ShortFetchPeriodFactor(15.0 * kKnot, 2000.0), 1e-12);
	// (W3 prep left 28 kn 18% low, held at 20%; with the steepened stress wind every speed is inside 10%.)
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingLeeShoreChopTest, "SailingSim.Lake.LeeShoreChop", Flags)
bool FSailingLeeShoreChopTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	// Rush Creek Yacht Club's spectrum point (the bake's 50 m cell off the club), 14 kn. In a northerly it is a lee shore:
	// the ray straight upwind finds the shore within 200 m and the game had 4 cm of chop where SWAN has 13 cm. In a
	// southerly the whole lake lies upwind.
	const double X = 5.0, Y = -35.0, U = 14.0 * kKnot;
	const double RayN = T.FetchToward(X, Y, 0.0), EffN = T.EffectiveFetch(X, Y, 0.0);
	const double HsN = FWaveField::TargetSignificantHeight(U, GameFetch(T, X, Y, 0.0));
	const double HsS = FWaveField::TargetSignificantHeight(U, GameFetch(T, X, Y, kPi));
	const double TpN = FWaveField::TargetPeakPeriod(U, GameFetch(T, X, Y, 0.0));
	AddInfo(FString::Printf(TEXT("Rush Creek, 14 kn northerly: fetch %.0f m straight upwind, %.0f m effective; Hs %.3f m (SWAN 0.133), Tp %.2f s (SWAN 1.86)"),
		RayN, EffN, HsN, TpN));
	AddInfo(FString::Printf(TEXT("Rush Creek, 14 kn southerly: Hs %.3f m (SWAN 0.138)"), HsS));
	TestTrue(TEXT("The straight-upwind ray is short (a lee shore)"), RayN < 400.0);
	TestTrue(TEXT("The effective fetch reaches down the lake"), EffN > 3.0 * RayN);
	TestTrue(TEXT("Lee-shore chop near SWAN's 13 cm"), FMath::Abs(HsN / 0.133 - 1.0) < 0.2);
	TestTrue(TEXT("Its period lengthens toward SWAN's"), TpN > 1.2);

	// Off a long straight shore the ray at angle a reaches it at d / cos a, so Saville's sum(F cos^2) / sum(cos) is d.
	const int Rows = 600, Cols = 600;
	std::vector<float> H(Rows * Cols);
	for (int R = 0; R < Rows; ++R) for (int C = 0; C < Cols; ++C) H[R * Cols + C] = R * 10.0 > 4000.0 ? 2.0f : -5.0f;
	FLakeTerrain Bay;
	Bay.InitSynthetic(Rows, Cols, 10.0, 0.0, -3000.0, H);
	// From 1 km off a straight north shore, the ray at angle a reaches it at 1 km / cos a.
	const double Eff = Bay.EffectiveFetch(3000.0, 0.0, 0.0), Ray = Bay.FetchToward(3000.0, 0.0, 0.0);
	AddInfo(FString::Printf(TEXT("1 km off a straight shore: ray %.0f m, effective %.0f m"), Ray, Eff));
	TestEqual(TEXT("Straight shore: the effective fetch is the perpendicular one"), Eff, Ray, 20.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingOverWaterGustsTest, "SailingSim.Physics.OverWaterGusts", Flags)
bool FSailingOverWaterGustsTest::RunTest(const FString& Parameters)
{
	// W6's LES of Ray Hubbard: over the water the gust intensity is 0.15 within a kilometre of the upwind shore, 0.14 at
	// 1-2 km, 0.13 at 2-4 km and 0.11 beyond; the wind 1.07 of the land's within 250 m, 1.13 from 0.5 to 2 km.
	TestEqual(TEXT("Gusts at the shore are the stations'"), FShelterMap::OpenWaterGust(0.0), 1.0, 1e-9);
	TestEqual(TEXT("... 0.15 / 0.15 within 500 m"), FShelterMap::OpenWaterGust(500.0), 1.0, 1e-9);
	TestEqual(TEXT("... 0.14 / 0.15 at 1.5 km"), FShelterMap::OpenWaterGust(1500.0), 0.14 / 0.15, 0.01);
	TestEqual(TEXT("... 0.13 / 0.15 at 3 km"), FShelterMap::OpenWaterGust(3000.0), 0.13 / 0.15, 0.01);
	TestEqual(TEXT("... 0.11 / 0.15 beyond 7 km"), FShelterMap::OpenWaterGust(8000.0), 0.11 / 0.15, 0.01);
	TestEqual(TEXT("Wind 0-250 m out / 1-2 km out (LES 1.07 / 1.13)"), FShelterMap::OpenWaterBuild(125.0) / FShelterMap::OpenWaterBuild(1500.0), 1.07 / 1.13, 0.01);
	TestEqual(TEXT("Wind 250-500 m out / 1-2 km out (LES 1.11 / 1.13)"), FShelterMap::OpenWaterBuild(375.0) / FShelterMap::OpenWaterBuild(1500.0), 1.11 / 1.13, 0.01);

	// A flat north shore (X > 9 km, a 1 m bank), 9 km of open water south of it; wind from the north. The field's gust
	// intensity measured at a point over an hour: near the shore it is the field's own (the stations'), far out it eases.
	const int Rows = 500, Cols = 40;
	std::vector<float> H(Rows * Cols);
	for (int R = 0; R < Rows; ++R) for (int C = 0; C < Cols; ++C) H[R * Cols + C] = R * 20.0 > 9000.0 ? 1.0f : -6.0f;
	FLakeTerrain Lake;
	Lake.InitSynthetic(Rows, Cols, 20.0, 0.0, 0.0, H);
	FShelterMap Shelter;
	Shelter.Build(Lake, 0.0, 40.0);
	FWindParams P;
	P.SpeedKnots = 12.0;
	P.GustIntensity = 0.15;
	FWindField Wind(P);
	Wind.SetShelter(&Shelter);
	FWindField Station(P); // no shelter map: the calibration's field, as the station-matched tests see it
	auto Intensity = [](const FWindField& W, double X, double Y)
	{
		double Sum = 0.0, Sq = 0.0;
		const int N = 3600;
		for (int I = 0; I < N; ++I)
		{
			const double G = W.GustFactorAt(Vec3(X, Y, 10.0), I * 1.0);
			Sum += G;
			Sq += G * G;
		}
		const double Mean = Sum / N;
		return FMath::Sqrt(FMath::Max(Sq / N - Mean * Mean, 0.0)) / Mean;
	};
	// Against the same field without the map at the same point (an hour at one point samples the kilometre cells only
	// partly, so points differ by more than the fetch alone).
	const double Near = Intensity(Wind, 8800.0, 400.0) / Intensity(Station, 8800.0, 400.0);
	const double Mid = Intensity(Wind, 6000.0, 400.0) / Intensity(Station, 6000.0, 400.0);
	const double Far = Intensity(Wind, 1000.0, 400.0) / Intensity(Station, 1000.0, 400.0);
	AddInfo(FString::Printf(TEXT("Gust intensity over the station's: %.3f 200 m from the upwind shore, %.3f at 3 km, %.3f at 8 km"), Near, Mid, Far));
	TestEqual(TEXT("Near the upwind shore the gusts are the station's"), Near, 1.0, 0.01);
	TestTrue(TEXT("They ease with fetch"), Mid < Near && Far < Mid);
	TestEqual(TEXT("3 km out about 0.13 / 0.15 of the shore's"), Mid, 0.13 / 0.15, 0.03);
	TestEqual(TEXT("8 km out about 0.11 / 0.15 of the shore's"), Far, 0.11 / 0.15, 0.03);
	TestEqual(TEXT("GustScaleAt follows the map"), Wind.GustScaleAt(1500.0, 400.0), Shelter.GustAt(1500.0, 400.0), 1e-9);
	TestEqual(TEXT("No shelter map: no change"), Station.GustScaleAt(1500.0, 400.0), 1.0, 1e-9);
	return true;
}

#endif
