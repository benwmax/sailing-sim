#include "LongWaveChecks.h"
#include "Fft.h"
#include "LongWaves.h"
#include "PortableRandom.h"
#include "SailingMath.h"
#include "Waves.h"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <memory>
#include <thread>

namespace Sailing
{
	namespace
	{
		std::string Format(const char* Fmt, ...)
#if defined(__clang__) || defined(__GNUC__)
			__attribute__((format(printf, 1, 2)))
#endif
			;
		std::string Format(const char* Fmt, ...)
		{
			char Buffer[512];
			va_list Args;
			va_start(Args, Fmt);
			std::vsnprintf(Buffer, sizeof(Buffer), Fmt, Args);
			va_end(Args);
			return Buffer;
		}

		FLongWaveParams Sea(double Knots, double FromDeg = 0.0, double Fetch = 15000.0)
		{
			FLongWaveParams P;
			P.WindMs = Knots * kKnot;
			P.WindFromRad = FromDeg * kDegToRad;
			P.FetchMeters = Fetch;
			return P;
		}

		std::unique_ptr<FLongWaves> SnappedSea(double Knots, uint64_t Seed = 1, double Depth = 0.0, double MinHz = 0.18, double FromDeg = 0.0)
		{
			auto W = std::make_unique<FLongWaves>(Seed);
			if (Depth > 0.0) W->SetDepth(Depth);
			FLongWaveParams P = Sea(Knots, FromDeg);
			P.MinHz = MinHz;
			W->SetParams(P);
			W->SnapToTarget();
			return W;
		}

		/** FWaveField at the same wind with its targets: the sines the FFT replaces (components 0-23). */
		std::unique_ptr<FWaveField> Sines(double Knots, double FromDeg = 0.0)
		{
			auto F = std::make_unique<FWaveField>(1);
			FWaveParams P;
			P.WindSpeedKnots = Knots;
			P.WindFromDegrees = FromDeg;
			P.FetchMeters = 15000.0;
			F->SetWind(P);
			F->SnapToTarget();
			return F;
		}

		/** Count workers pulling jobs from a shared counter: the order differs from run to run, the result must not. */
		FLongWaves::FParallelFor Workers(int Count)
		{
			return [Count](int Jobs, const std::function<void(int)>& Job)
			{
				std::atomic<int> Next { 0 };
				std::vector<std::thread> Threads;
				for (int W = 0; W < Count; ++W)
					Threads.emplace_back([&Next, Jobs, &Job]()
					{
						for (int J = Next.fetch_add(1); J < Jobs; J = Next.fetch_add(1)) Job(J);
					});
				for (std::thread& T : Threads) T.join();
			};
		}

		bool SameGrids(const FLongWaves::FKeyGrids& A, const FLongWaves::FKeyGrids& B)
		{
			for (int C = 0; C < kLongCascades; ++C)
			{
				if (A.bRunning[C] != B.bRunning[C]) return false;
				for (int F = 0; F < kLongFields; ++F)
				{
					if (A.F[C][F].size() != B.F[C][F].size()) return false;
					if (!A.F[C][F].empty() && std::memcmp(A.F[C][F].data(), B.F[C][F].data(), A.F[C][F].size() * sizeof(float)) != 0) return false;
				}
			}
			return true;
		}

		const char* kFieldNames[kLongFields] = { "H", "Vz", "Sx", "Sy", "U", "V", "Ax", "Ay", "Dx", "Dy", "Jxx", "Jyy", "Jxy" };
	}

	FLongWaveCheck LongWaveChecks::Spectrum()
	{
		FLongWaveCheck R { "Spectrum", true, {} };
		for (const double Kn : { 10.0, 15.0, 20.0, 28.0 })
		{
			for (const double Depth : { 0.0, 5.0 })
			{
				const auto W = SnappedSea(Kn, 1, Depth);
				auto S = Sines(Kn);
				if (Depth > 0.0) { S = std::make_unique<FWaveField>(1); S->SetDepth(Depth); FWaveParams P; P.WindSpeedKnots = Kn; P.FetchMeters = 15000.0; S->SetWind(P); S->SnapToTarget(); }
				double SinVar = 0.0, SinVf = 0.0, Bands[kWaveBands];
				for (int I = 0; I < 24; ++I)
				{
					const FWaveComponent& C = S->GetComponents()[I];
					const double E = 0.5 * C.Amplitude * C.Amplitude;
					SinVar += E;
					SinVf += E * C.Omega / (2.0 * kPi);
				}
				// The sines' Tm01 at their bands' centres (their own frequencies are drawn at random within each band).
				double CenVf = 0.0;
				for (int I = 0; I < 24; ++I)
				{
					const FWaveComponent& C = S->GetComponents()[I];
					CenVf += 0.5 * C.Amplitude * C.Amplitude * FWaveField::BandCentreHz(I / 3);
				}
				W->BandVariance(Bands);
				const double Var = W->Variance();
				const double Tm = W->MeanPeriod(), SinTm = SinVar / SinVf, CenTm = SinVar / CenVf;
				const double Dir = WrapAngle(W->MeanDirection() - kPi) / kDegToRad;
				const bool bVar = std::fabs(Var / SinVar - 1.0) < 0.01;
				const bool bTm = std::fabs(Tm / CenTm - 1.0) < 0.02;
				const bool bDir = std::fabs(Dir) < 2.0;
				R.bPass &= bVar && bTm && bDir;
				R.Lines.push_back(Format("%2.0f kn, depth %.0f m: variance %.5f m^2 against the sines' %.5f (%+.2f%%); Tm01 %.3f s against %.3f "
					"at band centres (%+.1f%%; %.3f at the sines' own frequencies); mean direction %+.2f deg off the wind%s",
					Kn, Depth, Var, SinVar, 100.0 * (Var / SinVar - 1.0), Tm, CenTm, 100.0 * (Tm / CenTm - 1.0), SinTm, Dir,
					bVar && bTm && bDir ? "" : "  FAIL"));
			}
		}
		const auto W = SnappedSea(20.0);
		for (int C = 0; C < kLongCascades; ++C)
		{
			if (!W->HasModes(C)) { R.Lines.push_back(Format("%s: no modes (the lake's spectrum ends inside L2)", kLongCascadeSpecs[C].Name)); continue; }
			double Lo = 0.0, Hi = 0.0;
			W->WavelengthRange(C, Lo, Hi);
			const double Max = C == 1 ? 0.5 * kLongCascadeSpecs[C].Tile : kLongCascadeSpecs[C].MaxWavelength;
			const bool bIn = Lo >= kLongCascadeSpecs[C].MinWavelength && Hi <= Max + 1e-9 && Lo >= 4.0 * W->Cell(C);
			R.bPass &= bIn;
			R.Lines.push_back(Format("%s: %d modes from %.2f to %.2f m (range %.1f to %.1f m; four cells %.2f m)%s", kLongCascadeSpecs[C].Name,
				W->ModeCount(C), Lo, Hi, kLongCascadeSpecs[C].MinWavelength, Max, 4.0 * W->Cell(C), bIn ? "" : "  FAIL"));
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::MatchesDirectSum()
	{
		FLongWaveCheck R { "MatchesDirectSum", true, {} };
		struct FCase { const char* Name; double Knots, Depth, MinHz; };
		const FCase Cases[] = { { "20 kn deep", 20.0, 0.0, 0.18 }, { "28 kn, 6 m deep", 28.0, 6.0, 0.18 }, { "25 kn with an open sea's range (L3)", 25.0, 0.0, 0.07 } };
		for (const FCase& Case : Cases)
		{
			const auto W = SnappedSea(Case.Knots, 7, Case.Depth, Case.MinHz);
			double Worst = 0.0;
			int WorstField = 0;
			int Running = 0;
			for (const int64_t Key : { int64_t(0), int64_t(517), int64_t(9001) })
			{
				FLongWaves::FKeyGrids G;
				W->EvaluateInto(Key, G);
				FPortableRandom Rng(HashCombine(uint64_t(Key), 99));
				for (int C = 0; C < kLongCascades; ++C)
				{
					if (!G.bRunning[C]) continue;
					Running |= 1 << C;
					double Rms[kLongFields];
					for (int F = 0; F < kLongFields; ++F)
					{
						double S2 = 0.0;
						for (const float V : G.F[C][F]) S2 += double(V) * V;
						Rms[F] = std::sqrt(S2 / G.F[C][F].size());
					}
					for (int P = 0; P < 64; ++P)
					{
						const int I = Rng.UniformInt(0, FLongWaves::N - 1), J = Rng.UniformInt(0, FLongWaves::N - 1);
						double X, Y, D[kLongFields];
						W->NodePosition(C, I, J, X, Y);
						W->DirectSum(C, X, Y, double(Key) / FLongWaves::KeyHz, D);
						for (int F = 0; F < kLongFields; ++F)
						{
							const double Err = std::fabs(double(G.F[C][F][size_t(I) * FLongWaves::N + J]) - D[F]) / std::max(1.0, Rms[F]);
							if (Err > Worst) { Worst = Err; WorstField = F; }
						}
					}
				}
			}
			const bool bOk = Worst < 1e-4;
			R.bPass &= bOk;
			R.Lines.push_back(Format("%s: cascades %s%s%s, worst error %.2e (field %s; tolerance 1e-4 x max(1, RMS))%s", Case.Name,
				Running & 1 ? "L1 " : "", Running & 2 ? "L2 " : "", Running & 4 ? "L3" : "", Worst, kFieldNames[WorstField], bOk ? "" : "  FAIL"));
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::TimeBlend()
	{
		FLongWaveCheck R { "TimeBlend", true, {} };
		for (const double Kn : { 15.0, 28.0 })
		{
			const auto W = SnappedSea(Kn);
			FLongWaves::FKeyGrids A, B;
			W->EvaluateInto(600, A);
			W->EvaluateInto(601, B);
			const std::vector<float>& HA = A.F[0][0];
			const std::vector<float>& HB = B.F[0][0];
			double S2 = 0.0, E2 = 0.0;
			FPortableRandom Rng(5);
			for (int P = 0; P < 256; ++P)
			{
				const int I = Rng.UniformInt(0, FLongWaves::N - 1), J = Rng.UniformInt(0, FLongWaves::N - 1);
				double X, Y, D[kLongFields];
				W->NodePosition(0, I, J, X, Y);
				W->DirectSum(0, X, Y, 600.5 / FLongWaves::KeyHz, D);
				const size_t Ix = size_t(I) * FLongWaves::N + J;
				const double Blend = 0.5 * (double(HA[Ix]) + HB[Ix]);
				S2 += D[0] * D[0];
				E2 += (Blend - D[0]) * (Blend - D[0]);
			}
			const double Rel = std::sqrt(E2 / S2);
			R.bPass &= Rel < 0.02;
			R.Lines.push_back(Format("%.0f kn: L1 half way between keys, RMS error %.2f%% of its RMS height (3.6 m waves at 30 Hz keys)%s", Kn, 100.0 * Rel, Rel < 0.02 ? "" : "  FAIL"));
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::Spreading()
	{
		FLongWaveCheck R { "Spreading", true, {} };
		for (const double Kn : { 12.0, 20.0 })
		{
			const auto W = SnappedSea(Kn, 3);
			// 20 deg bins: L1's lattice at 12 m is 7 deg between neighbouring directions, so 10 deg bins alias.
			constexpr int Bins = 18;
			double Got[Bins], Want[Bins] = {}, Bands[kWaveBands];
			W->DirectionHistogram(Bins, Got);
			W->BandVariance(Bands);
			const double Fp = 1.0 / FWaveField::TargetPeakPeriod(Kn * kKnot, 15000.0);
			for (int B = 0; B < 8; ++B)
			{
				// The band's spreading over each bin, normalized over the half plane (nothing travels upwind).
				const double Fc = FWaveField::BandCentreHz(B);
				double Part[Bins] = {}, Sum = 0.0;
				for (int S = 0; S < Bins * 50; ++S)
				{
					const double Th = -kPi + (S + 0.5) * 2.0 * kPi / (Bins * 50);
					if (std::fabs(Th) >= 0.5 * kPi) continue;
					const double D = FWaveField::DirectionalSpreading(Fc, Fp, Th);
					Part[((S + 25) / 50) % Bins] += D;
					Sum += D;
				}
				for (int Bin = 0; Bin < Bins; ++Bin) Want[Bin] += Bands[B] * Part[Bin] / Sum;
			}
			double Total = 0.0, Worst = 0.0, Peak = 0.0;
			for (int Bin = 0; Bin < Bins; ++Bin) Total += Got[Bin];
			std::string Row;
			for (int Bin = 0; Bin < Bins; ++Bin)
			{
				Worst = std::max(Worst, std::fabs(Got[Bin] - Want[Bin]) / Total);
				Peak = std::max(Peak, Want[Bin] / Total);
				if (Want[Bin] / Total > 0.001) Row += Format(" %+.0f:%.3f/%.3f", -180.0 + Bin * 20.0, Got[Bin] / Total, Want[Bin] / Total);
			}
			const bool bOk = Worst < 0.1 * Peak;
			R.bPass &= bOk;
			R.Lines.push_back(Format("%.0f kn: worst 20 deg bin off by %.4f of the energy (the peak bin holds %.3f; tolerance a tenth of it)%s", Kn, Worst, Peak, bOk ? "" : "  FAIL"));
			R.Lines.push_back("  bin centre: modes / sech^2" + Row);
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::Growth()
	{
		FLongWaveCheck R { "Growth", true, {} };
		const auto Target = SnappedSea(15.0);
		double Want[kWaveBands];
		Target->BandVariance(Want);
		FLongWaves W(1);
		W.SetParams(Sea(15.0));
		W.Advance(0);
		double Reached[kWaveBands];
		for (double& T : Reached) T = -1.0;
		for (int64_t Key = 1; Key < int64_t(400 * FLongWaves::KeyHz); ++Key)
		{
			W.Advance(Key);
			double Now[kWaveBands];
			W.BandVariance(Now);
			for (int B = 0; B < 8; ++B)
				if (Reached[B] < 0.0 && Want[B] > 0.0 && std::sqrt(Now[B] / Want[B]) >= 1.0 - std::exp(-1.0)) Reached[B] = Key / FLongWaves::KeyHz;
		}
		std::string Row;
		for (int B = 0; B < 8; ++B)
		{
			const double Tau = FWaveField::GrowthSeconds(1.0 / FWaveField::BandCentreHz(B));
			const bool bOk = Reached[B] > 0.0 && std::fabs(Reached[B] / Tau - 1.0) < 0.03;
			R.bPass &= bOk;
			Row += Format(" band %d %.1f/%.1f s%s;", B, Reached[B], Tau, bOk ? "" : " FAIL");
		}
		R.Lines.push_back("1 - 1/e of the height reached / GrowthSeconds:" + Row);
		return R;
	}

	FLongWaveCheck LongWaveChecks::WindShift()
	{
		FLongWaveCheck R { "WindShift", true, {} };
		for (const double Shift : { 30.0, 90.0 })
		{
			// The surface at a point through the shift, sampled at the physics' 120 Hz with the producer two keys ahead.
			auto W = SnappedSea(15.0, 2);
			const double Dt = 1.0 / 120.0;
			int64_t Produced = -1;
			double PrevH = 0.0, PrevVz = 0.0, WorstExcess = -1e9, MaxStep = 0.0;
			bool bShifted = false;
			for (int Step = 0; Step <= 120 * 20; ++Step)
			{
				const double T = Step * Dt;
				if (!bShifted && T >= 2.0) { W->SetParams(Sea(15.0, Shift)); bShifted = true; }
				const int64_t Want = int64_t(std::floor(T * FLongWaves::KeyHz)) + 2;
				for (int64_t K = std::max<int64_t>(Produced + 1, Want - 3); K <= Want; ++K) W->Produce(K);
				Produced = Want;
				double F[kLongFields];
				W->Sample(37.0, -12.0, T, nullptr, F);
				if (Step > 0)
				{
					const double Dh = std::fabs(F[0] - PrevH);
					MaxStep = std::max(MaxStep, Dh);
					WorstExcess = std::max(WorstExcess, Dh - (1.5 * std::max(std::fabs(F[1]), std::fabs(PrevVz)) * Dt + 0.001));
				}
				PrevH = F[0];
				PrevVz = F[1];
			}
			const bool bSmooth = WorstExcess <= 0.0 && W->GetSyncMisses() == 0;
			// The old direction's energy: the modes the new wind doesn't feed, 3 tau of the longest band after the shift.
			FLongWaves Decay(2);
			Decay.SetParams(Sea(15.0));
			Decay.SnapToTarget();
			Decay.Advance(0);
			Decay.SetParams(Sea(15.0, Shift));
			Decay.Advance(FLongWaves::TargetEveryKeys);
			const double Start = Decay.FadingVariance(), Total = Decay.Variance();
			const double Tau = FWaveField::GrowthSeconds(1.0 / FWaveField::BandCentreHz(0));
			Decay.Advance(FLongWaves::TargetEveryKeys + int64_t(3.0 * Tau * FLongWaves::KeyHz));
			const double End = Decay.FadingVariance();
			const bool bFade = Start > 0.0 && End / Start < 0.05;
			R.bPass &= bSmooth && bFade;
			R.Lines.push_back(Format("%.0f deg: largest 1/120 s height step %.1f mm, never past 1.5 x |dh/dt| dt + 1 mm (worst margin %+.2f mm), "
				"sync misses %llu; old direction's energy %.4f m^2 (%.0f%% of the sea) -> %.6f after 3 tau (%.2f%%)%s", Shift, 1000.0 * MaxStep,
				1000.0 * WorstExcess, (unsigned long long)W->GetSyncMisses(), Start, 100.0 * Start / Total, End, 100.0 * End / Start,
				bSmooth && bFade ? "" : "  FAIL"));
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::FrameRateFree()
	{
		FLongWaveCheck R { "FrameRateFree", true, {} };
		FLongWaves::FKeyGrids Ref;
		for (const int Fps : { 30, 60, 144 })
		{
			FLongWaves W(4);
			W.SetParams(Sea(12.0));
			bool bShifted = false;
			for (int Frame = 0; Frame <= 30 * Fps; ++Frame)
			{
				const double T = double(Frame) / Fps;
				if (!bShifted && T >= 10.0) { W.SetParams(Sea(20.0, 40.0)); bShifted = true; }
				W.Advance(int64_t(std::floor(T * FLongWaves::KeyHz + 1e-9)) + 2);
			}
			FLongWaves::FKeyGrids G;
			W.EvaluateInto(902, G);
			if (Fps == 30) Ref = G;
			const bool bSame = Fps == 30 || SameGrids(G, Ref);
			R.bPass &= bSame;
			R.Lines.push_back(Format("%d fps: key %lld, variance %.5f m^2%s", Fps, (long long)W.GetKey(), W.Variance(), Fps == 30 ? "" : bSame ? ", grids equal to 30 fps's to the bit" : "  FAIL: grids differ"));
		}
		return R;
	}

	FLongWaveCheck LongWaveChecks::Determinism()
	{
		FLongWaveCheck R { "Determinism", true, {} };
		const auto W = SnappedSea(20.0, 11, 4.0);
		FLongWaves::FKeyGrids One;
		W->EvaluateInto(777, One);
		for (const int Count : { 2, 8 })
		{
			FLongWaves::FKeyGrids G;
			W->EvaluateInto(777, G, Workers(Count));
			const bool bSame = SameGrids(G, One);
			R.bPass &= bSame;
			R.Lines.push_back(Format("%d workers: %s", Count, bSame ? "equal to one worker's to the bit" : "FAIL: grids differ"));
		}
		// A restart: the sea run 5 minutes from the start, and one started at that world time.
		FLongWaves A(11), B(11);
		A.SetDepth(4.0);
		B.SetDepth(4.0);
		A.SetParams(Sea(20.0));
		A.SnapToTarget();
		A.Advance(0);
		A.Advance(9000);
		B.SetParams(Sea(20.0));
		B.SnapToTarget();
		B.Advance(9000);
		FLongWaves::FKeyGrids GA, GB;
		A.EvaluateInto(9000, GA);
		B.EvaluateInto(9000, GB);
		const bool bRestart = SameGrids(GA, GB);
		R.bPass &= bRestart;
		R.Lines.push_back(bRestart ? "restart at 300 s: equal to the bit" : "restart at 300 s: FAIL: grids differ");
		return R;
	}

	FLongWaveCheck LongWaveChecks::LongClock()
	{
		FLongWaveCheck R { "LongClock", true, {} };
		const auto W = SnappedSea(20.0, 9);
		const int64_t Key = 30000000; // 1e6 s: eleven and a half days
		FLongWaves::FKeyGrids G;
		W->EvaluateInto(Key, G);
		double Worst = 0.0;
		FPortableRandom Rng(17);
		for (int C = 0; C < kLongCascades; ++C)
		{
			if (!G.bRunning[C]) continue;
			for (int P = 0; P < 32; ++P)
			{
				const int I = Rng.UniformInt(0, FLongWaves::N - 1), J = Rng.UniformInt(0, FLongWaves::N - 1);
				double X, Y, D[kLongFields];
				W->NodePosition(C, I, J, X, Y);
				W->DirectSum(C, X, Y, double(Key) / FLongWaves::KeyHz, D);
				Worst = std::max(Worst, std::fabs(double(G.F[C][0][size_t(I) * FLongWaves::N + J]) - D[0]));
			}
		}
		R.bPass = Worst < 0.001;
		R.Lines.push_back(Format("t = 1e6 s: worst height %.2e m from the straight sum (tolerance 1 mm)%s", Worst, R.bPass ? "" : "  FAIL"));
		return R;
	}

	namespace
	{
		// docs/long-wave-fft/: 64 heights (m) of seed 1's 20 kn sea at t = 100 s, made on the Mac (M5 Pro, clang). The PC
		// runs SailingSim.Physics.LongWaves.Golden in its next build: within 1e-5 m, not to the bit (libm's last ulp).
		const double kGolden[64] = {
#include "LongWaveGolden.inl"
		};
	}

	FLongWaveCheck LongWaveChecks::Golden()
	{
		FLongWaveCheck R { "Golden", true, {} };
		const auto W = SnappedSea(20.0, 1);
		W->Produce(3000);
		W->Produce(3001);
		double Worst = 0.0;
		std::string Table;
		for (int I = 0; I < 64; ++I)
		{
			double F[kLongFields];
			W->Sample(13.7 * I - 400.0, 31.3 * ((I * 7) % 64) - 900.0, 100.0, nullptr, F);
			Worst = std::max(Worst, std::fabs(F[0] - kGolden[I]));
			Table += Format("%.9f,%s", F[0], I % 4 == 3 ? "\n" : " ");
		}
		R.bPass = Worst < 1e-5;
		R.Lines.push_back(Format("64 heights at t = 100 s: worst %.2e m from the table (tolerance 1e-5)%s", Worst, R.bPass ? "" : "  FAIL"));
		if (!R.bPass) R.Lines.push_back("heights now (LongWaveGolden.inl):\n" + Table);
		return R;
	}

	FLongWaveCheck LongWaveChecks::NoWeave()
	{
		FLongWaveCheck R { "NoWeave", true, {} };
		constexpr double Knots = 20.0;
		constexpr int M = 256, P = 512;
		constexpr double Patch = 300.0, Step = Patch / M;
		const double Tp = FWaveField::TargetPeakPeriod(Knots * kKnot, 15000.0);
		const double Lp = kGravity * Tp * Tp / (2.0 * kPi);
		const double Rmin = 2.0 * Lp, Rmax = 0.5 * Patch;
		FFft2D Fft(P);

		// The height autocorrelation of a patch (zero padded, so no wrap; each lag divided by its overlap).
		auto Correlate = [&](const std::function<double(double, double)>& Height, std::vector<double>& Rho)
		{
			std::vector<double> H(size_t(M) * M);
			double Mean = 0.0;
			for (int I = 0; I < M; ++I) for (int J = 0; J < M; ++J) { H[size_t(I) * M + J] = Height(I * Step, J * Step); Mean += H[size_t(I) * M + J]; }
			Mean /= double(M) * M;
			std::vector<FComplexF> A(size_t(P) * P);
			double Var = 0.0;
			for (int I = 0; I < M; ++I)
				for (int J = 0; J < M; ++J)
				{
					const double V = H[size_t(I) * M + J] - Mean;
					A[size_t(I) * P + J].Re = float(V);
					Var += V * V;
				}
			Var /= double(M) * M;
			Fft.Forward(A.data());
			for (FComplexF& C : A) C = { C.Re * C.Re + C.Im * C.Im, 0.f };
			Fft.Inverse(A.data());
			Rho.assign(size_t(P) * P, 0.0);
			for (int I = 0; I < P; ++I)
				for (int J = 0; J < P; ++J)
				{
					const int Li = I < P / 2 ? I : I - P, Lj = J < P / 2 ? J : J - P;
					const double Overlap = double(M - std::abs(Li)) * double(M - std::abs(Lj));
					if (Overlap > 0.0) Rho[size_t(I) * P + J] = A[size_t(I) * P + J].Re / (double(P) * P) / Overlap / Var;
				}
		};
		// Tile lags: a cascade's lattice (its tile along its own axes), where its share of the sea repeats.
		auto TileLagNear = [](double Lx, double Ly, int& OutCascade, double& OutDist)
		{
			OutDist = 1e30;
			OutCascade = -1;
			for (int C = 0; C < 2; ++C)
			{
				const double Rot = kLongCascadeSpecs[C].RotationDeg * kDegToRad, Tile = kLongCascadeSpecs[C].Tile;
				const double U = (std::cos(Rot) * Lx + std::sin(Rot) * Ly) / Tile, V = (-std::sin(Rot) * Lx + std::cos(Rot) * Ly) / Tile;
				const double Ru = std::round(U), Rv = std::round(V);
				if (Ru == 0.0 && Rv == 0.0) continue;
				const double D = std::hypot(U - Ru, V - Rv) * Tile;
				if (D < OutDist) { OutDist = D; OutCascade = C; }
			}
		};
		auto Peaks = [&](const std::vector<double>& Rho, double& OutFree, double& OutFreeLag, double& OutTile, std::string& OutTileList)
		{
			OutFree = 0.0; OutFreeLag = 0.0; OutTile = 0.0;
			const int Reach = int(Rmax / Step);
			std::vector<std::pair<double, std::string>> Tiles;
			for (int Li = 0; Li <= Reach; ++Li)
				for (int Lj = -Reach; Lj <= Reach; ++Lj)
				{
					if (Li == 0 && Lj <= 0) continue; // half the plane: the correlation is even
					const double Lx = Li * Step, Ly = Lj * Step, L = std::hypot(Lx, Ly);
					if (L < Rmin || L > Rmax) continue;
					const double V = Rho[size_t(Li) * P + size_t((Lj + P) % P)];
					int C;
					double D;
					TileLagNear(Lx, Ly, C, D);
					if (D < 3.0) { OutTile = std::max(OutTile, V); continue; }
					if (V > OutFree) { OutFree = V; OutFreeLag = L; }
				}
			// Each tile lattice point inside the window, with the correlation there.
			for (int C = 0; C < 2; ++C)
			{
				const double Rot = kLongCascadeSpecs[C].RotationDeg * kDegToRad, Tile = kLongCascadeSpecs[C].Tile;
				for (int A = -2; A <= 2; ++A)
					for (int B = -2; B <= 2; ++B)
					{
						if (A == 0 && B == 0) continue;
						const double Lx = (std::cos(Rot) * A - std::sin(Rot) * B) * Tile, Ly = (std::sin(Rot) * A + std::cos(Rot) * B) * Tile;
						if (Lx < 0.0 || std::hypot(Lx, Ly) > Rmax) continue;
						const int Li = int(std::lround(Lx / Step)), Lj = int(std::lround(Ly / Step));
						Tiles.push_back({ Rho[size_t(Li) * P + size_t((Lj + P) % P)], Format("%s (%+.0f, %+.0f) m: %.2f", kLongCascadeSpecs[C].Name, Lx, Ly, Rho[size_t(Li) * P + size_t((Lj + P) % P)]) });
					}
			}
			OutTileList.clear();
			for (const auto& T : Tiles) OutTileList += (OutTileList.empty() ? "" : "; ") + T.second;
		};

		const auto W = SnappedSea(Knots, 1);
		W->Produce(3000);
		W->Produce(3001);
		std::vector<double> Rho;
		Correlate([&W](double X, double Y) { double F[kLongFields]; W->Sample(X, Y, 100.0, nullptr, F); return F[0]; }, Rho);
		double Free, FreeLag, Tile;
		std::string Tiles;
		Peaks(Rho, Free, FreeLag, Tile, Tiles);
		R.bPass = Free <= 0.25;
		R.Lines.push_back(Format("FFT at %.0f kn (peak wavelength %.1f m): highest correlation %.1f to %.0f m from zero lag, away from tile lags: %.3f at %.1f m%s",
			Knots, Lp, Rmin, Rmax, Free, FreeLag, R.bPass ? "" : "  FAIL"));
		R.Lines.push_back("  at the tile lags: " + (Tiles.empty() ? std::string("none inside the window") : Tiles));

		// The 24 sines FWaveField draws today (components 0-23), the same way.
		const auto S = Sines(Knots);
		Correlate([&S](double X, double Y)
		{
			double H = 0.0;
			for (int I = 0; I < 24; ++I)
			{
				const FWaveComponent& C = S->GetComponents()[I];
				H += C.Amplitude * std::sin(C.Kx * X + C.Ky * Y - C.Omega * 100.0 + C.Phase);
			}
			return H;
		}, Rho);
		Peaks(Rho, Free, FreeLag, Tile, Tiles);
		R.Lines.push_back(Format("the 24 sines: highest correlation away from zero lag %.3f at %.1f m (%s)", Free, FreeLag, Free > 0.25 ? "the weave" : "under 0.25"));
		return R;
	}

	std::vector<FLongWaveCheck> LongWaveChecks::RunAll()
	{
		return { Spectrum(), MatchesDirectSum(), TimeBlend(), Spreading(), Growth(), WindShift(), FrameRateFree(), Determinism(), LongClock(), Golden(), NoWeave() };
	}
}
