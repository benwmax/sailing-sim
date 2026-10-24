#include "WaveDetail.h"
#include "PortableRandom.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		/** In-place radix-2 complex FFT, inverse sense (positive exponent, no 1/N): x_n = sum_m X_m e^{2 pi i m n / N}. */
		void Fft(std::complex<double>* A, int Count, int Stride)
		{
			for (int I = 1, J = 0; I < Count; ++I)
			{
				int Bit = Count >> 1;
				for (; J & Bit; Bit >>= 1) J ^= Bit;
				J ^= Bit;
				if (I < J) std::swap(A[I * Stride], A[J * Stride]);
			}
			for (int Len = 2; Len <= Count; Len <<= 1)
			{
				const double Ang = 2.0 * kPi / Len;
				const std::complex<double> W(std::cos(Ang), std::sin(Ang));
				for (int I = 0; I < Count; I += Len)
				{
					std::complex<double> Wk(1.0, 0.0);
					for (int K = 0; K < Len / 2; ++K)
					{
						const std::complex<double> U = A[(I + K) * Stride], V = A[(I + K + Len / 2) * Stride] * Wk;
						A[(I + K) * Stride] = U + V;
						A[(I + K + Len / 2) * Stride] = U - V;
						Wk *= W;
					}
				}
			}
		}

		void Fft2(std::vector<std::complex<double>>& A, int Size)
		{
			for (int R = 0; R < Size; ++R) Fft(A.data() + R * Size, Size, 1);
			for (int C = 0; C < Size; ++C) Fft(A.data() + C, Size, Size);
		}

		// The physics' frequency range and JONSWAP shape (Waves.cpp), so the normalization matches FWaveField's.
		constexpr double kMinHz = 0.18, kMaxHz = 2.4;
		double JonswapShape(double F, double Fp)
		{
			if (F <= 0.0) return 0.0;
			const double Sigma = F <= Fp ? 0.07 : 0.09;
			const double R = std::exp(-(F - Fp) * (F - Fp) / (2.0 * Sigma * Sigma * Fp * Fp));
			return std::pow(F, -5.0) * std::exp(-1.25 * std::pow(Fp / F, 4.0)) * std::pow(3.3, R);
		}
	}

	double FWaveDetail::SpectrumAt(double F, double WindMs, double FetchMeters)
	{
		double Fp = 0.0;
		const double Alpha = SpectrumScale(WindMs, FetchMeters, Fp);
		return Alpha > 0.0 ? ShapedSpectrum(F, Fp, Alpha) : 0.0;
	}

	double FWaveDetail::ShapedSpectrum(double F, double Fp, double Alpha)
	{
		// Past the physics' top band the spectrum keeps falling as f^-5 (the saturation range).
		return Alpha * (F <= kMaxHz ? JonswapShape(F, Fp) : JonswapShape(kMaxHz, Fp) * std::pow(kMaxHz / F, 5.0));
	}

	double FWaveDetail::SpectrumScale(double WindMs, double FetchMeters, double& OutFp)
	{
		const double Hs = FWaveField::TargetSignificantHeight(WindMs, FetchMeters);
		OutFp = 0.0;
		if (Hs <= 0.0) return 0.0;
		const double Fp = 1.0 / FWaveField::TargetPeakPeriod(WindMs, FetchMeters);
		OutFp = Fp;
		// Scale the shape so its variance over the physics' range is (Hs/4)^2, as FWaveField scales its bands.
		double Integral = 0.0;
		constexpr int Steps = 2000;
		const double Ratio = std::pow(kMaxHz / kMinHz, 1.0 / Steps);
		double F0 = kMinHz;
		for (int I = 0; I < Steps; ++I)
		{
			const double F1 = F0 * Ratio;
			Integral += JonswapShape(std::sqrt(F0 * F1), Fp) * (F1 - F0);
			F0 = F1;
		}
		return Integral > 0.0 ? (Hs / 4.0) * (Hs / 4.0) / Integral : 0.0;
	}

	void FWaveDetail::Configure(const FWaveDetailParams& InParams, const std::vector<FCascadeSpec>& Specs)
	{
		Params = InParams;
		Cascades.clear();
		FPortableRandom Rng(Params.Seed);
		double Fp = 0.0;
		const double Alpha = SpectrumScale(Params.WindMs, Params.FetchMeters, Fp);
		for (const FCascadeSpec& S : Specs)
		{
			FCascade C;
			C.Spec = S;
			const int N = S.N;
			const double Dk = 2.0 * kPi / S.Tile;
			C.Modes.resize(size_t(N) * N);
			std::vector<std::complex<double>> H0(size_t(N) * N);
			for (int M = 0; M < N; ++M)
			{
				for (int Q = 0; Q < N; ++Q)
				{
					const int Mx = M < N / 2 ? M : M - N, My = Q < N / 2 ? Q : Q - N;
					FMode& Mode = C.Modes[size_t(M) * N + Q];
					Mode.Kx = Mx * Dk;
					Mode.Ky = My * Dk;
					Mode.K = std::sqrt(Mode.Kx * Mode.Kx + Mode.Ky * Mode.Ky);
					Mode.Omega = std::sqrt(kGravity * Mode.K);
					const double Gr = Rng.Gaussian(), Gi = Rng.Gaussian();
					if (Mode.K <= 0.0) continue;
					const double Wavelength = 2.0 * kPi / Mode.K;
					const double F = Mode.Omega / (2.0 * kPi);
					if (Wavelength < S.MinWavelength || Wavelength > S.MaxWavelength || F < Params.SplitHz) continue;
					// Directional spectrum in wavenumber space: E(f) df/dk D(theta) / k, with a small share in every
					// direction, as short waves have. docs/short-wave-spreading/: D is Donelan, Hamilton and Hui's (1985)
					// measured spreading, 0.5 beta sech^2(beta theta), narrowest at the peak (beta 2.4: about 42 deg at half
					// height) and widening away from it, with Banner's (1990) form past 1.6 fp. It was cos^2 (90 deg at half
					// height) at every frequency: at low wind and short fetch the peak sits inside the detail's range, and the
					// wavelets that break a calm lake's reflection into long, regular streaks came out short-crested.
					const double DfDk = 0.5 * std::sqrt(kGravity / Mode.K) / (2.0 * kPi);
					const double Rel = WrapAngle(std::atan2(Mode.Ky, Mode.Kx) - Params.TravelDirRad);
					const double D = 0.9 * FWaveField::DirectionalSpreading(F, Fp, Rel) + 0.1 / (2.0 * kPi);
					const double Psi = (Alpha > 0.0 ? ShapedSpectrum(F, Fp, Alpha) : 0.0) * DfDk * D / Mode.K;
					const double P = Psi * Dk * Dk * Params.Development * Params.Development;
					C.Variance += P;
					H0[size_t(M) * N + Q] = std::complex<double>(Gr, Gi) * std::sqrt(P / 4.0);
				}
			}
			for (int M = 0; M < N; ++M)
			{
				for (int Q = 0; Q < N; ++Q)
				{
					FMode& Mode = C.Modes[size_t(M) * N + Q];
					Mode.H0 = H0[size_t(M) * N + Q];
					Mode.H0MinusConj = std::conj(H0[size_t((N - M) % N) * N + (N - Q) % N]);
				}
			}
			Cascades.push_back(std::move(C));
		}
	}

	void FWaveDetail::Evaluate(int CascadeIndex, double T, FGrid& Out, double Scale) const
	{
		const FCascade& C = Cascades[CascadeIndex];
		const int N = C.Spec.N;
		const size_t NN = size_t(N) * N;
		// Four transforms, two real fields each: (H, Dx), (Dy, Sx), (Sy, Jxx), (Jyy, Jxy).
		std::vector<std::complex<double>> A(NN), B(NN), Cc(NN), D(NN);
		const std::complex<double> I(0.0, 1.0);
		for (size_t Idx = 0; Idx < NN; ++Idx)
		{
			const FMode& M = C.Modes[Idx];
			if (M.K <= 0.0) { A[Idx] = B[Idx] = Cc[Idx] = D[Idx] = 0.0; continue; }
			const std::complex<double> E(std::cos(M.Omega * T), std::sin(M.Omega * T));
			const std::complex<double> H = Scale * (M.H0 * E + M.H0MinusConj * std::conj(E));
			const double Ux = M.Kx / M.K, Uy = M.Ky / M.K;
			const std::complex<double> HDx = -I * Ux * H, HDy = -I * Uy * H, HSx = I * M.Kx * H, HSy = I * M.Ky * H;
			const std::complex<double> HJxx = M.Kx * Ux * H, HJyy = M.Ky * Uy * H, HJxy = M.Kx * Uy * H;
			A[Idx] = H + I * HDx;
			B[Idx] = HDy + I * HSx;
			Cc[Idx] = HSy + I * HJxx;
			D[Idx] = HJyy + I * HJxy;
		}
		Fft2(A, N);
		Fft2(B, N);
		Fft2(Cc, N);
		Fft2(D, N);
		Out.N = N;
		Out.Tile = C.Spec.Tile;
		Out.Time = T;
		for (std::vector<float>* V : { &Out.H, &Out.Dx, &Out.Dy, &Out.Sx, &Out.Sy, &Out.J }) V->resize(NN);
		const double L = Params.Choppiness;
		for (size_t Idx = 0; Idx < NN; ++Idx)
		{
			Out.H[Idx] = float(A[Idx].real());
			// Vertices move toward the crests (minus Tessendorf's D), so the Jacobian drops below 1 where a crest folds.
			Out.Dx[Idx] = float(-L * A[Idx].imag());
			Out.Dy[Idx] = float(-L * B[Idx].real());
			Out.Sx[Idx] = float(B[Idx].imag());
			Out.Sy[Idx] = float(Cc[Idx].real());
			const double Jxx = 1.0 - L * Cc[Idx].imag(), Jyy = 1.0 - L * D[Idx].real(), Jxy = -L * D[Idx].imag();
			Out.J[Idx] = float(Jxx * Jyy - Jxy * Jxy);
		}
		// W8: the whitecaps' Jacobian, from the displacement box-blurred (periodic, separable) over CapBlurMeters either
		// way, by central differences. The box's radius is fractional (its end taps weighted by the fraction), so the caps
		// grow smoothly with the wind.
		const double Rm = CapBlurMeters(Params.WindMs) / (C.Spec.Tile / N);
		const int Rb = int(std::floor(Rm));
		const float Edge = float(Rm - Rb);
		auto Blur = [N, Rb, Edge](const std::vector<float>& V)
		{
			std::vector<float> A(V.size()), B(V.size());
			const float Norm = 1.f / (float(2 * Rb + 1) + 2.f * Edge);
			for (int R = 0; R < N; ++R)
				for (int Col = 0; Col < N; ++Col)
				{
					float Sum = 0.f;
					for (int K = -Rb; K <= Rb; ++K) Sum += V[size_t(R) * N + (Col + K + N) % N];
					Sum += Edge * (V[size_t(R) * N + (Col - Rb - 1 + N) % N] + V[size_t(R) * N + (Col + Rb + 1) % N]);
					A[size_t(R) * N + Col] = Sum * Norm;
				}
			for (int R = 0; R < N; ++R)
				for (int Col = 0; Col < N; ++Col)
				{
					float Sum = 0.f;
					for (int K = -Rb; K <= Rb; ++K) Sum += A[size_t((R + K + N) % N) * N + Col];
					Sum += Edge * (A[size_t((R - Rb - 1 + N) % N) * N + Col] + A[size_t((R + Rb + 1) % N) * N + Col]);
					B[size_t(R) * N + Col] = Sum * Norm;
				}
			return B;
		};
		const std::vector<float> Bx = Blur(Out.Dx), By = Blur(Out.Dy);
		Out.JCap.resize(NN);
		const double H2 = 2.0 * C.Spec.Tile / N;
		auto At = [N](const std::vector<float>& V, int Row, int Col) { return double(V[size_t((Row + N) % N) * N + (Col + N) % N]); };
		for (int R = 0; R < N; ++R)
			for (int Cl = 0; Cl < N; ++Cl)
			{
				const double Xx = (At(Bx, R + 1, Cl) - At(Bx, R - 1, Cl)) / H2, Xy = (At(Bx, R, Cl + 1) - At(Bx, R, Cl - 1)) / H2;
				const double Yx = (At(By, R + 1, Cl) - At(By, R - 1, Cl)) / H2, Yy = (At(By, R, Cl + 1) - At(By, R, Cl - 1)) / H2;
				Out.JCap[size_t(R) * N + Cl] = float((1.0 + Xx) * (1.0 + Yy) - Xy * Yx);
			}
	}

	double FWaveDetail::CapBlurMeters(double WindMs)
	{
		const double At20 = CapBlurTexels * ChopCascade().Tile / ChopCascade().N;
		return Clamp(At20 * std::pow(std::max(WindMs, 0.0) / (20.0 * 1852.0 / 3600.0), 3.41 / 4.0), 0.18, At20);
	}

	void FWaveDetail::Sample(const FGrid& G, double X, double Y, double& OutH, double& OutDx, double& OutDy, double& OutJ)
	{
		const int N = G.N;
		const double Cell = G.Tile / N;
		const double U = X / Cell, W = Y / Cell;
		const double FU = std::floor(U), FW = std::floor(W);
		const double TU = U - FU, TW = W - FW;
		const int U0 = ((int(FU) % N) + N) % N, W0 = ((int(FW) % N) + N) % N, U1 = (U0 + 1) % N, W1 = (W0 + 1) % N;
		auto Bi = [&](const std::vector<float>& V)
		{
			return (1.0 - TU) * ((1.0 - TW) * V[U0 * N + W0] + TW * V[U0 * N + W1]) + TU * ((1.0 - TW) * V[U1 * N + W0] + TW * V[U1 * N + W1]);
		};
		OutH = Bi(G.H);
		OutDx = Bi(G.Dx);
		OutDy = Bi(G.Dy);
		OutJ = Bi(G.J);
	}

	double FWaveDetail::SampleCapJ(const FGrid& G, double X, double Y)
	{
		const int N = G.N;
		const double Cell = G.Tile / N;
		const double U = X / Cell, W = Y / Cell;
		const double FU = std::floor(U), FW = std::floor(W);
		const double TU = U - FU, TW = W - FW;
		const int U0 = ((int(FU) % N) + N) % N, W0 = ((int(FW) % N) + N) % N, U1 = (U0 + 1) % N, W1 = (W0 + 1) % N;
		const std::vector<float>& V = G.JCap;
		return (1.0 - TU) * ((1.0 - TW) * V[U0 * N + W0] + TW * V[U0 * N + W1]) + TU * ((1.0 - TW) * V[U1 * N + W0] + TW * V[U1 * N + W1]);
	}

	double FWaveDetail::LongJacobian(const FWaveComponent* Components, int Count, double OmegaMax, double Chop, double X, double Y, double T,
		double Spacing, double Fade)
	{
		double Jxx = 1.0, Jyy = 1.0, Jxy = 0.0;
		for (int I = 0; I < Count; ++I)
		{
			const FWaveComponent& W = Components[I];
			if (W.Amplitude <= 1e-5 || W.Omega >= OmegaMax) continue;
			const double K = std::sqrt(W.Kx * W.Kx + W.Ky * W.Ky);
			// make_materials.py long_wave_terms: saturate(2 pi / (k spacing) / 4 - 1).
			const double Keep = Spacing > 0.0 ? Clamp(6.2832 / (K * Spacing) / 4.0 - 1.0, 0.0, 1.0) : 1.0;
			const double S = std::sin(W.Kx * X + W.Ky * Y - W.Omega * T + W.Phase) * Chop * W.Amplitude * Keep * Fade / K;
			Jxx -= W.Kx * W.Kx * S;
			Jyy -= W.Ky * W.Ky * S;
			Jxy -= W.Kx * W.Ky * S;
		}
		return Jxx * Jyy - Jxy * Jxy;
	}

	FWaveDetail::FLongJacobians::FLongJacobians(const FWaveComponent* Components, int Count, double OmegaMax, double Chop, const double* Spacings,
		const double* Fades, int InPairs)
	{
		Pairs = std::min(InPairs, MaxPairs);
		for (int I = 0; I < Count; ++I)
		{
			const FWaveComponent& W = Components[I];
			if (W.Amplitude <= 1e-5 || W.Omega >= OmegaMax) continue;
			const double K = std::sqrt(W.Kx * W.Kx + W.Ky * W.Ky);
			FTerm T{ W.Kx, W.Ky, W.Omega, W.Phase, {} };
			for (int P = 0; P < Pairs; ++P)
			{
				const double Keep = Spacings[P] > 0.0 ? Clamp(6.2832 / (K * Spacings[P]) / 4.0 - 1.0, 0.0, 1.0) : 1.0;
				T.Coef[P] = Chop * W.Amplitude * Keep * Fades[P] / K;
			}
			Terms.push_back(T);
		}
	}

	void FWaveDetail::FLongJacobians::Evaluate(double X, double Y, double T, double* OutJ) const
	{
		double Jxx[MaxPairs], Jyy[MaxPairs], Jxy[MaxPairs];
		for (int P = 0; P < Pairs; ++P) { Jxx[P] = 1.0; Jyy[P] = 1.0; Jxy[P] = 0.0; }
		for (const FTerm& W : Terms)
		{
			const double Sin = std::sin(W.Kx * X + W.Ky * Y - W.Omega * T + W.Phase);
			const double Xx = W.Kx * W.Kx * Sin, Yy = W.Ky * W.Ky * Sin, Xy = W.Kx * W.Ky * Sin;
			for (int P = 0; P < Pairs; ++P)
			{
				Jxx[P] -= Xx * W.Coef[P];
				Jyy[P] -= Yy * W.Coef[P];
				Jxy[P] -= Xy * W.Coef[P];
			}
		}
		for (int P = 0; P < Pairs; ++P) OutJ[P] = Jxx[P] * Jyy[P] - Jxy[P] * Jxy[P];
	}

	/** The standard normal's quantile for a lower-tail share P under 0.024 (Acklam's rational approximation, 1e-9). */
	static double NormalTailQuantile(double P)
	{
		const double Q = std::sqrt(-2.0 * std::log(std::max(P, 1e-300)));
		return (((((-7.784894002430293e-03 * Q - 3.223964580411365e-01) * Q - 2.400758277161838e+00) * Q - 2.549732539343734e+00) * Q
			+ 4.374664141464968e+00) * Q + 2.938163982698783e+00)
			/ ((((7.784695709041462e-03 * Q + 3.224671290700398e-01) * Q + 2.445134137142996e+00) * Q + 3.754408661907416e+00) * Q + 1.0);
	}

	void FWaveDetail::CapThreshold(std::vector<float> Samples, double Target, double& OutThreshold, double& OutSlope)
	{
		if (Samples.empty() || Target <= 0.0) { OutThreshold = 0.0; OutSlope = 0.02; return; }
		const size_t N = Samples.size();
		auto Quantile = [&](double Q)
		{
			const size_t K = std::min(N - 1, size_t(std::max(Q, 0.0) * double(N)));
			std::nth_element(Samples.begin(), Samples.begin() + K, Samples.end());
			return double(Samples[K]);
		};
		// Under eight samples the quantile is the lowest few samples, which floors the cover near 1/N (the light-air
		// flecks): extrapolate down the tail, linear in the normal quantile (the fold's tail falls faster than an
		// exponential: an e-fold slope fitted above the floor capped a fifth of the target).
		const double Floor = 8.0 / double(N);
		if (Target < Floor && Floor < 0.008)
		{
			const double Up = 2.718281828 * Floor;
			const double At = Quantile(Floor), AtUp = Quantile(Up);
			// docs/calm-water/: a flat tail (calm water: the drawn fold scale is zero, every sample 1) has nothing to
			// extrapolate along, and the threshold came out at the samples themselves (1.0), so M_WaterV4's fold ramp capped
			// any pixel whose Jacobian dipped under 1, and its residue ramp (to 0.12 over the threshold) every pixel. The
			// shader's own Jacobian still folds a little in the fine ripples, which these samples don't see. Nothing breaks on
			// calm water: -1, which no drawn Jacobian reaches.
			if (AtUp - At < 0.002)
			{
				OutSlope = 0.002;
				OutThreshold = -1.0;
				return;
			}
			OutSlope = std::max(AtUp - At, 0.002);
			const double Zt = NormalTailQuantile(Target), Zf = NormalTailQuantile(Floor), Zu = NormalTailQuantile(Up);
			OutThreshold = At - std::max(AtUp - At, 0.0) * (Zf - Zt) / std::max(Zu - Zf, 1e-6);
			return;
		}
		OutThreshold = Quantile(Target);
		// The shift per e-fold of cover under the target (at least eight samples down the tail).
		const double LoShare = std::max(Target / 2.718281828, std::min(Floor, 0.5 * Target));
		const double Lo = Quantile(LoShare);
		OutSlope = std::max(OutThreshold - Lo, 0.002) / std::log(Target / LoShare);
	}
}
