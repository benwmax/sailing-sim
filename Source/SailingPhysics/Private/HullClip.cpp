#include "HullClip.h"
#include "SailingMath.h"

#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		double SternOf(const FHullShape& H) { return H.HasStations() ? H.Stations.front().X : H.SternX; }
		double BowOf(const FHullShape& H) { return H.HasStations() ? H.Stations.back().X : H.BowX; }
		double WidestHalfBeam(const FHullShape& H)
		{
			if (!H.HasStations()) return H.MaxHalfBeam;
			double W = 0.0;
			for (const FHullShape::FStation& S : H.Stations) W = std::max(W, S.Y.empty() ? 0.0 : S.Y.back());
			return W;
		}
	}

	void FHullClipMap::Build(const std::vector<FHullShape>& Hulls, double InMainDepth)
	{
		Texels.clear();
		MainDepth = InMainDepth;
		if (Hulls.empty()) return;
		double MinX = 1e9, MaxX = -1e9, MinY = 1e9, MaxY = -1e9;
		for (const FHullShape& H : Hulls)
		{
			const double W = WidestHalfBeam(H);
			MinX = std::min(MinX, SternOf(H));
			MaxX = std::max(MaxX, BowOf(H));
			MinY = std::min(MinY, H.CenterY - W);
			MaxY = std::max(MaxY, H.CenterY + W);
		}
		// Two texels of open water round the hulls, so the clamped edge reads outside.
		const double PadX = 2.0 * (MaxX - MinX) / (Cols - 4), PadY = 2.0 * (MaxY - MinY) / (Rows - 4);
		X0 = MinX - PadX;
		Y0 = MinY - PadY;
		SizeX = MaxX - MinX + 2.0 * PadX;
		SizeY = MaxY - MinY + 2.0 * PadY;
		Texels.resize(size_t(Cols) * Rows);
		for (int R = 0; R < Rows; ++R)
		{
			const double Y = Y0 + (R + 0.5) * SizeY / Rows;
			for (int C = 0; C < Cols; ++C)
			{
				const double X = X0 + (C + 0.5) * SizeX / Cols;
				// The hull this point is most inside (or least outside): its skin is the one the water meets here.
				FTexel Best;
				double BestIn = -1e9;
				for (const FHullShape& H : Hulls)
				{
					const double LocalY = Y - H.CenterY;
					const double Side = H.DeckHalfBeam(X) - std::fabs(LocalY);
					const double End = std::min(X - SternOf(H), BowOf(H) - X);
					const double In = std::min(Side, End);
					if (In <= BestIn) continue;
					BestIn = In;
					Best.Bottom = float(H.BottomZ(X, LocalY, MainDepth));
					Best.Sheer = float(H.SheerHeight(X));
					Best.Side = float(Side);
					Best.End = float(End);
				}
				Texels[size_t(R) * Cols + C] = Best;
			}
		}
	}

	FHullClipMap::FTexel FHullClipMap::Sample(double X, double Y) const
	{
		if (Texels.empty()) return FTexel();
		const double U = Clamp((X - X0) / SizeX * Cols - 0.5, 0.0, double(Cols - 1));
		const double V = Clamp((Y - Y0) / SizeY * Rows - 0.5, 0.0, double(Rows - 1));
		const int C0 = std::min(int(U), Cols - 2), R0 = std::min(int(V), Rows - 2);
		const double TU = U - C0, TV = V - R0;
		auto At = [this](int R, int C) -> const FTexel& { return Texels[size_t(R) * Cols + C]; };
		auto Mix = [&](float FTexel::*F)
		{
			const double A = Lerp(double(At(R0, C0).*F), double(At(R0, C0 + 1).*F), TU);
			const double B = Lerp(double(At(R0 + 1, C0).*F), double(At(R0 + 1, C0 + 1).*F), TU);
			return float(Lerp(A, B, TV));
		};
		FTexel Out;
		Out.Bottom = Mix(&FTexel::Bottom);
		Out.Sheer = Mix(&FTexel::Sheer);
		Out.Side = Mix(&FTexel::Side);
		Out.End = Mix(&FTexel::End);
		return Out;
	}

	std::vector<float> FHullClipMap::Pixels() const
	{
		std::vector<float> Out;
		Out.reserve(Texels.size() * 4);
		for (const FTexel& T : Texels)
		{
			Out.push_back(T.Bottom);
			Out.push_back(T.Sheer);
			Out.push_back(T.Side);
			Out.push_back(T.End);
		}
		return Out;
	}

	double FHullClipMap::Drop(double X, double Y, double Z, double UpZ) const
	{
		if (Texels.empty()) return 0.0;
		const FTexel T = Sample(X, Y);
		const double Immersion = Z - T.Bottom;
		const double Fade = Z < T.Sheer ? 0.05 : 0.15;
		const double Edge = Clamp(std::min(T.Side, T.End) / Fade, 0.0, 1.0);
		return std::min(2.0, std::max(0.0, 1.1 * Immersion + 0.03 * Clamp(Immersion / 0.05, 0.0, 1.0)) / std::max(UpZ, 0.3)) * Edge;
	}
}
