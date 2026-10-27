#include "Ocean.h"
#include "PortableRandom.h"
#include "SailingMath.h"
#include "LakeTerrain.h"
#include <algorithm>
#include <cmath>

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
		for (auto& C : CacheTime) for (std::atomic<double>& Time : C) Time.store(-1e30);
		++Generation;
		// Wind sea: fully developed (Pierson-Moskowitz) for the wind, scaled by how developed it is.
		const double U = std::max(Params.WindMs, 0.5);
		const bool bGiven = Params.WindSeaHs > 0.0 && Params.WindSeaTp > 0.0;
		const double HsWindTarget = bGiven ? Params.WindSeaHs : 0.21 * U * U / G * Clamp(Params.WindSeaFraction, 0.0, 1.0);
		const double OmegaPWind = bGiven ? 2.0 * kPi / std::max(Params.WindSeaTp, 2.0) : 0.877 * G / U / std::sqrt(std::max(Params.WindSeaFraction, 0.2));
		const double OmegaPSwell = 2.0 * kPi / std::max(Params.SwellTp, 3.0);
		const double WindTo = Params.WindFromRad + kPi, SwellTo = Params.SwellFromRad + kPi;
		// The long cascade carries wavelengths of 30 m and up (four or more grid cells per wave), the short one the rest.
		const double KSplit = 2.0 * kPi / 30.0;
		FPortableRandom Rng(Params.Seed);
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
					M.Phase = Rng.Uniform(0.0, 2.0 * kPi);
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
		double VelE[NumCascades] = {}, VelEK[NumCascades] = {};
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
			VelE[R.Cascade] += E * M.Omega * M.Omega;
			VelEK[R.Cascade] += E * M.Omega * M.Omega * K;
		}
		for (int C = 0; C < NumCascades; ++C) VelocityK[C] = VelE[C] > 0.0 ? VelEK[C] / VelE[C] : 0.0;
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
		for (int S = 0; S < CacheSize; ++S) if (CacheTime[C][S].load(std::memory_order_acquire) == T) return Cache[C][S];
		std::lock_guard<std::mutex> Lock(CacheLock);
		for (int S = 0; S < CacheSize; ++S) if (CacheTime[C][S].load(std::memory_order_relaxed) == T) return Cache[C][S]; // made meanwhile
		const int Slot = CacheNext[C];
		CacheNext[C] = (Slot + 1) % CacheSize;
		CacheTime[C][Slot].store(-1e30, std::memory_order_relaxed);
		FGrid& Grid = Cache[C][Slot];
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
			// Deep water: the surface's horizontal velocity is omega a along the travel direction, in phase with the height.
			const double K = std::hypot(M.Kx, M.Ky);
			const double Along = K > 1e-9 ? M.Omega / K : 0.0;
			Work[4][I] = F * (Along * M.Kx);
			Work[5][I] = F * (Along * M.Ky);
		}
		std::vector<float>* Out[6] = { &Grid.H, &Grid.Vz, &Grid.Sx, &Grid.Sy, &Grid.U, &Grid.V };
		for (int K = 0; K < 6; ++K)
		{
			Fft2(Work[K], N);
			Out[K]->resize(Count);
			for (size_t I = 0; I < Count; ++I) (*Out[K])[I] = float(Work[K][I].real());
		}
		CacheTime[C][Slot].store(T, std::memory_order_release);
		return Grid;
	}

	namespace
	{
		/** Grids are evaluated 30 times a second and blended in between (deterministic, a quarter of the work at 120 Hz). */
		constexpr double GridRate = 30.0;
	}

	void FOcean::BuildMask(const FLakeTerrain& Terrain, double Cell)
	{
		Mask = MakeMask(Terrain, Params.SwellFromRad, HsTotal, Cell);
		++MaskGeneration;
	}

	FOcean::FMask FOcean::MakeMask(const FLakeTerrain& Terrain, double SwellFromRad, double InHs, double Cell)
	{
		FMask Out;
		if (!Terrain.IsValid()) return Out;
		Out.Cell = Cell;
		Out.X0 = Terrain.GetOriginX();
		Out.Y0 = Terrain.GetOriginY();
		Out.Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1;
		Out.Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
		Out.Values.assign(size_t(Out.Rows) * Out.Cols, 0.0f);
		const int Rows = Out.Rows, Cols = Out.Cols;

		// Land on the mask grid: a cell is land if any terrain node in it is above the water, so a seawall or a jetty a
		// node or two wide still stops the swell.
		std::vector<uint8_t> Land(size_t(Rows) * Cols, 0);
		const int PerCell = std::max(1, int(std::lround(Cell / Terrain.GetCell())));
		for (int R = 0; R < Rows; ++R)
			for (int C = 0; C < Cols; ++C)
			{
				bool bLand = false;
				for (int I = 0; I < PerCell && !bLand; ++I)
					for (int J = 0; J < PerCell && !bLand; ++J)
						bLand = Terrain.NodeHeight(R * PerCell + I - PerCell / 2, C * PerCell + J - PerCell / 2) > 0.0;
				Land[size_t(R) * Cols + C] = bLand ? 1 : 0;
			}

		// Gulf swell: exposure is the share of the swell's directional spread that reaches a point from the open sea in
		// straight lines. Rays run toward where it comes from over +/-45 deg (cos^2 weights: the narrow swell widened by
		// refraction and diffraction at a gap); a ray is open if it leaves the charts over deep water (the Gulf: a bay
		// cut by the chart's edge is shallow) and shut by any land on the way. Behind a barrier every ray is shut; in an
		// inlet only those through the gap are open, a share that falls with the distance from it. The height follows
		// the square root of the energy share.
		constexpr int NumRays = 19;
		constexpr double Spread = 45.0 * kDegToRad, OpenDepth = 4.0;
		double RayDX[NumRays], RayDY[NumRays], RayW[NumRays], WSum = 0.0;
		for (int K = 0; K < NumRays; ++K)
		{
			const double A = -Spread + 2.0 * Spread * K / (NumRays - 1);
			RayDX[K] = std::cos(SwellFromRad + A);
			RayDY[K] = std::sin(SwellFromRad + A);
			RayW[K] = std::cos(0.5 * kPi * A / Spread) * std::cos(0.5 * kPi * A / Spread);
			WSum += RayW[K];
		}
		auto IsLand = [&](int R, int C) { return Land[size_t(R) * Cols + C] != 0; };
		// Exposure on a coarser grid (rays are slow to march and the share changes slowly), depth on the fine one.
		const int Step = 2;
		const int ER = (Rows - 1) / Step + 2, EC = (Cols - 1) / Step + 2;
		std::vector<float> Exposure(size_t(ER) * EC, -1.0f);
		for (int R = 0; R < ER; ++R)
			for (int C = 0; C < EC; ++C)
			{
				const int FR = std::min(R * Step, Rows - 1), FC = std::min(C * Step, Cols - 1);
				if (IsLand(FR, FC)) continue;   // filled from the water around it below
				double Open = 0.0;
				for (int K = 0; K < NumRays; ++K)
				{
					double PR = FR, PC = FC;
					for (;;)
					{
						PR += RayDX[K];
						PC += RayDY[K];
						const int IR = int(std::lround(PR)), IC = int(std::lround(PC));
						if (IR < 0 || IC < 0 || IR >= Rows || IC >= Cols)
						{
							const int LR = std::clamp(IR, 0, Rows - 1), LC = std::clamp(IC, 0, Cols - 1);
							if (Terrain.DepthAt(Out.X0 + LR * Cell, Out.Y0 + LC * Cell) >= OpenDepth) Open += RayW[K];
							break;
						}
						if (IsLand(IR, IC)) break;
					}
				}
				Exposure[size_t(R) * EC + C] = float(std::sqrt(Open / WSum));
			}
		// Coarse nodes on land take the mean of the water nodes beside them, so the sea reaches the beach (the depth limit
		// takes it down there) instead of fading out a coarse cell short of it.
		std::vector<float> Filled = Exposure;
		for (int R = 0; R < ER; ++R)
			for (int C = 0; C < EC; ++C)
			{
				if (Exposure[size_t(R) * EC + C] >= 0.0f) continue;
				double Sum = 0.0;
				int Count = 0;
				for (int DR = -1; DR <= 1; ++DR)
					for (int DC = -1; DC <= 1; ++DC)
					{
						const int NR = R + DR, NC = C + DC;
						if (NR < 0 || NC < 0 || NR >= ER || NC >= EC) continue;
						const float V = Exposure[size_t(NR) * EC + NC];
						if (V >= 0.0f) { Sum += V; ++Count; }
					}
				Filled[size_t(R) * EC + C] = Count > 0 ? float(Sum / Count) : 0.0f;
			}
		const double Hs = std::max(InHs, 0.1);
		for (int R = 0; R < Rows; ++R)
			for (int C = 0; C < Cols; ++C)
			{
				const double FR = double(R) / Step, FC = double(C) / Step;
				const int R0 = std::min(int(FR), ER - 2), C0 = std::min(int(FC), EC - 2);
				const double TR = FR - R0, TC = FC - C0;
				const double E = (1 - TR) * ((1 - TC) * Filled[size_t(R0) * EC + C0] + TC * Filled[size_t(R0) * EC + C0 + 1])
					+ TR * ((1 - TC) * Filled[size_t(R0 + 1) * EC + C0] + TC * Filled[size_t(R0 + 1) * EC + C0 + 1]);
				// Depth limit: waves break at a height of about 0.6 times the depth, so they die away across the shoals.
				const double Depth = Terrain.DepthAt(Out.X0 + R * Cell, Out.Y0 + C * Cell);
				const double Limit = Clamp(Depth / (1.6 * Hs), 0.0, 1.0);
				Out.Values[size_t(R) * Cols + C] = float(E * Limit);
			}
		return Out;
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

	void FOcean::OrbitalVelocity(double X, double Y, double T, double Depth, double& OutU, double& OutV) const
	{
		OutU = OutV = 0.0;
		const double M = MaskAt(X, Y);
		if (M <= 0.0) return;
		const double T0 = std::floor(T * GridRate) / GridRate, W = (T - T0) * GridRate;
		for (int C = 0; C < NumCascades; ++C)
		{
			const FGrid& A = Evaluate(C, T0);
			const FGrid& B = Evaluate(C, T0 + 1.0 / GridRate);
			const double Cell = Tile[C] / N, U = X / Cell, V = Y / Cell;
			const double Decay = M * std::exp(-VelocityK[C] * std::max(Depth, 0.0));
			OutU += Decay * ((1.0 - W) * Bilinear(A.U, U, V) + W * Bilinear(B.U, U, V));
			OutV += Decay * ((1.0 - W) * Bilinear(A.V, U, V) + W * Bilinear(B.V, U, V));
		}
	}
}
