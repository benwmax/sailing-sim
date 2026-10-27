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

	/** pc/shore-residential: a lot fence from P0 to P1 following the ground: a 1.8 m board fence (wood) or a 1.2 m black
	 *  iron one (rails and pickets). Stops where the ground drops under ZMin (the water's edge). */
	void Fence(FKitSection& Wood, FKitSection& Iron, const Sailing::FLakeTerrain& Terr, const FVector2D& P0, const FVector2D& P1, bool bWood, double ZMin)
	{
		const double L = FVector2D::Distance(P0, P1);
		if (L < 1.0) return;
		const int32 N = FMath::Max(1, FMath::CeilToInt32(L / 2.4));
		const FVector2D T = (P1 - P0) / L, Side(-T.Y, T.X);
		const float Yaw = float(FMath::RadiansToDegrees(FMath::Atan2(T.Y, T.X)));
		for (int32 I = 0; I < N; ++I)
		{
			const FVector2D A = P0 + (P1 - P0) * (double(I) / N), B = P0 + (P1 - P0) * (double(I + 1) / N);
			const double ZA = Terr.HeightAt(A.X, A.Y), ZB = Terr.HeightAt(B.X, B.Y);
			if (ZA < ZMin || ZB < ZMin) return;
			const double Pl = L / N;
			if (bWood)
			{
				// Both faces of the boards, and a post at the panel's start.
				Wood.Quad(FVector(A, ZA), FVector(A, ZA + 1.8), FVector(B, ZB + 1.8), FVector(B, ZB), { 0, 0 }, { 0, 1.8 }, { Pl, 1.8 }, { Pl, 0 });
				Wood.Quad(FVector(B + Side * 0.02, ZB), FVector(B + Side * 0.02, ZB + 1.8), FVector(A + Side * 0.02, ZA + 1.8), FVector(A + Side * 0.02, ZA), { 0, 0 }, { 0, 1.8 }, { Pl, 1.8 }, { Pl, 0 });
				Wood.Box(FVector(A + Side * 0.07, ZA + 0.95), FVector(0.05, 0.05, 0.95), Yaw);
			}
			else
			{
				Iron.Span(A, B, 0.03f, float(ZA + 0.12), float(ZA + 0.16));
				Iron.Span(A, B, 0.03f, float(ZA + 1.12), float(ZA + 1.18));
				Iron.Box(FVector(A, ZA + 0.62), FVector(0.03, 0.03, 0.62), Yaw);
				for (int32 Pk = 1; Pk < 6; ++Pk)
				{
					const FVector2D P = A + (B - A) * (Pk / 6.0);
					Iron.Box(FVector(P, FMath::Lerp(ZA, ZB, Pk / 6.0) + 0.66), FVector(0.01, 0.01, 0.52), Yaw);
				}
			}
		}
	}

	/** pc/shore-residential: a runabout under its fitted cover, as most boats on a Ray Hubbard lift sit: a hull from the
	 *  transom at Base to the bow along Fwd, Len long, Beam wide, from the keel at Z0, the cover's crown Hgt above it. */
	void CoveredBoat(FKitSection& Hull, FKitSection& Cover, const FVector2D& Base, const FVector2D& Fwd, double Len, double Beam, double Z0, double Hgt)
	{
		const FVector2D R(-Fwd.Y, Fwd.X);
		// Half beams at the transom, the shoulder, near the bow and the stem, at the chine (low) and the gunwale (high).
		const double X[4] = { 0.0, 0.62 * Len, 0.88 * Len, Len };
		const double WG[4] = { 0.5 * Beam, 0.5 * Beam, 0.36 * Beam, 0.04 };
		const double WC[4] = { 0.4 * Beam, 0.38 * Beam, 0.22 * Beam, 0.02 };
		const double ZG = Z0 + 0.75, ZC = Z0 + 0.25, ZT = Z0 + Hgt;
		auto P = [&](double Xi, double Yi, double Zi) { return FVector(Base + Fwd * Xi + R * Yi, Zi); };
		for (int32 I = 0; I < 3; ++I)
		{
			for (const double Sd : { -1.0, 1.0 })
			{
				const FVector Out(R * Sd, 0.0);
				FacedQuad(Hull, P(X[I], Sd * WC[I], ZC), P(X[I + 1], Sd * WC[I + 1], ZC), P(X[I + 1], Sd * WG[I + 1], ZG), P(X[I], Sd * WG[I], ZG), Out,
					{ X[I], 0 }, { X[I + 1], 0 }, { X[I + 1], 0.5 }, { X[I], 0.5 });
				FacedQuad(Hull, P(X[I], 0.0, Z0 + 0.1 * I), P(X[I + 1], 0.0, Z0 + 0.1 * (I + 1)), P(X[I + 1], Sd * WC[I + 1], ZC), P(X[I], Sd * WC[I], ZC), Out - FVector(0, 0, 1),
					{ X[I], 0 }, { X[I + 1], 0 }, { X[I + 1], 0.4 }, { X[I], 0.4 });
				// The cover: from just over the gunwale up to its crown along the centreline, falling toward the bow.
				const double ZTi = FMath::Lerp(ZT, ZG + 0.05, FMath::Square(X[I] / Len)), ZTj = FMath::Lerp(ZT, ZG + 0.05, FMath::Square(X[I + 1] / Len));
				FacedQuad(Cover, P(X[I], Sd * (WG[I] + 0.04), ZG - 0.08), P(X[I + 1], Sd * (WG[I + 1] + 0.04), ZG - 0.08), P(X[I + 1], 0.0, ZTj), P(X[I], 0.0, ZTi), Out + FVector(0, 0, 1),
					{ X[I], 0 }, { X[I + 1], 0 }, { X[I + 1], 1 }, { X[I], 1 });
			}
		}
		// The transom and the cover's back.
		FacedQuad(Hull, P(0, -WC[0], ZC), P(0, WC[0], ZC), P(0, WG[0], ZG), P(0, -WG[0], ZG), FVector(-Fwd, 0.0), { 0, 0 }, { Beam, 0 }, { Beam, 0.5 }, { 0, 0.5 });
		FacedQuad(Cover, P(-0.02, -WG[0] - 0.04, ZG - 0.08), P(-0.02, WG[0] + 0.04, ZG - 0.08), P(-0.02, 0.0, ZT), P(-0.02, 0.0, ZT), FVector(-Fwd, 0.0), { 0, 0 }, { Beam, 0 }, { Beam * 0.5, 0.6 }, { Beam * 0.5, 0.6 });
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
				// pc/shore-residential: a gutter along the fascia and a downspout down the wall's corner.
				if (bFull && !H.bCommercial)
				{
					Met.Span(FVector2D(E0) + Outs[S] * 0.07, FVector2D(E1) + Outs[S] * 0.07, 0.12f, float(ZE - 0.3), float(ZE - 0.16));
					const FVector2D DP = Cw[S] + Outs[S] * 0.06 + (Cw[(S + 1) % 4] - Cw[S]).GetSafeNormal() * 0.15;
					Met.Box(FVector(DP, 0.5 * (G + ZE - 0.3)), FVector(0.045, 0.045, 0.5 * (ZE - 0.3 - G)), float(FMath::RadiansToDegrees(FMath::Atan2(Outs[S].Y, Outs[S].X))));
				}
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
		FVector2D GarageAt = FVector2D::ZeroVector, GarageOut = FVector2D::ZeroVector;
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
					GarageAt = Run.P0 + T * (U + 0.5 * W);
					GarageOut = N * (0.5 * W);   // its direction, and half the door's width in its length
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
		if (H.bCommercial || bTall || OnDeck) continue;

		// pc/shore-residential (docs/near-shore-audit/phase-1): the lot round a house in the full-detail band. A North Texas
		// lakefront lot faces the water with a covered patio or a raised deck, fences its sides, runs a path down the lawn,
		// holds its bank with a concrete bulkhead or riprap, and keeps a boat in a covered slip on a lift.
		// All in the looks a house tile already carries (each new look was another material section on every one of the 553
		// tiles: 4 ms of game thread and 1.3 of render thread at the helm, wherever the camera was). Timber and iron are the
		// wall look painted (stained lap boards, black stucco), the bank is concrete, the boat's hull trim.
		FKitSection& Deck = Wall;
		FKitSection& Pile = Wall;
		FKitSection& Rip = Conc;
		FKitSection& Iron = Wall;
		FKitSection& Pale = Trim;
		const FColor WoodPaint = [&] { FColor C = Srgb(FLinearColor(0.30f, 0.21f, 0.13f) * (0.75f + 0.5f * Hash01(K, 58))); C.A = Siding; return C; }();
		Wall.Paint = WoodPaint; Wall.Tag = FVector2D(2.4, 0.5);
		const FVector2D Water = -Street, Across(-Street.Y, Street.X), Ctr(H.X, H.Y);
		const float WaterYaw = float(FMath::RadiansToDegrees(FMath::Atan2(Water.Y, Water.X)));
		auto Up = [](FKitSection& S, const FVector& A, const FVector& B, const FVector& C, const FVector& D)
		{
			FacedQuad(S, A, B, C, D, FVector::UpVector, { 0, 0 }, { float(FVector::Dist(A, B)), 0 }, { float(FVector::Dist(A, B)), float(FVector::Dist(B, C)) }, { 0, float(FVector::Dist(B, C)) });
		};
		// The house's reach toward the water and to either side of it, all wings.
		double Front = 0.0, SideW = 0.0;
		for (const FWingFrame& F : Wings)
		{
			for (int32 Cn = 0; Cn < 4; ++Cn)
			{
				const FVector2D P = F.At((Cn & 1) ? F.HL : -F.HL, (Cn & 2) ? F.HW : -F.HW) - Ctr;
				Front = FMath::Max(Front, FVector2D::DotProduct(P, Water));
				SideW = FMath::Max(SideW, FMath::Abs(FVector2D::DotProduct(P, Across)));
			}
		}
		// The shore straight out from the house's front (metres from its centre), if there's one within reach of a lawn.
		double Shore = -1.0;
		for (double D = Front + 2.0; D < Front + 70.0; D += 1.0)
		{
			if (Terr.HeightAt(Ctr.X + Water.X * D, Ctr.Y + Water.Y * D) < -0.05) { Shore = D; break; }
		}
		// The driveway: concrete from the garage door out toward the street, following the ground.
		if (GarageOut.SizeSquared() > 0.0)
		{
			const double HalfW = GarageOut.Size() + 0.3;
			const FVector2D N = GarageOut.GetSafeNormal(), T(-N.Y, N.X);
			for (int32 Sg = 0; Sg < 4; ++Sg)
			{
				const FVector2D A = GarageAt + N * (0.1 + 2.0 * Sg), B = GarageAt + N * (0.1 + 2.0 * (Sg + 1));
				const double ZA = FMath::Max(double(Terr.HeightAt(A.X, A.Y)), 0.2) + 0.04, ZB = FMath::Max(double(Terr.HeightAt(B.X, B.Y)), 0.2) + 0.04;
				Up(Conc, FVector(A - T * HalfW, Sg == 0 ? G + 0.04 : ZA), FVector(A + T * HalfW, Sg == 0 ? G + 0.04 : ZA), FVector(B + T * HalfW, ZB), FVector(B - T * HalfW, ZB));
			}
		}
		// The patio or deck on the main wing's wall that faces the water.
		int32 BackRun = INDEX_NONE;
		double BestDot = 0.6;
		for (int32 Ri = 0; Ri < Runs.Num(); ++Ri)
		{
			const double Dp = FVector2D::DotProduct(Runs[Ri].Out, Water);
			if (Runs[Ri].Wing == 0 && Dp > BestDot) { BestDot = Dp; BackRun = Ri; }
		}
		if (BackRun != INDEX_NONE && Hash01(K, 40) < 0.85f)
		{
			const FWallRun& Run = Runs[BackRun];
			const FVector2D T = (Run.P1 - Run.P0).GetSafeNormal(), N = Run.Out;
			const double L = FVector2D::Distance(Run.P0, Run.P1);
			const double Lp = FMath::Min(L * (0.45 + 0.3 * Hash01(K, 41)), 9.0), Dp = 3.0 + 1.4 * Hash01(K, 42);
			const double U0 = 0.5 + (L - Lp - 1.0) * Hash01(K, 43);
			const FVector2D A0 = Run.P0 + T * U0, A1 = A0 + T * Lp, F0 = A0 + N * Dp, F1 = A1 + N * Dp;
			bool bClear = Lp > 2.5 && Terr.HeightAt(0.5 * (F0.X + F1.X), 0.5 * (F0.Y + F1.Y)) > 0.3;
			for (int32 Wj = 1; Wj < Wings.Num() && bClear; ++Wj) bClear = !Wings[Wj].Contains(0.5 * (A0 + F1), -0.2);
			const float PostYaw = float(FMath::RadiansToDegrees(FMath::Atan2(T.Y, T.X)));
			if (bClear && Hash01(K, 44) < 0.6f)
			{
				// A covered patio: slab, posts and beam, and a shed roof off the wall below the eave.
				const double Zs = G + 0.12, Zt = FMath::Min(G + 2.75, E - 0.35), Zw = FMath::Min(Zt + 0.22 * Dp, E - 0.12);
				Up(Conc, FVector(A0, Zs), FVector(A1, Zs), FVector(F1, Zs), FVector(F0, Zs));
				WallQuad(Conc, F0, F1, Base, Zs, N, 0.0, G);
				const int32 Posts = FMath::Max(2, FMath::RoundToInt32(Lp / 3.5) + 1);
				for (int32 Pt = 0; Pt < Posts; ++Pt)
				{
					const FVector2D P = F0 - N * 0.18 + T * (0.15 + (Lp - 0.3) * Pt / (Posts - 1));
					Trim.Box(FVector(P, 0.5 * (Zs + Zt)), FVector(0.1, 0.1, 0.5 * (Zt - Zs)), PostYaw);
				}
				Trim.Span(F0 - N * 0.18, F1 - N * 0.18, 0.2f, float(Zt - 0.28), float(Zt));
				const FVector2D G0 = F0 + N * 0.3, G1 = F1 + N * 0.3;
				RoofPlane(Roof, FVector(G0, Zt), FVector(G1, Zt), FVector(A1, Zw), FVector(A0, Zw));
				WallQuad(Trim, G0, G1, Zt - 0.18, Zt, N, 0.0, Zt);
				FacedQuad(Trim, FVector(G0, Zt - 0.02), FVector(G1, Zt - 0.02), FVector(A1, Zw - 0.02), FVector(A0, Zw - 0.02), -FVector::UpVector, { 0, 0 }, { 1, 0 }, { 1, 1 }, { 0, 1 });
				// A sliding glass door out onto it.
				Wall.Paint = FColor(30, 32, 34, Glass);
				WallQuad(Wall, A0 + T * (0.5 * Lp - 1.2) + N * 0.016, A0 + T * (0.5 * Lp + 1.2) + N * 0.016, Zs, Zs + 2.1, N, 0.0, G);
				Wall.Paint = WoodPaint;
			}
			else if (bClear)
			{
				// A raised timber deck: boards on joists, posts to the ground, a rail round its open sides and steps down.
				const double Zd = G + 0.5 + 0.5 * Hash01(K, 45), Dd = Dp + 0.8;
				const FVector2D D0 = A0 + N * Dd, D1 = A1 + N * Dd;
				Deck.Box(FVector(0.5 * (A0 + D1), Zd - 0.05), FVector(0.5 * Lp, 0.5 * Dd, 0.05), PostYaw);
				for (const FVector2D& P : { D0, D1, 0.5 * (D0 + D1), A0 + N * 0.5 * Dd, A1 + N * 0.5 * Dd })
				{
					const double Zg = Terr.HeightAt(P.X, P.Y);
					Pile.Box(FVector(P, 0.5 * (Zg + Zd)), FVector(0.08, 0.08, 0.5 * FMath::Max(Zd - Zg, 0.1)), PostYaw);
				}
				for (const TPair<FVector2D, FVector2D>& Rail : { TPair<FVector2D, FVector2D>(D0, D1), TPair<FVector2D, FVector2D>(A0 + N * 0.05, D0), TPair<FVector2D, FVector2D>(A1 + N * 0.05, D1) })
				{
					Pile.Span(Rail.Key, Rail.Value, 0.08f, float(Zd + 0.9), float(Zd + 0.98));
					const double Rl = FVector2D::Distance(Rail.Key, Rail.Value);
					for (double U = 0.0; U <= Rl; U += 1.6)
					{
						Pile.Box(FVector(Rail.Key + (Rail.Value - Rail.Key) * (U / Rl), Zd + 0.45), FVector(0.04, 0.04, 0.45), PostYaw);
					}
				}
			}
		}
		// The rest needs the water within a lawn's reach.
		if (Shore < 0.0) continue;
		// Side fences down the lot toward the water, on most lots: board fences or black iron (the lake side stays open).
		if (Hash01(K, 46) < 0.7f)
		{
			const bool bWood = Hash01(K, 47) < 0.45f;
			const double D0 = 0.2 * Front, D1 = Shore - 3.0;
			if (D1 - D0 > 4.0)
			{
				for (const double Sd : { -1.0, 1.0 })
				{
					if (Hash01(K, 48 + (Sd > 0.0 ? 1 : 0)) < 0.35f) continue;
					const double Off = Sd * (SideW + 2.5 + 2.5 * Hash01(K, 50));
					if (!bWood) Iron.Paint = FColor(14, 14, 15, Stucco);
					Fence(Pile, Iron, Terr, Ctr + Across * Off + Water * D0, Ctr + Across * Off + Water * D1, bWood, 0.25);
					Wall.Paint = WoodPaint;
				}
			}
		}
		// The waterline along the lot: from points across it, the first wet sample marching out.
		const double Half = FMath::Clamp(SideW + 5.0, 8.0, 18.0);
		TArray<FVector2D, TInlineAllocator<20>> Line;
		for (double S = -Half; S <= Half + 0.01; S += 2.0)
		{
			for (double D = Shore - 10.0; D < Shore + 10.0; D += 0.5)
			{
				const FVector2D P = Ctr + Across * S + Water * D;
				if (Terr.HeightAt(P.X, P.Y) < -0.02) { Line.Add(P); break; }
			}
		}
		const float Edge = Hash01(K, 51);
		// A concrete path down the lawn to the water (or to the dock).
		if (Hash01(K, 52) < 0.6f)
		{
			const FVector2D S0 = Ctr + Water * (Front + 0.5) + Across * ((Hash01(K, 53) - 0.5) * SideW);
			const double Len = Shore - Front - 2.5;
			const int32 Sg = FMath::Max(1, FMath::FloorToInt32(Len / 2.0));
			for (int32 I = 0; I < Sg; ++I)
			{
				const FVector2D A = S0 + Water * (Len * I / Sg), B = S0 + Water * (Len * (I + 1) / Sg);
				const double ZA = Terr.HeightAt(A.X, A.Y) + 0.03, ZB = Terr.HeightAt(B.X, B.Y) + 0.03;
				if (ZA < 0.2 || ZB < 0.2) break;
				Up(Conc, FVector(A - Across * 0.5, ZA), FVector(A + Across * 0.5, ZA), FVector(B + Across * 0.5, ZB), FVector(B - Across * 0.5, ZB));
			}
		}
		if (Line.Num() < 3 || Edge > 0.85f) continue;   // a natural bank on some
		// The bank: a concrete bulkhead (most of the lake's developed shore) or riprap.
		const bool bBulkhead = Edge < 0.55f;
		for (int32 I = 0; I + 1 < Line.Num(); ++I)
		{
			const FVector2D A = Line[I], B = Line[I + 1];
			if (FVector2D::Distance(A, B) > 4.5) continue;
			FVector2D N = FVector2D(-(B - A).Y, (B - A).X).GetSafeNormal();
			if (FVector2D::DotProduct(N, Water) < 0.0) N = -N;
			if (bBulkhead)
			{
				const double Top = 0.5;
				WallQuad(Conc, A, B, -0.7, Top, N, 0.0, -0.7);
				Conc.Span(A - N * 0.15, B - N * 0.15, 0.34f, float(Top), float(Top + 0.12));
				// The fill behind it up to the lawn, so the cap doesn't stand alone as a kerb.
				const double ZA = Terr.HeightAt((A - N * 2.0).X, (A - N * 2.0).Y), ZB = Terr.HeightAt((B - N * 2.0).X, (B - N * 2.0).Y);
				Up(Conc, FVector(A - N * 0.3, Top + 0.12), FVector(B - N * 0.3, Top + 0.12), FVector(B - N * 2.0, FMath::Max(ZB, Top + 0.05)), FVector(A - N * 2.0, FMath::Max(ZA, Top + 0.05)));
			}
			else
			{
				// Riprap: a pile of stones down the bank, in steps so its face is broken, not a paved slope.
				for (int32 St = 0; St < 3; ++St)
				{
					const double I0 = 1.8 - 1.07 * St, I1 = I0 - 1.07, Z0 = -0.55 + 0.38 * St, Z1 = Z0 + 0.38;
					Up(Rip, FVector(A + N * I0, Z0), FVector(B + N * I0, Z0), FVector(B + N * I1, Z1), FVector(A + N * I1, Z1));
					Rip.Span(A + N * (I1 + 0.15), B + N * (I1 + 0.15), 0.4f, float(Z1 - 0.12), float(Z1 + 0.08));
				}
			}
		}
		// A boathouse on a third of the banked lots with water deep enough a few metres out, and none of the map's own docks
		// near: a walk out on piles, a U of decking round a slip, a gable roof, and the boat on its lift under a cover.
		if (Hash01(K, 54) > 0.35f) continue;
		const FVector2D Sp = Line[Line.Num() / 2];
		bool bDocked = false;
		for (const FLakeDock& Dk : Lake.Docks)
		{
			for (const FVector2D& P : Dk.Points) if (FVector2D::DistSquared(P, Sp) < 30.0 * 30.0) { bDocked = true; break; }
			if (bDocked) break;
		}
		const FVector2D Deep = Sp + Water * 10.0;
		if (bDocked || Terr.HeightAt(Deep.X, Deep.Y) > -0.7) continue;
		const double Zd = 1.0;
		Deck.Box(FVector(Sp + Water * 3.0, Zd - 0.06), FVector(3.0, 0.7, 0.06), WaterYaw);
		const FVector2D B0 = Sp + Water * 6.0;
		Deck.Box(FVector(B0 + Water * 0.7, Zd - 0.06), FVector(0.7, 3.8, 0.06), WaterYaw);
		for (const double Sd : { -1.0, 1.0 }) Deck.Box(FVector(B0 + Water * 5.4 + Across * (Sd * 3.2), Zd - 0.06), FVector(4.0, 0.6, 0.06), WaterYaw);
		for (double D = 0.6; D < 9.5; D += 3.0)
		{
			for (const double Sd : { -1.0, 1.0 })
			{
				Pile.Cylinder(FVector(Sp + Water * FMath::Min(D, 5.6) + Across * (Sd * 0.6), -2.0), 0.12f, float(Zd + 1.94), 6);
				Pile.Cylinder(FVector(B0 + Water * (D + 0.3) + Across * (Sd * 3.5), -2.0), 0.13f, float(Zd + 1.94), 6);
			}
		}
		// The roof on posts at the fingers' corners: ridge along the slip.
		const double Zr = Zd + 2.9, Rise = 1.5, Wr = 4.2, Lr = 9.6;
		for (const double D : { 0.2, 0.5 * Lr, Lr - 0.2 })
		{
			for (const double Sd : { -1.0, 1.0 }) Trim.Box(FVector(B0 + Water * D + Across * (Sd * 3.6), 0.5 * (Zd + Zr)), FVector(0.09, 0.09, 0.5 * (Zr - Zd)), WaterYaw);
		}
		const FVector RA(B0 - Water * 0.3 - Across * Wr, Zr), RB(B0 + Water * Lr - Across * Wr, Zr), RC(B0 + Water * Lr + Across * Wr, Zr), RD(B0 - Water * 0.3 + Across * Wr, Zr);
		const FVector R0(B0 - Water * 0.3, Zr + Rise), R1(B0 + Water * Lr, Zr + Rise);
		Roof.Paint = Srgb(FLinearColor(0.22f, 0.21f, 0.2f) * (0.8f + 0.4f * Hash01(K, 55))); Roof.Paint.A = Hash01(K, 56) < 0.5f ? Metal : Shingle;
		RoofPlane(Roof, RA, RB, R1, R0);
		RoofPlane(Roof, RC, RD, R0, R1);
		for (const double Sd : { -1.0, 1.0 })
		{
			const FVector2D E0 = B0 + Across * (Sd * Wr) - Water * 0.3, E1 = B0 + Across * (Sd * Wr) + Water * Lr;
			WallQuad(Trim, E0, E1, Zr - 0.2, Zr, Across * Sd, 0.0, Zr);
		}
		// The lift's cradle and the boat on it, covered.
		const double Zk = Zd - 0.15;
		for (const double D : { 2.0, 6.0 }) Met.Span(B0 + Water * (1.5 + D) - Across * 2.6, B0 + Water * (1.5 + D) + Across * 2.6, 0.15f, float(Zk - 0.15), float(Zk));
		// The cover is canvas: navy, tan, forest green or grey (the roof look's membrane finish, coloured per vertex).
		static const FLinearColor Canvas[] = { FLinearColor(0.03f, 0.05f, 0.12f), FLinearColor(0.42f, 0.36f, 0.25f), FLinearColor(0.05f, 0.12f, 0.06f), FLinearColor(0.25f, 0.26f, 0.27f) };
		Roof.Paint = Srgb(Canvas[HouseHash(K, 57) % UE_ARRAY_COUNT(Canvas)]); Roof.Paint.A = Membrane;
		CoveredBoat(Pale, Roof, B0 + Water * 1.6, Water, 6.8, 2.4, Zk, 1.35);
	}
}
