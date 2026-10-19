// Gulf swell: FOcean's mask on a world's terrain, standalone (no Unreal). Prints the build time and the mask at named
// points, and writes a greyscale map (north up) to Artifacts/ocean-mask-<World>.pgm. Usage: scripts/ocean-mask.sh
// [GalvestonBay|GulfPassage] [swell Hs m] [swell from deg]
#include "LakeTerrain.h"
#include "Ocean.h"
#include "SailingMath.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

using namespace Sailing;

static std::vector<uint8_t> ReadFile(const std::string& Path)
{
	std::ifstream F(Path, std::ios::binary);
	return std::vector<uint8_t>((std::istreambuf_iterator<char>(F)), std::istreambuf_iterator<char>());
}

int main(int Argc, char** Argv)
{
	const std::string World = Argc > 1 ? Argv[1] : "GalvestonBay";
	FLakeTerrain T;
	const std::vector<uint8_t> H = ReadFile("Content/TerrainData/" + World + ".height");
	if (!T.LoadHeight(H.data(), H.size())) { std::fprintf(stderr, "no %s.height (run from the repo root)\n", World.c_str()); return 1; }
	FOceanParams P;
	P.WindMs = 12.0 * kKnot;
	P.WindFromRad = kPi;
	P.SwellHs = Argc > 2 ? std::atof(Argv[2]) : 0.9;
	P.SwellTp = 9.0;
	P.SwellFromRad = (Argc > 3 ? std::atof(Argv[3]) : 135.0) * kDegToRad;
	FOcean Ocean;
	Ocean.Configure(P);
	const auto T0 = std::chrono::steady_clock::now();
	Ocean.BuildMask(T);
	const double Ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - T0).count();
	const FOcean::FMask& M = Ocean.GetMask();
	std::printf("%s: mask %d x %d at %.0f m, Hs %.2f m, built in %.0f ms\n", World.c_str(), M.Rows, M.Cols, M.Cell, Ocean.SignificantHeight(), Ms);
	struct FPoint { const char* Name; double X, Y; };
	const std::vector<FPoint> Points = World == "GalvestonBay"
		? std::vector<FPoint>{ { "1 km off the Seawall (25th St)", -29700, 23000 }, { "Pleasure Pier end", -29000, 22350 },
			{ "off 61st St", -31900, 18500 }, { "Gulf, south edge", -38500, 25000 }, { "Bolivar Roads, jetty mouth", -24800, 31500 },
			{ "Bolivar Roads (launch)", -20990, 24210 }, { "Galveston Channel", -22800, 22000 }, { "Texas City Dike", -16020, 15460 },
			{ "Red Fish Bar", -5490, 13990 }, { "off Clear Lake", -2170, 4780 }, { "Clear Lake", 430, -4410 }, { "West Bay", -27000, 5000 } }
		: std::vector<FPoint>{ { "offshore", -31000, -5000 }, { "West Bay", -12000, -25000 }, { "inside Bolivar Roads", 3000, -6000 },
			{ "entrance outbound", -1650, 2450 }, { "sea buoy", -5000, 6800 } };
	for (const FPoint& Pt : Points) std::printf("  %-34s %7.0f %7.0f  mask %.2f  depth %5.1f m\n", Pt.Name, Pt.X, Pt.Y, Ocean.MaskAt(Pt.X, Pt.Y), T.DepthAt(Pt.X, Pt.Y));
	const std::string Out = "Artifacts/ocean-mask-" + World + ".pgm";
	std::ofstream F(Out, std::ios::binary);
	F << "P5\n" << M.Cols << " " << M.Rows << "\n255\n";
	for (int R = M.Rows - 1; R >= 0; --R)
		for (int C = 0; C < M.Cols; ++C)
		{
			const double X = M.X0 + R * M.Cell, Y = M.Y0 + C * M.Cell;
			const double V = M.Values[size_t(R) * M.Cols + C];
			// land dark brown-grey (40), water from 70 (no swell) to 255 (open sea)
			F.put(char(T.HeightAt(X, Y) > 0.0 ? 30 : int(70 + 185 * V)));
		}
	std::printf("wrote %s\n", Out.c_str());
	return 0;
}
