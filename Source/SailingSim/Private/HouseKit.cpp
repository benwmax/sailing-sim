// Graphics G6: the shore's houses from the G2 footprints (FLakeHouse, Tools/terrain/build_houses.py). Each wing is a box to
// the lidar eave with its roof (hip, gable, shed or flat at the measured pitch), eaves with soffit and fascia; within 400 m
// of the water (the full-detail band) the outside walls get framed windows per storey, a front door and a garage door on
// the street side and a chimney on some. Wings overlap, so a cross-hipped or L-shaped roof comes out of the union.
#include "WorldKit.h"
#include "LakeData.h"
#include "SailingSim.h"

namespace
{
	// Wall finishes (FKitSection::Paint.A on HouseWall): must match M_HouseKitWall in scripts/make_materials.py.
	enum EWallCode : uint8 { Brick = 0, Siding = 1, Stucco = 2, Glass = 3, Door = 4, Garage = 5 };
	// Roof finishes (Paint.A on HouseRoof).
	enum ERoofCode : uint8 { Shingle = 0, Membrane = 1, Metal = 2 };

	uint32 HouseHash(uint32 K, uint32 Salt)
	{
		uint32 H = K * 0x9E3779B1u + Salt * 0x85EBCA77u;
		H ^= H >> 15; H *= 0x2C1B3C6Du; H ^= H >> 12; H *= 0x297A2D39u; H ^= H >> 15;
		return H;
	}
	float Hash01(uint32 K, uint32 Salt) { return float(HouseHash(K, Salt) & 0xFFFFFF) / float(0xFFFFFF); }

	FColor Srgb(const FLinearColor& L) { return L.ToFColor(true); }

	struct FWingFrame
	{
		FVector2D C, U, V;   // centre, long axis, across (V = U turned +90 deg, X toward Y)
		double HL, HW;
		FVector2D At(double A, double B) const { return C + U * A + V * B; }
		bool Contains(const FVector2D& P, double Margin = 0.0) const
		{
			const FVector2D D = P - C;
			return FMath::Abs(FVector2D::DotProduct(D, U)) < HL - Margin && FMath::Abs(FVector2D::DotProduct(D, V)) < HW - Margin;
		}
	};

	/** A vertical quad from P0 to P1 (plan), Z0..Z1, its front facing Out. U runs along from U0, V is height above G. */
	void WallQuad(FKitSection& S, FVector2D P0, FVector2D P1, double Z0, double Z1, const FVector2D& Out, double U0, double G)
	{
		FVector2D T = P1 - P0;
		if (FVector2D::DotProduct(FVector2D(-T.Y, T.X), Out) < 0.0) { Swap(P0, P1); T = -T; }
		const double L = T.Size();
		S.Quad(FVector(P0, Z0), FVector(P1, Z0), FVector(P1, Z1), FVector(P0, Z1),
			FVector2D(U0, Z0 - G), FVector2D(U0 + L, Z0 - G), FVector2D(U0 + L, Z1 - G), FVector2D(U0, Z1 - G));
	}

	/** A triangle in a wall plane (gable ends): the apex over the midpoint. */
	void WallTriangle(FKitSection& S, FVector2D P0, FVector2D P1, double Z0, const FVector& Apex, const FVector2D& Out, double G)
	{
		FVector2D T = P1 - P0;
		if (FVector2D::DotProduct(FVector2D(-T.Y, T.X), Out) < 0.0) { Swap(P0, P1); T = -T; }
		const double L = T.Size();
		S.Quad(FVector(P0, Z0), FVector(P1, Z0), Apex, Apex, FVector2D(0, Z0 - G), FVector2D(L, Z0 - G), FVector2D(L * 0.5, Apex.Z - G), FVector2D(L * 0.5, Apex.Z - G));
	}

	/** A sloped roof plane A-B (eave, Z = ZE) up to C-D (ridge side): front faces up. UVs: along the eave, up the slope. */
	void RoofPlane(FKitSection& S, const FVector& A, const FVector& B, const FVector& C, const FVector& D)
	{
		// The front is the side (D - A) x (B - A) points to: make it point up.
		const bool bUp = FVector::CrossProduct(D - A, B - A).Z >= 0.0;
		const FVector2D EaveDir = FVector2D(B - A).GetSafeNormal();
		auto UVof = [&](const FVector& P) { return FVector2D(FVector2D::DotProduct(FVector2D(P - A), EaveDir), FVector::Dist(P, FVector(FVector2D(A) + EaveDir * FVector2D::DotProduct(FVector2D(P - A), EaveDir), A.Z))); };
		if (bUp) S.Quad(A, B, C, D, UVof(A), UVof(B), UVof(C), UVof(D));
		else S.Quad(B, A, D, C, UVof(B), UVof(A), UVof(D), UVof(C));
	}

	/** A quad whose front faces Want (the Quad's front is (D - A) x (B - A)). */
	void FacedQuad(FKitSection& S, const FVector& A, FVector B, const FVector& C, FVector D, const FVector& Want, FVector2D UA, FVector2D UB, FVector2D UC, FVector2D UD)
	{
		if (FVector::DotProduct(FVector::CrossProduct(D - A, B - A), Want) < 0.0) { Swap(B, D); Swap(UB, UD); }
		S.Quad(A, B, C, D, UA, UB, UC, UD);
	}

	/** A bar standing proud of a wall: front and four sides, no back. Along T from U0 to U1 at the plane point O, Z0..Z1. */
	void Relief(FKitSection& S, const FVector2D& O, const FVector2D& T, const FVector2D& N, double U0, double U1, double Z0, double Z1, double Depth)
	{
		const FVector2D A0 = O + T * U0, A1 = O + T * U1, F0 = A0 + N * Depth, F1 = A1 + N * Depth;
		const double W = U1 - U0;
		// Front (faces N), top, bottom and the two ends.
		WallQuad(S, F0, F1, Z0, Z1, N, 0.0, Z0);
		FacedQuad(S, FVector(A0, Z1), FVector(F0, Z1), FVector(F1, Z1), FVector(A1, Z1), FVector::UpVector, { 0, 0 }, { Depth, 0 }, { Depth, W }, { 0, W });
		FacedQuad(S, FVector(A0, Z0), FVector(A1, Z0), FVector(F1, Z0), FVector(F0, Z0), -FVector::UpVector, { 0, 0 }, { W, 0 }, { W, Depth }, { 0, Depth });
		WallQuad(S, A0, F0, Z0, Z1, -T, 0.0, Z0);
		WallQuad(S, A1, F1, Z0, Z1, T, 0.0, Z0);
	}

	struct FWallRun { FVector2D P0, P1, Out; int32 Wing; };

	bool InOutline(const TArray<FVector2D>& Pts, const FVector2D& P)
	{
		bool bIn = false;
		for (int32 I = 0, J = Pts.Num() - 1; I < Pts.Num(); J = I++)
		{
			if ((Pts[I].Y > P.Y) != (Pts[J].Y > P.Y) && P.X < Pts[J].X + (Pts[I].X - Pts[J].X) * (P.Y - Pts[J].Y) / (Pts[I].Y - Pts[J].Y)) bIn = !bIn;
		}
		return bIn;
	}
}

void HouseTiles(const FLakeData& Lake, TMap<FIntPoint, TArray<int32>>& Out)
{
	const bool bMarina = Lake.Marina.IsLoaded();
	for (int32 K = 0; K < Lake.Houses.Num(); ++K)
	{
		const FLakeHouse& H = Lake.Houses[K];
		// The marina actor draws the club's own buildings.
		if (bMarina && Lake.Marina.Buildings.ContainsByPredicate([&](const FMarinaBuilding& M)
			{ return FVector2D::Distance(M.Center, FVector2D(H.X, H.Y)) < 0.5 * M.Size.Size() + 5.0; }))
		{
			continue;
		}
		Out.FindOrAdd(FIntPoint(FMath::FloorToInt32(H.X / UWorldKitLibrary::HouseTileM), FMath::FloorToInt32(H.Y / UWorldKitLibrary::HouseTileM))).Add(K);
	}
}

void BuildHouseGeometry(const FLakeData& Lake, TConstArrayView<int32> Indices, FKitGeometry& Out)
{
	const Sailing::FLakeTerrain& Terr = Lake.Terrain;
	FKitSection& Wall = Out[EKitLook::HouseWall];
	FKitSection& Roof = Out[EKitLook::HouseRoof];
	FKitSection& Trim = Out[EKitLook::Trim];
	FKitSection& Conc = Out[EKitLook::Concrete];
	FKitSection& Met = Out[EKitLook::Metal];
	// North Texas walls: brick (most), fibre-cement siding and stucco; trim white or cream.
	static const FLinearColor Bricks[] = { FLinearColor(0.30f, 0.11f, 0.07f), FLinearColor(0.38f, 0.18f, 0.10f), FLinearColor(0.42f, 0.30f, 0.20f),
		FLinearColor(0.25f, 0.13f, 0.09f), FLinearColor(0.50f, 0.40f, 0.30f), FLinearColor(0.34f, 0.24f, 0.18f) };
	static const FLinearColor Lights[] = { FLinearColor(0.72f, 0.68f, 0.58f), FLinearColor(0.62f, 0.60f, 0.55f), FLinearColor(0.78f, 0.77f, 0.73f),
		FLinearColor(0.45f, 0.50f, 0.52f), FLinearColor(0.60f, 0.52f, 0.40f), FLinearColor(0.55f, 0.56f, 0.50f), FLinearColor(0.36f, 0.40f, 0.42f) };
	static const FLinearColor Doors[] = { FLinearColor(0.85f, 0.85f, 0.82f), FLinearColor(0.04f, 0.04f, 0.045f), FLinearColor(0.30f, 0.17f, 0.08f),
		FLinearColor(0.06f, 0.10f, 0.20f), FLinearColor(0.35f, 0.05f, 0.04f), FLinearColor(0.20f, 0.24f, 0.18f) };
	// Round 10: the Gulf coast's stucco is paler and warmer, with the beachfront's pastels (the Seawall's blocks had North
	// Texas brick and greys).
	static const FLinearColor Coast[] = { FLinearColor(0.80f, 0.78f, 0.72f), FLinearColor(0.74f, 0.68f, 0.56f), FLinearColor(0.82f, 0.80f, 0.76f),
		FLinearColor(0.72f, 0.56f, 0.46f), FLinearColor(0.58f, 0.68f, 0.66f), FLinearColor(0.78f, 0.72f, 0.52f), FLinearColor(0.66f, 0.64f, 0.60f),
		FLinearColor(0.56f, 0.62f, 0.70f) };
	const bool bCoast = Lake.bOcean;
	// Round 10: decks on piles under these footprints (Lake.Decks, the same outlines the shore bake draws). The Pleasure Pier's
	// restaurant and shops stood in the Gulf from the water up, inside the pier's piles: they stand on its deck now.
	FBox2D Area(ForceInit);
	for (const int32 K : Indices) Area += FVector2D(Lake.Houses[K].X, Lake.Houses[K].Y);
	Area = Area.ExpandBy(5.0);
	TArray<const FLakeDeck*> NearDecks;
	for (const FLakeDeck& D : Lake.Decks)
	{
		if (D.Outline.Num() < 3) continue;
		FBox2D B(ForceInit);
		for (const FVector2D& P : D.Outline) B += P;
		if (B.Intersect(Area)) NearDecks.Add(&D);
	}
	for (const int32 K : Indices)
	{
		const FLakeHouse& H = Lake.Houses[K];
		const bool bFull = H.bFullDetail;
		double G = FMath::Max(double(Terr.HeightAt(H.X, H.Y)), 0.15);   // the terrain the player sees, never under the water line
		double EaveH = H.Eave;
		int32 Storeys = H.Storeys;
		const FLakeDeck* OnDeck = nullptr;
		for (const FLakeDeck* D : NearDecks)
		{
			if (D->Deck > G + 1.5 && (!OnDeck || D->Deck > OnDeck->Deck) && InOutline(D->Outline, FVector2D(H.X, H.Y))) OnDeck = D;
		}
		if (OnDeck)
		{
			// The lidar's eave and roof top were measured from the ground under the pier (the water): from the deck, a storey
			// at least.
			const double Top = H.Ground > -900.0 ? H.Ground + H.Eave : OnDeck->Deck + 3.5;
			G = OnDeck->Deck;
			EaveH = FMath::Clamp(Top - G, 3.0, 12.0);
			Storeys = FMath::Clamp(FMath::RoundToInt((EaveH - 0.3) / 2.9), 1, 4);
		}
		const double E = G + EaveH;
		// Round 10: four storeys and up (the Seawall's hotels and condos): windows on every storey, painted on (the full-detail
		// windows stopped at the third), and balconies along the side facing the water on most.
		const bool bTall = Storeys >= 4;
		const bool bBalconies = Hash01(K, 30) < 0.7f;
		TArray<FWingFrame, TInlineAllocator<4>> Wings;
		double Base = G;
		for (const FLakeHouse::FWing& W : H.Wings)
		{
			const double Yaw = FMath::DegreesToRadians(W.YawDeg);
			FWingFrame F{ FVector2D(W.X, W.Y), FVector2D(FMath::Cos(Yaw), FMath::Sin(Yaw)), FVector2D(-FMath::Sin(Yaw), FMath::Cos(Yaw)), W.HalfLength, W.HalfWidth };
			for (int32 Cn = 0; Cn < 4; ++Cn)
			{
				const FVector2D P = F.At((Cn & 1) ? F.HL : -F.HL, (Cn & 2) ? F.HW : -F.HW);
				Base = FMath::Min(Base, double(Terr.HeightAt(P.X, P.Y)));
			}
			Wings.Add(F);
		}
		Base = OnDeck ? G - 0.35 : Base - 0.4;
		// Finish and colours.
		const float Pick = Hash01(K, 1);
		uint8 Code = H.bCommercial ? (Pick < 0.5f ? Stucco : Brick) : (Pick < 0.5f ? Brick : (Pick < 0.78f ? Siding : Stucco));
		if (bCoast && (bTall || OnDeck)) Code = Pick < 0.85f ? Stucco : Brick;
		const FLinearColor WallCol = Code == Brick ? Bricks[HouseHash(K, 2) % UE_ARRAY_COUNT(Bricks)]
			: (bCoast ? Coast[HouseHash(K, 3) % UE_ARRAY_COUNT(Coast)] : Lights[HouseHash(K, 3) % UE_ARRAY_COUNT(Lights)]);
		const float Seed = Hash01(K, 4);
		const FVector2D WallTag(EaveH, Seed + (bFull && !H.bCommercial && !bTall ? 0.0 : 2.0));   // Tag.y >= 2: painted windows
		// NAIP's roof colours are bright (haze, no calibration): about 0.6 of them in linear reflectance.
		const FLinearColor Naip = FLinearColor::FromSRGBColor(H.RoofColor);
		const FLinearColor RoofCol = FLinearColor(Naip.R * 0.6f, Naip.G * 0.6f, Naip.B * 0.6f);
		Wall.Paint = Srgb(WallCol); Wall.Paint.A = Code; Wall.Tag = WallTag;
		Roof.Paint = Srgb(RoofCol); Roof.Paint.A = H.Roof == FLakeHouse::Flat ? Membrane : (H.Roof == FLakeHouse::Shed && H.bCommercial ? Metal : Shingle);
		Roof.Tag = FVector2D(Seed, 0.0);
		// The pitch: the lidar ridge over the main wing's half width, else the fit's pitch.
		double TanP = FMath::Tan(FMath::DegreesToRadians(double(H.PitchDeg)));
		if (H.Ridge > H.Eave + 0.3f && H.Roof != FLakeHouse::Flat && Wings.Num() > 0)
		{
			TanP = FMath::Clamp((H.Ridge - H.Eave) / FMath::Max(Wings[0].HW, 1.0), FMath::Tan(FMath::DegreesToRadians(10.0)), 1.0);
		}
		const double Over = H.Roof == FLakeHouse::Flat ? 0.0 : (bFull ? 0.5 : 0.35);
		const double Drop = Over * TanP;
		// The walls of every wing, and which stretches of them are outside (for windows and doors).
		TArray<FWallRun> Runs;
		for (int32 Wi = 0; Wi < Wings.Num(); ++Wi)
		{
			const FWingFrame& F = Wings[Wi];
			const FVector2D Cn[4] = { F.At(-F.HL, -F.HW), F.At(F.HL, -F.HW), F.At(F.HL, F.HW), F.At(-F.HL, F.HW) };
			const FVector2D Outs[4] = { -F.V, F.U, F.V, -F.U };
			double U0 = 0.0;
			for (int32 S = 0; S < 4; ++S)
			{
				const FVector2D& A = Cn[S];
				const FVector2D& B = Cn[(S + 1) % 4];
				WallQuad(Wall, A, B, Base, E, Outs[S], U0, G);
				U0 += FVector2D::Distance(A, B);
				Runs.Add({ A, B, Outs[S], Wi });
			}
			// A slab edge proud of the walls at the foot (the foundation line).
			for (int32 S = 0; S < 4 && bFull; ++S)
			{
				const FVector2D A = Cn[S] + Outs[S] * 0.03 + Outs[(S + 3) % 4] * 0.03, B = Cn[(S + 1) % 4] + Outs[S] * 0.03 + Outs[(S + 1) % 4] * 0.03;
				WallQuad(Conc, A, B, Base, G + 0.15, Outs[S], 0.0, G);
			}
		}
		// Roofs.
		for (int32 Wi = 0; Wi < Wings.Num(); ++Wi)
		{
			const FWingFrame& F = Wings[Wi];
			const double HL = F.HL + Over, HW = F.HW + Over, ZE = E - Drop;
			const FVector A(F.At(-HL, -HW), ZE), B(F.At(HL, -HW), ZE), C(F.At(HL, HW), ZE), D(F.At(-HL, HW), ZE);
			if (H.Roof == FLakeHouse::Flat)
			{
				RoofPlane(Roof, A, B, C, D);
				// A parapet on commercial and tall blocks, a lip on the rest.
				const double Par = H.bCommercial || bTall ? 0.7 : 0.25;
				const FVector2D Cn[4] = { FVector2D(A), FVector2D(B), FVector2D(C), FVector2D(D) };
				const FVector2D Outs[4] = { -F.V, F.U, F.V, -F.U };
				for (int32 S = 0; S < 4; ++S)
				{
					WallQuad(Wall, Cn[S], Cn[(S + 1) % 4], E, E + Par, Outs[S], 0.0, G);
					WallQuad(Wall, Cn[S] - Outs[S] * 0.2, Cn[(S + 1) % 4] - Outs[S] * 0.2, E, E + Par, -Outs[S], 0.0, G);
					Trim.Quad(FVector(Cn[S], E + Par), FVector(Cn[(S + 1) % 4], E + Par), FVector(Cn[(S + 1) % 4] - Outs[S] * 0.2, E + Par), FVector(Cn[S] - Outs[S] * 0.2, E + Par),
						{ 0, 0 }, { 1, 0 }, { 1, 0.2 }, { 0, 0.2 });
				}
				// Rooftop units on the big ones.
				if ((H.bCommercial || bTall) && Wi == 0 && F.HL > 8.0 && F.HW > 5.0)
				{
					const int32 Units = 1 + int32(HouseHash(K, 9) % 3);
					for (int32 Un = 0; Un < Units; ++Un)
					{
						const FVector2D P = F.At((Hash01(K, 10 + Un) - 0.5) * F.HL, (Hash01(K, 20 + Un) - 0.5) * F.HW);
						Met.Box(FVector(P, E + 0.6), FVector(1.1, 0.8, 0.6), float(FMath::RadiansToDegrees(FMath::Atan2(F.U.Y, F.U.X))));
					}
				}
				continue;
			}
			if (H.Roof == FLakeHouse::Shed)
			{
				const double Rise = 2.0 * HW * FMath::Min(TanP, 0.3);
				const FVector C2 = C + FVector(0, 0, Rise), D2 = D + FVector(0, 0, Rise);
				RoofPlane(Roof, A, B, C2, D2);
				WallQuad(Wall, F.At(-F.HL, F.HW), F.At(F.HL, F.HW), E, E + Rise - Drop, F.V, 0.0, G);
				WallTriangle(Wall, F.At(-F.HL, -F.HW), F.At(-F.HL, F.HW), E, FVector(F.At(-F.HL, F.HW), E + Rise - Drop), -F.U, G);
				WallTriangle(Wall, F.At(F.HL, -F.HW), F.At(F.HL, F.HW), E, FVector(F.At(F.HL, F.HW), E + Rise - Drop), F.U, G);
				continue;
			}
			const double ZR = ZE + HW * TanP;
			if (H.Roof == FLakeHouse::Gable)
			{
				const FVector R0(F.At(-HL, 0.0), ZR), R1(F.At(HL, 0.0), ZR);
				RoofPlane(Roof, A, B, R1, R0);
				RoofPlane(Roof, C, D, R0, R1);
				// Gable ends: the wall triangle up to the ridge (at the wall plane), the rake's underside.
				const double ZRw = E + F.HW * TanP;
				WallTriangle(Wall, F.At(-F.HL, -F.HW), F.At(-F.HL, F.HW), E, FVector(F.At(-F.HL, 0.0), ZRw), -F.U, G);
				WallTriangle(Wall, F.At(F.HL, -F.HW), F.At(F.HL, F.HW), E, FVector(F.At(F.HL, 0.0), ZRw), F.U, G);
				// Barge boards along the rakes.
				for (const double Su : { -1.0, 1.0 })
				{
					const FVector N(F.U * Su, 0.0);
					const FVector2D E0 = F.At(Su * HL, -HW), E1 = F.At(Su * HL, HW), M = F.At(Su * HL, 0.0);
					FacedQuad(Trim, FVector(E0, ZE - 0.2), FVector(M, ZR - 0.2), FVector(M, ZR), FVector(E0, ZE), N, { 0, 0 }, { HW, 0 }, { HW, 0.2 }, { 0, 0.2 });
					FacedQuad(Trim, FVector(M, ZR - 0.2), FVector(E1, ZE - 0.2), FVector(E1, ZE), FVector(M, ZR), N, { 0, 0 }, { HW, 0 }, { HW, 0.2 }, { 0, 0.2 });
				}
			}
			else
			{
				// Hip: the ridge along the long axis, short by the half width at each end (a pyramid on a square).
				const double RL = FMath::Max(0.0, HL - HW);
				const FVector R0(F.At(-RL, 0.0), ZR), R1(F.At(RL, 0.0), ZR);
				RoofPlane(Roof, A, B, R1, R0);
				RoofPlane(Roof, C, D, R0, R1);
				RoofPlane(Roof, B, C, R1, R1);
				RoofPlane(Roof, D, A, R0, R0);
			}
			// Soffit (under the overhang) and fascia (the eave's face) on the eave sides; all round on a hip.
			const FVector2D Cw[4] = { F.At(-F.HL, -F.HW), F.At(F.HL, -F.HW), F.At(F.HL, F.HW), F.At(-F.HL, F.HW) };
			const FVector Ce[4] = { A, B, C, D };
			const FVector2D Outs[4] = { -F.V, F.U, F.V, -F.U };
			for (int32 S = 0; S < 4; ++S)
			{
				if (H.Roof == FLakeHouse::Gable && (S == 1 || S == 3)) continue;
				const FVector& E0 = Ce[S];
				const FVector& E1 = Ce[(S + 1) % 4];
				WallQuad(Trim, FVector2D(E0), FVector2D(E1), ZE - 0.22, ZE, Outs[S], 0.0, ZE);
				// Soffit, facing down: from the eave edge in to the wall line.
				const FVector W0(Cw[S], ZE - 0.22), W1(Cw[(S + 1) % 4], ZE - 0.22);
				FacedQuad(Trim, FVector(E0.X, E0.Y, ZE - 0.22), FVector(E1.X, E1.Y, ZE - 0.22), W1, W0, -FVector::UpVector, { 0, 0 }, { 1, 0 }, { 1, Over }, { 0, Over });
			}
		}
		if (!bFull) continue;
		// The street side: away from the nearest water (the lakefront houses face the road).
		FVector2D Street = -Wings[0].V;
		for (double R = 25.0; R <= 400.0; R += 25.0)
		{
			bool bFound = false;
			for (int32 A = 0; A < 16 && !bFound; ++A)
			{
				const FVector2D Dir(FMath::Cos(A * UE_DOUBLE_PI / 8.0), FMath::Sin(A * UE_DOUBLE_PI / 8.0));
				if (Terr.HeightAt(H.X + R * Dir.X, H.Y + R * Dir.Y) < -0.3) { Street = -Dir; bFound = true; }
			}
			if (bFound) break;
		}
		// A chimney on a quarter of the pitched houses: brick, through the main roof near its ridge.
		if (H.Roof != FLakeHouse::Flat && !H.bCommercial && Hash01(K, 5) < 0.25f)
		{
			const FWingFrame& F = Wings[0];
			const FVector2D P = F.At((Hash01(K, 6) - 0.5) * F.HL, (Hash01(K, 7) - 0.5) * 0.6 * F.HW);
			const double Top = E + F.HW * TanP + 0.9;
			Wall.Paint = Srgb(Bricks[HouseHash(K, 8) % UE_ARRAY_COUNT(Bricks)]); Wall.Paint.A = Brick;
			const float Yaw = float(FMath::RadiansToDegrees(FMath::Atan2(F.U.Y, F.U.X)));
			const FVector2D Cn[4] = { P - F.U * 0.8 - F.V * 0.55, P + F.U * 0.8 - F.V * 0.55, P + F.U * 0.8 + F.V * 0.55, P - F.U * 0.8 + F.V * 0.55 };
			const FVector2D Outs[4] = { -F.V, F.U, F.V, -F.U };
			for (int32 S = 0; S < 4; ++S) WallQuad(Wall, Cn[S], Cn[(S + 1) % 4], E - 0.5, Top, Outs[S], 0.0, G);
			Conc.Box(FVector(P, Top + 0.06), FVector(0.9, 0.65, 0.06), Yaw);
			Wall.Paint = Srgb(WallCol); Wall.Paint.A = Code;
		}
		// Openings on the outside walls: front door and garage on the street side of the main wing, windows elsewhere.
		const FColor TrimCol = FColor::White;
		bool bDoor = false, bGarage = H.bCommercial || bTall || OnDeck || Wings[0].HL < 7.0;
		for (int32 Ri = 0; Ri < Runs.Num(); ++Ri)
		{
			const FWallRun& Run = Runs[Ri];
			const FVector2D T = (Run.P1 - Run.P0).GetSafeNormal();
			const double L = FVector2D::Distance(Run.P0, Run.P1);
			const FVector2D N = Run.Out;
			auto Outside = [&](double U)
			{
				const FVector2D P = Run.P0 + T * U + N * 0.4;
				for (int32 Wj = 0; Wj < Wings.Num(); ++Wj) if (Wj != Run.Wing && Wings[Wj].Contains(P)) return false;
				return true;
			};
			const bool bStreet = FVector2D::DotProduct(N, Street) > 0.6;
			TArray<FVector2D, TInlineAllocator<4>> Taken;   // U ranges used by doors
			if (bStreet && Run.Wing == 0 && !bGarage && L > 9.0)
			{
				// A double garage door near one end.
				const double W = H.Wings[0].HalfLength * 2.0 > 16.0 ? 4.9 : 2.7;
				const double U = Hash01(K, 11) < 0.5 ? 0.8 : L - 0.8 - W;
				if (Outside(U + 0.5 * W))
				{
					Wall.Paint = Srgb(Lights[HouseHash(K, 12) % 3]); Wall.Paint.A = Garage;
					WallQuad(Wall, Run.P0 + T * U + N * 0.02, Run.P0 + T * (U + W) + N * 0.02, G + 0.05, G + 2.15, N, 0.0, G);
					Trim.Paint = TrimCol;
					Relief(Trim, Run.P0, T, N, U - 0.12, U, G, G + 2.27, 0.06);
					Relief(Trim, Run.P0, T, N, U + W, U + W + 0.12, G, G + 2.27, 0.06);
					Relief(Trim, Run.P0, T, N, U - 0.12, U + W + 0.12, G + 2.15, G + 2.27, 0.06);
					Taken.Add(FVector2D(U - 0.5, U + W + 0.5));
					bGarage = true;
				}
			}
			if (bStreet && !bDoor && L > 4.0)
			{
				const double U = Taken.Num() ? (Taken[0].X > L * 0.5 ? Taken[0].X * 0.5 : 0.5 * (Taken[0].Y + L)) : 0.5 * L;
				if (Outside(U))
				{
					Wall.Paint = Srgb(Doors[HouseHash(K, 13) % UE_ARRAY_COUNT(Doors)]); Wall.Paint.A = Door;
					WallQuad(Wall, Run.P0 + T * (U - 0.48) + N * 0.02, Run.P0 + T * (U + 0.48) + N * 0.02, G + 0.15, G + 2.25, N, 0.0, G);
					Relief(Trim, Run.P0, T, N, U - 0.6, U - 0.48, G + 0.15, G + 2.37, 0.07);
					Relief(Trim, Run.P0, T, N, U + 0.48, U + 0.6, G + 0.15, G + 2.37, 0.07);
					Relief(Trim, Run.P0, T, N, U - 0.6, U + 0.6, G + 2.25, G + 2.37, 0.07);
					// The step in front.
					Conc.Box(FVector(Run.P0 + T * U + N * 0.6, G + 0.08), FVector(0.6, 0.75, 0.08), float(FMath::RadiansToDegrees(FMath::Atan2(T.Y, T.X))));
					Taken.Add(FVector2D(U - 0.9, U + 0.9));
					bDoor = true;
				}
			}
			// Windows: storeys of 2.9 m, one every 3.2 m or so, clear of the corners and the doors.
			const double Wd = 0.9 + 0.5 * Hash01(K, 14);
			const double Ht = 1.3 + 0.25 * Hash01(K, 15);
			const int32 Count = FMath::Max(0, int32((L - 1.6) / 3.2));
			for (int32 St = 0; St < Storeys && St < 3 && !bTall; ++St)
			{
				const double Z0 = G + 0.95 + 2.9 * St, Z1 = Z0 + Ht;
				if (Z1 > E - 0.3) break;
				for (int32 Wn = 0; Wn < FMath::Max(Count, L > 3.0 ? 1 : 0); ++Wn)
				{
					const double U = Count > 0 ? 0.8 + (L - 1.6) * (Wn + 0.5) / Count : 0.5 * L;
					if (!Outside(U)) continue;
					if (St == 0 && Taken.ContainsByPredicate([&](const FVector2D& R) { return U + 0.5 * Wd > R.X && U - 0.5 * Wd < R.Y; })) continue;
					if (Hash01(K * 64 + Ri, 100 + Wn + 8 * St) < 0.15f) continue;   // a blank stretch here and there
					Wall.Paint = FColor(30, 32, 34, Glass);
					WallQuad(Wall, Run.P0 + T * (U - 0.5 * Wd) + N * 0.015, Run.P0 + T * (U + 0.5 * Wd) + N * 0.015, Z0, Z1, N, U, G);
					// The frame standing 5 cm proud (its front and the three reveals round the glass; its outer edges are lost
					// against the wall) and a sill: ten quads a window, a third of a full house's bake.
					const double A = U - 0.5 * Wd, B = U + 0.5 * Wd, F = 0.05, W8 = 0.08;
					const FVector2D O = Run.P0 + N * F;
					WallQuad(Trim, O + T * (A - W8), O + T * A, Z0, Z1, N, 0.0, Z0);
					WallQuad(Trim, O + T * B, O + T * (B + W8), Z0, Z1, N, 0.0, Z0);
					WallQuad(Trim, O + T * (A - W8), O + T * (B + W8), Z1, Z1 + W8, N, 0.0, Z1);
					WallQuad(Trim, Run.P0 + T * A, O + T * A, Z0, Z1, T, 0.0, Z0);
					WallQuad(Trim, Run.P0 + T * B, O + T * B, Z0, Z1, -T, 0.0, Z0);
					FacedQuad(Trim, FVector(Run.P0 + T * A, Z1), FVector(Run.P0 + T * B, Z1), FVector(O + T * B, Z1), FVector(O + T * A, Z1), -FVector::UpVector,
						{ 0, 0 }, { Wd, 0 }, { Wd, F }, { 0, F });
					const FVector2D S0 = Run.P0 + T * (A - 0.12), S1 = Run.P0 + T * (B + 0.12), SF = N * 0.09;
					WallQuad(Trim, S0 + SF, S1 + SF, Z0 - 0.06, Z0, N, 0.0, Z0);
					FacedQuad(Trim, FVector(S0, Z0), FVector(S1, Z0), FVector(S1 + SF, Z0), FVector(S0 + SF, Z0), FVector::UpVector, { 0, 0 }, { Wd, 0 }, { Wd, 0.09 }, { 0, 0.09 });
					FacedQuad(Trim, FVector(S0, Z0 - 0.06), FVector(S1, Z0 - 0.06), FVector(S1 + SF, Z0 - 0.06), FVector(S0 + SF, Z0 - 0.06), -FVector::UpVector, { 0, 0 }, { Wd, 0 }, { Wd, 0.09 }, { 0, 0.09 });
				}
			}
			// Round 10: a tall block's balconies on the side facing the water: a slab a storey, glazed doors behind, a glass
			// balustrade on a rail, and a fin between the units every 7 m or so.
			if (bTall && bBalconies && FVector2D::DotProduct(N, -Street) > 0.6 && L > 6.0)
			{
				const int32 Units = FMath::Max(1, FMath::RoundToInt((L - 0.6) / 7.0));
				for (int32 St = 1; St < Storeys; ++St)
				{
					const double Z = G + 2.9 * St;
					if (Z + 2.6 > E) break;
					auto Clear = [&](double U) { return Outside(U); };
					if (!Clear(0.5 * L)) continue;
					Relief(Conc, Run.P0, T, N, 0.3, L - 0.3, Z - 0.2, Z, 1.4);
					Wall.Paint = FColor(30, 32, 34, Glass);
					WallQuad(Wall, Run.P0 + T * 0.4 + N * 0.03, Run.P0 + T * (L - 0.4) + N * 0.03, Z, Z + 2.4, N, 0.0, Z);
					WallQuad(Wall, Run.P0 + T * 0.35 + N * 1.36, Run.P0 + T * (L - 0.35) + N * 1.36, Z, Z + 1.0, N, 0.0, Z);
					Relief(Met, Run.P0 + N * 1.33, T, N, 0.3, L - 0.3, Z + 1.0, Z + 1.06, 0.06);
					for (int32 Un = 0; Un <= Units; ++Un)
					{
						const double U = 0.3 + (L - 0.6) * Un / Units;
						Relief(Conc, Run.P0, T, N, U - 0.1, U + 0.1, Z, Z + 2.7, 1.4);
					}
				}
			}
			Wall.Paint = Srgb(WallCol); Wall.Paint.A = Code;
		}
	}
}
