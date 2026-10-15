#include "SeaState.h"
#include "LakeTerrain.h"
#include "Waves.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	void FSeaFetch::March(const std::vector<uint8_t>& Water, int R, int C, double MarchCell, double FromRadians, double Max, std::vector<float>& Out)
	{
		// Semi-Lagrangian: the fetch of a water cell is the fetch at the point one row (or column) upwind, interpolated
		// between the two cells either side of it, plus the distance to it. Rows run north (+X), columns east (+Y); the
		// grid's edge counts as land, as FLakeTerrain::HeightAt's far outside does.
		Out.assign(size_t(R) * C, 0.f);
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		const bool bAlongRows = std::fabs(DX) >= std::fabs(DY);
		// Unit step along the major axis toward the wind; the minor axis moves by Slope cells; the distance is Step.
		const double Major = bAlongRows ? DX : DY, Minor = bAlongRows ? DY : DX;
		const int Dir = Major > 0.0 ? 1 : -1;
		const double Slope = Minor / std::fabs(Major);
		const double Step = MarchCell / std::fabs(Major);
		const int NMajor = bAlongRows ? R : C, NMinor = bAlongRows ? C : R;
		auto Index = [&](int A, int B) { return bAlongRows ? size_t(A) * C + B : size_t(B) * C + A; };
		// Upwind lines first.
		for (int K = 0; K < NMajor; ++K)
		{
			const int A = Dir > 0 ? NMajor - 1 - K : K;
			const int Up = A + Dir;
			for (int B = 0; B < NMinor; ++B)
			{
				const size_t I = Index(A, B);
				if (!Water[I]) continue;
				double Upwind = 0.0;
				if (Up >= 0 && Up < NMajor)
				{
					const double M = B + Slope;
					const int M0 = int(std::floor(M));
					const double T = M - M0;
					const double F0 = M0 >= 0 && M0 < NMinor ? Out[Index(Up, M0)] : 0.0;
					const double F1 = M0 + 1 >= 0 && M0 + 1 < NMinor ? Out[Index(Up, M0 + 1)] : 0.0;
					// A land cell upwind ends the fetch: interpolating toward it shortens the fetch by its share.
					Upwind = F0 * (1.0 - T) + F1 * T;
				}
				Out[I] = float(std::min(Upwind + Step, Max));
			}
		}
	}

	void FSeaFetch::Build(const FLakeTerrain& Terrain, double MapCell, double InMax)
	{
		MaxFetch = InMax;
		const double SizeX = (Terrain.GetRows() - 1) * Terrain.GetCell(), SizeY = (Terrain.GetCols() - 1) * Terrain.GetCell();
		if (MapCell <= 0.0)
		{
			MapCell = 50.0;
			while (std::max(SizeX, SizeY) / MapCell > 600.0) MapCell *= 2.0;
		}
		Cell = MapCell;
		OriginX = Terrain.GetOriginX() + 0.5 * Cell;
		OriginY = Terrain.GetOriginY() + 0.5 * Cell;
		Rows = std::max(1, int(SizeX / Cell));
		Cols = std::max(1, int(SizeY / Cell));

		// The march runs at half the map's cell: map cell (r, c) is the centre of march cells 2r..2r+1, 2c..2c+1.
		const double MarchCell = 0.5 * Cell;
		const int MR = 2 * Rows, MC = 2 * Cols;
		const double MX0 = Terrain.GetOriginX() + 0.5 * MarchCell, MY0 = Terrain.GetOriginY() + 0.5 * MarchCell;
		std::vector<uint8_t> Water(size_t(MR) * MC);
		std::vector<float> MarchDepth(size_t(MR) * MC);
		for (int R = 0; R < MR; ++R)
		{
			for (int C = 0; C < MC; ++C)
			{
				const double D = Terrain.DepthAt(MX0 + R * MarchCell, MY0 + C * MarchCell);
				Water[size_t(R) * MC + C] = D > 0.0 ? 1 : 0;
				MarchDepth[size_t(R) * MC + C] = float(D);
			}
		}
		Depth.assign(size_t(Rows) * Cols, 0.f);
		std::vector<float> Wet;
		for (int R = 0; R < Rows; ++R)
		{
			for (int C = 0; C < Cols; ++C)
			{
				double Sum = 0.0;
				for (int Q = 0; Q < 4; ++Q) Sum += MarchDepth[size_t(2 * R + Q / 2) * MC + 2 * C + Q % 2];
				Depth[size_t(R) * Cols + C] = float(Sum / 4.0);
				if (Sum > 0.0) Wet.push_back(float(Sum / 4.0));
			}
		}
		if (!Wet.empty())
		{
			std::nth_element(Wet.begin(), Wet.begin() + Wet.size() / 2, Wet.end());
			MedianDepth = Wet[Wet.size() / 2];
		}

		// 32 directions every 11.25 deg; each bin's Saville mean takes the nine within 45 deg of its own upwind direction:
		// sum(F cos^2 a) / sum(cos a), as FLakeTerrain::EffectiveFetch.
		constexpr int Rays = 2 * kSeaBins;
		double SavilleNorm = 0.0;
		for (int K = -4; K <= 4; ++K) SavilleNorm += std::cos(K * kPi / 16.0);
		Fetch.assign(size_t(Rows) * Cols * kSeaBins, 0.f);
		std::vector<float> Ray;
		for (int J = 0; J < Rays; ++J)
		{
			// Ray J looks toward FromRadians = J x 11.25 deg (where the wind and waves come from).
			const double From = J * 2.0 * kPi / Rays;
			March(Water, MR, MC, MarchCell, From, MaxFetch, Ray);
			for (int B = 0; B < kSeaBins; ++B)
			{
				// Bin B: waves travelling toward B x 22.5 deg come from B x 22.5 + 180 deg, ray 2B + 16.
				int K = J - (2 * B + Rays / 2);
				K = ((K % Rays) + Rays + Rays / 2) % Rays - Rays / 2;
				if (K < -4 || K > 4) continue;
				const double W = std::pow(std::cos(K * kPi / 16.0), 2.0) / SavilleNorm;
				for (int R = 0; R < Rows; ++R)
				{
					for (int C = 0; C < Cols; ++C)
					{
						// The map cell's centre is the corner of its four march cells: their mean.
						double F = 0.0;
						for (int Q = 0; Q < 4; ++Q) F += Ray[size_t(2 * R + Q / 2) * MC + 2 * C + Q % 2];
						Fetch[(size_t(R) * Cols + C) * kSeaBins + B] += float(W * F / 4.0);
					}
				}
			}
		}
		Soften(SoftenPasses);
	}

	void FSeaFetch::Soften(int Passes)
	{
		// A 3 x 3 mean over the water cells, per bin: the march's shadows behind points have knife edges (each of the 32
		// rays casts its own), where real waves spread round a point (diffraction, the spectrum's spread of directions).
		std::vector<float> Next(Fetch.size());
		for (int P = 0; P < Passes; ++P)
		{
			for (int R = 0; R < Rows; ++R)
			{
				for (int C = 0; C < Cols; ++C)
				{
					for (int B = 0; B < kSeaBins; ++B)
					{
						const size_t I = (size_t(R) * Cols + C) * kSeaBins + B;
						if (Depth[size_t(R) * Cols + C] <= 0.f) { Next[I] = Fetch[I]; continue; }
						double Sum = 0.0;
						int N = 0;
						for (int DR = -1; DR <= 1; ++DR)
						{
							for (int DC = -1; DC <= 1; ++DC)
							{
								const int RR = R + DR, CC = C + DC;
								if (RR < 0 || CC < 0 || RR >= Rows || CC >= Cols || Depth[size_t(RR) * Cols + CC] <= 0.f) continue;
								Sum += Fetch[(size_t(RR) * Cols + CC) * kSeaBins + B];
								++N;
							}
						}
						Next[I] = float(Sum / N);
					}
				}
			}
			Fetch.swap(Next);
		}
	}

	double FSeaFetch::FetchToward(double X, double Y, double TravelRadians) const
	{
		if (!IsValid()) return MaxFetch;
		const int R = Clamp(int(std::lround((X - OriginX) / Cell)), 0, Rows - 1);
		const int C = Clamp(int(std::lround((Y - OriginY) / Cell)), 0, Cols - 1);
		double A = std::fmod(TravelRadians / (2.0 * kPi / kSeaBins), double(kSeaBins));
		if (A < 0.0) A += kSeaBins;
		const int B0 = int(A) % kSeaBins, B1 = (B0 + 1) % kSeaBins;
		const double T = A - std::floor(A);
		return FetchAt(R, C, B0) * (1.0 - T) + FetchAt(R, C, B1) * T;
	}

	double FSeaMap::TmaFactor(double Omega, double H)
	{
		// Kitaigorodskii, Krasitskii and Zaslavskii (1975), as in the TMA spectrum (Bouws et al. 1985): the depth factor
		// in omega_h = omega sqrt(h / g), 0.5 omega_h^2 up to 1, 1 - 0.5 (2 - omega_h)^2 up to 2, then 1 (deep).
		if (H <= 0.0) return 0.0;
		const double Wh = Omega * std::sqrt(H / kGravity);
		if (Wh <= 1.0) return 0.5 * Wh * Wh;
		if (Wh < 2.0) return 1.0 - 0.5 * (2.0 - Wh) * (2.0 - Wh);
		return 1.0;
	}

	void FSeaMap::Build(const FSeaFetch& Fetch, const FWaveComponent* Components, double InWindMs, double InTravel, bool bShallow, double TowardWind,
		const std::function<double(double, double)>& OpenSea)
	{
		Rows = Fetch.GetRows(); Cols = Fetch.GetCols(); Cell = Fetch.GetCell();
		OriginX = Fetch.GetOriginX(); OriginY = Fetch.GetOriginY();
		WindMs = InWindMs; TravelRadians = InTravel; ReferenceFetch = Fetch.GetMaxFetch();
		Values.assign(size_t(Rows) * Cols * kSeaChannels, 1.f);
		if (Rows == 0) return;

		// Each component's band (the field lays them out band by band), its direction between two bins, and the band
		// amplitude factor of the growth laws' spectrum against log fetch (10 m to the reference), so a cell costs a
		// table lookup per component.
		constexpr int NF = 64;
		const double LogF0 = std::log(10.0), LogF1 = std::log(ReferenceFetch);
		double Table[kWaveBands][NF];
		double Reference[kWaveBands];
		for (int B = 0; B < kWaveBands; ++B)
		{
			Reference[B] = FWaveField::BandAmplitudeFactor(B, WindMs, ReferenceFetch);
			for (int I = 0; I < NF; ++I)
			{
				Table[B][I] = FWaveField::BandAmplitudeFactor(B, WindMs, std::exp(LogF0 + (LogF1 - LogF0) * I / (NF - 1)));
			}
		}
		struct FComp { int Band, Bin0, Bin1; double T, Omega, Energy; };
		FComp Comp[kWaveComponents];
		double ShortEnergy = 0.0;
		for (int I = 0; I < kWaveComponents; ++I)
		{
			const FWaveComponent& W = Components[I];
			FComp& P = Comp[I];
			P.Band = I / kWaveDirectionsPerBand;
			// The direction its fetch is read along: its own, pulled toward the wind's by TowardWind (see Build's comment).
			const double Own = std::atan2(W.Ky, W.Kx);
			double A = (TravelRadians + (1.0 - TowardWind) * WrapAngle(Own - TravelRadians)) / (2.0 * kPi / kSeaBins);
			A = std::fmod(A, double(kSeaBins));
			if (A < 0.0) A += kSeaBins;
			P.Bin0 = int(A) % kSeaBins; P.Bin1 = (P.Bin0 + 1) % kSeaBins; P.T = A - std::floor(A);
			P.Omega = W.Omega;
			// The short waves' weights: their share of the reference sea now (cos^2 about the travel direction).
			const double Rel = WrapAngle(std::atan2(W.Ky, W.Kx) - TravelRadians);
			const double Spread = std::fabs(Rel) < kPi * 0.5 ? std::pow(std::cos(Rel), 2.0) : 0.0;
			P.Energy = I >= kSeaLongComponents ? Reference[P.Band] * Reference[P.Band] * Spread : 0.0;
			ShortEnergy += P.Energy;
		}
		const bool bCalm = WindMs < 0.5;
		for (int R = 0; R < Rows; ++R)
		{
			for (int C = 0; C < Cols; ++C)
			{
				float* Out = &Values[(size_t(R) * Cols + C) * kSeaChannels];
				const double H = Fetch.DepthAt(R, C);
				const bool bOpen = OpenSea && OpenSea(OriginX + R * Cell, OriginY + C * Cell) > 0.5;
				double Short = 0.0;
				for (int I = 0; I < kWaveComponents; ++I)
				{
					const FComp& P = Comp[I];
					if (I >= kSeaLongComponents && P.Energy <= 0.0) continue;
					double Ratio = 1.0;
					if (!bCalm)
					{
						const double F = bOpen ? 200.0 : std::max(Fetch.FetchAt(R, C, P.Bin0) * (1.0 - P.T) + Fetch.FetchAt(R, C, P.Bin1) * P.T, 10.0);
						const double X = Clamp((std::log(F) - LogF0) / (LogF1 - LogF0) * (NF - 1), 0.0, NF - 1.0);
						const int X0 = std::min(int(X), NF - 2);
						const double Amp = Table[P.Band][X0] + (Table[P.Band][X0 + 1] - Table[P.Band][X0]) * (X - X0);
						Ratio = Reference[P.Band] > 1e-12 ? Amp / Reference[P.Band] : 1.0;
					}
					// On land there is no sea; in shallow water the long waves lose energy (TMA).
					Ratio *= H > 0.0 ? (bShallow ? std::sqrt(TmaFactor(P.Omega, H)) : 1.0) : 0.0;
					if (I < kSeaLongComponents) Out[I] = float(Ratio);
					else Short += P.Energy * Ratio * Ratio;
				}
				Out[kSeaLongComponents] = float(ShortEnergy > 0.0 ? std::sqrt(Short / ShortEnergy) : (H > 0.0 ? 1.0 : 0.0));
			}
		}
	}

	void FSeaMap::Sample(double X, double Y, float* Out) const
	{
		if (Rows == 0)
		{
			for (int I = 0; I < kSeaChannels; ++I) Out[I] = 1.f;
			return;
		}
		const double U = Clamp((X - OriginX) / Cell, 0.0, Rows - 1.0), V = Clamp((Y - OriginY) / Cell, 0.0, Cols - 1.0);
		const int R0 = std::min(int(U), std::max(Rows - 2, 0)), C0 = std::min(int(V), std::max(Cols - 2, 0));
		const int R1 = std::min(R0 + 1, Rows - 1), C1 = std::min(C0 + 1, Cols - 1);
		const float TU = float(U - R0), TV = float(V - C0);
		const float* A = CellAt(R0, C0);
		const float* B = CellAt(R0, C1);
		const float* Cc = CellAt(R1, C0);
		const float* D = CellAt(R1, C1);
		for (int I = 0; I < kSeaChannels; ++I)
		{
			const float Top = A[I] + (B[I] - A[I]) * TV, Bottom = Cc[I] + (D[I] - Cc[I]) * TV;
			Out[I] = Top + (Bottom - Top) * TU;
		}
	}
}
