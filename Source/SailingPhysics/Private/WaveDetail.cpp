#include "WaveDetail.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>
#include <random>

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
		std::mt19937 Rng(Params.Seed);
		std::normal_distribution<double> Gauss(0.0, 1.0);
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
					const double Gr = Gauss(Rng), Gi = Gauss(Rng);
					if (Mode.K <= 0.0) continue;
					const double Wavelength = 2.0 * kPi / Mode.K;
					const double F = Mode.Omega / (2.0 * kPi);
					if (Wavelength < S.MinWavelength || Wavelength > S.MaxWavelength || F < Params.SplitHz) continue;
					// Directional spectrum in wavenumber space: E(f) df/dk D(theta) / k, D = cos^2 about the wind (the
					// physics' spreading) with a small share in every direction, as short waves have.
					const double DfDk = 0.5 * std::sqrt(kGravity / Mode.K) / (2.0 * kPi);
					const double Rel = WrapAngle(std::atan2(Mode.Ky, Mode.Kx) - Params.TravelDirRad);
					const double D = 0.9 * (std::fabs(Rel) < 0.5 * kPi ? (2.0 / kPi) * std::cos(Rel) * std::cos(Rel) : 0.0) + 0.1 / (2.0 * kPi);
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
}
