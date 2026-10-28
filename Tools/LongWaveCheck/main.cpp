// docs/long-wave-fft/: the long-wave FFT standalone (no Unreal). Runs the checks SailingSim.Physics.LongWaves.* run, then
// times the FFT kernel and a key's grids on this machine. `--swan <swan-compare.csv> <points.csv>` also compares the sea map
// with one channel per cascade against SWAN's points (SeaMapSwan), beside today's channel per sine.
// Usage: scripts/long-wave-check.sh [--swan]
#include "Fft.h"
#include "LakeTerrain.h"
#include "LongWaveChecks.h"
#include "LongWaves.h"
#include "SeaState.h"
#include "Waves.h"
#include <zlib.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace Sailing;

static double Now()
{
	return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

static double Median(std::vector<double> V)
{
	if (V.empty()) return 0.0;
	std::nth_element(V.begin(), V.begin() + V.size() / 2, V.end());
	return V[V.size() / 2];
}

static double Percentile(std::vector<double> V, double P)
{
	if (V.empty()) return 0.0;
	std::sort(V.begin(), V.end());
	return V[std::min(V.size() - 1, size_t(P * V.size()))];
}

static FLongWaves::FParallelFor Workers(int Count)
{
	return [Count](int Jobs, const std::function<void(int)>& Job)
	{
		std::atomic<int> Next { 0 };
		std::vector<std::thread> Threads;
		for (int W = 0; W < Count; ++W)
			Threads.emplace_back([&Next, Jobs, &Job]() { for (int J = Next.fetch_add(1); J < Jobs; J = Next.fetch_add(1)) Job(J); });
		for (std::thread& T : Threads) T.join();
	};
}

static void Timings()
{
	std::printf("\ntimings (this machine, clang -O2, no fused multiply-adds)\n");
	for (const int Size : { 128, 256 })
	{
		FFft2D Fft(Size);
		std::vector<FComplexF> A(size_t(Size) * Size);
		for (size_t I = 0; I < A.size(); ++I) A[I] = { float(std::sin(I * 0.37)), float(std::cos(I * 0.11)) };
		const int Reps = Size == 128 ? 400 : 100;
		std::vector<double> Ms;
		for (int R = 0; R < Reps; ++R)
		{
			const double T0 = Now();
			Fft.Inverse(A.data());
			Ms.push_back(Now() - T0);
		}
		std::printf("kernel %d^2 complex 2D inverse: median %.3f ms, p99 %.3f ms\n", Size, Median(Ms), Percentile(Ms, 0.99));
	}
	for (const ELongWaveLayout Layout : { ELongWaveLayout::Ranges, ELongWaveLayout::PerBand })
	for (const double Kn : { 10.0, 20.0, 28.0 })
	{
		FLongWaves W(1, Layout);
		FLongWaveParams P;
		P.WindMs = Kn * kKnot;
		P.FetchMeters = 15000.0;
		W.SetParams(P);
		W.SnapToTarget();
		int Running = 0, Modes = 0;
		for (int C = 0; C < W.NumCascades(); ++C) if (W.IsRunning(C)) { ++Running; Modes += W.ModeCount(C); }
		std::printf("%s layout:\n", Layout == ELongWaveLayout::Ranges ? "ranges (L1, L2)" : "per band");
		for (const int Threads : { 1, 4 })
		{
			const FLongWaves::FParallelFor Par = Threads > 1 ? Workers(Threads) : nullptr;
			std::vector<double> Ms;
			for (int64_t K = 0; K < 300; ++K)
			{
				const double T0 = Now();
				W.Produce(K, Par);
				Ms.push_back(Now() - T0);
			}
			std::printf("%2.0f kn: %d cascades, %d modes, a key's grids (13 fields, 7 transforms a cascade) on %d thread%s: mean %.3f ms, p99 %.3f ms\n",
				Kn, Running, Modes, Threads, Threads > 1 ? "s" : "", [&Ms]() { double S = 0.0; for (double V : Ms) S += V; return S / Ms.size(); }(), Percentile(Ms, 0.99));
		}
		// Physics reads: Sample at random points (both keys in the ring).
		W.Produce(1000);
		W.Produce(1001);
		const int Reads = 200000;
		double Sink = 0.0;
		const double T0 = Now();
		for (int I = 0; I < Reads; ++I)
		{
			double F[kLongFields];
			W.Sample(0.37 * I, -0.23 * I, 1000.3 / FLongWaves::KeyHz, nullptr, F);
			Sink += F[0];
		}
		const double T1 = Now();
		FWaveField Sines(1);
		FWaveParams SP;
		SP.WindSpeedKnots = Kn;
		SP.FetchMeters = 15000.0;
		Sines.SetWind(SP);
		Sines.SnapToTarget();
		for (int I = 0; I < Reads; ++I)
		{
			double H, Vz, Sx, Sy;
			Sines.Sample(0.37 * I, -0.23 * I, 33.3, H, Vz, Sx, Sy);
			Sink += H;
		}
		const double T2 = Now();
		std::printf("     one physics read: FFT Sample (13 fields) %.3f us; FWaveField::Sample (48 sines, today) %.3f us  [%g]\n",
			1000.0 * (T1 - T0) / Reads, 1000.0 * (T2 - T1) / Reads, Sink * 0.0);
	}
}

static std::vector<uint8_t> ReadFile(const std::string& Path)
{
	std::ifstream F(Path, std::ios::binary);
	return std::vector<uint8_t>((std::istreambuf_iterator<char>(F)), std::istreambuf_iterator<char>());
}

/** Hs and the band spectrum's peak period from variance per FWaveField band (WaveCheck's SeaAt). */
static void HsTp(const double* Band, double& Hs, double& Tp)
{
	double V = 0.0, Best = -1.0, Density[kWaveBands];
	int Peak = 0;
	for (int B = 0; B < kWaveBands; ++B)
	{
		V += Band[B];
		Density[B] = Band[B] / FWaveField::BandWidthHz(B);
		if (Density[B] > Best) { Best = Density[B]; Peak = B; }
	}
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
}

static std::vector<std::string> SplitCsv(const std::string& Line)
{
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
	return F;
}

static bool SeaMapSwan(const char* PointsCsv, ELongWaveLayout Layout)
{
	FLakeTerrain T;
	const std::vector<uint8_t> H = ReadFile("Content/TerrainData/RayHubbard.height");
	if (!T.LoadHeight(H.data(), H.size())) { std::fprintf(stderr, "no RayHubbard.height (run from the repo root)\n"); return false; }
	const std::vector<uint8_t> Z = ReadFile("Content/TerrainData/RayHubbard.detail");
	if (Z.size() > 8 && std::memcmp(Z.data(), "SSDZ", 4) == 0)
	{
		uint32_t RawSize = 0;
		std::memcpy(&RawSize, Z.data() + 4, 4);
		std::vector<uint8_t> Raw(RawSize);
		uLongf Len = RawSize;
		if (uncompress(Raw.data(), &Len, Z.data() + 8, Z.size() - 8) == Z_OK) T.LoadDetail(Raw.data(), Len);
	}
	FSeaFetch Fetch;
	Fetch.Build(T, 50.0);
	// The ten SWAN points (WaveCheck's table).
	struct FPoint { const char* Name; double X, Y; };
	const FPoint Points[] = {
		{ "Rush Creek Yacht Club", 5, -35 }, { "Off Rush Creek, open water", 605, -535 },
		{ "South lake, near the dam", -895, -1385 }, { "Chandlers Landing", 5555, 1115 },
		{ "North lake, below the SH-66 causeway", 9505, -535 }, { "Chandlers Landing", 5605, 1765 },
		{ "Harry Myers Park", 11155, 2565 }, { "open-7", 3255, -2535 }, { "open-8", 8105, -3935 }, { "open-9", 13355, 165 } };

	struct FSea { std::unique_ptr<FWaveField> Sines; std::shared_ptr<FSeaMap> Map; std::unique_ptr<FLongWaves> Long; };
	std::map<std::pair<int, int>, FSea> Seas;
	auto SeaFor = [&](int Kn, double FromDeg) -> FSea&
	{
		FSea& S = Seas[{ int(FromDeg * 10.0 + 0.5), Kn }];
		if (S.Sines) return S;
		S.Sines = std::make_unique<FWaveField>(1);
		FWaveParams P;
		P.WindSpeedKnots = Kn;
		P.WindFromDegrees = FromDeg;
		P.FetchMeters = 15000.0;
		S.Sines->SetDepth(Fetch.GetMedianDepth());
		S.Sines->SetWind(P);
		S.Map = std::make_shared<FSeaMap>();
		S.Map->Build(Fetch, S.Sines->GetComponents(), Kn * kKnot, FromDeg * kDegToRad + kPi);
		S.Sines->SetSeaMap(S.Map);
		S.Sines->SnapToTarget();
		S.Long = std::make_unique<FLongWaves>(1, Layout);
		S.Long->SetDepth(Fetch.GetMedianDepth());
		FLongWaveParams L;
		L.WindMs = Kn * kKnot;
		L.WindFromRad = FromDeg * kDegToRad;
		L.FetchMeters = Fetch.GetMaxFetch();
		S.Long->SetParams(L);
		S.Long->SnapToTarget();
		return S;
	};
	// The cascade channels at a point: bilinear between cell centres, as FSeaMap::Sample (and the shader's atlas).
	auto ChannelsAt = [&](const FLongWaves& W, double X, double Y, float* Out)
	{
		const double U = std::clamp((X - Fetch.GetOriginX()) / Fetch.GetCell(), 0.0, Fetch.GetRows() - 1.0);
		const double V = std::clamp((Y - Fetch.GetOriginY()) / Fetch.GetCell(), 0.0, Fetch.GetCols() - 1.0);
		const int R0 = std::min(int(U), Fetch.GetRows() - 2), C0 = std::min(int(V), Fetch.GetCols() - 2);
		const double TU = U - R0, TV = V - C0;
		float A[kLongCascades], B[kLongCascades], C[kLongCascades], D[kLongCascades];
		W.SeaChannelsAt(Fetch, R0, C0, A);
		W.SeaChannelsAt(Fetch, R0, C0 + 1, B);
		W.SeaChannelsAt(Fetch, R0 + 1, C0, C);
		W.SeaChannelsAt(Fetch, R0 + 1, C0 + 1, D);
		for (int I = 0; I < kLongCascades; ++I)
		{
			const double Top = A[I] + (B[I] - A[I]) * TV, Bottom = C[I] + (D[I] - C[I]) * TV;
			Out[I] = float(Top + (Bottom - Top) * TU);
		}
	};

	std::ifstream Pc(PointsCsv);
	std::string Line;
	std::getline(Pc, Line);
	std::map<std::string, int> RowOfKey;
	constexpr int kGroupings = 5;
	const char* kGroupName[kGroupings] = { "0-3|4-7", "0-2|3-5|6-7", "0-1|2-3|4-5|6-7", "0-2|3-4|5-7", "each band" };
	const int kGroupOf[kGroupings][8] = { { 0, 0, 0, 0, 1, 1, 1, 1 }, { 0, 0, 0, 1, 1, 1, 2, 2 }, { 0, 0, 1, 1, 2, 2, 3, 3 }, { 0, 0, 0, 1, 1, 2, 2, 2 }, { 0, 1, 2, 3, 4, 5, 6, 7 } };
	std::vector<double> GHs[kGroupings], GTp[kGroupings], GTpAbs[kGroupings];
	std::vector<double> ErrMap, ErrFft, TErrMap, TErrFft, TBiasMap, TBiasFft;
	std::ofstream Out("Artifacts/long-wave-sea-map.csv");
	Out << "point,wind_from,knots,swan_hs,map_hs,fft_hs,swan_tp,map_tp,fft_tp,ch_l1,ch_l2\n";
	while (std::getline(Pc, Line))
	{
		const std::vector<std::string> F = SplitCsv(Line);
		if (F.size() < 9 || F[0] != "RayHubbard") continue;
		const double From = std::stod(F[2]);
		const int Kn = std::stoi(F[3]);
		const std::string Key = F[1] + "|" + F[2] + "|" + F[3];
		const int Nth = RowOfKey[Key]++;
		const FPoint* P = nullptr;
		int Count = 0;
		for (const FPoint& Q : Points) if (F[1] == Q.Name && Count++ == Nth) { P = &Q; break; }
		if (!P) continue;
		FSea& S = SeaFor(Kn, From);
		const double SwanHs = std::stod(F[5]), SwanTp = std::stod(F[7]);
		// Today: one channel per sine (the long 24) and the short scale.
		float R[kSeaChannels];
		S.Sines->SeaRatiosAt(P->X, P->Y, R);
		double BandMap[kWaveBands] = {}, BandFft[kWaveBands] = {};
		for (int I = 0; I < kWaveComponents; ++I)
		{
			const double A = S.Sines->GetComponents()[I].Amplitude * R[std::min(I, kSeaLongComponents)];
			BandMap[I / kWaveDirectionsPerBand] += 0.5 * A * A;
			if (I >= kSeaLongComponents) BandFft[I / kWaveDirectionsPerBand] += 0.5 * A * A;
		}
		// The FFT: one channel per cascade, each cascade's bands scaled by it; the short waves as today.
		float Ch[kLongCascades];
		ChannelsAt(*S.Long, P->X, P->Y, Ch);
		for (int C = 0; C < kLongCascades; ++C)
		{
			double CB[kWaveBands];
			S.Long->BandVariance(CB, C);
			for (int B = 0; B < kWaveBands; ++B) BandFft[B] += double(Ch[C]) * Ch[C] * CB[B];
		}
		double MapHs, MapTp, FftHs, FftTp;
		HsTp(BandMap, MapHs, MapTp);
		HsTp(BandFft, FftHs, FftTp);
		// Which split of the long bands into channels the sea map needs: each grouping's channel is the energy-weighted
		// ratio over its bands (both cascades), at the nearest cell.
		{
			const int R0 = std::clamp(int(std::lround((P->X - Fetch.GetOriginX()) / Fetch.GetCell())), 0, Fetch.GetRows() - 1);
			const int C0 = std::clamp(int(std::lround((P->Y - Fetch.GetOriginY()) / Fetch.GetCell())), 0, Fetch.GetCols() - 1);
			float Dummy[kLongCascades];
			double Share[kLongCascades][kWaveBands];
			S.Long->SeaChannelsAt(Fetch, R0, C0, Dummy, Share);
			double E[kLongCascades][kWaveBands];
			for (int C = 0; C < kLongCascades; ++C) S.Long->BandVariance(E[C], C);
			for (int G = 0; G < kGroupings; ++G)
			{
				double Band[kWaveBands] = {};
				for (int I = kSeaLongComponents; I < kWaveComponents; ++I)
				{
					const double A = S.Sines->GetComponents()[I].Amplitude * R[kSeaLongComponents];
					Band[I / kWaveDirectionsPerBand] += 0.5 * A * A;
				}
				double Num[8] = {}, Den[8] = {};
				for (int C = 0; C < kLongCascades; ++C)
					for (int B = 0; B < 8; ++B) { Num[kGroupOf[G][B]] += E[C][B] * Share[C][B]; Den[kGroupOf[G][B]] += E[C][B]; }
				for (int C = 0; C < kLongCascades; ++C)
					for (int B = 0; B < 8; ++B) { const int Gi = kGroupOf[G][B]; Band[B] += E[C][B] * (Den[Gi] > 0.0 ? Num[Gi] / Den[Gi] : 0.0); }
				double Hs, Tp;
				HsTp(Band, Hs, Tp);
				if (SwanHs > 0.005) { GHs[G].push_back(std::fabs(std::log(Hs / SwanHs))); GTp[G].push_back(std::log(Tp / SwanTp)); GTpAbs[G].push_back(std::fabs(std::log(Tp / SwanTp))); }
			}
		}
		Out << '"' << P->Name << "\"," << From << ',' << Kn << ',' << SwanHs << ',' << MapHs << ',' << FftHs << ',' << SwanTp << ',' << MapTp << ',' << FftTp << ',' << Ch[0] << ',' << Ch[1] << '\n';
		if (SwanHs <= 0.005) continue;
		ErrMap.push_back(std::fabs(std::log(MapHs / SwanHs)));
		ErrFft.push_back(std::fabs(std::log(FftHs / SwanHs)));
		TErrMap.push_back(std::fabs(std::log(MapTp / SwanTp)));
		TErrFft.push_back(std::fabs(std::log(FftTp / SwanTp)));
		TBiasMap.push_back(std::log(MapTp / SwanTp));
		TBiasFft.push_back(std::log(FftTp / SwanTp));
	}
	for (int G = 0; G < kGroupings; ++G)
		std::printf("  bands grouped %s: Hs %.3f, Tp |log| %.3f, bias %+.1f%%\n", kGroupName[G], Median(GHs[G]), Median(GTpAbs[G]), 100.0 * (std::exp(Median(GTp[G])) - 1.0));
	const bool bPass = !ErrFft.empty() && Median(ErrFft) <= 0.10 && std::fabs(std::exp(Median(TBiasFft)) - 1.0) <= 0.05;
	std::printf("\nSeaMapSwan, %s layout: %zu cases against SWAN's points (Artifacts/long-wave-sea-map.csv)\n", Layout == ELongWaveLayout::Ranges ? "ranges" : "per band", ErrFft.size());
	std::printf("  median |log Hs error|: a channel per sine (today) %.3f, a channel per cascade %.3f (limit 0.10)\n", Median(ErrMap), Median(ErrFft));
	std::printf("  Tp: median |log error| today %.3f, per cascade %.3f; median bias today %+.1f%%, per cascade %+.1f%% (limit 5%%)\n",
		Median(TErrMap), Median(TErrFft), 100.0 * (std::exp(Median(TBiasMap)) - 1.0), 100.0 * (std::exp(Median(TBiasFft)) - 1.0));
	std::printf("  %s\n", bPass ? "pass" : "FAIL");
	return bPass;
}

int main(int Argc, char** Argv)
{
	bool bAll = true;
	const double T0 = Now();
	for (const ELongWaveLayout Layout : { ELongWaveLayout::PerBand, ELongWaveLayout::Ranges })
	for (const FLongWaveCheck& C : LongWaveChecks::RunAll(Layout))
	{
		if (C.Name == "Spectrum") std::printf("--- %s layout\n", Layout == ELongWaveLayout::Ranges ? "ranges (the brief's L1, L2, L3)" : "per band (the game's)");
		std::printf("%s  %s\n", C.bPass ? "pass" : "FAIL", C.Name.c_str());
		for (const std::string& L : C.Lines) std::printf("      %s\n", L.c_str());
		bAll &= C.bPass;
	}
	std::printf("checks took %.1f s\n", (Now() - T0) / 1000.0);
	Timings();
	if (Argc >= 3 && std::string(Argv[1]) == "--swan")
	{
		SeaMapSwan(Argv[2], ELongWaveLayout::Ranges);
		bAll &= SeaMapSwan(Argv[2], ELongWaveLayout::PerBand);
	}
	return bAll ? 0 : 1;
}
