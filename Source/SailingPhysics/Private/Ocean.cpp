#include "Ocean.h"
#include "SailingMath.h"
#include "LakeTerrain.h"
#include <algorithm>
#include <cmath>
#include <random>

namespace Sailing
{
	namespace
	{
		constexpr double G = 9.81;

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

		/** JONSWAP shape (unnormalized), angular frequency. */
		double Jonswap(double Omega, double OmegaP, double Gamma)
		{
			if (Omega <= 0.0) return 0.0;
			const double Sigma = Omega <= OmegaP ? 0.07 : 0.09;
			const double R = std::exp(-(Omega - OmegaP) * (Omega - OmegaP) / (2.0 * Sigma * Sigma * OmegaP * OmegaP));
			return std::pow(Omega, -5.0) * std::exp(-1.25 * std::pow(OmegaP / Omega, 4.0)) * std::pow(Gamma, R);
		}

		double Bilinear(const std::vector<float>& V, double U, double W)
		{
			const int N = FOcean::N;
			const double FU = std::floor(U), FW = std::floor(W);
			const double TU = U - FU, TW = W - FW;
			const int U0 = ((int(FU) % N) + N) % N, W0 = ((int(FW) % N) + N) % N;
			const int U1 = (U0 + 1) % N, W1 = (W0 + 1) % N;
			return (1.0 - TU) * ((1.0 - TW) * V[U0 * N + W0] + TW * V[U0 * N + W1]) + TU * ((1.0 - TW) * V[U1 * N + W0] + TW * V[U1 * N + W1]);
		}
	}

	constexpr double FOcean::Tile[FOcean::NumCascades];

	FOcean::FOcean()
	{
		for (auto& W : Work) W.resize(size_t(N) * N);
		Configure(FOceanParams());
	}

	void FOcean::Configure(const FOceanParams& InParams)
	{
		Params = InParams;
		for (auto& C : Cache) for (FGrid& Grid : C) Grid.Time = -1e30;
		// Wind sea: fully developed (Pierson-Moskowitz) for the wind, scaled by how developed it is.
		const double U = std::max(Params.WindMs, 0.5);
		const double HsWindTarget = 0.21 * U * U / G * Clamp(Params.WindSeaFraction, 0.0, 1.0);
		const double OmegaPWind = 0.877 * G / U / std::sqrt(std::max(Params.WindSeaFraction, 0.2));
		const double OmegaPSwell = 2.0 * kPi / std::max(Params.SwellTp, 3.0);
		const double WindTo = Params.WindFromRad + kPi, SwellTo = Params.SwellFromRad + kPi;
		// The long cascade carries wavelengths of 30 m and up (four or more grid cells per wave), the short one the rest.
		const double KSplit = 2.0 * kPi / 30.0;
		std::mt19937 Rng(Params.Seed);
		std::uniform_real_distribution<double> Phase(0.0, 2.0 * kPi);
		// Unnormalized energies per mode for each component, then scaled so each has its significant height.
		struct FRaw { int Cascade, Index; double Wind, Swell; };
		std::vector<FRaw> Raw;
		double SumWind = 0.0, SumSwell = 0.0;
		for (int C = 0; C < NumCascades; ++C)
		{
			Modes[C].assign(size_t(N) * N, FMode());
			const double Dk = 2.0 * kPi / Tile[C];
			for (int I = 0; I < N; ++I)
			{
				for (int J = 0; J < N; ++J)
				{
					const int MI = I < N / 2 ? I : I - N, MJ = J < N / 2 ? J : J - N;
					FMode& M = Modes[C][size_t(I) * N + J];
					M.Kx = MI * Dk;
					M.Ky = MJ * Dk;
					M.Phase = Phase(Rng);
					const double K = std::hypot(M.Kx, M.Ky);
					if (K < 1e-9) continue;
					M.Omega = std::sqrt(G * K);
					// Each wavelength belongs to one cascade only.
					if ((C == 0 && K > KSplit) || (C == 1 && K <= KSplit) || (C == 1 && (std::abs(MI) == N / 2 || std::abs(MJ) == N / 2))) continue;
					const double Theta = std::atan2(M.Ky, M.Kx);
					// Energy per unit wavenumber area: S(omega) D(theta) (d omega / d k) / k.
					const double Jac = (0.5 * G / M.Omega) / K * Dk * Dk;
					const double DW = WrapAngle(Theta - WindTo), DS = WrapAngle(Theta - SwellTo);
					const double SpreadWind = std::fabs(DW) < 0.5 * kPi ? std::pow(std::cos(DW), 2.0) : 0.0;
					const double SpreadSwell = std::fabs(DS) < 0.5 * kPi ? std::pow(std::cos(DS), 40.0) : 0.0;
					FRaw R;
					R.Cascade = C;
					R.Index = I * N + J;
					R.Wind = Jonswap(M.Omega, OmegaPWind, 3.3) * SpreadWind * Jac;
					R.Swell = Jonswap(M.Omega, OmegaPSwell, 7.0) * SpreadSwell * Jac;
					SumWind += R.Wind;
					SumSwell += R.Swell;
					Raw.push_back(R);
				}
			}
		}
		// m0 = Hs^2 / 16 = sum a^2 / 2.
		const double ScaleWind = SumWind > 0.0 ? HsWindTarget * HsWindTarget / 16.0 / SumWind : 0.0;
		const double ScaleSwell = SumSwell > 0.0 ? Params.SwellHs * Params.SwellHs / 16.0 / SumSwell : 0.0;
		double M0 = 0.0, M1 = 0.0, M0W = 0.0, DirX = 0.0, DirY = 0.0;
		for (const FRaw& R : Raw)
		{
			FMode& M = Modes[R.Cascade][R.Index];
			const double E = R.Wind * ScaleWind + R.Swell * ScaleSwell; // a^2 / 2
			M.Amplitude = std::sqrt(2.0 * E);
			M0 += E;
			M0W += R.Wind * ScaleWind;
			M1 += E * M.Omega;
			const double K = std::hypot(M.Kx, M.Ky);
			DirX += E * M.Kx / K;
			DirY += E * M.Ky / K;
		}
		// The spectrum in wavelength bins, for added resistance (a boat feels waves near her own length most).
		const int Bins = 16;
		std::vector<double> BV(Bins, 0.0), BX(Bins, 0.0), BY(Bins, 0.0);
		for (const FRaw& R : Raw)
		{
			const FMode& M = Modes[R.Cascade][R.Index];
			const double K = std::hypot(M.Kx, M.Ky);
			const double E = 0.5 * M.Amplitude * M.Amplitude;
			const int B = Clamp(int(std::floor(std::log(2.0 * kPi / K / 2.0) / std::log(250.0) * Bins)), 0, Bins - 1);
			BV[B] += E;
			BX[B] += E * M.Kx / K;
			BY[B] += E * M.Ky / K;
		}
		BandList.clear();
		for (int B = 0; B < Bins; ++B)
		{
			if (BV[B] <= 0.0) continue;
			FWaveBand Band;
			Band.Wavelength = 2.0 * std::pow(250.0, (B + 0.5) / Bins);
			Band.Variance = BV[B];
			Band.Direction = std::atan2(BY[B], BX[B]);
			BandList.push_back(Band);
		}
		HsTotal = 4.0 * std::sqrt(M0);
		HsWind = 4.0 * std::sqrt(M0W);
		Tm01 = M1 > 0.0 ? 2.0 * kPi * M0 / M1 : 0.0;
		MeanDir = std::atan2(DirY, DirX);
	}

	const FOcean::FGrid& FOcean::Evaluate(int C, double T) const
	{
		for (const FGrid& Grid : Cache[C]) if (Grid.Time == T) return Grid;
		FGrid& Grid = Cache[C][CacheNext[C]];
		CacheNext[C] = (CacheNext[C] + 1) % CacheSize;
		Grid.Time = T;
		const size_t Count = size_t(N) * N;
		for (size_t I = 0; I < Count; ++I)
		{
			const FMode& M = Modes[C][I];
			const std::complex<double> F = M.Amplitude * std::polar(1.0, M.Phase - M.Omega * T);
			Work[0][I] = F;
			Work[1][I] = F * std::complex<double>(0.0, -M.Omega);
			Work[2][I] = F * std::complex<double>(0.0, M.Kx);
			Work[3][I] = F * std::complex<double>(0.0, M.Ky);
		}
		std::vector<float>* Out[4] = { &Grid.H, &Grid.Vz, &Grid.Sx, &Grid.Sy };
		for (int K = 0; K < 4; ++K)
		{
			Fft2(Work[K], N);
			Out[K]->resize(Count);
			for (size_t I = 0; I < Count; ++I) (*Out[K])[I] = float(Work[K][I].real());
		}
		return Grid;
	}

	namespace
	{
		/** Grids are evaluated 30 times a second and blended in between (deterministic, a quarter of the work at 120 Hz). */
		constexpr double GridRate = 30.0;
	}

	void FOcean::BuildMask(const FLakeTerrain& Terrain, double Cell)
	{
		Mask = FMask();
		if (!Terrain.IsValid()) return;
		Mask.Cell = Cell;
		Mask.X0 = Terrain.GetOriginX();
		Mask.Y0 = Terrain.GetOriginY();
		Mask.Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1;
		Mask.Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
		Mask.Values.assign(size_t(Mask.Rows) * Mask.Cols, 0.0f);
		// Exposure on a coarser grid (fetch is slow to find and changes slowly), depth on the fine one.
		const int Step = 4;
		const int ER = Mask.Rows / Step + 2, EC = Mask.Cols / Step + 2;
		std::vector<float> Exposure(size_t(ER) * EC, 0.0f);
		for (int R = 0; R < ER; ++R)
			for (int C = 0; C < EC; ++C)
			{
				const double X = Mask.X0 + R * Step * Cell, Y = Mask.Y0 + C * Step * Cell;
				// Open water toward the swell: march until land; leaving the charted area is the open Gulf.
				double Fetch = 20000.0;
				const double DX = std::cos(Params.SwellFromRad), DY = std::sin(Params.SwellFromRad);
				const double XMax = Mask.X0 + Terrain.GetRows() * Terrain.GetCell(), YMax = Mask.Y0 + Terrain.GetCols() * Terrain.GetCell();
				for (double D = 0.0; D < 20000.0; D += 100.0)
				{
					const double PX = X + DX * D, PY = Y + DY * D;
					if (PX < Mask.X0 || PY < Mask.Y0 || PX > XMax || PY > YMax) break;
					if (Terrain.HeightAt(PX, PY) > 0.0) { Fetch = D; break; }
				}
				Exposure[size_t(R) * EC + C] = float(SmoothStep(3000.0, 12000.0, Fetch));
			}
		const double Hs = std::max(HsTotal, 0.1);
		for (int R = 0; R < Mask.Rows; ++R)
			for (int C = 0; C < Mask.Cols; ++C)
			{
				const double FR = double(R) / Step, FC = double(C) / Step;
				const int R0 = std::min(int(FR), ER - 2), C0 = std::min(int(FC), EC - 2);
				const double TR = FR - R0, TC = FC - C0;
				const double E = (1 - TR) * ((1 - TC) * Exposure[size_t(R0) * EC + C0] + TC * Exposure[size_t(R0) * EC + C0 + 1])
					+ TR * ((1 - TC) * Exposure[size_t(R0 + 1) * EC + C0] + TC * Exposure[size_t(R0 + 1) * EC + C0 + 1]);
				const double Depth = Terrain.DepthAt(Mask.X0 + R * Cell, Mask.Y0 + C * Cell);
				const double Limit = Clamp(Depth / (1.6 * Hs), 0.0, 1.0);
				Mask.Values[size_t(R) * Mask.Cols + C] = float(E * Limit);
			}
	}

	double FOcean::MaskAt(double X, double Y) const
	{
		if (Mask.Rows == 0) return 1.0;
		const double FR = (X - Mask.X0) / Mask.Cell, FC = (Y - Mask.Y0) / Mask.Cell;
		if (FR < 0.0 || FC < 0.0 || FR > Mask.Rows - 1 || FC > Mask.Cols - 1) return 1.0; // beyond the charts: open sea
		const int R0 = std::min(int(FR), Mask.Rows - 2), C0 = std::min(int(FC), Mask.Cols - 2);
		const double TR = FR - R0, TC = FC - C0;
		const float* V = Mask.Values.data();
		return (1 - TR) * ((1 - TC) * V[size_t(R0) * Mask.Cols + C0] + TC * V[size_t(R0) * Mask.Cols + C0 + 1])
			+ TR * ((1 - TC) * V[size_t(R0 + 1) * Mask.Cols + C0] + TC * V[size_t(R0 + 1) * Mask.Cols + C0 + 1]);
	}

	double FOcean::Height(double X, double Y, double T) const
	{
		const double M = MaskAt(X, Y);
		if (M <= 0.0) return 0.0;
		const double T0 = std::floor(T * GridRate) / GridRate, W = (T - T0) * GridRate;
		double H = 0.0;
		for (int C = 0; C < NumCascades; ++C)
		{
			const FGrid& A = Evaluate(C, T0);
			const FGrid& B = Evaluate(C, T0 + 1.0 / GridRate);
			const double Cell = Tile[C] / N;
			H += (1.0 - W) * Bilinear(A.H, X / Cell, Y / Cell) + W * Bilinear(B.H, X / Cell, Y / Cell);
		}
		return H * M;
	}

	void FOcean::Sample(double X, double Y, double T, double& OutHeight, double& OutVz, double& OutSlopeX, double& OutSlopeY) const
	{
		OutHeight = OutVz = OutSlopeX = OutSlopeY = 0.0;
		const double M = MaskAt(X, Y);
		if (M <= 0.0) return;
		const double T0 = std::floor(T * GridRate) / GridRate, W = (T - T0) * GridRate;
		for (int C = 0; C < NumCascades; ++C)
		{
			const FGrid& A = Evaluate(C, T0);
			const FGrid& B = Evaluate(C, T0 + 1.0 / GridRate);
			const double Cell = Tile[C] / N, U = X / Cell, V = Y / Cell;
			OutHeight += (1.0 - W) * Bilinear(A.H, U, V) + W * Bilinear(B.H, U, V);
			OutVz += (1.0 - W) * Bilinear(A.Vz, U, V) + W * Bilinear(B.Vz, U, V);
			OutSlopeX += (1.0 - W) * Bilinear(A.Sx, U, V) + W * Bilinear(B.Sx, U, V);
			OutSlopeY += (1.0 - W) * Bilinear(A.Sy, U, V) + W * Bilinear(B.Sy, U, V);
		}
		OutHeight *= M;
		OutVz *= M;
		OutSlopeX *= M;
		OutSlopeY *= M;
	}
}
