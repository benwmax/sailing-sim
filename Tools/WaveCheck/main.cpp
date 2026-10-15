// Mac polish: the lake's sea against the PC's SWAN bake of Ray Hubbard (docs/water-3/swan-compare.csv on w3-swan-bake),
// Hs and peak period, standalone (no Unreal). The statistic is SailingSim.Physics.WaveGrowthSwan's: per wind direction the
// median over the lake's water every 250 m, then the median over the 16 directions. SWAN's Tp at a direction and speed is
// the bake's median SWAN / game period ratio times the median period of the game the bake compared against (the SPM law in
// U on FLakeTerrain::FetchToward). Usage: scripts/wave-check.sh <swan-compare.csv>
#include "LakeTerrain.h"
#include "Waves.h"
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
	return 0;
}
