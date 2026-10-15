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
		void Threshold(std::vector<double>& V, double Coverage, std::vector<float>& Out, int Channel, double SoftStd = 0.5)
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
			double Edge = Sorted[K];
			const double Soft = SoftStd * Std;
			// W5a: the quantile edge gives the coverage's mean only for a field symmetric about it; the cumulus cells are
			// skewed (a few tall peaks), so solve for the edge whose mean presence is the coverage (presence falls as the
			// edge rises).
			auto MeanAt = [&](double E)
			{
				double Sum = 0.0;
				for (size_t I = 0; I < Count; I += 7) Sum += Clamp(0.5 + (V[I] - E) / (2.0 * Soft), 0.0, 1.0);
				return Sum / double((Count + 6) / 7);
			};
			double Lo = Edge - 4.0 * Soft, Hi = Edge + 4.0 * Soft;
			for (int It = 0; It < 24; ++It)
			{
				const double Mid = 0.5 * (Lo + Hi);
				(MeanAt(Mid) > Coverage ? Lo : Hi) = Mid;
			}
			Edge = 0.5 * (Lo + Hi);
			for (size_t I = 0; I < Count; ++I) Out[I * 4 + Channel] = float(Clamp(0.5 + (V[I] - Edge) / (2.0 * Soft), 0.0, 1.0));
		}
	}

	double FStormShape::TierX(double X)
	{
		const double A = 1.0 - Smooth(2.0 * ShelfTierM, 3.0 * ShelfTierM, X);
		return X - A * ShelfTierM / (2.0 * kPi) * std::sin(2.0 * kPi * X / ShelfTierM);
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
			const double Top = Base + ShelfLipM + TierX(X) * ShelfSlope;
			const double In = Smooth(Base, Base + 25.0, Alt) * (1.0 - Smooth(Top - 150.0, Top, Alt));
			Dens = std::max(Dens, 1.0 * In * (1.0 - Smooth(ShelfDepthM - 600.0, ShelfDepthM, X)));
		}
		// Rain core, towering as the storm builds.
		const double Core = Smooth(-CoreBehindM, -CoreBehindM - 1500.0, D) * (1.0 - Smooth(-CoreBehindM - 14000.0, -CoreBehindM - 20000.0, D));
		const double CoreTop = CoreBaseM + (CoreTopM - CoreBaseM) * Build;
		if (Core > 0.0) Dens = std::max(Dens, Core * Smooth(CoreBaseM, CoreBaseM + 200.0, Alt) * (1.0 - Smooth(CoreTop - 1500.0, CoreTop, Alt)));
		// Anvil, spreading ahead high up and thinning: thin ice cloud (Graphics G1; mirrored in make_materials.py).
		if (D > -CoreBehindM - 15000.0 && D < AnvilAheadM)
		{
			const double Ahead = Clamp(1.0 - std::max(D, 0.0) / AnvilAheadM, 0.0, 1.0);
			const double Lower = AnvilBaseM + (1.0 - Ahead) * 2000.0;
			Dens = std::max(Dens, 0.12 * Ahead * Build * Smooth(Lower, Lower + 400.0, Alt) * (1.0 - Smooth(CoreTopM - 800.0, CoreTopM, Alt)));
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
		// Cloud streets form in a steady wind aloft (about 4 m/s and up).
		const double Streets = Clamp((DriftLen - 3.0) / 5.0, 0.0, 1.0);

		// W5a: cumulus come in all sizes, not one. Real fields follow a power law (many small, few large: number density
		// n(D) ~ D^-2.5, so each size class below has about 2.4 times the clouds of the next larger one). Each class is a
		// jittered lattice of seeded cells in the drifting frame, spacing growing as r^0.75; a cell's peak grows with its
		// size (r^0.6, as a big cell builds taller), so after the coverage threshold the small ones are low, thin puffs
		// and the big ones reach the full height. Their outlines are lumpy at their own scale.
		struct FCuClass { double Radius, Spacing; uint32_t Seed; };
		static constexpr FCuClass Classes[] = { { 2000.0, 7000.0, 71u }, { 1100.0, 4500.0, 73u }, { 600.0, 2900.0, 79u }, { 330.0, 1850.0, 83u } };
		auto CellField = [&](double Ac, double Bc, double Stretch)
		{
			double V = 0.0;
			for (const FCuClass& K : Classes)
			{
				const double Gx = Ac / (K.Spacing * Stretch), Gy = Bc / K.Spacing;
				const int32_t Ix = int32_t(std::floor(Gx)), Iy = int32_t(std::floor(Gy));
				for (int32_t Dx = -1; Dx <= 1; ++Dx)
				{
					for (int32_t Dy = -1; Dy <= 1; ++Dy)
					{
						const uint32_t H = Hash2(Ix + Dx, Iy + Dy, K.Seed);
						if ((H & 0xff) > 217) continue;   // about 15% of the lattice is empty sky
						const double Jx = ((H >> 8) & 0xff) / 255.0, Jy = ((H >> 16) & 0xff) / 255.0;
						const double R = K.Radius * (0.75 + 0.5 * ((H >> 24) & 0xff) / 255.0);
						const double Cx = (Ix + Dx + 0.15 + 0.7 * Jx) * K.Spacing * Stretch, Cy = (Iy + Dy + 0.15 + 0.7 * Jy) * K.Spacing;
						const double Ex = (Ac - Cx) / (R * Stretch), Ey = (Bc - Cy) / R;
						double E2 = Ex * Ex + Ey * Ey;
						if (E2 >= 2.0) continue;
						E2 *= 1.0 + 0.8 * (Fbm(Ac / (0.7 * R), Bc / (0.7 * R), K.Seed + 7u, 3) - 0.5);
						if (E2 >= 1.0) continue;
						const double Bump = (1.0 - E2) * (1.0 - E2);
						V = std::max(V, Bump * std::pow(R / 2000.0, 0.6));
					}
				}
			}
			return V;
		};

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
				// Cumulus: cells from a few hundred metres to 4 km across (W5a, above), more and bigger over the land (heated
				// in the afternoon); with a wind aloft they line up in streets along it, 3 to 4 km apart (Graphics G1). A little
				// of the old noise keeps the field from being only round cells.
				const double Ac = X * Ux + Y * Uy, Bc = -X * Uy + Y * Ux;
				const double Stretch = 1.0 + 0.4 * Streets;
				Cu[I] = CellField(Ac, Bc, Stretch) + 0.25 * (Fbm(Ac / (2000.0 * Stretch), Bc / 2000.0, 11u, 4) - 0.5)
					+ 0.4 * (Land[I] - LandMean) + 0.09 * Streets * std::cos(Bc / 3600.0 * 6.283185307 + 1.7 * Fbm(Ac / 9000.0, Bc / 9000.0, 13u, 2));
				// Stratus: broad, gently varied.
				St[I] = Fbm(X / 9000.0, Y / 9000.0, 23u, 3);
				// Cirrus: streaks drawn out along the wind aloft.
				const double A = X * Ux + Y * Uy, B = -X * Uy + Y * Ux;
				Ci[I] = Fbm(A / 9000.0, B / 1400.0, 37u, 4);
			}
		}
		// Cumulus presence ramps over a whole standard deviation: the renderer raises each cell's top with it (domes, not
		// flat-topped prisms).
		Threshold(Cu, Sky[ECloudLayer::Cumulus].Coverage, Rgba, 0, 1.1);
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

	double FWeatherMap::SunTransmittance(const FCloudSky& Sky, const FGustFront& Front, double FrontTravelM, double DriftT, double X, double Y,
		double SunX, double SunY, double SunZ) const
	{
		if (Rgba.empty() || SunZ <= 0.02) return SunZ > 0.0 ? 0.5 : 0.0;
		const double Cell = SizeMeters / N;
		auto Sample = [&](double Px, double Py, int Channel)
		{
			// The map lies in the drifting frame (world = field + Drift * T).
			const double U = (Px - Sky.DriftX * DriftT - X0) / Cell - 0.5, V = (Py - Sky.DriftY * DriftT - Y0) / Cell - 0.5;
			const int R = Clamp(int(std::floor(U + 0.5)), 0, N - 1), C = Clamp(int(std::floor(V + 0.5)), 0, N - 1);
			return double(Rgba[(size_t(R) * N + C) * 4 + Channel]);
		};
		const double Move = Front.MoveDegrees * kDegToRad;
		const double Dx = std::cos(Move), Dy = std::sin(Move);
		double Depth = 0.0;
		constexpr int Steps = 48;
		const double Top = 7000.0, Step = Top / Steps;
		for (int I = 0; I < Steps; ++I)
		{
			const double Alt = (I + 0.5) * Step;
			const double T = Alt / SunZ;
			const double Px = X + SunX * T, Py = Y + SunY * T;
			double Dens = 0.0;
			auto Profile = [&](const FCloudLayer& L, int Channel)
			{
				const double H = (Alt / 1000.0 - L.BaseKm) / std::max(L.TopKm - L.BaseKm, 0.05);
				return H > 0.0 && H < 1.0 ? Sample(Px, Py, Channel) * L.Density : 0.0;
			};
			Dens += Profile(Sky[ECloudLayer::Cumulus], 0) * 0.6 + Profile(Sky[ECloudLayer::Stratus], 1);
			if (Front.bActive && Sky[ECloudLayer::Storm].Coverage > 0.0)
			{
				const double D = (Px - Front.StartX) * Dx + (Py - Front.StartY) * Dy - FrontTravelM;
				Dens += FStormShape::Density(D, Alt, Sample(Px, Py, 3), Sky[ECloudLayer::Storm].Coverage);
			}
			// An average cloud extinction: 0.02 /m at full density, about half of that left after the noise.
			Depth += Dens * 0.01 * Step / SunZ;
		}
		return std::exp(-Depth);
	}

	double FWeatherMap::Mean(int Channel) const
	{
		double Sum = 0.0;
		const size_t Count = Rgba.size() / 4;
		for (size_t I = 0; I < Count; ++I) Sum += Rgba[I * 4 + Channel];
		return Count ? Sum / double(Count) : 0.0;
	}
}
