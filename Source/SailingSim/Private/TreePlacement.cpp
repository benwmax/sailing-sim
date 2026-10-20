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

	// T2 species: the low ground by the water (m above it) where the waterline trees grow: the lake's bank above the pool,
	// the coast's above MLLW (its marsh edges and the spoil banks' salt cedar).
	constexpr float kLakeWaterlineM = 2.5f;
	constexpr float kCoastWaterlineM = 2.0f;
	// The lidar crowns are many more and closer together than the canopy map's trees: only those nearest the water.
	constexpr float kLakeCrownWaterlineM = 1.8f;

	bool LeansToWater(ETreeSpecies S) { return S == ETreeSpecies::BlackWillow || S == ETreeSpecies::Cottonwood || S == ETreeSpecies::SaltCedar; }

	// The models lean toward +X (build_trees.py's "stemmed" trees): turn that side downhill, to the water, within 25 deg.
	float YawToWater(const Sailing::FLakeTerrain& T, double X, double Y, float Jitter, float Fallback)
	{
		const double GX = T.HeightAt(X + 10.0, Y) - T.HeightAt(X - 10.0, Y), GY = T.HeightAt(X, Y + 10.0) - T.HeightAt(X, Y - 10.0);
		if (GX * GX + GY * GY < 0.01) return Fallback;
		return float(FMath::RadiansToDegrees(FMath::Atan2(-GY, -GX))) + (Jitter * 2.f - 1.f) * 25.f;
	}

	ETreeSpecies CanopySpecies(ETreeRegion Region, float Kind, float Ground, float U)
	{
		switch (Region)
		{
		case ETreeRegion::CrossTimbers:
			// By the water: black willow most, cottonwood, and the upland mix behind them.
			if (Ground < kLakeWaterlineM && U < 0.75f) return U < 0.45f ? ETreeSpecies::BlackWillow : ETreeSpecies::Cottonwood;
			return Kind < 0.12f ? ETreeSpecies::RedCedar : (Kind < 0.22f ? ETreeSpecies::LiveOak : (Kind < 0.55f ? ETreeSpecies::PostOak
				: (Kind < 0.78f ? ETreeSpecies::CedarElm : ETreeSpecies::Sugarberry)));
		case ETreeRegion::GulfCoast:
			// Salt cedar on the low ground by the water; live oak and sugarberry (hackberry) on the ridges, a few cedar elms.
			if (Ground < kCoastWaterlineM && U < 0.7f) return ETreeSpecies::SaltCedar;
			return Kind < 0.5f ? ETreeSpecies::LiveOak : (Kind < 0.78f ? ETreeSpecies::Sugarberry : (Kind < 0.9f ? ETreeSpecies::CedarElm : ETreeSpecies::SaltCedar));
		default:
			return Kind < 0.12f ? ETreeSpecies::RedCedar : (Kind < 0.3f ? ETreeSpecies::LiveOak : (Kind < 0.66f ? ETreeSpecies::PostOak : ETreeSpecies::CedarElm));
		}
	}
}

ETreeRegion TreeRegionFor(const FString& LakeName)
{
	if (LakeName == TEXT("RayHubbard")) return ETreeRegion::CrossTimbers;
	if (LakeName == TEXT("GalvestonBay") || LakeName == TEXT("GulfPassage") || LakeName == TEXT("TexasCoast")) return ETreeRegion::GulfCoast;
	return ETreeRegion::Classic;
}

void TreeHeightRange(ETreeSpecies Species, float& MinH, float& MaxH)
{
	// LiveOak, PostOak, CedarElm, RedCedar (V6), then sugarberry, black willow, cottonwood, salt cedar.
	static const float Min[] = { 8.f, 10.f, 12.f, 6.f, 9.f, 7.f, 16.f, 3.5f }, Max[] = { 12.f, 14.f, 16.f, 10.f, 14.f, 12.f, 24.f, 6.f };
	static_assert(UE_ARRAY_COUNT(Min) == int32(ETreeSpecies::Count), "a height range per species");
	MinH = Min[int32(Species)];
	MaxH = Max[int32(Species)];
}

void PlaceTreeInstances(const Sailing::FLakeTerrain& T, float Fraction, TArray<FTreeInstance>& Out, ETreeRegion Region)
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
				I.Species = CanopySpecies(Region, Kind, float(Ground), Region == ETreeRegion::Classic ? 0.f : TreeRand(Seed + K * 13 + 7));
				const float U = TreeRand(Seed + K * 13 + 4);
				float MinH, MaxH;
				TreeHeightRange(I.Species, MinH, MaxH);
				I.Height = FMath::Lerp(MinH, MaxH, U);
				I.Yaw = 360.f * TreeRand(Seed + K * 13 + 5);
				if (LeansToWater(I.Species)) I.Yaw = YawToWater(T, PX, PY, TreeRand(Seed + K * 13 + 8), I.Yaw);
				I.Variant = uint8(TreeRand(Seed + K * 13 + 6) < 0.5f ? 0 : 1);
				Out.Add(I);
			}
		}
	}
}

void PlaceCrownTrees(const Sailing::FLakeTerrain& T, TConstArrayView<FLakeCrown> Crowns, float Fraction, TArray<FTreeInstance>& Out, ETreeRegion Region)
{
	PlaceTreeInstances(T, Fraction, Out, Region);
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
		if (Region == ETreeRegion::CrossTimbers && Ground < kLakeCrownWaterlineM && !C.bCedar && TreeRand(Seed + 9) < 0.7f)
		{
			// T2 species: right by the water (most of it: the bottomland's oaks and elms stand among them) the tall crowns are
			// cottonwoods, the spreading and the low ones black willows.
			if (C.Height > 15.f) I.Species = U < 0.7f ? ETreeSpecies::Cottonwood : ETreeSpecies::PostOak;
			else I.Species = U < 0.6f ? ETreeSpecies::BlackWillow : (U < 0.8f ? ETreeSpecies::Sugarberry : (Aspect > 0.4f ? ETreeSpecies::Cottonwood : ETreeSpecies::CedarElm));
		}
		else if (Region == ETreeRegion::GulfCoast)
		{
			// The coast: salt cedar in the low thickets by the water, live oak's spreading crowns, sugarberry the rest.
			if (Ground < kCoastWaterlineM && C.Height < 8.f) I.Species = U < 0.75f ? ETreeSpecies::SaltCedar : ETreeSpecies::Sugarberry;
			else if (Aspect > 0.45f) I.Species = U < 0.8f ? ETreeSpecies::LiveOak : ETreeSpecies::Sugarberry;
			else I.Species = U < 0.45f ? ETreeSpecies::Sugarberry : (U < 0.75f ? ETreeSpecies::LiveOak : (U < 0.9f ? ETreeSpecies::CedarElm
				: (C.Height < 8.f ? ETreeSpecies::SaltCedar : ETreeSpecies::LiveOak)));
		}
		else if (C.bCedar) I.Species = ETreeSpecies::RedCedar;
		else if (Aspect > 0.5f) I.Species = U < 0.55f ? ETreeSpecies::LiveOak : ETreeSpecies::PostOak;
		else if (Region == ETreeRegion::CrossTimbers)
		{
			// T2 species: sugarberry takes a share of the cross timbers' narrower and middling crowns.
			if (Aspect < 0.28f) I.Species = U < 0.5f ? ETreeSpecies::CedarElm : (U < 0.72f ? ETreeSpecies::RedCedar : (U < 0.88f ? ETreeSpecies::Sugarberry : ETreeSpecies::PostOak));
			else if (C.Height < 7.f) I.Species = U < 0.5f ? ETreeSpecies::CedarElm : (U < 0.68f ? ETreeSpecies::Sugarberry : (U < 0.88f ? ETreeSpecies::PostOak : ETreeSpecies::RedCedar));
			else if (C.Height > 14.f) I.Species = U < 0.55f ? ETreeSpecies::PostOak : (U < 0.8f ? ETreeSpecies::LiveOak : (U < 0.9f ? ETreeSpecies::Sugarberry : ETreeSpecies::CedarElm));
			else I.Species = U < 0.38f ? ETreeSpecies::PostOak : (U < 0.6f ? ETreeSpecies::CedarElm : (U < 0.78f ? ETreeSpecies::Sugarberry
				: (U < 0.92f ? ETreeSpecies::LiveOak : ETreeSpecies::RedCedar)));
		}
		else if (Aspect < 0.28f) I.Species = U < 0.6f ? ETreeSpecies::CedarElm : (U < 0.8f ? ETreeSpecies::RedCedar : ETreeSpecies::PostOak);
		else if (C.Height < 7.f) I.Species = U < 0.6f ? ETreeSpecies::CedarElm : (U < 0.85f ? ETreeSpecies::PostOak : ETreeSpecies::RedCedar);
		else if (C.Height > 14.f) I.Species = U < 0.6f ? ETreeSpecies::PostOak : (U < 0.85f ? ETreeSpecies::LiveOak : ETreeSpecies::CedarElm);
		else I.Species = U < 0.45f ? ETreeSpecies::PostOak : (U < 0.75f ? ETreeSpecies::CedarElm : (U < 0.92f ? ETreeSpecies::LiveOak : ETreeSpecies::RedCedar));
		I.Yaw = 360.f * TreeRand(Seed + 5);
		if (LeansToWater(I.Species)) I.Yaw = YawToWater(T, C.X, C.Y, TreeRand(Seed + 8), I.Yaw);
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
	const bool bDeciduous = Tree.Species != ETreeSpecies::LiveOak && Tree.Species != ETreeSpecies::RedCedar;
	L.Deciduous = bDeciduous ? 0.35f + 0.65f * U(2) : 0.f;
	// The autumn colour: post oak russet-brown; cedar elm, sugarberry and salt cedar yellow to gold; willow and cottonwood
	// the brightest yellow.
	switch (Tree.Species)
	{
	case ETreeSpecies::CedarElm: L.AutumnHue = 0.75f + 0.25f * U(3); break;
	case ETreeSpecies::Sugarberry: L.AutumnHue = 0.7f + 0.3f * U(3); break;
	case ETreeSpecies::SaltCedar: L.AutumnHue = 0.55f + 0.35f * U(3); break;
	case ETreeSpecies::BlackWillow:
	case ETreeSpecies::Cottonwood: L.AutumnHue = 0.88f + 0.12f * U(3); break;
	default: L.AutumnHue = 0.25f * U(3); break;
	}
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