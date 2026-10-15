// Mac polish: the lake's sea against the PC's SWAN bake of Ray Hubbard (docs/water-3/swan-compare.csv on w3-swan-bake),
// Hs and peak period, standalone (no Unreal). The statistic is SailingSim.Physics.WaveGrowthSwan's: per wind direction the
// median over the lake's water every 250 m, then the median over the 16 directions. SWAN's Tp at a direction and speed is
// the bake's median SWAN / game period ratio times the median period of the game the bake compared against (the SPM law in
// U on FLakeTerrain::FetchToward). Usage: scripts/wave-check.sh <swan-compare.csv>
// W3: `--map <points.csv> <out.csv>` sails the sea map (SeaState.h: every component scaled by its own direction's fetch
// and the depth) instead: the same lake-wide medians, then SWAN's ten points against the map and the old single ray.
#include "LakeTerrain.h"
#include "Waves.h"
#include "SeaState.h"
#include <memory>
#include <zlib.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace Sailing;

static std::vector<uint8_t> ReadFile(const std::string& Path)
{
	std::ifstream F(Path, std::ios::binary);
	return std::vector<uint8_t>((std::istreambuf_iterator<char>(F)), std::istreambuf_iterator<char>());
}

static double Median(std::vector<double> V)
{
	if (V.empty()) return 0.0;
	std::nth_element(V.begin(), V.begin() + V.size() / 2, V.end());
	return V[V.size() / 2];
}

int main(int Argc, char** Argv)
{
	if (Argc < 2) { std::fprintf(stderr, "usage: wave-check <swan-compare.csv>\n"); return 2; }
	FLakeTerrain T;
	const std::vector<uint8_t> H = ReadFile("Content/TerrainData/RayHubbard.height");
	if (!T.LoadHeight(H.data(), H.size())) { std::fprintf(stderr, "no RayHubbard.height (run from the repo root)\n"); return 1; }
	const std::vector<uint8_t> Z = ReadFile("Content/TerrainData/RayHubbard.detail");
	if (Z.size() > 8 && std::memcmp(Z.data(), "SSDZ", 4) == 0)
	{
		uint32_t RawSize = 0;
		std::memcpy(&RawSize, Z.data() + 4, 4);
		std::vector<uint8_t> Raw(RawSize);
		uLongf Len = RawSize;
		if (uncompress(Raw.data(), &Len, Z.data() + 8, Z.size() - 8) == Z_OK) T.LoadDetail(Raw.data(), Len);
	}

	// tp_ratio_median per (direction, knots).
	std::map<std::pair<int, int>, double> TpRatio;
	std::map<int, std::vector<double>> SwanHs;
	std::ifstream Csv(Argv[1]);
	std::string Line;
	std::getline(Csv, Line);
	while (std::getline(Csv, Line))
	{
		std::vector<std::string> F;
		std::stringstream S(Line);
		std::string Cell;
		while (std::getline(S, Cell, ',')) F.push_back(Cell);
		if (F.size() < 10 || F[0] != "RayHubbard") continue;
		const int Dir = static_cast<int>(std::stod(F[1]) * 10.0 + 0.5), Kn = std::stoi(F[2]);
		TpRatio[{ Dir, Kn }] = std::stod(F[9]);
		SwanHs[Kn].push_back(std::stod(F[4]));
	}

	std::vector<std::pair<double, double>> Cells;
	for (double X = T.GetOriginX(); X < T.GetOriginX() + T.GetRows() * T.GetCell(); X += 250.0)
		for (double Y = T.GetOriginY(); Y < T.GetOriginY() + T.GetCols() * T.GetCell(); Y += 250.0)
			if (T.HeightAt(X, Y) < 0.0) Cells.push_back({ X, Y });
	std::vector<std::vector<double>> Eff(16), Ray(16);
	for (int D = 0; D < 16; ++D)
		for (const auto& C : Cells)
		{
			const double A = D * 22.5 * kDegToRad;
			Eff[D].push_back(std::clamp(T.EffectiveFetch(C.first, C.second, A), 200.0, 15000.0));
			Ray[D].push_back(T.FetchToward(C.first, C.second, A));
		}

	std::printf("%zu water cells\nknots,swan_hs,game_hs,hs_err,swan_tp,game_tp,tp_err\n", Cells.size());
	for (const int Kn : { 5, 8, 11, 14, 18, 22, 28 })
	{
		const double U = Kn * kKnot;
		std::vector<double> Hs, Tp, SwanTp;
		for (int D = 0; D < 16; ++D)
		{
			std::vector<double> CellHs, CellTp, Bake;
			for (size_t I = 0; I < Cells.size(); ++I)
			{
				CellHs.push_back(FWaveField::TargetSignificantHeight(U, Eff[D][I]));
				CellTp.push_back(FWaveField::TargetPeakPeriod(U, Eff[D][I]));
				Bake.push_back(FWaveField::GrowthLawPeriod(U, Ray[D][I]));
			}
			Hs.push_back(Median(CellHs));
			Tp.push_back(Median(CellTp));
			SwanTp.push_back(TpRatio[{ D * 225, Kn }] * Median(Bake));
		}
		const double Sh = Median(SwanHs[Kn]), Gh = Median(Hs), St = Median(SwanTp), Gt = Median(Tp);
		std::printf("%d,%.3f,%.3f,%+.1f%%,%.2f,%.2f,%+.1f%%\n", Kn, Sh, Gh, 100.0 * (Gh / Sh - 1.0), St, Gt, 100.0 * (Gt / St - 1.0));
	}
	if (Argc < 5 || std::string(Argv[2]) != "--map") return 0;

	// W3: the sea map. Points (map frame, north and east m) as Tools/water/swan_bake.py picks them on the 50 m grid.
	struct FPoint { const char* Name; double X, Y; };
	const FPoint Points[] = {
		{ "Rush Creek Yacht Club", 5, -35 }, { "Off Rush Creek, open water", 605, -535 },
		{ "South lake, near the dam", -895, -1385 }, { "Chandlers Landing", 5555, 1115 },
		{ "North lake, below the SH-66 causeway", 9505, -535 }, { "Chandlers Landing", 5605, 1765 },
		{ "Harry Myers Park", 11155, 2565 }, { "open-7", 3255, -2535 }, { "open-8", 8105, -3935 }, { "open-9", 13355, 165 } };
	const double Lean = Argc > 5 ? std::atof(Argv[5]) : kSeaTowardWind;
	FSeaFetch Fetch;
	Fetch.Build(T, 50.0);
	std::printf("\nsea map: %d x %d cells of %.0f m, median depth %.1f m\n", Fetch.GetRows(), Fetch.GetCols(), Fetch.GetCell(), Fetch.GetMedianDepth());
	// The sea where the map has it: Hs and the peak of the band spectrum (variance per Hz) at a point.
	auto SeaAt = [](const FWaveField& W, double X, double Y, double& Hs, double& Tp)
	{
		float R[kSeaChannels];
		W.SeaRatiosAt(X, Y, R);
		double Band[kWaveBands] = {};
		for (int I = 0; I < kWaveComponents; ++I)
		{
			const double A = W.GetComponents()[I].Amplitude * R[std::min(I, kSeaLongComponents)];
			Band[I / kWaveDirectionsPerBand] += 0.5 * A * A;
		}
		double V = 0.0, Best = -1.0, Density[kWaveBands];
		int Peak = 0;
		for (int B = 0; B < kWaveBands; ++B)
		{
			V += Band[B];
			Density[B] = Band[B] / FWaveField::BandWidthHz(B);
			if (Density[B] > Best) { Best = Density[B]; Peak = B; }
		}
		// The peak between band centres: a parabola through the log densities against log frequency (bands are log-spaced).
		double Shift = 0.0;
		if (Peak > 0 && Peak < kWaveBands - 1 && Density[Peak - 1] > 0.0 && Density[Peak + 1] > 0.0)
		{
			const double L0 = std::log(Density[Peak - 1]), L1 = std::log(Density[Peak]), L2 = std::log(Density[Peak + 1]);
			const double Den = L0 - 2.0 * L1 + L2;
			if (Den < 0.0) Shift = std::clamp(0.5 * (L0 - L2) / Den, -0.5, 0.5);
		}
		const double Step = std::log(FWaveField::BandCentreHz(1) / FWaveField::BandCentreHz(0));
		Tp = 1.0 / (FWaveField::BandCentreHz(Peak) * std::exp(Shift * Step));
		Hs = 4.0 * std::sqrt(V);
	};
	auto FieldFor = [&](int Kn, double FromDeg, std::shared_ptr<FSeaMap>& Map)
	{
		auto W = std::make_unique<FWaveField>(1);
		FWaveParams P;
		P.WindSpeedKnots = Kn;
		P.WindFromDegrees = FromDeg;
		P.FetchMeters = 15000.0;
		W->SetDepth(Fetch.GetMedianDepth());
		W->SetWind(P);
		Map = std::make_shared<FSeaMap>();
		Map->Build(Fetch, W->GetComponents(), Kn * kKnot, FromDeg * kDegToRad + kPi, true, Lean);
		W->SetSeaMap(Map);
		W->SnapToTarget();
		return W;
	};
	std::printf("knots,swan_hs,map_hs,hs_err,ratio_p10,ratio_p90\n");
	// SWAN's per-direction medians.
	std::map<std::pair<int, int>, double> SwanDir;
	{
		std::ifstream C2(Argv[1]);
		std::getline(C2, Line);
		while (std::getline(C2, Line))
		{
			std::vector<std::string> F;
			std::stringstream S(Line);
			std::string Cell;
			while (std::getline(S, Cell, ',')) F.push_back(Cell);
			if (F.size() < 10 || F[0] != "RayHubbard") continue;
			SwanDir[{ static_cast<int>(std::stod(F[1]) * 10.0 + 0.5), std::stoi(F[2]) }] = std::stod(F[4]);
		}
	}
	for (const int Kn : { 5, 8, 11, 14, 18, 22, 28 })
	{
		std::vector<double> Hs, Ratio;
		for (int D = 0; D < 16; ++D)
		{
			std::shared_ptr<FSeaMap> Map;
			const auto W = FieldFor(Kn, D * 22.5, Map);
			std::vector<double> CellHs;
			for (const auto& C : Cells) { double CH, CP; SeaAt(*W, C.first, C.second, CH, CP); CellHs.push_back(CH); }
			Hs.push_back(Median(CellHs));
			Ratio.push_back(SwanDir[{ D * 225, Kn }] / std::max(Hs.back(), 1e-6));
		}
		std::sort(Ratio.begin(), Ratio.end());
		const double Sh = Median(SwanHs[Kn]), Gh = Median(Hs);
		std::printf("%d,%.3f,%.3f,%+.1f%%,%.2f,%.2f\n", Kn, Sh, Gh, 100.0 * (Gh / Sh - 1.0), Ratio[1], Ratio[14]);
	}

	// The sea over the lake at 14 kn from the north and from the south (Artifacts/sea-map-14kn-<from>.csv: Hs per map
	// cell, rows north), for docs/water-3's figure.
	for (const int From : { 0, 180 })
	{
		std::shared_ptr<FSeaMap> Map;
		const auto W = FieldFor(14, From, Map);
		std::ofstream G("Artifacts/sea-map-14kn-" + std::to_string(From) + ".csv");
		for (int R = 0; R < Fetch.GetRows(); ++R)
		{
			for (int C = 0; C < Fetch.GetCols(); ++C)
			{
				double CH = 0.0, CP = 0.0;
				if (Fetch.DepthAt(R, C) > 0.0) SeaAt(*W, Fetch.GetOriginX() + R * Fetch.GetCell(), Fetch.GetOriginY() + C * Fetch.GetCell(), CH, CP);
				G << (C ? "," : "") << CH;
			}
			G << '\n';
		}
	}

	// The points: SWAN against the map and against the old ray (points.csv's game columns).
	std::ifstream Pc(Argv[3]);
	std::ofstream Out(Argv[4]);
	Out << "point,wind_from,knots,swan_hs,map_hs,now_hs,ray_hs,swan_tp,map_tp,now_tp,ray_tp\n";
	std::getline(Pc, Line);
	std::map<std::string, int> Seen;
	std::vector<double> ErrMap, ErrRay, ErrNow, TErrMap, TErrRay, TErrNow;
	std::map<std::string, std::vector<double>> PointMap, PointRay, PointNow;
	std::map<std::pair<int, int>, std::pair<std::unique_ptr<FWaveField>, std::shared_ptr<FSeaMap>>> Fields;
	std::map<std::string, int> RowOfKey;
	while (std::getline(Pc, Line))
	{
		// Quoted names have commas.
		std::vector<std::string> F;
		std::string Cell;
		bool bQuote = false;
		for (char Ch : Line)
		{
			if (Ch == '"') bQuote = !bQuote;
			else if (Ch == ',' && !bQuote) { F.push_back(Cell); Cell.clear(); }
			else Cell += Ch;
		}
		F.push_back(Cell);
		if (F.size() < 9 || F[0] != "RayHubbard") continue;
		const double From = std::stod(F[2]);
		const int Kn = std::stoi(F[3]);
		// Two points share a name: the first and second rows of a case are the first and second point of that name.
		const std::string Key = F[1] + "|" + F[2] + "|" + F[3];
		const int Nth = RowOfKey[Key]++;
		const FPoint* P = nullptr;
		int Count = 0;
		for (const FPoint& Q : Points) if (F[1] == Q.Name && Count++ == Nth) { P = &Q; break; }
		if (!P) continue;
		auto& Slot = Fields[{ static_cast<int>(From * 10.0 + 0.5), Kn }];
		if (!Slot.first) Slot.first = FieldFor(Kn, From, Slot.second);
		double Hs, Tp;
		SeaAt(*Slot.first, P->X, P->Y, Hs, Tp);
		const double SwanHsP = std::stod(F[5]), RayHs = std::stod(F[6]), SwanTp = std::stod(F[7]), RayTp = std::stod(F[8]);
		// The game before W3: one sea for the whole lake from the effective fetch at the boat (W3 prep).
		const double NowFetch = std::clamp(T.EffectiveFetch(P->X, P->Y, From * kDegToRad), 200.0, 15000.0);
		const double NowHs = FWaveField::TargetSignificantHeight(Kn * kKnot, NowFetch), NowTp = FWaveField::TargetPeakPeriod(Kn * kKnot, NowFetch);
		Out << '"' << P->Name << "\"," << From << ',' << Kn << ',' << SwanHsP << ',' << Hs << ',' << NowHs << ',' << RayHs << ',' << SwanTp << ',' << Tp << ',' << NowTp << ',' << RayTp << '\n';
		if (SwanHsP <= 0.005) continue;
		ErrMap.push_back(std::fabs(std::log(Hs / SwanHsP)));
		ErrRay.push_back(std::fabs(std::log(std::max(RayHs, 1e-3) / SwanHsP)));
		ErrNow.push_back(std::fabs(std::log(NowHs / SwanHsP)));
		TErrNow.push_back(std::fabs(std::log(NowTp / SwanTp)));
		PointNow[P->Name].push_back(NowHs / SwanHsP);
		TErrMap.push_back(std::fabs(std::log(Tp / SwanTp)));
		TErrRay.push_back(std::fabs(std::log(std::max(RayTp, 0.1) / SwanTp)));
		PointMap[P->Name].push_back(Hs / SwanHsP);
		PointRay[P->Name].push_back(RayHs / SwanHsP);
	}
	std::printf("\npoints: %zu cases; median |log error| Hs: map %.2f, before W3 %.2f, bake's ray %.2f; Tp: map %.2f, before %.2f, ray %.2f\n",
		ErrMap.size(), Median(ErrMap), Median(ErrNow), Median(ErrRay), Median(TErrMap), Median(TErrNow), Median(TErrRay));
	std::printf("point,map/swan,before/swan,ray/swan (medians)\n");
	for (const auto& [Name, V] : PointMap) std::printf("\"%s\",%.2f,%.2f,%.2f\n", Name.c_str(), Median(V), Median(PointNow[Name]), Median(PointRay[Name]));
	return 0;
}
