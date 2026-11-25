// Wildlife Phase 1 (docs/wildlife-1/README.md): the distant birds standalone (no Unreal). For each world's launch spots and
// a few months it builds the habitat map on the real terrain, runs FBirdFlocks for some minutes of sim time with the
// camera on a boat (moored, or sailing with --sail) and prints how many flocks each bird has against the count the table
// expects, the birds drawn per band against the tier's budget, the flushes, and the time an update takes. It fails when a
// count drifts far from its expectation, a band overflows its budget, or a flying bird is below the ground.
// Usage: scripts/wildlife-check.sh [World|all] [--months 1,4,7,10] [--hour 10] [--minutes 10] [--sail] [--tier 2] [--spot N]
//        [--species] [--scale <density>]
#include "LakeTerrain.h"
#include "Wildlife.h"
#include "WorldStream.h"
#include <zlib.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

using namespace Sailing;

namespace
{
	constexpr double kPiD = 3.14159265358979323846;

	std::vector<uint8_t> ReadFile(const std::string& Path)
	{
		std::ifstream F(Path, std::ios::binary);
		return std::vector<uint8_t>((std::istreambuf_iterator<char>(F)), std::istreambuf_iterator<char>());
	}
	std::string ReadText(const std::string& Path)
	{
		std::ifstream F(Path);
		std::stringstream S;
		S << F.rdbuf();
		return S.str();
	}

	bool LoadTerrain(const std::string& World, FLakeTerrain& T)
	{
		std::vector<uint8_t> H = ReadFile("Content/TerrainData/" + World + ".height");
		if (H.size() > 200 && T.LoadHeight(H.data(), H.size())) return true;
		// a composed world: every tile of <World>.tiles
		const std::vector<uint8_t> Bytes = ReadFile("Content/TerrainData/" + World + ".tiles");
		FTileIndex Index;
		if (Bytes.size() < 200 || !Index.Parse(Bytes.data(), Bytes.size())) return false;
		std::vector<std::shared_ptr<const FTerrainTile>> Set;
		for (const FTileEntry& E : Index.GetTiles())
		{
			if (E.Offset + E.StoredSize > Bytes.size()) return false;
			const uint8_t* Stored = Bytes.data() + E.Offset;
			if (E.Flags & kTileZlib)
			{
				uLongf Len = uLongf(size_t(E.Cells + 1) * size_t(E.Cells + 1) * 2);
				std::vector<uint8_t> Raw(Len);
				if (uncompress(Raw.data(), &Len, Stored, E.StoredSize) != Z_OK) return false;
				Set.push_back(Index.MakeTile(E, Raw.data(), Len));
			}
			else Set.push_back(Index.MakeTile(E, Stored, E.StoredSize));
		}
		T.SetTiles(std::make_shared<const FTileSet>(Index.GetTileM(), Index.GetOriginX(), Index.GetOriginY(), Set), Index.GetFinestCell());
		return true;
	}

	struct FSpot { std::string Name; double N = 0.0, E = 0.0, HeadingDeg = 0.0; };

	// Launch spots from <World>.json ("xy": [north, east], "heading"): a small hand reader, the format is fixed.
	std::vector<FSpot> LaunchSpots(const std::string& World)
	{
		std::vector<FSpot> Out;
		const std::string J = ReadText("Content/TerrainData/" + World + ".json");
		size_t P = J.find("\"launch_spots\"");
		if (P == std::string::npos) return Out;
		int Depth = 0;
		size_t I = J.find('[', P);
		const size_t Start = I;
		for (; I < J.size(); ++I)
		{
			if (J[I] == '[') ++Depth;
			else if (J[I] == ']' && --Depth == 0) break;
		}
		const std::string Block = J.substr(Start, I - Start);
		size_t Q = 0;
		while ((Q = Block.find("\"name\"", Q)) != std::string::npos)
		{
			FSpot S;
			const size_t A = Block.find('"', Block.find(':', Q) + 1);
			const size_t B = Block.find('"', A + 1);
			S.Name = Block.substr(A + 1, B - A - 1);
			const size_t XY = Block.find("\"xy\"", B);
			const size_t NextName = Block.find("\"name\"", B);
			if (XY == std::string::npos || (NextName != std::string::npos && XY > NextName)) { Q = B; continue; }
			const size_t LB = Block.find('[', XY);
			S.N = std::atof(Block.c_str() + LB + 1);
			S.E = std::atof(Block.c_str() + Block.find(',', LB) + 1);
			const size_t H = Block.find("\"heading\"", B);
			if (H != std::string::npos && (NextName == std::string::npos || H < NextName)) S.HeadingDeg = std::atof(Block.c_str() + Block.find(':', H) + 1);
			Out.push_back(S);
			Q = B;
		}
		return Out;
	}

	bool IsHarbourName(const std::string& N)
	{
		for (const char* W : { "Yacht Club", "yacht club", "Port", "port", "marina", "Marina", "Quai", "harbour", "Harbour", "Landing" })
		{
			if (N.find(W) != std::string::npos) return true;
		}
		return false;
	}

	/** The sun's elevation (deg) for a month and local solar hour at a latitude: enough for the activity curves. */
	double SunElevation(int Month, double Hour, double LatDeg)
	{
		const double Day = (Month - 1) * 30.4 + 15.0;
		const double Decl = 23.44 * std::sin(2.0 * kPiD * (284.0 + Day) / 365.0) * kPiD / 180.0;
		const double Lat = LatDeg * kPiD / 180.0;
		const double Ha = (Hour - 12.0) * 15.0 * kPiD / 180.0;
		return std::asin(std::sin(Lat) * std::sin(Decl) + std::cos(Lat) * std::cos(Decl) * std::cos(Ha)) * 180.0 / kPiD;
	}

	std::vector<int> ParseList(const char* S)
	{
		std::vector<int> Out;
		std::stringstream SS(S);
		std::string Item;
		while (std::getline(SS, Item, ',')) if (!Item.empty()) Out.push_back(std::atoi(Item.c_str()));
		return Out;
	}

	struct FRun
	{
		double Expected = 0.0, MeanFlocks = 0.0, MeanBirds = 0.0, MeanFar = 0.0, MeanMid = 0.0, MeanNear = 0.0;
		int MaxFar = 0, MaxMid = 0, MaxNear = 0, Flushes = 0, Spawned = 0, Retired = 0, Underground = 0, NotFinite = 0;
		double MeanMs = 0.0, MaxMs = 0.0, P99Ms = 0.0, MapMs = 0.0;
		int MapBuilds = 0, Timed = 0;
		std::vector<double> PerBirdMean, PerBirdExpected;
		bool bBudgetOk = true;
	};
}

int main(int Argc, char** Argv)
{
	std::string Which = "all";
	std::vector<int> Months = { 1, 4, 7, 10 };
	double Hour = 10.0, Minutes = 10.0, Scale = 1.0;
	bool bSail = false, bSpecies = false;
	int Tier = 2, OnlySpot = -1;
	for (int I = 1; I < Argc; ++I)
	{
		const std::string A = Argv[I];
		auto Next = [&]() { return I + 1 < Argc ? Argv[++I] : ""; };
		if (A == "--months") Months = ParseList(Next());
		else if (A == "--hour") Hour = std::atof(Next());
		else if (A == "--minutes") Minutes = std::atof(Next());
		else if (A == "--sail") bSail = true;
		else if (A == "--tier") Tier = std::atoi(Next());
		else if (A == "--spot") OnlySpot = std::atoi(Next());
		else if (A == "--species") bSpecies = true;
		else if (A == "--scale") Scale = std::atof(Next());
		else if (A[0] != '-') Which = A;
		else { std::fprintf(stderr, "unknown option %s\n", A.c_str()); return 2; }
	}
	const std::vector<std::string> Worlds = Which == "all"
		? std::vector<std::string>{ "RayHubbard", "GalvestonBay", "GulfPassage", "Marseille", "TexasCoast" }
		: std::vector<std::string>{ Which };
	const FBirdBudget Budget = BirdBudgetForTier(Tier);
	int Failures = 0;
	std::printf("tier %d budget far %d mid %d near %d; %.0f min a run at %.1f h%s\n", Tier, Budget.Far, Budget.Mid, Budget.Near,
		Minutes, Hour, bSail ? ", sailing 3 m/s" : ", moored");

	for (const std::string& World : Worlds)
	{
		FWildlifeTable Table;
		std::string Err;
		if (!Table.LoadText(ReadText("Content/TerrainData/" + World + ".wildlife.json"), &Err))
		{
			std::printf("%s: no table (%s)\n", World.c_str(), Err.c_str());
			++Failures;
			continue;
		}
		FLakeTerrain Terrain;
		if (!LoadTerrain(World, Terrain))
		{
			std::printf("%s: no terrain (git lfs pull the .height or .tiles; run from the repo root)\n", World.c_str());
			++Failures;
			continue;
		}
		const double Lat = 0.5 * (Table.Box[1] + Table.Box[3]);
		const std::vector<FSpot> Spots = LaunchSpots(World);
		std::vector<FSpot> Harbours;
		for (const FSpot& S : Spots) if (IsHarbourName(S.Name)) Harbours.push_back(S);
		FWildlifeWorld W;
		W.HeightAt = [&Terrain](double N, double E) { return Terrain.HeightAt(N, E); };
		W.CanopyAt = [&Terrain](double N, double E) { return Terrain.CanopyAt(N, E); };
		W.IsHarbour = [&Harbours](double N, double E)
		{
			for (const FSpot& H : Harbours) if (std::hypot(N - H.N, E - H.E) < 300.0) return true;
			return false;
		};
		std::printf("\n%s: %zu birds (%d other animals), %zu launch spots, latitude %.2f\n", World.c_str(), Table.Birds.size(),
			Table.OtherAnimals, Spots.size(), Lat);

		for (size_t SI = 0; SI < Spots.size(); ++SI)
		{
			if (OnlySpot >= 0 && int(SI) != OnlySpot) continue;
			const FSpot& Spot = Spots[SI];
			for (int Month : Months)
			{
				FWildlifeConditions C;
				C.Month = Month;
				C.LocalHour = Hour;
				C.SunElevationDeg = SunElevation(Month, Hour, Lat);
				C.WindKn = 9.0;
				C.WindFromDeg = 170.0;
				FBirdFlocks Flocks;
				Flocks.Reset(Table, 1000u + 17u * SI + uint64_t(Month));
				Flocks.SetBudget(Budget);
				Flocks.SetDensityScale(Scale);
				FWildlifeHabitatMap Map;
				FRun R;
				R.PerBirdMean.assign(Table.Birds.size(), 0.0);
				R.PerBirdExpected.assign(Table.Birds.size(), 0.0);
				auto BuildMap = [&](double N, double E)
				{
					const auto T0 = std::chrono::steady_clock::now();
					Map.Build(W, N, E);
					R.MapMs = std::max(R.MapMs, std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - T0).count());
					++R.MapBuilds;
				};
				FBirdObservers Obs;
				FBirdObservers::FBoat Boat;
				Boat.North = Spot.N; Boat.East = Spot.E; Boat.HeadingRad = Spot.HeadingDeg * kPiD / 180.0; Boat.bPlayer = true;
				Boat.SpeedMs = bSail ? 3.0 : 0.0;
				BuildMap(Boat.North, Boat.East);
				const double Dt = 1.0 / 30.0;
				const int Steps = int(Minutes * 60.0 / Dt);
				const int Warm = Steps / 5;
				int Samples = 0;
				std::vector<double> Times;
				for (int K = 0; K < Steps; ++K)
				{
					if (bSail)
					{
						// sail on, turning back when the water ahead gets shallow
						const double AN = Boat.North + 60.0 * std::cos(Boat.HeadingRad), AE = Boat.East + 60.0 * std::sin(Boat.HeadingRad);
						if (Terrain.HeightAt(AN, AE) > -1.5) Boat.HeadingRad += 0.6 * Dt;
						Boat.North += Boat.SpeedMs * std::cos(Boat.HeadingRad) * Dt;
						Boat.East += Boat.SpeedMs * std::sin(Boat.HeadingRad) * Dt;
						if (std::hypot(Boat.North - Map.CenterNorth(), Boat.East - Map.CenterEast()) > 1500.0) BuildMap(Boat.North, Boat.East);
					}
					Obs.CamNorth = Boat.North - 8.0 * std::cos(Boat.HeadingRad);
					Obs.CamEast = Boat.East - 8.0 * std::sin(Boat.HeadingRad);
					Obs.CamUp = 3.0;
					Obs.Boats.assign(1, Boat);
					const auto T0 = std::chrono::steady_clock::now();
					Flocks.Update(Dt, C, Obs, Map);
					const double Ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - T0).count();
					if (K >= Warm) { R.MeanMs += Ms; R.MaxMs = std::max(R.MaxMs, Ms); ++R.Timed; Times.push_back(Ms); }
					const FBirdFlocks::FStats& St = Flocks.Stats();
					if (St.Far > Budget.Far || St.Mid > Budget.Mid || St.Near > Budget.Near) R.bBudgetOk = false;
					for (const FBirdDraw& D : Flocks.Draw())
					{
						// (Every field the actor turns into an instance: one NaN transform makes the whole component's bounds NaN.)
						const float Fields[] = {float(D.North), float(D.East), float(D.Up), D.HeadingRad, D.PitchRad, D.BankRad, D.WingPhase, D.WingAmp,
							D.Fold, D.Fade, D.SizeM, D.DistanceM};
						bool bFinite = true;
						for (float V : Fields) bFinite &= std::isfinite(V);
						if (!bFinite)
						{
							if (std::getenv("WILDLIFE_DEBUG") && R.NotFinite < 8)
								std::printf("    not finite: %s state %d at %.1f,%.1f,%.1f heading %f pitch %f bank %f phase %f size %f\n", BirdStyleName(D.Style), int(D.State),
									D.North, D.East, D.Up, D.HeadingRad, D.PitchRad, D.BankRad, D.WingPhase, D.SizeM);
							++R.NotFinite;
						}
						const bool bAir = D.State != EBirdState::OnWater && D.State != EBirdState::Standing && D.State != EBirdState::Diving &&
							D.State != EBirdState::Landing && D.State != EBirdState::TakingOff;
						if (bAir && D.Up < Terrain.HeightAt(D.North, D.East) - 1.0)
						{
							if (std::getenv("WILDLIFE_DEBUG") && R.Underground < 8)
								std::printf("    under: %s state %d up %.1f ground %.1f map %.1f at %.0f,%.0f\n", BirdStyleName(D.Style), int(D.State), D.Up,
									Terrain.HeightAt(D.North, D.East), Map.HeightAt(D.North, D.East), D.North, D.East);
							++R.Underground;
						}
					}
					if (K < Warm || K % 15) continue;
					++Samples;
					R.MeanFar += St.Far; R.MeanMid += St.Mid; R.MeanNear += St.Near;
					R.MaxFar = std::max(R.MaxFar, St.Far); R.MaxMid = std::max(R.MaxMid, St.Mid); R.MaxNear = std::max(R.MaxNear, St.Near);
					R.MeanBirds += St.Birds;
					for (int B = 0; B < Flocks.TableBirds(); ++B)
					{
						const int Have = Flocks.FlockCountOf(B);
						const double E = Flocks.ExpectedNow(B);
						R.PerBirdMean[size_t(B)] += Have;
						R.PerBirdExpected[size_t(B)] += E;
						R.MeanFlocks += Have;
						R.Expected += E;
					}
				}
				const double Inv = Samples > 0 ? 1.0 / Samples : 0.0;
				R.MeanMs /= std::max(1, R.Timed);
				std::sort(Times.begin(), Times.end());
				R.P99Ms = Times.empty() ? 0.0 : Times[std::min(Times.size() - 1, size_t(0.99 * double(Times.size())))]; R.MeanFar *= Inv; R.MeanMid *= Inv; R.MeanNear *= Inv; R.MeanBirds *= Inv; R.MeanFlocks *= Inv; R.Expected *= Inv;
				for (size_t B = 0; B < R.PerBirdMean.size(); ++B) { R.PerBirdMean[B] *= Inv; R.PerBirdExpected[B] *= Inv; }
				const FBirdFlocks::FStats& St = Flocks.Stats();
				R.Flushes = St.Flushes; R.Spawned = St.Spawned; R.Retired = St.Retired;
				// a count may wander, but not far: within 40% of what's expected (or 1.5 flocks for the scarce)
				const bool bCountOk = std::fabs(R.MeanFlocks - R.Expected) <= std::max(1.5, 0.4 * R.Expected);
				const bool bOk = bCountOk && R.bBudgetOk && R.Underground == 0 && R.NotFinite == 0;
				if (!bOk) ++Failures;
				std::printf("  %-38.38s m%02d sun %4.0f  flocks %5.1f (expect %5.1f)  birds %5.0f  drawn quads %5.1f/%-3d bodies mid %4.1f/%-3d near %3.1f/%-2d"
					"  flushes %3d  update %.3f ms (p99 %.2f, max %.2f)  map %.0f ms x%d%s%s%s%s\n",
					Spot.Name.c_str(), Month, C.SunElevationDeg, R.MeanFlocks, R.Expected, R.MeanBirds, R.MeanFar, R.MaxFar, R.MeanMid, R.MaxMid,
					R.MeanNear, R.MaxNear, R.Flushes, R.MeanMs, R.P99Ms, R.MaxMs, R.MapMs, R.MapBuilds,
					bCountOk ? "" : "  COUNT OFF", R.bBudgetOk ? "" : "  OVER BUDGET", R.Underground ? "  UNDERGROUND" : "", R.NotFinite ? "  NAN" : "");
				if (R.Underground) std::printf("    %d bird-frames below the ground\n", R.Underground);
				if (bSpecies)
				{
					std::vector<std::pair<double, int>> Order;
					for (size_t B = 0; B < R.PerBirdMean.size(); ++B) Order.push_back({ -R.PerBirdExpected[B] - R.PerBirdMean[B], int(B) });
					std::sort(Order.begin(), Order.end());
					for (const auto& O : Order)
					{
						const int B = O.second;
						if (R.PerBirdExpected[size_t(B)] < 0.01 && R.PerBirdMean[size_t(B)] < 0.01) continue;
						const FWildBird& Bd = Flocks.TableBird(B);
						std::printf("      %-28.28s %-12s %5.2f flocks (expect %5.2f)  group %d..%d\n", Bd.Name.c_str(), BirdStyleName(Bd.Style),
							R.PerBirdMean[size_t(B)], R.PerBirdExpected[size_t(B)], Bd.GroupTypical, Bd.GroupP90);
					}
				}
			}
		}
	}
	std::printf("\n%s (%d failing runs)\n", Failures ? "FAIL" : "PASS", Failures);
	return Failures ? 1 : 0;
}
