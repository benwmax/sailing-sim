#include "LongWaves.h"
#include "PortableRandom.h"
#include "SailingMath.h"
#include "SeaState.h"
#include <algorithm>
#include <climits>
#include <cmath>

// No fused multiply-adds: the same grids on arm64 as on x64 MSVC (docs/long-wave-fft/, determinism).
#if defined(__clang__)
#pragma clang fp contract(off)
#endif

namespace Sailing
{
	namespace
	{
		constexpr double kBandMinHz = 0.18;  // FWaveField's band 0 starts here
		constexpr double kBandMaxHz = 2.4;   // and band 15 ends here

		double BandRatio() { return std::pow(kBandMaxHz / kBandMinHz, 1.0 / kWaveBands); }

		/** FWaveField's band of a frequency (-1 below band 0, kWaveBands past band 15). */
		int BandOf(double F)
		{
			if (F < kBandMinHz) return -1;
			const int B = int(std::floor(std::log(F / kBandMinHz) / std::log(BandRatio())));
			return std::min(B, kWaveBands);
		}

		/** ComputeTargetAmplitudes' JONSWAP shape (gamma 3.3), unscaled. */
		double JonswapShape(double F, double Fp)
		{
			const double Sigma = F <= Fp ? 0.07 : 0.09;
			const double R = std::exp(-(F - Fp) * (F - Fp) / (2.0 * Sigma * Sigma * Fp * Fp));
			return std::pow(F, -5.0) * std::exp(-1.25 * std::pow(Fp / F, 4.0)) * std::pow(3.3, R);
		}

		/** Wavenumber of angular frequency Omega in depth H (as Waves.cpp's WavenumberFor). */
		double WavenumberFor(double Omega, double H)
		{
			const double Deep = Omega * Omega / kGravity;
			if (H <= 0.0) return Deep;
			double K = std::max(Deep, Omega / std::sqrt(kGravity * H));
			for (int I = 0; I < 30; ++I)
			{
				const double T = std::tanh(K * H);
				const double F = kGravity * K * T - Omega * Omega;
				const double D = kGravity * (T + K * H * (1.0 - T * T));
				const double Next = K - F / D;
				if (std::fabs(Next - K) < 1e-12 * K) { K = Next; break; }
				K = Next;
			}
			return K;
		}

		/** Pairs of fields packed into one complex transform (real part, imaginary part); -1 = nothing. */
		constexpr int kPairs = 7;
		constexpr int kPairField[kPairs][2] = {
			{ int(ELongField::H), int(ELongField::Vz) },
			{ int(ELongField::Sx), int(ELongField::Sy) },
			{ int(ELongField::U), int(ELongField::V) },
			{ int(ELongField::Ax), int(ELongField::Ay) },
			{ int(ELongField::Dx), int(ELongField::Dy) },
			{ int(ELongField::Jxx), int(ELongField::Jyy) },
			{ int(ELongField::Jxy), -1 },
		};

		int64_t FloorMod(int64_t A, int64_t B) { return ((A % B) + B) % B; }
	}

	double FLongWaves::SplitHz()
	{
		return kBandMinHz * std::pow(BandRatio(), 8.0);
	}

	FLongWaves::FLongWaves(uint64_t InWorldSeed, ELongWaveLayout InLayout)
		: WorldSeed(InWorldSeed)
		, Layout(InLayout)
		, Fft64(new FFft2D(64))
		, Fft128(new FFft2D(128))
		, Ring(new FSlot[RingKeys])
	{
		LayModes();
	}

	double FLongWaves::MaxWavelength(int Cascade) const
	{
		return 2.0 * kPi / std::max(Cascades[Cascade].MinK, 1e-12);
	}

	void FLongWaves::SetDepth(double DepthMeters)
	{
		Depth = std::max(DepthMeters, 0.0);
		LayModes();
		bParamsDirty = true;
	}

	void FLongWaves::SetParams(const FLongWaveParams& In)
	{
		const bool bRange = In.MinHz != Params.MinHz || In.MaxHz != Params.MaxHz;
		if (bRange || In.WindMs != Params.WindMs || In.WindFromRad != Params.WindFromRad || In.FetchMeters != Params.FetchMeters
			|| In.Choppiness != Params.Choppiness)
		{
			Params = In;
			bParamsDirty = true;
			// A new range lays the modes again (configuration, not weather: the amplitudes start from calm).
			if (bRange) LayModes();
		}
		if (!bAdvanced) ComputeTargets();
	}

	void FLongWaves::LayModes()
	{
		const double MaxHz = Params.MaxHz > 0.0 ? Params.MaxHz : SplitHz();
		// The swell cascade runs only when the spectrum reaches past 165 m (L2's tile / 2): an open sea, never a lake.
		const double Longest = 2.0 * kPi / WavenumberFor(2.0 * kPi * Params.MinHz, Depth);
		const bool bSwell = Longest > 0.5 * kLongRangeSpecs[1].Tile;

		// The layout's cascades.
		static const char* const BandNames[8] = { "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7" };
		NumCas = 0;
		if (Layout == ELongWaveLayout::Ranges)
		{
			for (int C = 0; C < (bSwell ? 3 : 2); ++C) Cascades[NumCas++].Spec = kLongRangeSpecs[C];
		}
		else
		{
			for (int B = 0; B < 8; ++B)
			{
				// Tile: 16 of the band's shortest waves at this depth (four cells each on 64^2); its longest are under 2 of
				// those, far inside tile / 2. Turned by the golden angle band to band, so no two lattices line up.
				const double Shortest = 2.0 * kPi / WavenumberFor(2.0 * kPi * kBandMinHz * std::pow(BandRatio(), B + 1), Depth);
				FLongWaveCascadeSpec& Spec = Cascades[NumCas++].Spec;
				Spec = FLongWaveCascadeSpec();
				Spec.Name = BandNames[B];
				Spec.Tile = 16.0 * Shortest;
				Spec.RotationDeg = std::fmod(137.50776405003785 * (B + 1), 360.0);
				Spec.Band = B;
				Spec.Size = 64;
			}
			if (bSwell)
			{
				FLongWaveCascadeSpec& Spec = Cascades[NumCas++].Spec;
				Spec = kLongRangeSpecs[2];
				Spec.MinWavelength = 0.0; // everything under band 0's frequency
			}
		}
		const int Last = Layout == ELongWaveLayout::Ranges ? NumCas - 1 : -1;

		const uint64_t Base = HashCombine(WorldSeed, HashString("longwave"));
		for (int C = 0; C < kLongCascades; ++C)
		{
			FCascade& Cas = Cascades[C];
			Cas.Modes.clear();
			if (C >= NumCas) continue;
			const FLongWaveCascadeSpec& Spec = Cas.Spec;
			const int N = Spec.Size;
			Cas.Fft = N == 64 ? Fft64.get() : Fft128.get();
			const double Rot = Spec.RotationDeg * kDegToRad;
			Cas.Cos = std::cos(Rot);
			Cas.Sin = std::sin(Rot);
			const double Dk = 2.0 * kPi / Spec.Tile;
			const bool bBand = Spec.Band >= 0;
			// (Per band, the swell cascade takes the frequencies under band 0, to its tile / 2.)
			const bool bBelowBands = Layout == ELongWaveLayout::PerBand && !bBand;
			Cas.MinK = 2.0 * kPi / (bBand || bBelowBands || C == Last ? 0.5 * Spec.Tile : Spec.MaxWavelength);
			Cas.MaxK = !bBand && Spec.MinWavelength > 0.0 ? 2.0 * kPi / Spec.MinWavelength : 2.0 * kPi / (4.0 * Spec.Tile / N);

			// Every node's Gaussian, drawn in index order whether it runs or not: the sea doesn't reshuffle with the depth.
			FPortableRandom Rng(HashCombine(Base, HashString(Spec.Name)));
			std::vector<double> Xi(size_t(N) * N * 2);
			// (Each half carries a quarter: E|xi|^2 = 1/2, so the real field's variance is the modes' sum of Amp^2.)
			for (double& G : Xi) G = Rng.Gaussian() * 0.5;

			std::vector<int> Lookup(size_t(N) * N, -1);
			for (int I = 0; I < N; ++I)
			{
				if (I == N / 2) continue;
				const int MI = I < N / 2 ? I : I - N;
				for (int J = 0; J < N; ++J)
				{
					if (J == N / 2) continue;
					const int MJ = J < N / 2 ? J : J - N;
					const double Lx = MI * Dk, Ly = MJ * Dk;
					const double K = std::sqrt(Lx * Lx + Ly * Ly);
					if (K <= 0.0 || K < Cas.MinK * (1.0 - 1e-12) || K >= Cas.MaxK) continue;
					const double Th = Depth > 0.0 ? std::tanh(K * Depth) : 1.0;
					const double Omega = std::sqrt(kGravity * K * Th);
					const double F = Omega / (2.0 * kPi);
					if (F < Params.MinHz || F >= MaxHz) continue;
					const int Band = BandOf(F);
					if (bBand && Band != Spec.Band) continue;
					if (bBelowBands && Band >= 0) continue;
					FMode M;
					M.Index = I * N + J;
					M.Mirror = ((N - I) % N) * N + (N - J) % N;
					M.Kx = Cas.Cos * Lx - Cas.Sin * Ly;
					M.Ky = Cas.Sin * Lx + Cas.Cos * Ly;
					M.K = K;
					M.Omega = Omega;
					M.Freq = F;
					M.Band = Band;
					M.Coth = Depth > 0.0 && K * Depth < 20.0 ? 1.0 / Th : 1.0;
					M.XiRe = Xi[size_t(M.Index) * 2];
					M.XiIm = Xi[size_t(M.Index) * 2 + 1];
					const double Period = M.Band >= 0 ? 1.0 / FWaveField::BandCentreHz(M.Band) : 1.0 / F;
					M.Decay = 1.0 - std::exp(-(1.0 / KeyHz) / FWaveField::GrowthSeconds(Period));
					Lookup[size_t(M.Index)] = int(Cas.Modes.size());
					Cas.Modes.push_back(M);
				}
			}
			// The mirror as an index into Modes (the annulus is symmetric: every mode's -k runs too).
			for (FMode& M : Cas.Modes) M.Mirror = Lookup[size_t(M.Mirror)];
		}
		bAdvanced = false;
		StateKey = 0;
		for (int S = 0; S < RingKeys; ++S) Ring[S].Key.store(INT64_MIN, std::memory_order_release);
		ComputeTargets();
	}

	double FLongWaves::ModeShape(const FMode& M, double Fp, double TravelDir) const
	{
		const double Rel = WrapAngle(std::atan2(M.Ky, M.Kx) - TravelDir);
		if (std::fabs(Rel) >= 0.5 * kPi) return 0.0;
		// S(f) D(f, theta) (df/dk) / k: the spectrum's density per unit area of wavenumber (the node's area dk^2 is the
		// cascade's, applied by the caller).
		const double Kh = M.K * Depth;
		const double Cg = 0.5 * M.Omega / M.K * (Depth > 0.0 && Kh < 20.0 ? 1.0 + 2.0 * Kh / std::sinh(2.0 * Kh) : 1.0);
		return JonswapShape(M.Freq, Fp) * FWaveField::DirectionalSpreading(M.Freq, Fp, Rel) * (Cg / (2.0 * kPi)) / M.K;
	}

	void FLongWaves::ComputeTargets()
	{
		bParamsDirty = false;
		const double U = Params.WindMs;
		if (U < 0.5)
		{
			for (FCascade& C : Cascades) for (FMode& M : C.Modes) M.Target = 0.0;
			return;
		}
		const double Fetch = Params.FetchMeters;
		const double Fp = 1.0 / FWaveField::TargetPeakPeriod(U, Fetch);
		const double TravelDir = Params.WindFromRad + kPi;
		const double Hs = FWaveField::TargetSignificantHeight(U, Fetch);
		// ComputeTargetAmplitudes' scale: the whole 16-band discrete spectrum carries Hs.
		double Sum16 = 0.0;
		for (int B = 0; B < kWaveBands; ++B) Sum16 += JonswapShape(FWaveField::BandCentreHz(B), Fp) * FWaveField::BandWidthHz(B);
		const double Scale2 = Sum16 > 1e-12 ? (Hs / 4.0) * (Hs / 4.0) / Sum16 : 0.0;

		// Each band in range gets exactly the variance FWaveField gives it (BandAmplitudeFactor^2 / 2), shared among its
		// modes by their density; below band 0 (an open sea's longer range) the continuous density at the same scale.
		double BandShape[kWaveBands] = {};
		std::vector<double> Shape[kLongCascades];
		for (int C = 0; C < kLongCascades; ++C)
		{
			const double Dk = 2.0 * kPi / Cascades[C].Spec.Tile;
			Shape[C].resize(Cascades[C].Modes.size());
			for (size_t I = 0; I < Cascades[C].Modes.size(); ++I)
			{
				const FMode& M = Cascades[C].Modes[I];
				Shape[C][I] = ModeShape(M, Fp, TravelDir) * Dk * Dk;
				if (M.Band >= 0 && M.Band < kWaveBands) BandShape[M.Band] += Shape[C][I];
			}
		}
		double BandVar[kWaveBands];
		for (int B = 0; B < kWaveBands; ++B)
		{
			const double A = FWaveField::BandAmplitudeFactor(B, U, Fetch);
			BandVar[B] = 0.5 * A * A;
		}
		for (int C = 0; C < kLongCascades; ++C)
		{
			for (size_t I = 0; I < Cascades[C].Modes.size(); ++I)
			{
				FMode& M = Cascades[C].Modes[I];
				double V = 0.0;
				if (M.Band >= 0 && M.Band < kWaveBands) V = BandShape[M.Band] > 0.0 ? BandVar[M.Band] * Shape[C][I] / BandShape[M.Band] : 0.0;
				else if (M.Band < 0) V = Scale2 * Shape[C][I];
				M.Target = std::sqrt(V);
			}
		}
	}

	void FLongWaves::Advance(int64_t Key)
	{
		if (!bAdvanced)
		{
			if (bParamsDirty) ComputeTargets();
			StateKey = Key;
			bAdvanced = true;
			return;
		}
		for (int64_t K = StateKey + 1; K <= Key; ++K)
		{
			if (bParamsDirty && FloorMod(K, TargetEveryKeys) == 0) ComputeTargets();
			for (FCascade& C : Cascades)
				for (FMode& M : C.Modes) M.Amp += (M.Target - M.Amp) * M.Decay;
		}
		StateKey = std::max(StateKey, Key);
	}

	void FLongWaves::SnapToTarget()
	{
		if (bParamsDirty) ComputeTargets();
		for (FCascade& C : Cascades)
			for (FMode& M : C.Modes) M.Amp = M.Target;
	}

	namespace
	{
		struct FCplx { double Re, Im; };
		inline FCplx Mul(FCplx A, FCplx B) { return { A.Re * B.Re - A.Im * B.Im, A.Re * B.Im + A.Im * B.Re }; }
		inline FCplx MulI(FCplx A) { return { -A.Im, A.Re }; }
		inline FCplx Scale(FCplx A, double S) { return { A.Re * S, A.Im * S }; }
	}

	/** Every field's spectral coefficient at a mode (with -k's amplitude for the Hermitian pair), time T. */
	static void FieldSpectra(double XiRe, double XiIm, double Amp, double MXiRe, double MXiIm, double MAmp,
		double Kx, double Ky, double K, double Omega, double Coth, double Lambda, double T, FCplx* Out)
	{
		double Phase = std::fmod(Omega * T, 2.0 * kPi);
		const double C = std::cos(Phase), S = std::sin(Phase);
		const FCplx H0 = { XiRe * Amp, XiIm * Amp };
		const FCplx H0m = { MXiRe * MAmp, -MXiIm * MAmp }; // conj(h0(-k))
		// h0(k) e^{-i w t} travels toward +k; its partner conj(h0(-k)) e^{+i w t} keeps the field real.
		const FCplx A = Mul(H0, { C, -S });
		const FCplx B = Mul(H0m, { C, S });
		const FCplx Ht = { A.Re + B.Re, A.Im + B.Im };
		const FCplx G = { A.Re - B.Re, A.Im - B.Im };
		const double Ux = Kx / K, Uy = Ky / K;
		Out[int(ELongField::H)] = Ht;
		Out[int(ELongField::Vz)] = Scale(MulI(G), -Omega);
		Out[int(ELongField::Sx)] = Scale(MulI(Ht), Kx);
		Out[int(ELongField::Sy)] = Scale(MulI(Ht), Ky);
		Out[int(ELongField::U)] = Scale(G, Ux * Omega * Coth);
		Out[int(ELongField::V)] = Scale(G, Uy * Omega * Coth);
		Out[int(ELongField::Ax)] = Scale(MulI(Ht), -Omega * Omega * Coth * Ux);
		Out[int(ELongField::Ay)] = Scale(MulI(Ht), -Omega * Omega * Coth * Uy);
		Out[int(ELongField::Dx)] = Scale(MulI(Ht), -Lambda * Ux);
		Out[int(ELongField::Dy)] = Scale(MulI(Ht), -Lambda * Uy);
		Out[int(ELongField::Jxx)] = Scale(Ht, Lambda * Kx * Ux);
		Out[int(ELongField::Jyy)] = Scale(Ht, Lambda * Ky * Uy);
		Out[int(ELongField::Jxy)] = Scale(Ht, Lambda * Kx * Uy);
	}

	bool FLongWaves::IsRunning(int Cascade) const
	{
		return HasModes(Cascade) && CascadeVariance(Cascade) > 1e-6;
	}

	void FLongWaves::EvaluateInto(int64_t Key, FKeyGrids& Out, const FParallelFor& Parallel) const
	{
		Out.Key = Key;
		const double T = double(Key) / KeyHz;
		const double Lambda = Params.Choppiness;
		int Running[kLongCascades];
		int NumRunning = 0;
		for (int C = 0; C < kLongCascades; ++C)
		{
			Out.bRunning[C] = IsRunning(C);
			if (Out.bRunning[C]) Running[NumRunning++] = C;
			else for (std::vector<float>& F : Out.F[C]) F.clear();
		}
		if (NumRunning == 0) return;

		std::vector<FComplexF> Work[kLongCascades][kPairs];
		auto Fill = [&](int R)
		{
			const int C = Running[R];
			const size_t Count = size_t(Cascades[C].Spec.Size) * Cascades[C].Spec.Size;
			for (std::vector<FComplexF>& W : Work[C]) W.assign(Count, FComplexF());
			FCplx Spec[kLongFields];
			for (const FMode& M : Cascades[C].Modes)
			{
				const FMode& Mir = Cascades[C].Modes[size_t(M.Mirror)];
				FieldSpectra(M.XiRe, M.XiIm, M.Amp, Mir.XiRe, Mir.XiIm, Mir.Amp, M.Kx, M.Ky, M.K, M.Omega, M.Coth, Lambda, T, Spec);
				for (int P = 0; P < kPairs; ++P)
				{
					const FCplx A = Spec[kPairField[P][0]];
					const FCplx B = kPairField[P][1] >= 0 ? Spec[kPairField[P][1]] : FCplx { 0.0, 0.0 };
					// A + i B: after the transform the real part is field A, the imaginary part field B.
					Work[C][P][size_t(M.Index)] = { float(A.Re - B.Im), float(A.Im + B.Re) };
				}
			}
		};
		auto Transform = [&](int Job)
		{
			const int C = Running[Job / kPairs], P = Job % kPairs;
			const size_t Count = size_t(Cascades[C].Spec.Size) * Cascades[C].Spec.Size;
			Cascades[C].Fft->Inverse(Work[C][P].data());
			const int FA = kPairField[P][0], FB = kPairField[P][1];
			std::vector<float>& A = Out.F[C][FA];
			A.resize(Count);
			for (size_t I = 0; I < Count; ++I) A[I] = Work[C][P][I].Re;
			if (FB >= 0)
			{
				std::vector<float>& B = Out.F[C][FB];
				B.resize(Count);
				for (size_t I = 0; I < Count; ++I) B[I] = Work[C][P][I].Im;
			}
		};
		if (Parallel)
		{
			Parallel(NumRunning, Fill);
			Parallel(NumRunning * kPairs, Transform);
		}
		else
		{
			for (int R = 0; R < NumRunning; ++R) Fill(R);
			for (int J = 0; J < NumRunning * kPairs; ++J) Transform(J);
		}
	}

	void FLongWaves::ProduceLocked(int64_t Key, const FParallelFor& Parallel) const
	{
		FSlot& Slot = Ring[size_t(FloorMod(Key, RingKeys))];
		Slot.Key.store(INT64_MIN, std::memory_order_release);
		EvaluateInto(Key, Slot.Grids, Parallel);
		Slot.Key.store(Key, std::memory_order_release);
	}

	void FLongWaves::Produce(int64_t Key, const FParallelFor& Parallel)
	{
		std::lock_guard<std::mutex> Lock(ProduceLock);
		Advance(Key);
		ProduceLocked(Key, Parallel);
	}

	const FLongWaves::FKeyGrids* FLongWaves::FindKey(int64_t Key) const
	{
		const FSlot& Slot = Ring[size_t(FloorMod(Key, RingKeys))];
		return Slot.Key.load(std::memory_order_acquire) == Key ? &Slot.Grids : nullptr;
	}

	const FLongWaves::FKeyGrids& FLongWaves::GetKeyGrids(int64_t Key) const
	{
		if (const FKeyGrids* G = FindKey(Key)) return *G;
		SyncMisses.fetch_add(1, std::memory_order_relaxed);
		ProduceLocked(Key, nullptr);
		return Ring[size_t(FloorMod(Key, RingKeys))].Grids;
	}

	namespace
	{
		/** One cascade's fields, bilinear at a local grid position (in cells), added to Acc with weight W. */
		void AddBilinear(const std::vector<float>* F, int Size, double U, double V, double W, double* Acc)
		{
			const double Fu = std::floor(U), Fv = std::floor(V);
			const double Tu = U - Fu, Tv = V - Fv;
			const int I0 = int(FloorMod(int64_t(Fu), Size)), J0 = int(FloorMod(int64_t(Fv), Size));
			const int I1 = (I0 + 1) % Size, J1 = (J0 + 1) % Size;
			const size_t A = size_t(I0) * Size + J0, B = size_t(I0) * Size + J1, C = size_t(I1) * Size + J0, D = size_t(I1) * Size + J1;
			const double WA = (1.0 - Tu) * (1.0 - Tv) * W, WB = (1.0 - Tu) * Tv * W, WC = Tu * (1.0 - Tv) * W, WD = Tu * Tv * W;
			for (int Field = 0; Field < kLongFields; ++Field)
			{
				const float* P = F[Field].data();
				Acc[Field] += WA * P[A] + WB * P[B] + WC * P[C] + WD * P[D];
			}
		}
	}

	void FLongWaves::Sample(double X, double Y, double T, const float* Ratio, double* Out) const
	{
		const double KeyF = T * KeyHz;
		const int64_t K0 = int64_t(std::floor(KeyF));
		const double W = KeyF - double(K0);
		auto Accumulate = [&](const FKeyGrids& G0, const FKeyGrids& G1)
		{
			for (int I = 0; I < kLongFields; ++I) Out[I] = 0.0;
			for (int C = 0; C < NumCas; ++C)
			{
				const FCascade& Cas = Cascades[C];
				const int Size = Cas.Spec.Size;
				const double Cell = Cas.Spec.Tile / Size;
				const double U = (Cas.Cos * X + Cas.Sin * Y) / Cell, V = (-Cas.Sin * X + Cas.Cos * Y) / Cell;
				const double R = Ratio ? double(Ratio[C]) : 1.0;
				if (G0.bRunning[C] && !G0.F[C][0].empty()) AddBilinear(G0.F[C], Size, U, V, (1.0 - W) * R, Out);
				if (G1.bRunning[C] && !G1.F[C][0].empty()) AddBilinear(G1.F[C], Size, U, V, W * R, Out);
			}
		};
		// Lock-free when both keys are in the ring and nobody wrote over them while they were read.
		const FKeyGrids* A = FindKey(K0);
		const FKeyGrids* B = FindKey(K0 + 1);
		if (A && B)
		{
			Accumulate(*A, *B);
			if (FindKey(K0) == A && FindKey(K0 + 1) == B) return;
		}
		std::lock_guard<std::mutex> Lock(ProduceLock);
		const FKeyGrids& G0 = GetKeyGrids(K0);
		const FKeyGrids& G1 = GetKeyGrids(K0 + 1);
		Accumulate(G0, G1);
	}

	double FLongWaves::CascadeVariance(int Cascade) const
	{
		double V = 0.0;
		for (const FMode& M : Cascades[Cascade].Modes) V += M.Amp * M.Amp;
		return V;
	}

	double FLongWaves::Variance() const
	{
		double V = 0.0;
		for (int C = 0; C < kLongCascades; ++C) V += CascadeVariance(C);
		return V;
	}

	double FLongWaves::FadingVariance() const
	{
		double V = 0.0;
		for (const FCascade& C : Cascades) for (const FMode& M : C.Modes) if (M.Target <= 0.0) V += M.Amp * M.Amp;
		return V;
	}

	void FLongWaves::WavelengthRange(int Cascade, double& OutMin, double& OutMax) const
	{
		OutMin = 1e30; OutMax = 0.0;
		for (const FMode& M : Cascades[Cascade].Modes)
		{
			OutMin = std::min(OutMin, 2.0 * kPi / M.K);
			OutMax = std::max(OutMax, 2.0 * kPi / M.K);
		}
	}

	void FLongWaves::DirectionHistogram(int Bins, double* Out) const
	{
		for (int B = 0; B < Bins; ++B) Out[B] = 0.0;
		const double TravelDir = Params.WindFromRad + kPi;
		for (const FCascade& C : Cascades)
			for (const FMode& M : C.Modes)
			{
				const double Rel = WrapAngle(std::atan2(M.Ky, M.Kx) - TravelDir);
				// Bins centred on the wind (bin Bins / 2 spans -half..+half a bin), so modes straight downwind sit inside one.
				const int B = int(std::floor((Rel + kPi) / (2.0 * kPi) * Bins + 0.5)) % Bins;
				Out[B] += M.Amp * M.Amp;
			}
	}

	double FLongWaves::TargetVariance() const
	{
		double V = 0.0;
		for (const FCascade& C : Cascades) for (const FMode& M : C.Modes) V += M.Target * M.Target;
		return V;
	}

	void FLongWaves::BandVariance(double* Out, int Cascade) const
	{
		for (int B = 0; B < kWaveBands; ++B) Out[B] = 0.0;
		for (int C = 0; C < kLongCascades; ++C)
			if (Cascade < 0 || Cascade == C)
				for (const FMode& M : Cascades[C].Modes)
					if (M.Band >= 0 && M.Band < kWaveBands) Out[M.Band] += M.Amp * M.Amp;
	}

	double FLongWaves::MeanPeriod() const
	{
		double E = 0.0, Ef = 0.0;
		for (const FCascade& C : Cascades)
			for (const FMode& M : C.Modes) { E += M.Amp * M.Amp; Ef += M.Amp * M.Amp * M.Freq; }
		return Ef > 0.0 ? E / Ef : 0.0;
	}

	double FLongWaves::MeanDirection() const
	{
		double X = 0.0, Y = 0.0;
		for (const FCascade& C : Cascades)
			for (const FMode& M : C.Modes) { X += M.Amp * M.Amp * M.Kx / M.K; Y += M.Amp * M.Amp * M.Ky / M.K; }
		return std::atan2(Y, X);
	}

	double FLongWaves::MeanWavenumber(int Cascade) const
	{
		double W = 0.0, Wk = 0.0;
		for (const FMode& M : Cascades[Cascade].Modes)
		{
			const double E = M.Amp * M.Amp * M.Omega * M.Omega;
			W += E;
			Wk += E * M.K;
		}
		return W > 0.0 ? Wk / W : 0.0;
	}

	void FLongWaves::CascadeBands(int Cascade, std::vector<FWaveBand>& Out) const
	{
		constexpr int Bins = 16;
		Out.assign(Bins, FWaveBand());
		const FCascade& Cas = Cascades[Cascade];
		if (Cas.Modes.empty()) return;
		double KLo = 1e30, KHi = 0.0;
		for (const FMode& M : Cas.Modes) { KLo = std::min(KLo, M.K); KHi = std::max(KHi, M.K); }
		const double Step = std::log(KHi / KLo) / Bins + 1e-12;
		double Lw[Bins] = {}, Dx[Bins] = {}, Dy[Bins] = {};
		for (const FMode& M : Cas.Modes)
		{
			const int B = std::min(int(std::log(M.K / KLo) / Step), Bins - 1);
			const double E = M.Amp * M.Amp;
			Out[size_t(B)].Variance += E;
			Lw[B] += E * 2.0 * kPi / M.K;
			Dx[B] += E * M.Kx / M.K;
			Dy[B] += E * M.Ky / M.K;
		}
		for (int B = 0; B < Bins; ++B)
		{
			FWaveBand& W = Out[size_t(B)];
			W.Wavelength = W.Variance > 0.0 ? Lw[B] / W.Variance : 2.0 * kPi / (KLo * std::exp((B + 0.5) * Step));
			W.Direction = std::atan2(Dy[B], Dx[B]);
		}
	}

	void FLongWaves::SeaChannelsAt(const FSeaFetch& Fetch, int Row, int Col, float* Out, double (*OutBand)[kWaveBands]) const
	{
		const double H = Fetch.DepthAt(Row, Col);
		const double U = Params.WindMs;
		const double Ref = Params.FetchMeters;
		const double TravelDir = Params.WindFromRad + kPi;
		const double BinStep = 2.0 * kPi / kSeaBins;
		// Each band's amplitude ratio (squared) at each bin's fetch against the reference: FSeaMap's table, per cell.
		double Ratio2[kWaveBands][kSeaBins];
		bool bBand[kWaveBands] = {};
		for (const FCascade& Cas : Cascades) for (const FMode& M : Cas.Modes) if (M.Band >= 0 && M.Band < kWaveBands) bBand[M.Band] = true;
		for (int B = 0; B < kWaveBands; ++B)
		{
			if (!bBand[B]) continue;
			const double RefAmp = FWaveField::BandAmplitudeFactor(B, U, Ref);
			for (int Bin = 0; Bin < kSeaBins; ++Bin)
			{
				const double F = std::max(Fetch.FetchAt(Row, Col, Bin), 10.0);
				const double R = RefAmp > 1e-12 ? FWaveField::BandAmplitudeFactor(B, U, F) / RefAmp : 1.0;
				Ratio2[B][Bin] = R * R;
			}
		}
		for (int C = 0; C < kLongCascades; ++C)
		{
			double E = 0.0, ER = 0.0, BandE[kWaveBands] = {}, BandER[kWaveBands] = {};
			for (const FMode& M : Cascades[C].Modes)
			{
				const double Em = M.Target * M.Target;
				if (Em <= 0.0) continue;
				double R2 = 1.0;
				if (U >= 0.5 && M.Band >= 0 && M.Band < kWaveBands)
				{
					// The direction its fetch is read along: its own, pulled toward the wind's (FSeaMap's kSeaTowardWind).
					const double Own = std::atan2(M.Ky, M.Kx);
					double A = (TravelDir + (1.0 - kSeaTowardWind) * WrapAngle(Own - TravelDir)) / BinStep;
					A = std::fmod(A, double(kSeaBins));
					if (A < 0.0) A += kSeaBins;
					const int B0 = int(A) % kSeaBins, B1 = (B0 + 1) % kSeaBins;
					const double T = A - std::floor(A);
					R2 = Ratio2[M.Band][B0] * (1.0 - T) + Ratio2[M.Band][B1] * T;
				}
				R2 *= H > 0.0 ? FSeaMap::TmaFactor(M.Omega, H) : 0.0;
				E += Em;
				ER += Em * R2;
				if (M.Band >= 0 && M.Band < kWaveBands) { BandE[M.Band] += Em; BandER[M.Band] += Em * R2; }
			}
			Out[C] = float(E > 0.0 ? std::sqrt(ER / E) : (H > 0.0 ? 1.0 : 0.0));
			if (OutBand)
				for (int B = 0; B < kWaveBands; ++B) OutBand[C][B] = BandE[B] > 0.0 ? BandER[B] / BandE[B] : 0.0;
		}
	}

	void FLongWaves::DirectSum(int Cascade, double X, double Y, double T, double* Out) const
	{
		for (int I = 0; I < kLongFields; ++I) Out[I] = 0.0;
		const FCascade& Cas = Cascades[Cascade];
		FCplx Spec[kLongFields];
		for (const FMode& M : Cas.Modes)
		{
			const FMode& Mir = Cas.Modes[size_t(M.Mirror)];
			FieldSpectra(M.XiRe, M.XiIm, M.Amp, Mir.XiRe, Mir.XiIm, Mir.Amp, M.Kx, M.Ky, M.K, M.Omega, M.Coth, Params.Choppiness, T, Spec);
			const double P = M.Kx * X + M.Ky * Y;
			const double C = std::cos(P), S = std::sin(P);
			for (int F = 0; F < kLongFields; ++F) Out[F] += Spec[F].Re * C - Spec[F].Im * S;
		}
	}

	void FLongWaves::NodePosition(int Cascade, int I, int J, double& OutX, double& OutY) const
	{
		const FCascade& Cas = Cascades[Cascade];
		const double Cell = Cas.Spec.Tile / Cas.Spec.Size;
		const double Lx = I * Cell, Ly = J * Cell;
		OutX = Cas.Cos * Lx - Cas.Sin * Ly;
		OutY = Cas.Sin * Lx + Cas.Cos * Ly;
	}
}
