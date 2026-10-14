#include "TreePlacement.h"
#include "LakeTerrain.h"

namespace
{
	uint32 TreeHash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}
	float TreeRand(uint32 Seed) { return (TreeHash(Seed) & 0xFFFFFF) / float(0xFFFFFF); }
}

void PlaceTreeInstances(const Sailing::FLakeTerrain& T, float Fraction, TArray<FTreeInstance>& Out)
{
	Out.Reset();
	const double Step = 20.0;
	const int32 Rows = int32(T.GetRows() * T.GetCell() / Step), Cols = int32(T.GetCols() * T.GetCell() / Step);
	// Coarse water proximity: 100 m cells within 15 cells of water.
	const int32 CR = Rows / 5 + 1, CC = Cols / 5 + 1;
	TArray<uint8> NearWater;
	NearWater.SetNumZeroed(CR * CC);
	for (int32 R = 0; R < CR; ++R)
		for (int32 C = 0; C < CC; ++C)
			if (T.HeightAt(T.GetOriginX() + (R + 0.5) * 100.0, T.GetOriginY() + (C + 0.5) * 100.0) < 0.0)
				for (int32 DR = -15; DR <= 15; ++DR)
					for (int32 DC = -15; DC <= 15; ++DC)
						if (R + DR >= 0 && R + DR < CR && C + DC >= 0 && C + DC < CC && DR * DR + DC * DC <= 225) NearWater[(R + DR) * CC + C + DC] = 1;

	for (int32 R = 0; R < Rows; ++R)
	{
		for (int32 C = 0; C < Cols; ++C)
		{
			if (!NearWater[(R / 5) * CC + C / 5]) continue;
			const double X = T.GetOriginX() + (R + 0.5) * Step, Y = T.GetOriginY() + (C + 0.5) * Step;
			const double Density = T.CanopyAt(X, Y) / 12.0 * Fraction;
			const uint32 Seed = uint32(R * 92821 + C * 68917);
			const int32 Count = int32(Density * 1.6 + TreeRand(Seed));
			for (int32 K = 0; K < Count; ++K)
			{
				const double PX = X + (TreeRand(Seed + K * 13 + 1) - 0.5) * Step, PY = Y + (TreeRand(Seed + K * 13 + 2) - 0.5) * Step;
				const double Ground = T.HeightAt(PX, PY);
				if (Ground < 0.8) continue;
				// Slope from the neighbours: red cedar takes the steep, open banks.
				const double Slope = FMath::Abs(T.HeightAt(PX + 10.0, PY) - T.HeightAt(PX - 10.0, PY)) / 20.0 + FMath::Abs(T.HeightAt(PX, PY + 10.0) - T.HeightAt(PX, PY - 10.0)) / 20.0;
				const float Kind = TreeRand(Seed + K * 13 + 3) - float(FMath::Min(Slope, 0.3));
				FTreeInstance I;
				I.Position = FVector2D(PX, PY);
				I.Ground = float(Ground);
				I.Species = Kind < 0.12f ? ETreeSpecies::RedCedar : (Kind < 0.3f ? ETreeSpecies::LiveOak : (Kind < 0.66f ? ETreeSpecies::PostOak : ETreeSpecies::CedarElm));
				const float U = TreeRand(Seed + K * 13 + 4);
				static const float MinH[] = { 8.f, 10.f, 12.f, 6.f }, MaxH[] = { 12.f, 14.f, 16.f, 10.f };
				I.Height = FMath::Lerp(MinH[int32(I.Species)], MaxH[int32(I.Species)], U);
				I.Yaw = 360.f * TreeRand(Seed + K * 13 + 5);
				I.Variant = uint8(TreeRand(Seed + K * 13 + 6) < 0.5f ? 0 : 1);
				Out.Add(I);
			}
		}
	}
}
