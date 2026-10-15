#include "Misc/AutomationTest.h"
#include "LakeData.h"
#include "LakeTerrain.h"
#include "SeaState.h"
#include "Waves.h"
#include <algorithm>
#include <memory>
#include <vector>

#if WITH_DEV_AUTOMATION_TESTS

using namespace Sailing;

// W3, sea state by direction (docs/water-3): the fetch map, the sea map and the field reading it, against the PC's SWAN
// bake of Ray Hubbard (docs/water-3/swan-bake.md).

namespace
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	double SeaMedian(std::vector<double> V)
	{
		if (V.empty()) return 0.0;
		std::nth_element(V.begin(), V.begin() + V.size() / 2, V.end());
		return V[V.size() / 2];
	}

	/** A field at this wind with the sea map built for it, at its target (as the game mode sets them up). */
	std::unique_ptr<FWaveField> SeaFieldFor(const FSeaFetch& Fetch, double Knots, double FromDegrees)
	{
		auto W = std::make_unique<FWaveField>(1);
		FWaveParams P;
		P.WindSpeedKnots = Knots;
		P.WindFromDegrees = FromDegrees;
		W->SetDepth(Fetch.GetMedianDepth());
		W->SetWind(P);
		auto Map = std::make_shared<FSeaMap>();
		Map->Build(Fetch, W->GetComponents(), Knots * kKnot, FromDegrees * kDegToRad + kPi);
		W->SetSeaMap(Map);
		W->SnapToTarget();
		return W;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSeaFetchTest, "SailingSim.Physics.SeaFetch", Flags)
bool FSailingSeaFetchTest::RunTest(const FString& Parameters)
{
	// The march: a 2 km x 1 km basin of 10 m cells in land. Toward the north (waves from the south) the fetch at a cell is
	// its distance from the south shore; along a diagonal it is the distance to the shore along the diagonal.
	const int R = 200, C = 100;
	std::vector<uint8_t> Water(R * C, 1);
	std::vector<float> Out;
	FSeaFetch::March(Water, R, C, 10.0, kPi, 15000.0, Out);
	TestEqual(TEXT("From the south: the north edge's fetch is the basin's length"), double(Out[(R - 1) * C + 50]), 2000.0, 1.0);
	TestEqual(TEXT("... and the middle's half of it"), double(Out[99 * C + 50]), 1000.0, 1.0);
	FSeaFetch::March(Water, R, C, 10.0, 0.0, 300.0, Out);
	TestEqual(TEXT("The cap holds"), double(Out[0]), 300.0, 1e-3);
	// From the south-west (225 deg) at the basin's north-east corner: the shore 100 cells west along the diagonal.
	FSeaFetch::March(Water, R, C, 10.0, 225.0 * kDegToRad, 15000.0, Out);
	TestEqual(TEXT("Along a diagonal"), double(Out[(R - 1) * C + C - 1]), 1000.0 * FMath::Sqrt(2.0), 15.0);

	// The map's Saville fetch against FLakeTerrain::EffectiveFetch (rays to the shore) over Ray Hubbard.
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	const double Start = FPlatformTime::Seconds();
	FSeaFetch Fetch;
	Fetch.Build(T);
	const double BuildSeconds = FPlatformTime::Seconds() - Start;
	AddInfo(FString::Printf(TEXT("Ray Hubbard: %d x %d cells of %.0f m, median depth %.1f m, built in %.2f s"),
		Fetch.GetRows(), Fetch.GetCols(), Fetch.GetCell(), Fetch.GetMedianDepth(), BuildSeconds));
	TestEqual(TEXT("The lake's map is 50 m"), Fetch.GetCell(), 50.0);
	TestTrue(TEXT("Built at load in under 2 s"), BuildSeconds < 2.0);
	std::vector<double> Ratio;
	for (int I = 0; I < 400; ++I)
	{
		const int Row = (I * 37) % Fetch.GetRows(), Col = (I * 53) % Fetch.GetCols();
		if (Fetch.DepthAt(Row, Col) < 2.0) continue;
		const double X = Fetch.GetOriginX() + Row * Fetch.GetCell(), Y = Fetch.GetOriginY() + Col * Fetch.GetCell();
		for (int B = 0; B < kSeaBins; B += 3)
		{
			const double Travel = B * 2.0 * kPi / kSeaBins;
			const double Ray = FMath::Clamp(T.EffectiveFetch(X, Y, Travel + kPi), 50.0, 15000.0);
			Ratio.push_back(FMath::Max(Fetch.FetchAt(Row, Col, B), 50.f) / Ray);
		}
	}
	std::sort(Ratio.begin(), Ratio.end());
	const double P25 = Ratio[Ratio.size() / 4], P50 = Ratio[Ratio.size() / 2], P75 = Ratio[3 * Ratio.size() / 4];
	AddInfo(FString::Printf(TEXT("Map / rays over %d samples: p25 %.2f, median %.2f, p75 %.2f"), int(Ratio.size()), P25, P50, P75));
	TestTrue(TEXT("The march agrees with the rays (median within 10%)"), FMath::Abs(P50 - 1.0) < 0.1);
	TestTrue(TEXT("... and half the points within 25%"), P25 > 0.75 && P75 < 1.25);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSeaDepthTest, "SailingSim.Physics.SeaDepth", Flags)
bool FSailingSeaDepthTest::RunTest(const FString& Parameters)
{
	// TMA (Bouws et al. 1985): Kitaigorodskii's factor is 1 in deep water, 0.5 omega_h^2 in the shallow limit.
	TestEqual(TEXT("TMA: deep"), FSeaMap::TmaFactor(2.0 * kPi / 2.0, 50.0), 1.0, 1e-9);
	const double Omega = 2.0 * kPi / 3.0, H = 0.5;
	const double Wh = Omega * FMath::Sqrt(H / kGravity);
	TestEqual(TEXT("TMA: shallow limit"), FSeaMap::TmaFactor(Omega, H), 0.5 * Wh * Wh, 1e-9);
	TestEqual(TEXT("TMA: continuous at omega_h = 1"), FSeaMap::TmaFactor(1.0 / FMath::Sqrt(3.0 / kGravity), 3.0), 0.5, 1e-9);
	TestEqual(TEXT("TMA: dry"), FSeaMap::TmaFactor(Omega, 0.0), 0.0, 1e-12);

	// Shallow-water dispersion: in 3 m of water a 3 s wave satisfies omega^2 = g k tanh(k h) and travels slower than in
	// deep water (Galveston's chop moved 10 to 20% too fast).
	FWaveField Deep(1), Shallow(1);
	Shallow.SetDepth(3.0);
	double Slowest = 1.0;
	for (int I = 0; I < kWaveComponents; ++I)
	{
		const FWaveComponent& A = Deep.GetComponents()[I];
		const FWaveComponent& B = Shallow.GetComponents()[I];
		const double K = FMath::Sqrt(B.Kx * B.Kx + B.Ky * B.Ky), KDeep = FMath::Sqrt(A.Kx * A.Kx + A.Ky * A.Ky);
		TestEqual(TEXT("Frequency kept"), B.Omega, A.Omega, 1e-12);
		TestEqual(TEXT("Dispersion in 3 m"), B.Omega * B.Omega, kGravity * K * FMath::Tanh(K * 3.0), 1e-9 * B.Omega * B.Omega);
		TestEqual(TEXT("Direction kept"), FMath::Atan2(B.Ky, B.Kx), FMath::Atan2(A.Ky, A.Kx), 1e-9);
		Slowest = FMath::Min(Slowest, KDeep / K);
	}
	AddInfo(FString::Printf(TEXT("In 3 m the longest component travels at %.0f%% of its deep-water speed"), 100.0 * Slowest));
	TestTrue(TEXT("The long waves slow down in 3 m"), Slowest < 0.85);

	// Without a map the field is the same sea everywhere (polars, reference checks).
	FWaveParams P;
	P.WindSpeedKnots = 14.0;
	P.FetchMeters = 3000.0;
	Deep.SetWind(P);
	Deep.SnapToTarget();
	TestEqual(TEXT("No map: Hs anywhere is the field's"), Deep.SignificantHeightAt(1234.0, -5678.0), Deep.SignificantHeight(), 1e-12);
	TestEqual(TEXT("No map: the target is the growth law's"), Deep.SignificantHeight(), FWaveField::TargetSignificantHeight(14.0 * kKnot, 3000.0), 1e-3);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSeaStateSwanTest, "SailingSim.Lake.SeaStateSwan", Flags)
bool FSailingSeaStateSwanTest::RunTest(const FString& Parameters)
{
	FLakeData Lake;
	if (!TestTrue(TEXT("Lake Ray Hubbard data loads"), Lake.Load(FLakeData::DefaultDirectory(), TEXT("RayHubbard")))) return false;
	const FLakeTerrain& T = Lake.Terrain;
	FSeaFetch Fetch;
	Fetch.Build(T);

	// SWAN's lake medians (docs/water-3/swan-compare.csv, the median over its 16 directions of the median over the wet
	// cells), against the map's sea sampled every 250 m of water.
	TArray<FVector2D> Cells;
	for (double X = T.GetOriginX(); X < T.GetOriginX() + T.GetRows() * T.GetCell(); X += 250.0)
		for (double Y = T.GetOriginY(); Y < T.GetOriginY() + T.GetCols() * T.GetCell(); Y += 250.0)
			if (T.HeightAt(X, Y) < 0.0) Cells.Add(FVector2D(X, Y));
	struct FCase { double Knots, Swan; };
	const FCase Cases[] = { { 5.0, 0.048 }, { 11.0, 0.125 }, { 18.0, 0.238 }, { 28.0, 0.493 } };
	for (const FCase& Case : Cases)
	{
		std::vector<double> PerDirection;
		for (int D = 0; D < 16; D += 2)
		{
			const auto W = SeaFieldFor(Fetch, Case.Knots, D * 22.5);
			std::vector<double> Hs;
			for (const FVector2D& C : Cells) Hs.push_back(W->SignificantHeightAt(C.X, C.Y));
			PerDirection.push_back(SeaMedian(Hs));
		}
		const double Game = SeaMedian(PerDirection);
		AddInfo(FString::Printf(TEXT("%.0f kn: lake median Hs %.3f m, SWAN %.3f m (%+.0f%%)"), Case.Knots, Game, Case.Swan, 100.0 * (Game / Case.Swan - 1.0)));
		TestTrue(*FString::Printf(TEXT("Lake median within 10%% of SWAN at %.0f kn"), Case.Knots), FMath::Abs(Game / Case.Swan - 1.0) < 0.1);
	}

	// Each point its own sea (SWAN's spectrum points, docs/water-3/points.csv), 14 kn: the lee shore at the club in a
	// northerly, the open lake off it, the long fetch to the dam.
	struct FPoint { const TCHAR* Name; double X, Y, From, Swan; };
	const FPoint Points[] = {
		{ TEXT("Rush Creek Yacht Club, northerly"), 5.0, -35.0, 0.0, 0.133 },
		{ TEXT("Off Rush Creek, northerly"), 605.0, -535.0, 0.0, 0.165 },
		{ TEXT("South lake near the dam, northerly"), -895.0, -1385.0, 0.0, 0.256 },
		{ TEXT("Off Rush Creek, southerly"), 605.0, -535.0, 180.0, 0.197 },
		{ TEXT("Chandlers Landing, southerly"), 5555.0, 1115.0, 180.0, 0.20 } };
	double Club = 0.0, Dam = 0.0;
	for (const FPoint& P : Points)
	{
		const auto W = SeaFieldFor(Fetch, 14.0, P.From);
		const double Hs = W->SignificantHeightAt(P.X, P.Y);
		AddInfo(FString::Printf(TEXT("%s: Hs %.3f m, SWAN %.3f m"), P.Name, Hs, P.Swan));
		TestTrue(*FString::Printf(TEXT("%s within 30%% of SWAN"), P.Name), FMath::Abs(Hs / P.Swan - 1.0) < 0.3);
		if (P.X == 5.0) Club = Hs;
		if (P.X == -895.0) Dam = Hs;
	}
	TestTrue(TEXT("In a northerly the club's lee shore has less sea than the dam"), Club < 0.75 * Dam);

	// The map scales what the boat feels and what is drawn alike: BandsAt's variance is SignificantHeightAt's, and land
	// has no sea.
	const auto W = SeaFieldFor(Fetch, 14.0, 0.0);
	for (const FPoint& P : Points)
	{
		std::vector<FWaveBand> Bands;
		W->BandsAt(P.X, P.Y, Bands);
		double V = 0.0;
		for (const FWaveBand& B : Bands) V += B.Variance;
		TestEqual(TEXT("Bands at a point carry its Hs"), 4.0 * FMath::Sqrt(V), W->SignificantHeightAt(P.X, P.Y), 1e-3);
	}
	TestEqual(TEXT("No sea on land"), W->SignificantHeightAt(T.GetOriginX() + 10.0, T.GetOriginY() + 10.0), 0.0, 1e-6);
	return true;
}

#endif
