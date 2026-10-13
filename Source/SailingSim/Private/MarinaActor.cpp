#include "MarinaActor.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "LakeData.h"
#include "Marina.h"
#include "WorldKit.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/ConstructorHelpers.h"

using namespace Sailing;

namespace
{
	uint32 MHash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}
	float MRand(uint32 Seed) { return (MHash(Seed) & 0xFFFFFF) / float(0xFFFFFF); }

	TMap<FString, FString> LoadScans()
	{
		TMap<FString, FString> Out;
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectContentDir(), TEXT("World/Scans.json")))) return Out;
		TSharedPtr<FJsonObject> Root;
		if (FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root)
		{
			for (const auto& KV : Root->Values) Out.Add(FString(KV.Key), KV.Value->AsString());
		}
		return Out;
	}
}

AMarinaActor::AMarinaActor()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	// Nothing here moves: static components keep their cached virtual shadow pages (movable ones re-mark them every frame).
	RootComponent->SetMobility(EComponentMobility::Static);
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Surf(TEXT("/Game/World/M_WorldSurface.M_WorldSurface"));
	SurfaceMaterial = Surf.Object;
}

UMaterialInterface* AMarinaActor::Surface(const FLinearColor& Color, float Roughness, float Pattern, float Windows, float Metallic)
{
	UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
	M->SetVectorParameterValue(TEXT("Color"), Color);
	M->SetScalarParameterValue(TEXT("Roughness"), Roughness);
	M->SetScalarParameterValue(TEXT("Pattern"), Pattern);
	M->SetScalarParameterValue(TEXT("Windows"), Windows);
	M->SetScalarParameterValue(TEXT("Metallic"), Metallic);
	return M;
}

void AMarinaActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (GM && GM->GetLake().Marina.IsLoaded()) Build(GM->GetLake().Marina);
}

void AMarinaActor::Build(const FMarina& Marina)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	const FLakeTerrain* Terrain = GM && GM->GetLake().IsLoaded() ? &GM->GetLake().Terrain : nullptr;
	const TMap<FString, FString> ScanMap = LoadScans();
	TArray<FString> Replaced;
	for (const auto& KV : ScanMap)
	{
		// A scan, authored in the map frame (cm, origin at the club's origin), stands in for the generated structure.
		if (UStaticMesh* ScanMesh = LoadObject<UStaticMesh>(nullptr, *KV.Value))
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Static);
			C->SetupAttachment(RootComponent);
			C->SetStaticMesh(ScanMesh);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->RegisterComponent();
			Scans.Add(C);
			Replaced.Add(KV.Key);
			UE_LOG(LogSailing, Display, TEXT("Marina: %s replaced by the scan %s"), *KV.Key, *KV.Value);
		}
	}
	auto Generated = [&](const FString& Id) { return !Replaced.Contains(Id) && !Replaced.ContainsByPredicate([&](const FString& R) { return Id.StartsWith(R + TEXT(".")); }); };

	FKitGeometry All;
	BuildGeometry(Marina, Terrain, Generated, All);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(UWorldKitLibrary::TileM, Tiles);
	// Each 40 m tile: the Nanite mesh baked from this same geometry (scripts/make-world-models.sh), or else a static
	// procedural mesh (no Nanite: on High its virtual shadow marking overflows, so rebake after changing the layout).
	UMaterialInterface* Materials[int32(EKitLook::Count)] = {};
	int32 Baked = 0;
	const bool bForceProcedural = FParse::Param(FCommandLine::Get(), TEXT("SailingProceduralMarina"));
	for (const auto& KV : Tiles)
	{
		const FString Name = FKitGeometry::TileAssetName(TEXT("Marina"), KV.Key);
		UStaticMesh* BakedMesh = bForceProcedural || Replaced.Num() > 0 ? nullptr : LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Baked/%s.%s"), *Name, *Name));
		if (BakedMesh)
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Static);
			C->SetupAttachment(RootComponent);
			C->SetStaticMesh(BakedMesh);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->RegisterComponent();
			Tiled.Add(C);
			++Baked;
			continue;
		}
		UProceduralMeshComponent* M = NewObject<UProceduralMeshComponent>(this);
		M->SetMobility(EComponentMobility::Static);
		M->SetupAttachment(RootComponent);
		M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		M->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		M->RegisterComponent();
		for (int32 K = 0; K < int32(EKitLook::Count); ++K)
		{
			const FKitSection& D = KV.Value.Sections[K];
			if (D.V.Num() == 0) continue;
			if (!Materials[K])
			{
				const FKitLookDesc& L = KitLook(EKitLook(K));
				Materials[K] = Surface(L.Color, L.Roughness, L.Pattern, L.Windows, L.Metallic);
			}
			M->CreateMeshSection_LinearColor(K, D.V, D.T, D.N, D.UV, {}, D.Tan, false);
			M->SetMaterial(K, Materials[K]);
		}
		Tiled.Add(M);
	}

	// The breakwater: limestone riprap piled along its line (the world kit's three rocks, scaled and turned per piece).
	TArray<FTransform> RockX[3];
	uint32 Seed = 7;
	for (const FMarinaLine& L : Marina.Breakwaters)
	{
		if (!Generated(L.Id)) continue;
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D A = L.Points[I - 1], B = L.Points[I];
			const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
			const float Len = float(FVector2D::Distance(A, B));
			for (float D = 0.f; D < Len; D += 1.1f)
			{
				for (int32 K = -2; K <= 2; ++K)
				{
					const float Across = K * 0.22f * L.Width + (MRand(++Seed) - 0.5f) * 0.6f;
					const float Crest = L.Height * (1.f - FMath::Square(Across / (0.55f * L.Width)));
					const FVector2D P = A + Dir * (D + (MRand(++Seed) - 0.5f)) + Left * Across;
					const float Size = 0.8f + 0.9f * MRand(++Seed);
					const int32 Kind = int32(MHash(++Seed) % 3);
					const float Pitch = (MRand(++Seed) - 0.5f) * 40.f, Yaw = MRand(++Seed) * 360.f, Roll = (MRand(++Seed) - 0.5f) * 40.f;
					RockX[Kind].Add(FTransform(FRotator(Pitch, Yaw, Roll), FVector(P.X, P.Y, Crest - 0.25f * Size) * 100.0, FVector(Size)));
				}
			}
		}
	}
	for (int32 K = 0; K < 3; ++K)
	{
		UStaticMesh* Rock = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Props/SM_Rock_%d.SM_Rock_%d"), K, K));
		if (!Rock || RockX[K].Num() == 0) continue;
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
		C->SetMobility(EComponentMobility::Static);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Rock);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		C->RegisterComponent();
		C->AddInstances(RockX[K], false, true);
		Rocks.Add(C);
	}

	// Neighbours: J/22s berthed bow in, sails off, in the occupied slips (the fleet's model).
	static const TCHAR* Parts[] = { TEXT("/Game/Boats/J22/SM_J22_Hull.SM_J22_Hull"), TEXT("/Game/Boats/J22/SM_J22_Mast.SM_J22_Mast"),
		TEXT("/Game/Boats/J22/SM_J22_Boom.SM_J22_Boom"), TEXT("/Game/Boats/J22/SM_J22_Rudder.SM_J22_Rudder") };
	// (Low keeps the docks but leaves the slips empty.)
	UStaticMesh* HullMesh = USailingSettings::Get()->Quality != ESailingQuality::Low ? LoadObject<UStaticMesh>(nullptr, Parts[0]) : nullptr;
	if (HullMesh)
	{
		const FVector Step = HullMesh->FindSocket(TEXT("MastStep")) ? HullMesh->FindSocket(TEXT("MastStep"))->RelativeLocation : FVector(80.f, 0.f, 50.f);
		const FVector RudderAt = HullMesh->FindSocket(TEXT("RudderPivot")) ? HullMesh->FindSocket(TEXT("RudderPivot"))->RelativeLocation : FVector(-330.f, 0.f, 20.f);
		const FVector Offsets[] = { FVector::ZeroVector, Step, Step + FVector(0.f, 0.f, 95.f), RudderAt };
		TArray<TArray<FTransform>> Per;
		Per.SetNum(4);
		for (const FMarinaSlip& Slip : Marina.Slips)
		{
			if (!Slip.bOccupied) continue;
			const FTransform Boat(FRotator(0.f, Slip.HeadingDeg, 0.f), FVector(Slip.Center.X, Slip.Center.Y, 0.0) * 100.0);
			for (int32 K = 0; K < 4; ++K) Per[K].Add(FTransform(FRotator::ZeroRotator, Offsets[K]) * Boat);
		}
		for (int32 K = 0; K < 4; ++K)
		{
			UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Static);
			C->SetupAttachment(RootComponent);
			C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, Parts[K]));
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			// The mast is not Nanite (it bends on the sailing boat): ninety of them overflow the virtual shadow map's
			// non-Nanite marking, and their thin shadows are lost in the shadow map's resolution anyway.
			C->SetCastShadow(K != 1);
			C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
			C->SetCullDistances(0, 1500 * 100);
			C->RegisterComponent();
			C->AddInstances(Per[K], false, true);
			Boats.Add(C);
		}
	}
	UE_LOG(LogSailing, Display, TEXT("Marina %s: %d rows, %d slips (%d occupied), %d buildings, %d of %d tiles baked, home slip %s"), *Marina.Name, Marina.Rows.Num(), Marina.Slips.Num(),
		Marina.Slips.FilterByPredicate([](const FMarinaSlip& Sl) { return Sl.bOccupied; }).Num(), Marina.Buildings.Num(), Baked, Tiles.Num(),
		Marina.HomeSlip != INDEX_NONE ? *Marina.Slips[Marina.HomeSlip].Id : TEXT("none"));
}

void AMarinaActor::BuildGeometry(const FMarina& Marina, const FLakeTerrain* Terrain, TFunctionRef<bool(const FString&)> Generated, FKitGeometry& G)
{
	const float Deck = FloatingDeckHeight;
	// Dock rows: floating deck on black floats, pilings every 9 m alternating sides, finger piers, cleats, boxes, power.
	for (int32 RI = 0; RI < Marina.Rows.Num(); ++RI)
	{
		const FMarinaRow& R = Marina.Rows[RI];
		if (!Generated(R.Id)) continue;
		const FVector2D A = R.Points[0], B = R.Points.Last();
		const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
		G[EKitLook::Decking].Span(A, B, R.Width, Deck - 0.12f, Deck);
		G[EKitLook::Floats].Span(A + Dir * 0.3, B - Dir * 0.3, R.Width * 0.85f, -0.35f, Deck - 0.12f);
		const float Length = float(FVector2D::Distance(A, B));
		for (float X = 1.0f; X < Length; X += 9.f)
		{
			const FVector2D P = A + Dir * X + Left * ((int32(X / 9.f) % 2 ? 1.0 : -1.0) * (0.5 * R.Width + 0.2));
			G[EKitLook::Pilings].Cylinder(FVector(P.X, P.Y, -3.f), 0.17f, 5.6f);
		}
		for (float X = 4.0f; X < Length; X += 16.f)
		{
			const FVector2D P = A + Dir * X;
			G[EKitLook::Lamp].Box(FVector(P.X, P.Y, Deck + 0.5f), FVector(0.06f, 0.06f, 0.5f), 0.f);
			G[EKitLook::White].Box(FVector(P.X, P.Y, Deck + 1.05f), FVector(0.12f, 0.12f, 0.06f), 0.f);
		}
	}
	for (const FMarinaSlip& Slip : Marina.Slips)
	{
		const FMarinaRow& R = Marina.Rows[Slip.Row];
		if (!Generated(R.Id)) continue;
		const FVector2D Out = (Slip.FingerB - Slip.FingerA).GetSafeNormal();
		const FVector2D Along(Out.Y, -Out.X);
		G[EKitLook::Decking].Span(Slip.FingerA, Slip.FingerB, 0.6f, Deck - 0.1f, Deck - 0.02f);
		G[EKitLook::Floats].Span(Slip.FingerA + Out * 0.2, Slip.FingerB, 0.45f, -0.3f, Deck - 0.1f);
		// Cleats at the finger's end and middle; a piling at its tip.
		for (const float T : { 0.45f, 0.95f })
		{
			const FVector2D P = FMath::Lerp(Slip.FingerA, Slip.FingerB, T);
			G[EKitLook::Metal].Box(FVector(P.X, P.Y, Deck + 0.03f), FVector(0.14f, 0.03f, 0.04f), float(FMath::RadiansToDegrees(FMath::Atan2(Out.Y, Out.X))));
		}
		G[EKitLook::Pilings].Cylinder(FVector(Slip.FingerB.X + Along.X * 0.45, Slip.FingerB.Y + Along.Y * 0.45, -3.f), 0.15f, 5.2f);
		const uint32 Seed = uint32(Slip.Row * 1000 + Slip.Index * 2 + (Slip.Side > 0 ? 0 : 1));
		const FVector2D Root = Slip.FingerA + Out * 0.6;
		if (MRand(Seed) < 0.35f)
		{
			// A white dock box at the finger's root.
			G[EKitLook::White].Box(FVector(Root.X, Root.Y, Deck + 0.3f), FVector(0.6f, 0.28f, 0.3f), float(FMath::RadiansToDegrees(FMath::Atan2(Out.Y, Out.X))));
		}
		if (Slip.Index % 2 == 0)
		{
			// A power pedestal between two slips.
			const FVector2D P = Slip.FingerA - Out * 0.4;
			G[EKitLook::White].Box(FVector(P.X, P.Y, Deck + 0.5f), FVector(0.13f, 0.13f, 0.5f), 0.f);
			G[EKitLook::Metal].Box(FVector(P.X, P.Y, Deck + 1.03f), FVector(0.16f, 0.16f, 0.03f), 0.f);
		}
	}
	// Walkways and fixed piers on pilings.
	auto Fixed = [&](const FMarinaLine& L)
	{
		if (!Generated(L.Id)) return;
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D A = L.Points[I - 1], B = L.Points[I];
			G[EKitLook::Decking].Span(A, B, L.Width, L.Height - 0.15f, L.Height);
			const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
			const float Len = float(FVector2D::Distance(A, B));
			for (float X = 0.f; X <= Len; X += 4.f)
			{
				for (const double Side : { -1.0, 1.0 })
				{
					const FVector2D P = A + Dir * X + Left * (Side * (0.5 * L.Width - 0.12));
					G[EKitLook::Pilings].Cylinder(FVector(P.X, P.Y, -3.f), 0.13f, 3.f + L.Height);
				}
			}
			// Hand rails along fixed piers, on posts every 2 m.
			for (float X = 0.f; X <= Len; X += 2.f)
			{
				for (const double Side : { -1.0, 1.0 })
				{
					const FVector2D P = A + Dir * X + Left * (Side * (0.5 * L.Width - 0.05));
					G[EKitLook::Trim].Box(FVector(P.X, P.Y, L.Height + 0.5f), FVector(0.04f, 0.04f, 0.5f), 0.f);
				}
			}
			for (const double Side : { -1.0, 1.0 })
			{
				G[EKitLook::Trim].Span(A + Left * (Side * (0.5 * L.Width - 0.05)), B + Left * (Side * (0.5 * L.Width - 0.05)), 0.08f, L.Height + 0.95f, L.Height + 1.05f);
			}
		}
	};
	for (const FMarinaLine& L : Marina.Walkways) Fixed(L);
	for (const FMarinaLine& L : Marina.Piers) Fixed(L);

	// Buildings: the clubhouse (lap siding with windows, hip roof with an overhang) and the pool.
	for (const FMarinaBuilding& B : Marina.Buildings)
	{
		if (!Generated(B.Id)) continue;
		const float Ground = Terrain ? float(Terrain->HeightAt(B.Center.X, B.Center.Y)) : 2.f;
		const FRotator Rot(0.f, B.HeadingDeg, 0.f);
		const FVector C(B.Center.X, B.Center.Y, Ground);
		if (B.Kind == TEXT("pool"))
		{
			G[EKitLook::Concrete].Box(C + FVector(0, 0, 0.05f), FVector(0.5f * B.Size.X + 2.f, 0.5f * B.Size.Y + 2.f, 0.12f), B.HeadingDeg);
			G[EKitLook::PoolWater].Box(C + FVector(0, 0, 0.12f), FVector(0.5f * B.Size.X, 0.5f * B.Size.Y, 0.06f), B.HeadingDeg);
			continue;
		}
		const float HX = 0.5f * B.Size.X, HY = 0.5f * B.Size.Y, H = B.Height;
		G[EKitLook::Concrete].Box(C + FVector(0, 0, -0.3f), FVector(HX + 0.4f, HY + 0.4f, 0.5f), B.HeadingDeg);
		G[EKitLook::Siding].Box(C + FVector(0, 0, 0.2f + 0.5f * H), FVector(HX, HY, 0.5f * H), B.HeadingDeg);
		// Hip roof: eaves overhang 0.7 m, the ridge along the long side.
		const float O = 0.7f, Z0 = Ground + 0.2f + H, Z1 = Z0 + B.Roof;
		auto P = [&](float X, float Y, float Z) { return FVector(B.Center.X, B.Center.Y, 0.f) + Rot.RotateVector(FVector(X, Y, 0.f)) + FVector(0, 0, Z); };
		const float RX = FMath::Max(HX - HY, 0.5f);
		const FVector E00 = P(-HX - O, -HY - O, Z0), E10 = P(HX + O, -HY - O, Z0), E11 = P(HX + O, HY + O, Z0), E01 = P(-HX - O, HY + O, Z0);
		const FVector R0 = P(-RX, 0.f, Z1), R1 = P(RX, 0.f, Z1);
		const float Slope = FMath::Sqrt(FMath::Square(HY + O) + FMath::Square(B.Roof));
		G[EKitLook::Roof].Quad(E00, R0, R1, E10, { 0, 0 }, { HX + O - RX, Slope }, { HX + O + RX, Slope }, { 2 * (HX + O), 0 });
		G[EKitLook::Roof].Quad(E11, R1, R0, E01, { 0, 0 }, { HX + O - RX, Slope }, { HX + O + RX, Slope }, { 2 * (HX + O), 0 });
		G[EKitLook::Roof].Quad(E01, R0, R0, E00, { 0, 0 }, { HY + O, Slope }, { HY + O, Slope }, { 2 * (HY + O), 0 });
		G[EKitLook::Roof].Quad(E10, R1, R1, E11, { 0, 0 }, { HY + O, Slope }, { HY + O, Slope }, { 2 * (HY + O), 0 });
		// Fascia under the eaves.
		G[EKitLook::Trim].Span(FVector2D(E00), FVector2D(E10), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E10), FVector2D(E11), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E11), FVector2D(E01), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E01), FVector2D(E00), 0.06f, Z0 - 0.25f, Z0);
	}

}
