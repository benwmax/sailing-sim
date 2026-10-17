#include "TreePlacement.h"
#include "LakeTerrain.h"
#include "PortableRandom.h"
#include "SailingSim.h"

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

void PlaceCrownTrees(const Sailing::FLakeTerrain& T, TConstArrayView<FLakeCrown> Crowns, float Fraction, TArray<FTreeInstance>& Out)
{
	PlaceTreeInstances(T, Fraction, Out);
	if (Crowns.Num() == 0) return;
	// The crowns' band, in 100 m cells: any cell with a crown within 200 m. The canopy-map trees there give way.
	TSet<FIntPoint> Band;
	for (const FLakeCrown& C : Crowns)
	{
		const FIntPoint Cell(FMath::FloorToInt32(C.X / 100.f), FMath::FloorToInt32(C.Y / 100.f));
		for (int32 Dx = -2; Dx <= 2; ++Dx) for (int32 Dy = -2; Dy <= 2; ++Dy) Band.Add(Cell + FIntPoint(Dx, Dy));
	}
	Out.RemoveAll([&](const FTreeInstance& I) { return Band.Contains(FIntPoint(FMath::FloorToInt32(I.Position.X / 100.0), FMath::FloorToInt32(I.Position.Y / 100.0))); });
	const int32 Filled = Out.Num();
	for (int32 K = 0; K < Crowns.Num(); ++K)
	{
		const FLakeCrown& C = Crowns[K];
		const uint32 Seed = TreeHash(uint32(FMath::RoundToInt32(C.X * 10.f)) * 73856093u ^ uint32(FMath::RoundToInt32(C.Y * 10.f)) * 19349663u);
		if (TreeRand(Seed) > Fraction) continue;
		// Stand on the drawn ground (the lidar's median can sit a little off the 5 m grid's surface).
		const double Ground = T.HeightAt(C.X, C.Y);
		if (Ground < 0.3) continue;
		FTreeInstance I;
		I.Position = FVector2D(C.X, C.Y);
		I.Ground = float(Ground);
		I.Height = C.Height;
		// The kept far crowns stand for their neighbours: a little wider, so the far shore keeps its mass.
		I.Crown = C.Radius * (C.Weight > 1 ? 1.25f : 1.f);
		// By the crown's shape as well as its height: a spreading crown (radius over half the height) is an oak, live oak
		// most of all; a narrow one an elm or a cedar. The model then needs little stretching to the measured width.
		const float U = TreeRand(Seed + 3);
		const float Aspect = C.Radius / FMath::Max(C.Height, 1.f);
		if (C.bCedar) I.Species = ETreeSpecies::RedCedar;
		else if (Aspect > 0.5f) I.Species = U < 0.55f ? ETreeSpecies::LiveOak : ETreeSpecies::PostOak;
		else if (Aspect < 0.28f) I.Species = U < 0.6f ? ETreeSpecies::CedarElm : (U < 0.8f ? ETreeSpecies::RedCedar : ETreeSpecies::PostOak);
		else if (C.Height < 7.f) I.Species = U < 0.6f ? ETreeSpecies::CedarElm : (U < 0.85f ? ETreeSpecies::PostOak : ETreeSpecies::RedCedar);
		else if (C.Height > 14.f) I.Species = U < 0.6f ? ETreeSpecies::PostOak : (U < 0.85f ? ETreeSpecies::LiveOak : ETreeSpecies::CedarElm);
		else I.Species = U < 0.45f ? ETreeSpecies::PostOak : (U < 0.75f ? ETreeSpecies::CedarElm : (U < 0.92f ? ETreeSpecies::LiveOak : ETreeSpecies::RedCedar));
		I.Yaw = 360.f * TreeRand(Seed + 5);
		I.Variant = uint8(TreeRand(Seed + 6) < 0.5f ? 0 : 1);
		Out.Add(I);
	}
	UE_LOG(LogSailing, Display, TEXT("Trees: %d lidar crowns placed, %d canopy-map trees outside their band"), Out.Num() - Filled, Filled);
}

FTreeLook TreeLookFor(const FTreeInstance& Tree)
{
	// The tree's id: its position to 0.25 m (a crown or canopy-cell tree never moves), hashed.
	const uint64_t Id = Sailing::HashCombine(uint64_t(int64_t(FMath::RoundToDouble(Tree.Position.X * 4.0))), uint64_t(int64_t(FMath::RoundToDouble(Tree.Position.Y * 4.0))));
	auto U = [Id](uint64_t K) { return float(double(Sailing::Hash64(Id ^ (K * 0x9E3779B97F4A7C15ull)) >> 11) * (1.0 / 9007199254740992.0)); };
	FTreeLook L;
	L.Tint = U(1);
	// The deciduous trees turn, each its own amount (some early, some hardly); the evergreens keep their green.
	const bool bDeciduous = Tree.Species == ETreeSpecies::PostOak || Tree.Species == ETreeSpecies::CedarElm;
	L.Deciduous = bDeciduous ? 0.35f + 0.65f * U(2) : 0.f;
	L.AutumnHue = Tree.Species == ETreeSpecies::CedarElm ? 0.75f + 0.25f * U(3) : 0.25f * U(3);
	// A small lean, up to 3 degrees either way (a whole stand standing ruler-straight read as planted).
	L.LeanPitch = (U(4) * 2.f - 1.f) * 3.f;
	L.LeanRoll = (U(5) * 2.f - 1.f) * 3.f;
	return L;
}

namespace
{
	float Ramp(float X, float A, float B) { const float T = FMath::Clamp((X - A) / (B - A), 0.f, 1.f); return T * T * (3.f - 2.f * T); }
}

float AutumnAmount(int32 DayOfYear)
{
	// North Texas: colour from early October to a peak near Thanksgiving (day 329); post oaks keep their brown leaves
	// through the winter, and the trees leaf out green again by late March.
	const float D = float((DayOfYear - 1 + 366) % 366 + 1);
	if (D >= 274.f) return Ramp(D, 274.f, 329.f);
	return 1.f - Ramp(D, 46.f, 79.f);
}

float SpringAmount(int32 DayOfYear)
{
	const float D = float((DayOfYear - 1 + 366) % 366 + 1);
	return Ramp(D, 60.f, 95.f) * (1.f - Ramp(D, 110.f, 152.f));
}