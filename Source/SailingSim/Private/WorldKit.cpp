#include "WorldKit.h"
#include "SailingSim.h"
#include "LakeData.h"
#include "Marina.h"
#include "MarinaActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#if WITH_EDITOR
#include "AssetRegistry/AssetRegistryModule.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#endif

const FKitLookDesc& KitLook(EKitLook Look)
{
	static const FKitLookDesc Looks[int32(EKitLook::Count)] = {
		{ TEXT("Decking"), FLinearColor(0.42f, 0.40f, 0.36f), 0.85f, 1.f, 0.f, 0.f },   // weathered composite decking
		{ TEXT("Floats"), FLinearColor(0.05f, 0.05f, 0.05f), 0.6f, 0.f, 0.f, 0.f },     // black polyethylene floats
		{ TEXT("Pilings"), FLinearColor(0.32f, 0.27f, 0.21f), 0.9f, 4.f, 0.f, 0.f },    // treated pine pilings
		{ TEXT("Metal"), FLinearColor(0.75f, 0.76f, 0.78f), 0.3f, 0.f, 0.f, 1.f },      // galvanized cleats and caps
		{ TEXT("White"), FLinearColor(0.85f, 0.86f, 0.84f), 0.45f, 0.f, 0.f, 0.f },     // dock boxes, pedestals
		{ TEXT("Siding"), FLinearColor(0.78f, 0.74f, 0.64f), 0.75f, 3.f, 1.f, 0.f },    // lap siding with windows
		{ TEXT("Roof"), FLinearColor(0.20f, 0.20f, 0.21f), 0.8f, 2.f, 0.f, 0.f },       // asphalt shingles
		{ TEXT("Concrete"), FLinearColor(0.62f, 0.60f, 0.56f), 0.85f, 4.f, 0.f, 0.f },  // concrete
		{ TEXT("PoolWater"), FLinearColor(0.10f, 0.45f, 0.55f), 0.05f, 0.f, 0.f, 0.f }, // pool
		{ TEXT("Trim"), FLinearColor(0.88f, 0.88f, 0.86f), 0.5f, 0.f, 0.f, 0.f },       // white trim and rails
		{ TEXT("Lamp"), FLinearColor(0.15f, 0.15f, 0.15f), 0.5f, 5.f, 0.f, 0.5f },      // painted steel lamp posts
		{ TEXT("Asphalt"), FLinearColor(0.11f, 0.11f, 0.11f), 0.9f, 6.f, 0.f, 0.f },    // road surface with lane markings
		{ TEXT("Steel"), FLinearColor(0.30f, 0.36f, 0.40f), 0.55f, 5.f, 0.f, 0.6f },    // painted steel girders
		{ TEXT("LampGlow"), FLinearColor(1.0f, 0.78f, 0.50f), 0.4f, 0.f, 0.f, 0.f },    // sodium/LED lamp heads (glow at night)
		{ TEXT("Riprap"), FLinearColor(0.50f, 0.47f, 0.42f), 0.9f, 7.f, 0.f, 0.f },     // granite and limestone riprap
		{ TEXT("HouseWall"), FLinearColor(0.7f, 0.66f, 0.58f), 0.8f, 0.f, 0.f, 0.f },   // M_HouseKitWall: colour and finish per vertex
		{ TEXT("HouseRoof"), FLinearColor(0.2f, 0.2f, 0.2f), 0.85f, 0.f, 0.f, 0.f },    // M_HouseKitRoof: NAIP roof colour per vertex
	};
	return Looks[int32(Look)];
}

UMaterialInterface* KitMaterial(EKitLook Look)
{
	const TCHAR* Name = KitLook(Look).Name;
	return LoadObject<UMaterialInterface>(nullptr, *FString::Printf(TEXT("/Game/World/MI_World_%s.MI_World_%s"), Name, Name));
}

void FKitSection::Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector2D& UA, const FVector2D& UB, const FVector2D& UC, const FVector2D& UD)
{
	const int32 I = V.Num();
	const FVector Nrm = FVector::CrossProduct(D - A, B - A).GetSafeNormal();
	const FProcMeshTangent Tg((B - A).GetSafeNormal(), false);
	for (const FVector& P : { A, B, C, D }) { V.Add(P * 100.0); N.Add(Nrm); Tan.Add(Tg); Col.Add(Paint); UV1.Add(Tag); }
	UV.Append({ UA, UB, UC, UD });
	T.Append({ I, I + 1, I + 2, I, I + 2, I + 3 });
}

void FKitSection::Box(const FVector& C, const FVector& E, float YawDeg, bool bBottom)
{
	const FRotator R(0.f, YawDeg, 0.f);
	auto P = [&](float X, float Y, float Z) { return C + R.RotateVector(FVector(X * E.X, Y * E.Y, Z * E.Z)); };
	const float LX = 2.f * E.X, LY = 2.f * E.Y, LZ = 2.f * E.Z;
	Quad(P(-1, -1, 1), P(-1, 1, 1), P(1, 1, 1), P(1, -1, 1), { 0, 0 }, { LY, 0 }, { LY, LX }, { 0, LX });
	if (bBottom) Quad(P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1), { 0, 0 }, { LX, 0 }, { LX, LY }, { 0, LY });
	Quad(P(-1, -1, -1), P(-1, 1, -1), P(-1, 1, 1), P(-1, -1, 1), { 0, 0 }, { LY, 0 }, { LY, LZ }, { 0, LZ });
	Quad(P(1, 1, -1), P(1, -1, -1), P(1, -1, 1), P(1, 1, 1), { 0, 0 }, { LY, 0 }, { LY, LZ }, { 0, LZ });
	Quad(P(1, -1, -1), P(-1, -1, -1), P(-1, -1, 1), P(1, -1, 1), { 0, 0 }, { LX, 0 }, { LX, LZ }, { 0, LZ });
	Quad(P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1), { 0, 0 }, { LX, 0 }, { LX, LZ }, { 0, LZ });
}

void FKitSection::Span(const FVector2D& A, const FVector2D& B, float W, float Z0, float Z1, bool bBottom)
{
	const FVector2D M = 0.5 * (A + B);
	const FVector2D D = B - A;
	Box(FVector(M.X, M.Y, 0.5f * (Z0 + Z1)), FVector(0.5f * D.Size(), 0.5f * W, 0.5f * (Z1 - Z0)), float(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X))), bBottom);
}

void FKitSection::Cylinder(const FVector& Base, float Radius, float Height, int32 Sides)
{
	for (int32 K = 0; K < Sides; ++K)
	{
		const float A0 = 2.f * UE_PI * K / Sides, A1 = 2.f * UE_PI * (K + 1) / Sides;
		const FVector P0(FMath::Cos(A0) * Radius, FMath::Sin(A0) * Radius, 0.f), P1(FMath::Cos(A1) * Radius, FMath::Sin(A1) * Radius, 0.f);
		const float U0 = Radius * A0, U1 = Radius * A1;
		Quad(Base + P1, Base + P0, Base + P0 + FVector(0, 0, Height), Base + P1 + FVector(0, 0, Height), { U1, 0 }, { U0, 0 }, { U0, Height }, { U1, Height });
		const int32 I = N.Num() - 4;
		N[I] = N[I + 3] = P1.GetSafeNormal();
		N[I + 1] = N[I + 2] = P0.GetSafeNormal();
	}
}

int32 FKitGeometry::NumQuads() const
{
	int32 Q = 0;
	for (const FKitSection& S : Sections) Q += S.V.Num() / 4;
	return Q;
}

void FKitGeometry::SplitTiles(double TileM, TMap<FIntPoint, FKitGeometry>& Out) const
{
	const double TileCm = TileM * 100.0;
	for (int32 K = 0; K < int32(EKitLook::Count); ++K)
	{
		const FKitSection& Src = Sections[K];
		for (int32 Q = 0; Q + 3 < Src.V.Num(); Q += 4)
		{
			const FVector C = 0.25 * (Src.V[Q] + Src.V[Q + 1] + Src.V[Q + 2] + Src.V[Q + 3]);
			FKitSection& D = Out.FindOrAdd(FIntPoint(FMath::FloorToInt32(C.X / TileCm), FMath::FloorToInt32(C.Y / TileCm))).Sections[K];
			const int32 I = D.V.Num();
			for (int32 J = 0; J < 4; ++J)
			{
				D.V.Add(Src.V[Q + J]); D.N.Add(Src.N[Q + J]); D.UV.Add(Src.UV[Q + J]); D.Tan.Add(Src.Tan[Q + J]);
				D.Col.Add(Src.Col[Q + J]); D.UV1.Add(Src.UV1[Q + J]);
			}
			D.T.Append({ I, I + 1, I + 2, I, I + 2, I + 3 });
		}
	}
}

FString FKitGeometry::TileAssetName(const FString& Prefix, const FIntPoint& Tile)
{
	auto Num = [](int32 X) { return X < 0 ? FString::Printf(TEXT("m%d"), -X) : FString::FromInt(X); };
	return FString::Printf(TEXT("SM_%s_%s_%s"), *Prefix, *Num(Tile.X), *Num(Tile.Y));
}

int32 SpawnKitTiles(AActor* Owner, const TMap<FIntPoint, FKitGeometry>& Tiles, const FString& Prefix, bool bProcedural,
	TFunctionRef<UMaterialInterface*(EKitLook)> Material, TArray<TObjectPtr<UPrimitiveComponent>>& Out, EComponentMobility::Type Mobility)
{
	int32 Baked = 0;
	for (const auto& KV : Tiles)
	{
		const FString Name = FKitGeometry::TileAssetName(Prefix, KV.Key);
		UStaticMesh* Mesh = bProcedural ? nullptr : LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Baked/%s.%s"), *Name, *Name));
		if (Mesh)
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(Owner);
			C->SetMobility(Mobility);
			C->SetupAttachment(Owner->GetRootComponent());
			C->SetStaticMesh(Mesh);
			C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->RegisterComponent();
			Out.Add(C);
			++Baked;
			continue;
		}
		// No Nanite: on High a big procedural layout overflows the virtual shadow map's non-Nanite marking (rebake instead).
		UProceduralMeshComponent* M = NewObject<UProceduralMeshComponent>(Owner);
		M->SetMobility(Mobility);
		M->SetupAttachment(Owner->GetRootComponent());
		M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		M->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		M->RegisterComponent();
		for (int32 K = 0; K < int32(EKitLook::Count); ++K)
		{
			const FKitSection& D = KV.Value.Sections[K];
			if (D.V.Num() == 0) continue;
			M->CreateMeshSection(K, D.V, D.T, D.N, D.UV, D.UV1, {}, {}, D.Col, D.Tan, false);
			M->SetMaterial(K, Material(EKitLook(K)));
		}
		Out.Add(M);
	}
	return Baked;
}

float BridgeWidth(const FLakeBridge& Br)
{
	if (Br.Kind.IsEmpty()) return 10.f; // charted bridges (S-57) carry no road class
	if (Br.Kind == TEXT("motorway") || Br.Kind == TEXT("construction") || Br.Kind == TEXT("trunk")) return 16.f;
	if (Br.Kind == TEXT("primary")) return 12.f;
	if (Br.Kind == TEXT("secondary") || Br.Kind == TEXT("tertiary")) return 10.f;
	if (Br.Kind == TEXT("motorway_link") || Br.Kind == TEXT("trunk_link") || Br.Kind == TEXT("primary_link") || Br.Kind == TEXT("residential")) return 8.f;
	return 0.f;
}

bool KitDrawsPiers(const FLakeData& Lake)
{
	double Length = 0.0;
	for (const FLakeDock& D : Lake.Docks)
	{
		if (D.Kind == TEXT("breakwater")) continue;
		for (int32 I = 1; I < D.Points.Num(); ++I) Length += FVector2D::Distance(D.Points[I - 1], D.Points[I]);
	}
	return Length < 50000.0;
}

void BuildShoreGeometry(const FLakeData& Lake, FKitGeometry& G)
{
	const bool bPiers = KitDrawsPiers(Lake);
	const FBox2D MarinaBox = Lake.Marina.Bounds();
	auto Jitter = [](const FVector2D& P, uint32 Salt)
	{
		uint32 X = uint32(int32(FMath::FloorToInt32(P.X * 0.5)) * 73856093) ^ uint32(int32(FMath::FloorToInt32(P.Y * 0.5)) * 19349663) ^ (Salt * 83492791u);
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return (X & 0xFFFF) / 65535.f - 0.5f;
	};
	for (const FLakeDock& D : Lake.Docks)
	{
		if (MarinaBox.bIsValid && MarinaBox.IsInside(D.Points[0])) continue;
		const bool bRiprap = D.Kind == TEXT("breakwater");
		if (!bRiprap && !bPiers) continue;
		if (bRiprap)
		{
			// Riprap: a rubble mound about 6 m across and 0.8 m above the water (the core: ABridgesActor piles boulders over
			// it on Medium and up), its cross-sections jittered every 3 m; it runs 1.5 m below the water.
			FKitSection& S = G[EKitLook::Riprap];
			for (int32 I = 1; I < D.Points.Num(); ++I)
			{
				const FVector2D A = D.Points[I - 1], B = D.Points[I];
				const double Len = FVector2D::Distance(A, B);
				if (Len < 0.5) continue;
				const FVector2D Dir = (B - A) / Len, Left(-Dir.Y, Dir.X);
				const int32 Steps = FMath::Max(1, int32(Len / 3.0));
				auto Section = [&](int32 K, FVector Out[5])
				{
					const FVector2D C = A + Dir * (Len * K / Steps);
					static const float Across[5] = { -3.2f, -1.6f, 0.f, 1.6f, 3.2f };
					static const float Up[5] = { -1.5f, 0.4f, 0.8f, 0.4f, -1.5f };   // Graphics G2: a core under the boulders
					for (int32 J = 0; J < 5; ++J)
					{
						const FVector2D P = C + Left * (Across[J] + 0.5f * Jitter(C, J * 7 + 1));
						Out[J] = FVector(P.X, P.Y, Up[J] + (J == 0 || J == 4 ? 0.f : 0.7f * Jitter(C, J * 7 + 2)));
					}
				};
				FVector Prev[5], Next[5];
				Section(0, Prev);
				for (int32 K = 1; K <= Steps; ++K)
				{
					Section(K, Next);
					const float U0 = float(Len * (K - 1) / Steps), U1 = float(Len * K / Steps);
					for (int32 J = 0; J < 4; ++J)
					{
						S.Quad(Prev[J], Prev[J + 1], Next[J + 1], Next[J], { U0, float(J) * 1.8f }, { U0, float(J + 1) * 1.8f }, { U1, float(J + 1) * 1.8f }, { U1, float(J) * 1.8f });
					}
					FMemory::Memcpy(Prev, Next, sizeof(Prev));
				}
			}
			continue;
		}
		// A private pier: 1.8 m of decking 0.6 m above the pool on pilings every 3 m, both sides.
		for (int32 I = 1; I < D.Points.Num(); ++I)
		{
			const FVector2D A = D.Points[I - 1], B = D.Points[I];
			const double Len = FVector2D::Distance(A, B);
			if (Len < 0.3) continue;
			const FVector2D Dir = (B - A) / Len, Left(-Dir.Y, Dir.X);
			const float W = D.bClosed ? 0.6f : 1.8f;  // closed outlines (platforms): a 0.6 m rim board round the edge
			G[EKitLook::Decking].Span(A - Dir * 0.3, B + Dir * 0.3, W, 0.45f, 0.6f, true);
			for (double X = 0.0; X <= Len; X += 3.0)
			{
				for (const double Side : { -1.0, 1.0 })
				{
					const FVector2D P = A + Dir * X + Left * (Side * (0.5 * W - 0.1));
					G[EKitLook::Pilings].Cylinder(FVector(P.X, P.Y, -2.5f), 0.12f, 3.4f, 6);
				}
			}
		}
	}
}

float BridgeRoadZ(const FLakeBridge& Br) { return float(Br.DeckHeight) + 0.33f; }

void BuildBridgeGeometry(const FLakeData& Lake, FKitGeometry& G)
{
	for (const FLakeBridge& Br : Lake.Bridges)
	{
		const bool bRail = Br.Kind == TEXT("rail");
		const float Road = BridgeWidth(Br);
		const bool bFoot = !bRail && Road == 0.f;
		const float W = bRail ? 5.f : (bFoot ? 3.f : Road + 1.2f);
		const float Z0 = float(Br.DeckHeight);               // underside of the slab
		const float GirderDepth = bRail ? 1.5f : (bFoot ? 0.4f : 0.9f);
		const float Bottom = Z0 - GirderDepth;               // where a mast strikes (FLakeData::BuildObstacles: deck - 1 m)
		const float Spacing = bFoot ? 6.f : (bRail ? 20.f : (Road >= 16.f ? 36.f : 30.f));
		double Along = 0.0, NextPier = 0.0, NextLamp = 20.0;
		for (int32 I = 1; I < Br.Points.Num(); ++I)
		{
			const FVector2D A = Br.Points[I - 1], B = Br.Points[I];
			const double Len = FVector2D::Distance(A, B);
			if (Len < 0.5) continue;
			const FVector2D Dir = (B - A) / Len, Left(-Dir.Y, Dir.X);
			// Carry the deck a little past each joint so bends close up.
			const FVector2D A1 = A - Dir * 0.4, B1 = B + Dir * 0.4;
			if (bFoot)
			{
				G[EKitLook::Decking].Span(A1, B1, W, Z0, Z0 + 0.15f, true);
				G[EKitLook::Pilings].Span(A1 + Left * (0.5 * W - 0.2), B1 + Left * (0.5 * W - 0.2), 0.25f, Bottom, Z0);
				G[EKitLook::Pilings].Span(A1 - Left * (0.5 * W - 0.2), B1 - Left * (0.5 * W - 0.2), 0.25f, Bottom, Z0);
				for (const double Side : { -1.0, 1.0 })
				{
					G[EKitLook::Trim].Span(A1 + Left * (Side * (0.5 * W - 0.05)), B1 + Left * (Side * (0.5 * W - 0.05)), 0.08f, Z0 + 1.05f, Z0 + 1.15f);
				}
			}
			else
			{
				G[EKitLook::Concrete].Span(A1, B1, W, Z0, Z0 + 0.3f, true);
				if (bRail)
				{
					G[EKitLook::Concrete].Span(A1, B1, 3.6f, Z0 + 0.3f, Z0 + 0.6f);
					for (const double Side : { -0.72, 0.72 }) G[EKitLook::Metal].Span(A1 + Left * Side, B1 + Left * Side, 0.07f, Z0 + 0.6f, Z0 + 0.76f);
					for (const double Side : { -1.3, 1.3 }) G[EKitLook::Steel].Span(A1 + Left * Side, B1 + Left * Side, 0.5f, Bottom, Z0, true);
				}
				else
				{
					G[EKitLook::Asphalt].Span(A1 + Left * 0.0, B1, Road, Z0 + 0.3f, Z0 + 0.33f);
					const int32 Girders = FMath::Max(2, int32(W / 2.6f));
					for (int32 K = 0; K < Girders; ++K)
					{
						const double Off = (K + 0.5) / Girders * (W - 1.0) - 0.5 * (W - 1.0);
						G[EKitLook::Concrete].Span(A1 + Left * Off, B1 + Left * Off, 0.5f, Bottom, Z0, true);
					}
					// Jersey barriers: a wide foot and a narrower wall.
					for (const double Side : { -1.0, 1.0 })
					{
						const FVector2D O = Left * (Side * (0.5 * W - 0.3));
						G[EKitLook::Concrete].Span(A1 + O, B1 + O, 0.6f, Z0 + 0.3f, Z0 + 0.6f);
						G[EKitLook::Concrete].Span(A1 + O, B1 + O, 0.3f, Z0 + 0.6f, Z0 + 1.15f);
					}
				}
			}
			// Pier bents and lamp posts at their spacing along the whole way.
			while (NextPier <= Along + Len)
			{
				const FVector2D P = A + Dir * (NextPier - Along);
				NextPier += Spacing;
				const float Ground = float(Lake.Terrain.HeightAt(P.X, P.Y));
				if (Ground > Bottom - 0.5f) continue;              // on the embankment: no pier needed
				const float Bed = FMath::Min(Ground, 0.f) - 0.5f;
				const float Yaw = float(FMath::RadiansToDegrees(FMath::Atan2(Dir.Y, Dir.X)));
				if (bFoot)
				{
					for (const double Side : { -1.0, 1.0 })
					{
						const FVector2D Q = P + Left * (Side * (0.5 * W - 0.2));
						G[EKitLook::Pilings].Cylinder(FVector(Q.X, Q.Y, Bed), 0.15f, Bottom - Bed);
					}
					continue;
				}
				const int32 Cols = bRail ? 2 : (Road >= 16.f ? 3 : (Road >= 10.f ? 2 : 1));
				const float Radius = Cols == 1 ? 0.75f : (bRail ? 0.45f : 0.55f);
				for (int32 K = 0; K < Cols; ++K)
				{
					const double Off = Cols == 1 ? 0.0 : (double(K) / (Cols - 1) - 0.5) * (W - 3.0);
					const FVector2D Q = P + Left * Off;
					G[EKitLook::Concrete].Cylinder(FVector(Q.X, Q.Y, Bed), Radius, Bottom - 1.1f - Bed, 12);
				}
				G[EKitLook::Concrete].Box(FVector(P.X, P.Y, Bottom - 0.55f), FVector(1.f, 0.5f * (W - 0.6f), 0.55f), Yaw, true);
			}
			while (!bRail && !bFoot && Road >= 10.f && NextLamp <= Along + Len)
			{
				// Lamp posts on the left barrier every 60 m, arms reaching over the lanes.
				const FVector2D P = A + Dir * (NextLamp - Along) + Left * (0.5 * W - 0.3);
				NextLamp += 60.0;
				const float Top = Z0 + 11.f;
				G[EKitLook::Lamp].Cylinder(FVector(P.X, P.Y, Z0 + 1.15f), 0.12f, Top - Z0 - 1.15f, 6);
				const FVector2D Head = P - Left * 2.6;
				G[EKitLook::Lamp].Span(P, Head, 0.1f, Top - 0.1f, Top);
				G[EKitLook::LampGlow].Box(FVector(Head.X, Head.Y, Top - 0.16f), FVector(0.35f, 0.18f, 0.07f), float(FMath::RadiansToDegrees(FMath::Atan2(Dir.Y, Dir.X))), true);
				G.Lights.Add({ FVector(Head.X, Head.Y, Top - 0.4f), 0 });
			}
			Along += Len;
		}
	}
}

TArray<UStaticMesh*> UWorldKitLibrary::BakeBridges(const FString& LakeName)
{
	TArray<UStaticMesh*> Out;
#if WITH_EDITOR
	FLakeData Lake;
	if (!Lake.Load(FLakeData::DefaultDirectory(), LakeName)) return Out;
	FKitGeometry All;
	BuildBridgeGeometry(Lake, All);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(BridgeTileM, Tiles);
	for (const auto& KV : Tiles)
	{
		if (UStaticMesh* M = BakeMesh(KV.Value, TEXT("/Game/World/Baked/") + FKitGeometry::TileAssetName(TEXT("Bridges_") + LakeName, KV.Key))) Out.Add(M);
	}
	UE_LOG(LogSailing, Display, TEXT("Baked the %s bridges: %d quads in %d tiles"), *LakeName, All.NumQuads(), Out.Num());
#endif
	return Out;
}

TArray<UStaticMesh*> UWorldKitLibrary::BakeShore(const FString& LakeName)
{
	TArray<UStaticMesh*> Out;
#if WITH_EDITOR
	FLakeData Lake;
	if (!Lake.Load(FLakeData::DefaultDirectory(), LakeName)) return Out;
	FKitGeometry All;
	BuildShoreGeometry(Lake, All);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(ShoreTileM, Tiles);
	for (const auto& KV : Tiles)
	{
		if (UStaticMesh* M = BakeMesh(KV.Value, TEXT("/Game/World/Baked/") + FKitGeometry::TileAssetName(TEXT("Shore_") + LakeName, KV.Key))) Out.Add(M);
	}
	UE_LOG(LogSailing, Display, TEXT("Baked the %s shore: %d quads in %d tiles"), *LakeName, All.NumQuads(), Out.Num());
#endif
	return Out;
}

TArray<UStaticMesh*> UWorldKitLibrary::BakeHouses(const FString& LakeName)
{
	TArray<UStaticMesh*> Out;
#if WITH_EDITOR
	FLakeData Lake;
	if (!Lake.Load(FLakeData::DefaultDirectory(), LakeName) || Lake.Houses.Num() == 0) return Out;
	TMap<FIntPoint, TArray<int32>> Tiles;
	HouseTiles(Lake, Tiles);
	int64 Quads = 0;
	for (const auto& KV : Tiles)
	{
		FKitGeometry G;
		BuildHouseGeometry(Lake, KV.Value, G);
		Quads += G.NumQuads();
		if (UStaticMesh* M = BakeMesh(G, TEXT("/Game/World/Baked/") + FKitGeometry::TileAssetName(TEXT("Houses_") + LakeName, KV.Key))) Out.Add(M);
	}
	UE_LOG(LogSailing, Display, TEXT("Baked the %s houses: %d houses, %lld quads in %d tiles"), *LakeName, Lake.Houses.Num(), Quads, Out.Num());
#endif
	return Out;
}

TArray<UStaticMesh*> UWorldKitLibrary::BakeMarina(const FString& LakeName)
{
	TArray<UStaticMesh*> Out;
#if WITH_EDITOR
	FLakeData Lake;
	if (!Lake.Load(FLakeData::DefaultDirectory(), LakeName) || !Lake.Marina.IsLoaded()) return Out;
	FKitGeometry All;
	AMarinaActor::BuildGeometry(Lake.Marina, &Lake.Terrain, [](const FString&) { return true; }, All);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(TileM, Tiles);
	for (const auto& KV : Tiles)
	{
		if (UStaticMesh* M = BakeMesh(KV.Value, TEXT("/Game/World/Baked/") + FKitGeometry::TileAssetName(TEXT("Marina"), KV.Key))) Out.Add(M);
	}
	UE_LOG(LogSailing, Display, TEXT("Baked the %s marina: %d quads in %d tiles"), *LakeName, All.NumQuads(), Out.Num());
#endif
	return Out;
}

#if WITH_EDITOR
UStaticMesh* UWorldKitLibrary::BakeMesh(const FKitGeometry& Geometry, const FString& PackagePath)
{
	const FString Name = FPackageName::GetLongPackageAssetName(PackagePath);
	UPackage* Package = CreatePackage(*PackagePath);
	Package->FullyLoad();
	UStaticMesh* Mesh = FindObject<UStaticMesh>(Package, *Name);
	if (!Mesh) Mesh = NewObject<UStaticMesh>(Package, *Name, RF_Public | RF_Standalone);

	FMeshDescription MD;
	FStaticMeshAttributes Attr(MD);
	Attr.Register();
	TVertexAttributesRef<FVector3f> Positions = Attr.GetVertexPositions();
	TVertexInstanceAttributesRef<FVector3f> Normals = Attr.GetVertexInstanceNormals();
	TVertexInstanceAttributesRef<FVector3f> Tangents = Attr.GetVertexInstanceTangents();
	TVertexInstanceAttributesRef<float> Signs = Attr.GetVertexInstanceBinormalSigns();
	TVertexInstanceAttributesRef<FVector2f> UVs = Attr.GetVertexInstanceUVs();
	TPolygonGroupAttributesRef<FName> Slots = Attr.GetPolygonGroupMaterialSlotNames();
	// Graphics G6: a second UV channel and vertex colours for the looks that carry them (the houses).
	TVertexInstanceAttributesRef<FVector4f> Colors = Attr.GetVertexInstanceColors();
	UVs.SetNumChannels(2);
	Mesh->GetStaticMaterials().Reset();
	for (int32 K = 0; K < int32(EKitLook::Count); ++K)
	{
		const FKitSection& S = Geometry.Sections[K];
		if (S.V.Num() == 0) continue;
		const FKitLookDesc& Look = KitLook(EKitLook(K));
		const FName Slot(Look.Name);
		const FPolygonGroupID Group = MD.CreatePolygonGroup();
		Slots[Group] = Slot;
		UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, *FString::Printf(TEXT("/Game/World/MI_World_%s.MI_World_%s"), Look.Name, Look.Name));
		Mesh->GetStaticMaterials().Add(FStaticMaterial(Mat, Slot, Slot));
		TArray<FVertexInstanceID> Inst;
		Inst.Reserve(S.V.Num());
		for (int32 I = 0; I < S.V.Num(); ++I)
		{
			const FVertexID V = MD.CreateVertex();
			Positions[V] = FVector3f(S.V[I]);
			const FVertexInstanceID VI = MD.CreateVertexInstance(V);
			Normals[VI] = FVector3f(S.N[I]);
			Tangents[VI] = FVector3f(S.Tan[I].TangentX);
			Signs[VI] = 1.f;
			UVs.Set(VI, 0, FVector2f(S.UV[I]));
			UVs.Set(VI, 1, FVector2f(S.UV1[I]));
			Colors[VI] = FVector4f(FLinearColor::FromSRGBColor(S.Col[I]));
			Inst.Add(VI);
		}
		for (int32 I = 0; I + 2 < S.T.Num(); I += 3)
		{
			MD.CreatePolygon(Group, { Inst[S.T[I]], Inst[S.T[I + 1]], Inst[S.T[I + 2]] });
		}
	}
	Mesh->SetNumSourceModels(1);
	FStaticMeshSourceModel& Src = Mesh->GetSourceModel(0);
	Src.BuildSettings.bRecomputeNormals = false;
	Src.BuildSettings.bRecomputeTangents = false;
	Src.BuildSettings.bGenerateLightmapUVs = false;
	Src.BuildSettings.bUseFullPrecisionUVs = true;
	Mesh->CreateMeshDescription(0, MoveTemp(MD));
	Mesh->CommitMeshDescription(0);
	FMeshNaniteSettings Nanite = Mesh->GetNaniteSettings();
	Nanite.bEnabled = true;
	Mesh->SetNaniteSettings(Nanite);
	Mesh->Build(true);
	Mesh->PostEditChange();
	Mesh->MarkPackageDirty();
	FAssetRegistryModule::AssetCreated(Mesh);
	return Mesh;
}
#endif
