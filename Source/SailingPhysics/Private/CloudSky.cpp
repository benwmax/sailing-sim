#include "CloudSky.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	const char* CloudLayerName(ECloudLayer Layer)
	{
		switch (Layer)
		{
		case ECloudLayer::Cumulus: return "Cumulus";
		case ECloudLayer::Stratus: return "Stratus";
		case ECloudLayer::Cirrus: return "Cirrus";
		case ECloudLayer::Storm: return "Storm";
		default: return "?";
		}
	}

	void FCloudSky::Span(double& OutBaseKm, double& OutTopKm) const
	{
		OutBaseKm = 1e9;
		OutTopKm = 0.0;
		for (int I = 0; I < int(ECloudLayer::Count); ++I)
		{
			const FCloudLayer& L = Layers[I];
			// Cirrus is drawn on the sky dome (a thin sheet 8 km up): spanning it would spread the tracer's samples thin.
			if (L.Coverage <= 0.0 || I == int(ECloudLayer::Cirrus)) continue;
			OutBaseKm = std::min(OutBaseKm, L.BaseKm);
			OutTopKm = std::max(OutTopKm, L.TopKm);
		}
		if (OutTopKm <= 0.0) { OutBaseKm = 1.4; OutTopKm = 2.6; }
	}

	namespace
	{
		double Smooth(double E0, double E1, double X)
		{
			const double T = Clamp((X - E0) / (E1 - E0), 0.0, 1.0);
			return T * T * (3.0 - 2.0 * T);
		}

		uint32_t Hash2(int32_t X, int32_t Y, uint32_t Seed)
		{
			uint32_t H = uint32_t(X) * 0x8da6b343u ^ uint32_t(Y) * 0xd8163841u ^ Seed * 0xcb1ab31fu;
			H ^= H >> 16; H *= 0x7feb352du; H ^= H >> 15; H *= 0x846ca68bu; H ^= H >> 16;
			return H;
		}

		double ValueNoise(double X, double Y, uint32_t Seed)
		{
			const double Fx = std::floor(X), Fy = std::floor(Y);
			const int32_t Ix = int32_t(Fx), Iy = int32_t(Fy);
			const double Tx = X - Fx, Ty = Y - Fy;
			const double Sx = Tx * Tx * (3.0 - 2.0 * Tx), Sy = Ty * Ty * (3.0 - 2.0 * Ty);
			auto V = [&](int32_t A, int32_t B) { return (Hash2(A, B, Seed) & 0xffffff) / double(0xffffff); };
			return Lerp(Lerp(V(Ix, Iy), V(Ix + 1, Iy), Sx), Lerp(V(Ix, Iy + 1), V(Ix + 1, Iy + 1), Sx), Sy);
		}

		double Fbm(double X, double Y, uint32_t Seed, int Octaves)
		{
			double Sum = 0.0, Amp = 0.5, Norm = 0.0;
			for (int O = 0; O < Octaves; ++O)
			{
				Sum += Amp * ValueNoise(X, Y, Seed + O * 101u);
				Norm += Amp;
				X = X * 2.03 + 17.1;
				Y = Y * 2.03 - 9.7;
				Amp *= 0.5;
			}
			return Sum / Norm;
		}

		/** Presence from a field: the (1 - coverage) quantile is the edge, soft over half a standard deviation either way,
		 *  so the mean presence is the coverage. */
		void Threshold(std::vector<double>& V, double Coverage, std::vector<float>& Out, int Channel)
		{
			const size_t Count = V.size();
			if (Coverage <= 0.0) { for (size_t I = 0; I < Count; ++I) Out[I * 4 + Channel] = 0.f; return; }
			if (Coverage >= 1.0) { for (size_t I = 0; I < Count; ++I) Out[I * 4 + Channel] = 1.f; return; }
			double Mean = 0.0, Sq = 0.0;
			for (double X : V) { Mean += X; Sq += X * X; }
			Mean /= double(Count);
			const double Std = std::sqrt(std::max(Sq / double(Count) - Mean * Mean, 1e-12));
			std::vector<double> Sorted = V;
			const size_t K = std::min(Count - 1, size_t((1.0 - Coverage) * double(Count)));
			std::nth_element(Sorted.begin(), Sorted.begin() + K, Sorted.end());
			const double Edge = Sorted[K];
			const double Soft = 0.5 * Std;
			for (size_t I = 0; I < Count; ++I) Out[I * 4 + Channel] = float(Clamp(0.5 + (V[I] - Edge) / (2.0 * Soft), 0.0, 1.0));
		}
	}

	double FStormShape::Density(double D, double Alt, double Mask, double Build)
	{
		if (Mask <= 0.0 || Build <= 0.0) return 0.0;
		double Dens = 0.0;
		// Shelf cloud: X metres behind its lip.
		const double X = ShelfLeadM - D;
		if (X >= 0.0 && X <= ShelfDepthM)
		{
			const double Base = ShelfBaseM - 120.0 * Smooth(0.0, 800.0, X);
			const double Top = Base + ShelfLipM + X * ShelfSlope;
			const double In = Smooth(Base, Base + 25.0, Alt) * (1.0 - Smooth(Top - 150.0, Top, Alt));
			Dens = std::max(Dens, 1.0 * In * (1.0 - Smooth(ShelfDepthM - 600.0, ShelfDepthM, X)));
		}
		// Rain core, towering as the storm builds.
		const double Core = Smooth(-CoreBehindM, -CoreBehindM - 1500.0, D) * (1.0 - Smooth(-CoreBehindM - 14000.0, -CoreBehindM - 20000.0, D));
		const double CoreTop = CoreBaseM + (CoreTopM - CoreBaseM) * Build;
		if (Core > 0.0) Dens = std::max(Dens, Core * Smooth(CoreBaseM, CoreBaseM + 200.0, Alt) * (1.0 - Smooth(CoreTop - 1500.0, CoreTop, Alt)));
		// Anvil, spreading ahead high up and thinning.
		if (D > -CoreBehindM - 15000.0 && D < AnvilAheadM)
		{
			const double Ahead = Clamp(1.0 - std::max(D, 0.0) / AnvilAheadM, 0.0, 1.0);
			const double Lower = AnvilBaseM + (1.0 - Ahead) * 2000.0;
			Dens = std::max(Dens, 0.35 * Ahead * Build * Smooth(Lower, Lower + 400.0, Alt) * (1.0 - Smooth(CoreTopM - 800.0, CoreTopM, Alt)));
		}
		return Dens * Mask;
	}

	void FWeatherMap::Paint(const FCloudSky& Sky, const FGustFront& Front, double CenterX, double CenterY, double T)
	{
		// The map is painted in the clouds' own frame, which drifts with the wind aloft: a texel at field point F lies over
		// world point F + Drift * T. The renderer samples it at (world - Drift * T), so it moves smoothly between paints.
		const double Ox = Sky.DriftX * T, Oy = Sky.DriftY * T;
		const double Cell = SizeMeters / N;
		X0 = std::floor((CenterX - Ox - 0.5 * SizeMeters) / Cell) * Cell;
		Y0 = std::floor((CenterY - Oy - 0.5 * SizeMeters) / Cell) * Cell;
		const size_t Count = size_t(N) * N;
		Rgba.assign(Count * 4, 0.f);
		const double DriftLen = std::sqrt(Sky.DriftX * Sky.DriftX + Sky.DriftY * Sky.DriftY);
		const double Ux = DriftLen > 0.1 ? Sky.DriftX / DriftLen : 1.0, Uy = DriftLen > 0.1 ? Sky.DriftY / DriftLen : 0.0;

		std::vector<double> Cu(Count), St(Count), Ci(Count);
		std::vector<double> Land(Count, 0.5);
		if (LandFraction)
		{
			for (int R = 0; R < N; ++R)
				for (int C = 0; C < N; ++C) Land[size_t(R) * N + C] = Clamp(LandFraction(X0 + (R + 0.5) * Cell + Ox, Y0 + (C + 0.5) * Cell + Oy), 0.0, 1.0);
		}
		double LandMean = 0.0;
		for (double L : Land) LandMean += L;
		LandMean /= double(Count);
		for (int R = 0; R < N; ++R)
		{
			for (int C = 0; C < N; ++C)
			{
				const size_t I = size_t(R) * N + C;
				const double X = X0 + (R + 0.5) * Cell, Y = Y0 + (C + 0.5) * Cell;
				// Cumulus: cells a kilometre or two across, more of them over the land (heated in the afternoon).
				Cu[I] = Fbm(X / 2200.0, Y / 2200.0, 11u, 4) + 0.18 * (Land[I] - LandMean);
				// Stratus: broad, gently varied.
				St[I] = Fbm(X / 9000.0, Y / 9000.0, 23u, 3);
				// Cirrus: streaks drawn out along the wind aloft.
				const double A = X * Ux + Y * Uy, B = -X * Uy + Y * Ux;
				Ci[I] = Fbm(A / 9000.0, B / 1400.0, 37u, 4);
			}
		}
		Threshold(Cu, Sky[ECloudLayer::Cumulus].Coverage, Rgba, 0);
		Threshold(St, Sky[ECloudLayer::Stratus].Coverage, Rgba, 1);
		Threshold(Ci, Sky[ECloudLayer::Cirrus].Coverage, Rgba, 2);

		// Storm: its extent along the gust front (a cell some 35 km long), with a ragged end. The front is in the world
		// frame: where the texel lies now.
		if (Front.bActive && Sky[ECloudLayer::Storm].Coverage > 0.0)
		{
			const double Move = Front.MoveDegrees * kDegToRad;
			const double Px = -std::sin(Move), Py = std::cos(Move); // along the front line
			for (int R = 0; R < N; ++R)
			{
				for (int C = 0; C < N; ++C)
				{
					const double X = X0 + (R + 0.5) * Cell, Y = Y0 + (C + 0.5) * Cell;
					const double Lateral = (X + Ox - Front.StartX) * Px + (Y + Oy - Front.StartY) * Py;
					const double Ragged = 0.35 * (Fbm(X / 6000.0, Y / 6000.0, 53u, 3) - 0.5);
					Rgba[(size_t(R) * N + C) * 4 + 3] = float(Clamp(1.0 - Smooth(14000.0, 20000.0, std::fabs(Lateral)) + Ragged, 0.0, 1.0));
				}
			}
		}
	}

	double FWeatherMap::Mean(int Channel) const
	{
		double Sum = 0.0;
		const size_t Count = Rgba.size() / 4;
		for (size_t I = 0; I < Count; ++I) Sum += Rgba[I * 4 + Channel];
		return Count ? Sum / double(Count) : 0.0;
	}
}
