#include "Skyline.h"
#include <algorithm>
#include <cmath>
#include <cstring>

namespace Sailing
{
	namespace
	{
		template <typename T> T ReadLE(const uint8_t* P) { T V; std::memcpy(&V, P, sizeof(T)); return V; }
	}

	bool FSkyline::Load(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 3;
		if (Size < Header || std::memcmp(Data, "SSKL", 4) != 0 || ReadLE<uint32_t>(Data + 4) != 1) return false;
		const int NX = int(ReadLE<uint32_t>(Data + 8)), NY = int(ReadLE<uint32_t>(Data + 12));
		if (NX < 2 || NY < 2 || Size < Header + size_t(NX) * NY * 2) return false;
		Cols = NX;
		Rows = NY;
		Cell = ReadLE<float>(Data + 16);
		OriginX = ReadLE<float>(Data + 20);
		OriginY = ReadLE<float>(Data + 24);
		Heights.resize(size_t(NX) * NY);
		std::memcpy(Heights.data(), Data + Header, Heights.size() * 2);
		return true;
	}

	double FSkyline::HeightAt(double X, double Y) const
	{
		if (Heights.empty()) return 0.0;
		const double FR = (X - OriginX) / Cell, FC = (Y - OriginY) / Cell;
		if (FR < 0.0 || FC < 0.0 || FR >= Rows - 1 || FC >= Cols - 1) return 0.0;
		const int R = int(FR), C = int(FC);
		const double TR = FR - R, TC = FC - C;
		auto H = [&](int RR, int CC) { return double(Heights[size_t(RR) * Cols + CC]); };
		return (H(R, C) * (1.0 - TC) + H(R, C + 1) * TC) * (1.0 - TR) + (H(R + 1, C) * (1.0 - TC) + H(R + 1, C + 1) * TC) * TR;
	}

	double FSkyline::ElevationAngle(double X, double Y, double EyeZ, double Azimuth, double MinM, double MaxM, double Step, double* OutDistance) const
	{
		const double DX = std::cos(Azimuth), DY = std::sin(Azimuth);
		double Best = -1.5707963267948966, BestD = 0.0;
		for (double D = MinM; D <= MaxM; D += Step)
		{
			const double H = HeightAt(X + DX * D, Y + DY * D);
			if (H <= 0.0) continue;
			const double A = std::atan2(H - D * D / (2.0 * EarthR) - EyeZ, D);
			if (A > Best) { Best = A; BestD = D; }
		}
		if (OutDistance) *OutDistance = BestD;
		return Best;
	}

	void FSkyline::Compute(double X, double Y, double EyeZ, int Count, double MinM, double MaxM, std::vector<float>& OutAngles, std::vector<float>& OutDistances) const
	{
		OutAngles.assign(size_t(std::max(Count, 1)), -1.5707964f);
		OutDistances.assign(OutAngles.size(), 0.f);
		if (Heights.empty()) return;
		for (int K = 0; K < Count; ++K)
		{
			double D = 0.0;
			// Half-cell steps: the grid's own resolution, so a summit is never stepped over.
			OutAngles[size_t(K)] = float(ElevationAngle(X, Y, EyeZ, 2.0 * 3.141592653589793 * K / Count, MinM, MaxM, 0.5 * Cell, &D));
			OutDistances[size_t(K)] = float(D);
		}
	}
}
