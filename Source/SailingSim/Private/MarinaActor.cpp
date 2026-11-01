#include "MarinaActor.h"
#include "SailingFrame.h"
#include "BenchRunner.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "BoatLivery.h"
#include "SailingSim.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "LakeData.h"
#include "Marina.h"
#include "WorldKit.h"
#include "SailingAudio.h"
#include "Components/AudioComponent.h"
#include "BoatModel.h"
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

FLinearColor FBerthedBoat::PowerHullColour(uint32 Seed)
{
	// Mac polish: a marina's power boats are mostly white; the painted hulls are navy and dark blue, then ivory, greys,
	// black and the odd sea green (shares out of 100).
	struct FPaint { uint32 Share; FLinearColor Colour; };
	static const FPaint Paints[] = { { 66, FLinearColor(0.80f, 0.80f, 0.78f) }, { 8, FLinearColor(0.75f, 0.71f, 0.60f) },
		{ 9, FLinearColor(0.015f, 0.03f, 0.09f) }, { 5, FLinearColor(0.03f, 0.09f, 0.26f) }, { 5, FLinearColor(0.42f, 0.44f, 0.45f) },
		{ 4, FLinearColor(0.02f, 0.02f, 0.022f) }, { 3, FLinearColor(0.30f, 0.50f, 0.45f) } };
	uint32 Pick = MHash(Seed * 2246822519u + 3u) % 100u;
	for (const FPaint& P : Paints)
	{
		if (Pick < P.Share) return P.Colour;
		Pick -= P.Share;
	}
	return Paints[0].Colour;
}

void SpawnBerthedBoats(AActor* Owner, USceneComponent* Root, TConstArrayView<FBerthedBoat> Placed, float CullScale, EComponentMobility::Type Mobility,
	TArray<TObjectPtr<UInstancedStaticMeshComponent>>& Out, EWearSite Site)
{
	// Graphics G6: six berthed dresses per class (build_berthed.py variants: cover colours, flaked mains, a tarp, dodgers,
	// fenders, gear), one picked per slip, so no two neighbours in a row look alike. Graphics G7: a boat may be scaled to her
	// measured length (the coast's moored boats), and a power boat (Type 255) is the runabout.
	static const TCHAR* Parts[] = { TEXT("Hull"), TEXT("Mast"), TEXT("Boom"), TEXT("Rudder"), TEXT("Berthed"),
		TEXT("Berthed_1"), TEXT("Berthed_2"), TEXT("Berthed_3"), TEXT("Berthed_4"), TEXT("Berthed_5") };
	constexpr int32 NumDress = 6;
	TMap<uint8, TArray<TArray<FTransform>>> PerClass;
	TMap<uint8, TArray<uint32>> Seeds; // Graphics G3: each neighbour's livery (hull colour and wear, per instance)
	TMap<uint8, TArray<UStaticMesh*>> MeshesByClass;
	TMap<uint8, TArray<TArray<FWearSeed>>> Wear;  // Environment E1: per part, per instance, beside PerClass
	// pc/j22-detail: painted spars (BoatLivery.h PaintSpars), per part, per instance, beside PerClass; a class's spar parts
	// are drawn by two components, anodised and painted (one finish per component).
	TMap<uint8, TArray<TArray<bool>>> SparPaint;
	TMap<uint8, FBoatLivery> PaintedLook;
	for (const FBerthedBoat& P : Placed)
	{
		if (!MeshesByClass.Contains(P.Type))
		{
			TArray<UStaticMesh*> M;
			if (FBerthedBoat::IsPower(P.Type))
			{
				// The vessel kit's models (build_vessels.py), one per class; Mac polish added the express cruiser, the
				// sportfisherman and the motor yacht.
				const TCHAR* Name = P.Type == FBerthedBoat::PowerBoat ? TEXT("Runabout") : P.Type == FBerthedBoat::PowerYacht ? TEXT("Committee")
					: P.Type == FBerthedBoat::PowerExpress ? TEXT("Express") : P.Type == FBerthedBoat::PowerSport ? TEXT("Sportfish") : TEXT("MotorYacht");
				M.Add(LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Vessels/SM_Vessel_%s.SM_Vessel_%s"), Name, Name)));
				M.SetNum(UE_ARRAY_COUNT(Parts));
			}
			else
			{
				const TCHAR* Tag = P.Type == uint8(Sailing::EBoatType::Catalina22) ? TEXT("Catalina22") : (P.Type == uint8(Sailing::EBoatType::Catalina30) ? TEXT("Catalina30") : TEXT("J22"));
				for (const TCHAR* Part : Parts) M.Add(LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Boats/%s/SM_%s_%s.SM_%s_%s"), Tag, Tag, Part, Tag, Part)));
			}
			MeshesByClass.Add(P.Type, M);
			PerClass.Add(P.Type).SetNum(UE_ARRAY_COUNT(Parts));
			Wear.Add(P.Type).SetNum(UE_ARRAY_COUNT(Parts));
			SparPaint.Add(P.Type).SetNum(UE_ARRAY_COUNT(Parts));
		}
		const TArray<UStaticMesh*>& M = MeshesByClass[P.Type];
		if (!M[0]) continue;
		// Through int32 (Mac polish): straight to uint32, every neighbour south-west of the origin hashed to 0 on arm64 and
		// they all wore the same dress, livery and paint.
		const uint32 H = uint32(int32(P.Center.X * 13.0 + P.Center.Y * 7.0));
		const FTransform Boat(FRotator(0.f, P.HeadingDeg + (MRand(H) - 0.5f) * 3.f, 0.f), FVector(P.Center.X, P.Center.Y, 0.0) * 100.0, FVector(P.Scale));
		const uint32 WearId = FWearSeed::IdAt(P.Center);
		const FWearSeed W = FWearSeed::Make(WearId, Site, EWearWater::Floating, P.HeadingDeg,
			P.Cover >= 0 ? P.Cover : int32(MHash(WearId) % uint32(FSlipLook::NumCover)));
		if (FBerthedBoat::IsPower(P.Type))
		{
			PerClass[P.Type][0].Add(Boat);
			Wear[P.Type][0].Add(W);
			SparPaint[P.Type][0].Add(false);
			if (FBerthedBoat::IsPainted(P.Type)) Seeds.FindOrAdd(P.Type).Add(MHash(H) | 1u);
			continue;
		}
		const Sailing::FBoatConfig C = Sailing::FBoatConfig::Make(Sailing::EBoatType(P.Type));
		const UStaticMeshSocket* Step = M[0]->FindSocket(TEXT("MastStep"));
		const UStaticMeshSocket* Stock = M[0]->FindSocket(TEXT("RudderPivot"));
		const FVector Offsets[] = { FVector::ZeroVector, Step ? Step->RelativeLocation : FVector::ZeroVector,
			FVector(C.MainLuffX, 0.0, C.BoomZ) * 100.0, Stock ? Stock->RelativeLocation : FVector::ZeroVector };
		const FBoatLivery Look = SampleBoatLivery(int32(P.Type), MHash(H) | 1u);
		if (Look.bSparPainted) PaintedLook.Add(P.Type, Look);
		for (int32 K = 0; K < 4; ++K)
		{
			PerClass[P.Type][K].Add(FTransform(FRotator::ZeroRotator, Offsets[K]) * Boat);
			Wear[P.Type][K].Add(W);
			SparPaint[P.Type][K].Add((K == 1 || K == 2) && Look.bSparPainted);   // mast and boom (the hull's livery is per instance)
		}
		int32 Dress = 4 + (P.Dress >= 0 ? P.Dress % NumDress : int32(MHash(H * 31u + 7u) % NumDress));
		if (!M[Dress]) Dress = 4;
		PerClass[P.Type][Dress].Add(Boat);
		Wear[P.Type][Dress].Add(W);
		SparPaint[P.Type][Dress].Add(Look.bSparPainted);
		Seeds.FindOrAdd(P.Type).Add(MHash(H) | 1u);
	}
	for (const auto& KV : PerClass)
	{
		for (int32 K = 0; K < UE_ARRAY_COUNT(Parts); ++K)
		{
			UStaticMesh* Mesh = MeshesByClass[KV.Key][K];
			// The berthed dress carries a straight Nanite mast: the class's bending (non-Nanite) mast is left out.
			if (K == 1 && MeshesByClass[KV.Key][4]) continue;
			if (!Mesh || KV.Value[K].Num() == 0) continue;
			for (int32 Painted = 0; Painted < 2; ++Painted)
			{
				// This finish's instances (pc/j22-detail: anodised, then painted spars).
				const TArray<bool>& Paint = SparPaint[KV.Key][K];
				TArray<FTransform> X;
				TArray<FWearSeed> Ws;
				TArray<int32> Index;   // into the class's boats (Seeds) for the hull, which is never split
				for (int32 I = 0; I < KV.Value[K].Num(); ++I)
				{
					if (Paint[I] != (Painted == 1)) continue;
					X.Add(KV.Value[K][I]);
					Ws.Add(Wear[KV.Key][K][I]);
					Index.Add(I);
				}
				if (X.Num() == 0) continue;
				// Many boats over a bay (Graphics G7: two thousand on the coast) are culled by cluster.
				UInstancedStaticMeshComponent* C = X.Num() > 400 ? NewObject<UHierarchicalInstancedStaticMeshComponent>(Owner) : NewObject<UInstancedStaticMeshComponent>(Owner);
				C->SetMobility(Mobility);
				C->SetupAttachment(Root);
				C->SetStaticMesh(Mesh);
				C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				// The masts are not Nanite (they bend on a sailing boat): ninety of them overflow the virtual shadow
				// map's non-Nanite marking, and their thin shadows are lost in its resolution anyway.
				C->SetCastShadow(K != 1);
				C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
				C->SetCullDistances(0, int32((K >= 4 ? 900 : 1500) * 100 * CullScale));
				// Booms, rudders and the berthed dress (masts, wires, covers, fenders, lines) cast no shadow: a hundred boats'
				// worth of thin shadows are lost in the shadow map anyway, and they cost the High tier its frame rate.
				if (K >= 2) C->SetCastShadow(false);
				const bool bLivery = K == 0 && !FBerthedBoat::IsPower(KV.Key);
				const bool bPaint = K == 0 && FBerthedBoat::IsPainted(KV.Key);
				// Livery 0-6 on a sailing hull, paint 0-2 on a painted power hull, then (Environment E1) her wear seed from
				// FWearSeed::Slot. A sailing boat's other parts carry it too, with -1 below the slot: M_BoatSurface's "no
				// livery here" (its custom data defaults). The unpainted power classes' materials read their own defaults, so
				// they stay without custom data for now.
				const bool bSail = !FBerthedBoat::IsPower(KV.Key);
				const bool bWear = bSail || bPaint;
				if (bWear) C->NumCustomDataFloats = FWearSeed::TotalFloats;
				C->RegisterComponent();
				C->AddInstances(SailingFrame::ToWorldTransforms(Owner->GetWorld(), X), false, true);
				if (Painted == 1) PaintSpars(C, PaintedLook[KV.Key]);
				for (int32 I = 0; I < Ws.Num() && bWear; ++I)
				{
					float D[FWearSeed::TotalFloats];
					for (int32 J = 0; J < FWearSeed::Slot; ++J) D[J] = bSail ? -1.f : 0.f;
					if (bLivery)
					{
						const FBoatLivery L = SampleBoatLivery(int32(KV.Key), Seeds[KV.Key][Index[I]]);
						const float Liv[7] = { L.Wear.X, L.Wear.Y, L.Wear.Z, L.Wear.W, L.Hull.R, L.Hull.G, L.Hull.B };
						FMemory::Memcpy(D, Liv, sizeof(Liv));
					}
					if (bPaint)
					{
						const FLinearColor Hue = FBerthedBoat::PowerHullColour(Seeds[KV.Key][Index[I]]);
						D[0] = Hue.R; D[1] = Hue.G; D[2] = Hue.B;
					}
					Ws[I].Write(D + FWearSeed::Slot);
					C->SetCustomData(I, TArrayView<const float>(D, FWearSeed::TotalFloats), false);
				}
				if (bWear) C->MarkRenderStateDirty();
				Out.Add(C);
			}
		}
	}
}

bool AreNeighbourSlips(const FMarinaSlip& A, const FMarinaSlip& B)
{
	if (A.Row != B.Row) return false;
	return A.Side == B.Side ? FMath::Abs(A.Index - B.Index) == 1 : A.Index == B.Index;
}

void AssignSlipLooks(const FMarina& Marina, TArray<FSlipLook>& Out)
{
	// Slips run row by row, one side then the other, so the neighbours a slip can have already been given are its
	// predecessor on its side and the slip across the dock: at most two values to step off, from four or more.
	Out.SetNum(Marina.Slips.Num());
	TMultiMap<int32, int32> ByRow;
	for (int32 I = 0; I < Marina.Slips.Num(); ++I) ByRow.Add(Marina.Slips[I].Row, I);
	for (int32 I = 0; I < Marina.Slips.Num(); ++I)
	{
		const FMarinaSlip& S = Marina.Slips[I];
		const uint32 Id = FWearSeed::IdOf(S.Id);
		TArray<int32> Done;
		ByRow.MultiFind(S.Row, Done);
		auto Pick = [&](int32 N, uint32 Stream, int32 FSlipLook::* Field)
		{
			int32 V = int32(MHash(Id ^ MHash(Stream)) % uint32(N));
			for (int32 Tries = 0; Tries < N; ++Tries)
			{
				const bool bTaken = Done.ContainsByPredicate([&](int32 J) { return J < I && AreNeighbourSlips(S, Marina.Slips[J]) && Out[J].*Field == V; });
				if (!bTaken) break;
				V = (V + 1) % N;
			}
			Out[I].*Field = V;
		};
		Pick(FSlipLook::NumDress, 1u, &FSlipLook::Dress);
		Pick(FSlipLook::NumClutter, 2u, &FSlipLook::Clutter);
		Pick(FSlipLook::NumCover, 3u, &FSlipLook::Cover);
	}
}

AMarinaActor::AMarinaActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.25f;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	// Nothing here moves: static components keep their cached virtual shadow pages (movable ones re-mark them every frame).
	RootComponent->SetMobility(EComponentMobility::Static);
}

void AMarinaActor::BeginPlay()
{
	Super::BeginPlay();
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (GM && GM->GetLake().Marina.IsLoaded()) Build(GM->GetLake().Marina);
}

void AMarinaActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || Voices.Num() == 0) return;
	const double Wind = GM->GetWind().VelocityAt(Sailing::Vec3(-40.0, 160.0, 10.0), GM->GetSimTime()).LengthXY();
	for (USailingWorldSynth* V : Voices)
	{
		if (V->Kind == EWorldSound::MarinaHalyards)
		{
			V->Rate = FMath::Clamp(float(Wind) / 9.f, 0.f, 1.f);
			V->Level = FMath::Clamp(float(Wind - 1.5) / 5.f, 0.f, 1.f) * 0.9f;
		}
		else
		{
			// Gulls fly by day, and call more on a calm morning.
			V->Rate = FMath::Clamp(1.f - float(Wind) / 12.f, 0.2f, 1.f);
		}
	}
	// The gulls wheel in wide circles over the rows, one higher and wider than the other.
	GullClock += DeltaSeconds;
	for (int32 K = 0; K < GullPoints.Num(); ++K)
	{
		const float A = GullClock * (0.05f + 0.02f * K) + K * 2.1f;
		GullPoints[K]->SetRelativeLocation(FVector(-30.0 + (60.0 + 40.0 * K) * FMath::Cos(A), 170.0 + (80.0 + 30.0 * K) * FMath::Sin(A), 15.0 + 10.0 * K) * 100.0);
	}
}

static UStaticMesh* LoadDockKit(AMarinaActor::EDockKit Kit);

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
	const bool bKit = HasDockKit();
	BuildGeometry(Marina, Terrain, Generated, All, bKit);
	TMap<FIntPoint, FKitGeometry> Tiles;
	All.SplitTiles(UWorldKitLibrary::TileM, Tiles);
	// Each 40 m tile: the Nanite mesh baked from this same geometry (scripts/make-world-models.sh), or else procedural.
	const int32 Baked = SpawnKitTiles(this, Tiles, TEXT("Marina"), Replaced.Num() > 0 || FParse::Param(SailingArgs::Dev(), TEXT("SailingProceduralWorld")),
		KitMaterial, Tiled);

	// The breakwater: limestone riprap piled along its line. Near-shore phase 3 (audit item 5: one rounded shape repeated
	// in a line): twelve shapes (build_props.py: the first six, then slabs, long blocks and angular pieces), sizes spread
	// as quarried armour stone is (many middling, a few big, small chinking in the gaps), each stretched its own way and
	// tipped as it fell, a toe of the biggest at the water on the lake side, and each its own shade of limestone
	// (M_WorldSurface's stone pattern reads custom data 10-15: age, care, sun, its wet line, site, and its shade).
	constexpr int32 NumRocks = 12;
	TArray<FTransform> RockX[NumRocks];
	TArray<float> RockD[NumRocks];
	uint32 Seed = 7;
	auto AddRock = [&](const FVector2D& P, float Z, float Size, float Flat)
	{
		const int32 Kind = int32(MHash(++Seed) % NumRocks);
		const float Pitch = (MRand(++Seed) - 0.5f) * 50.f, Yaw = MRand(++Seed) * 360.f, Roll = (MRand(++Seed) - 0.5f) * 50.f;
		// (Drawn one by one: three draws inside one constructor call are unsequenced, so compilers could order them differently.)
		const float SX = 0.8f + 0.45f * MRand(++Seed);
		const float SY = 0.8f + 0.45f * MRand(++Seed);
		const float SZ = 0.75f + 0.4f * MRand(++Seed);
		const FVector Stretch(Size * SX, Size * SY, Size * Flat * SZ);
		RockX[Kind].Add(FTransform(FRotator(Pitch, Yaw, Roll), FVector(P.X, P.Y, Z) * 100.0, Stretch));
		float D[16] = {};
		D[10] = 15.f + 10.f * MRand(++Seed); D[11] = 0.3f; D[12] = 0.5f; D[13] = 0.5f + 0.4f * MRand(++Seed); D[14] = 0.f; D[15] = MRand(++Seed);
		RockD[Kind].Append(D, 16);
	};
	for (const FMarinaLine& L : Marina.Breakwaters)
	{
		if (!Generated(L.Id)) continue;
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D A = L.Points[I - 1], B = L.Points[I];
			const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
			const float Len = float(FVector2D::Distance(A, B));
			for (float D = 0.f; D < Len; D += 0.8f + 0.7f * MRand(++Seed))
			{
				for (int32 K = -2; K <= 2; ++K)
				{
					const float Across = K * 0.22f * L.Width + (MRand(++Seed) - 0.5f) * 0.8f;
					const float Crest = L.Height * (1.f - FMath::Square(Across / (0.55f * L.Width)));
					const FVector2D P = A + Dir * (D + (MRand(++Seed) - 0.5f)) + Left * Across;
					// Armour stone: mostly 0.8-1.5 m, one in eight up to 2.3 m.
					const float U = MRand(++Seed);
					const float Size = U < 0.875f ? 0.8f + 0.7f * (U / 0.875f) : 1.5f + 0.8f * ((U - 0.875f) / 0.125f);
					AddRock(P, Crest - 0.25f * Size, Size, 1.f);
					// Chinking: a small stone in the gap now and then.
					if (MRand(++Seed) < 0.35f)
					{
						const FVector2D Q = P + Dir * 0.55f + Left * ((MRand(++Seed) - 0.5f) * 0.6f);
						const float S = 0.35f + 0.3f * MRand(++Seed);
						AddRock(Q, Crest - 0.1f, S, 0.8f);
					}
				}
				// The toe: big stones along the waterline on both faces, half drowned.
				if (MRand(++Seed) < 0.5f)
				{
					const float Side = MRand(++Seed) < 0.5f ? -1.f : 1.f;
					const FVector2D P = A + Dir * D + Left * (Side * (0.62f * L.Width + 0.4f * MRand(++Seed)));
					const float Size = 1.4f + 0.8f * MRand(++Seed);
					AddRock(P, -0.35f * Size, Size, 0.9f);
				}
			}
		}
	}
	for (int32 K = 0; K < NumRocks; ++K)
	{
		UStaticMesh* Rock = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Props/SM_Rock_%d.SM_Rock_%d"), K, K));
		if (!Rock || RockX[K].Num() == 0) continue;
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
		C->SetMobility(EComponentMobility::Static);
		C->SetupAttachment(RootComponent);
		C->SetStaticMesh(Rock);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
		C->NumCustomDataFloats = 16;
		C->RegisterComponent();
		C->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), RockX[K]), false, true);
		C->SetCustomData(0, RockX[K].Num() - 1, TConstArrayView<float>(RockD[K]), true);
		Rocks.Add(C);
	}

	// Club docks pass 2: the docks' hardware as meshes, static instances drawn within 150 m (the floats to 600 m: they
	// shape the docks' waterline from across the harbour).
	if (bKit)
	{
		TArray<FTransform> KitX[int32(EDockKit::Count)];
		DockKitPlacements(Marina, Generated, KitX);
		int32 Instances = 0;
		for (int32 K = 0; K < int32(EDockKit::Count); ++K)
		{
			UStaticMesh* Mesh = LoadDockKit(EDockKit(K));
			if (!Mesh || KitX[K].Num() == 0) continue;
			UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this);
			C->SetMobility(EComponentMobility::Static);
			C->SetupAttachment(RootComponent);
			C->SetStaticMesh(Mesh);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->ShadowCacheInvalidationBehavior = EShadowCacheInvalidationBehavior::Static;
			C->SetCullDistances(0, EDockKit(K) == EDockKit::Float ? 60000 : 15000);
			C->RegisterComponent();
			C->AddInstances(SailingFrame::ToWorldTransforms(GetWorld(), KitX[K]), false, true);
			DockKit.Add(C);
			Instances += KitX[K].Num();
		}
		UE_LOG(LogSailing, Display, TEXT("Marina: %d dock kit instances in %d meshes"), Instances, DockKit.Num());
	}

	// Neighbours (Visual V7): J/22s and Catalina 22s bow in in their slips, Catalina 30s alongside the fixed pier, each
	// the class's own model with what a boat in her slip wears (build_berthed.py: standing rigging, furled jib, sail
	// cover, halyards, fenders, dock lines). Low keeps the docks but leaves the slips empty.
	if (USailingSettings::Get()->Quality != ESailingQuality::Low)
	{
		// Environment E1: each slip's dress and cover are stepped off its neighbours' (AssignSlipLooks).
		TArray<FSlipLook> Looks;
		AssignSlipLooks(Marina, Looks);
		TArray<FBerthedBoat> Placed;
		for (int32 I = 0; I < Marina.Slips.Num(); ++I)
		{
			const FMarinaSlip& Slip = Marina.Slips[I];
			if (!Slip.bOccupied) continue;
			FBerthedBoat B{ Slip.Center, Slip.HeadingDeg, Slip.BoatType };
			B.Dress = Looks[I].Dress;
			B.Cover = Looks[I].Cover;
			Placed.Add(B);
		}
		for (const FMarinaAlongside& A : Marina.Alongside) Placed.Add({ A.Center, A.HeadingDeg, A.BoatType });
		SpawnBerthedBoats(this, RootComponent, Placed, 1.f, EComponentMobility::Static, Boats,
			GM && GM->GetLake().IsLoaded() ? WearSiteFor(GM->GetLake()) : EWearSite::Lake);
	}
	// Sound: halyards on every dock row (louder with the wind), and a pair of gulls wheeling over the harbour.
	for (const FMarinaRow& R : Marina.Rows)
	{
		const FVector2D Mid = 0.5 * (R.Points[0] + R.Points.Last());
		USceneComponent* At = NewObject<USceneComponent>(this);
		At->SetupAttachment(RootComponent);
		At->SetRelativeLocation(FVector(Mid.X, Mid.Y, 6.0) * 100.0);
		At->RegisterComponent();
		USailingWorldSynth* Voice = nullptr;
		SailingSound::MakeWorldSound(this, At, EWorldSound::MarinaHalyards, 250.f, Voice);
		Voices.Add(Voice);
	}
	for (int32 K = 0; K < 2; ++K)
	{
		USceneComponent* At = NewObject<USceneComponent>(this);
		At->SetupAttachment(RootComponent);
		At->RegisterComponent();
		USailingWorldSynth* Voice = nullptr;
		SailingSound::MakeWorldSound(this, At, EWorldSound::Gulls, 400.f, Voice);
		Voice->Level = 0.6f;
		Voices.Add(Voice);
		GullPoints.Add(At);
	}

	UE_LOG(LogSailing, Display, TEXT("Marina %s: %d rows, %d slips (%d occupied), %d buildings, %d of %d tiles baked, home slip %s"), *Marina.Name, Marina.Rows.Num(), Marina.Slips.Num(),
		Marina.Slips.FilterByPredicate([](const FMarinaSlip& Sl) { return Sl.bOccupied; }).Num(), Marina.Buildings.Num(), Baked, Tiles.Num(),
		Marina.HomeSlip != INDEX_NONE ? *Marina.Slips[Marina.HomeSlip].Id : TEXT("none"));
}

const TCHAR* AMarinaActor::DockKitName(EDockKit Kit)
{
	static const TCHAR* Names[] = { TEXT("Cleat"), TEXT("Pedestal"), TEXT("Box"), TEXT("PilingCap"), TEXT("Hoop"), TEXT("Ladder"), TEXT("Float"), TEXT("Extinguisher") };
	return Names[int32(Kit)];
}

static UStaticMesh* LoadDockKit(AMarinaActor::EDockKit Kit)
{
	const TCHAR* Name = AMarinaActor::DockKitName(Kit);
	return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/World/Docks/SM_Dock_%s.SM_Dock_%s"), Name, Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
}

bool AMarinaActor::HasDockKit()
{
	for (int32 K = 0; K < int32(EDockKit::Count); ++K)
	{
		if (!LoadDockKit(EDockKit(K))) return false;
	}
	return true;
}

void AMarinaActor::DockKitPlacements(const FMarina& Marina, TFunctionRef<bool(const FString&)> Generated, TArray<FTransform> (&Out)[int32(EDockKit::Count)])
{
	// The same points BuildGeometry's kit boxes stand on (club docks pass 2: Tools/blender/build_docks.py's meshes stand
	// there instead). Map frame in cm; each mesh's X along its finger, or out from the dock's edge.
	const float Deck = FloatingDeckHeight;
	auto Add = [&](EDockKit Kit, const FVector2D& P, float Z, const FVector2D& Facing, const FVector& Scale = FVector::OneVector)
	{
		const float Yaw = float(FMath::RadiansToDegrees(FMath::Atan2(Facing.Y, Facing.X)));
		Out[int32(Kit)].Add(FTransform(FRotator(0.f, Yaw, 0.f), FVector(P.X, P.Y, Z) * 100.0, Scale));
	};
	for (const FMarinaRow& R : Marina.Rows)
	{
		if (!Generated(R.Id)) continue;
		const FVector2D A = R.Points[0], B = R.Points.Last();
		const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
		const float Length = float(FVector2D::Distance(A, B));
		// Float modules under the deck: 2.4 m with gaps, their tops under the deck's frame.
		for (float F0 = 0.3f; F0 + 0.5f < Length - 0.3f; F0 += 2.65f)
		{
			const float F1 = FMath::Min(F0 + 2.4f, Length - 0.3f);
			Add(EDockKit::Float, A + Dir * (0.5f * (F0 + F1)), Deck - 0.12f, Dir, FVector(F1 - F0, R.Width * 0.85f, Deck - 0.12f + 0.35f));
		}
		// The row pilings' caps and hoops (BuildGeometry: every 9 m, alternating sides, 0.2 m off the deck's edge).
		for (float X = 1.0f; X < Length; X += 9.f)
		{
			const double Side = int32(X / 9.f) % 2 ? 1.0 : -1.0;
			const FVector2D P = A + Dir * X + Left * (Side * (0.5 * R.Width + 0.2));
			Add(EDockKit::PilingCap, P, 1.9f, Dir);
			Add(EDockKit::Hoop, P, Deck - 0.06f, Left * Side);
		}
		// A swim ladder off the row's end.
		Add(EDockKit::Ladder, B, Deck, Dir);
	}
	for (const FMarinaSlip& Slip : Marina.Slips)
	{
		const FMarinaRow& R = Marina.Rows[Slip.Row];
		if (!Generated(R.Id)) continue;
		const FVector2D Out2 = (Slip.FingerB - Slip.FingerA).GetSafeNormal();
		const FVector2D Along(Out2.Y, -Out2.X);
		const float FingerLength = float(FVector2D::Distance(Slip.FingerA, Slip.FingerB));
		Add(EDockKit::Float, FMath::Lerp(Slip.FingerA + Out2 * 0.2, Slip.FingerB, 0.5f), Deck - 0.1f, Out2, FVector(FingerLength - 0.2f, 0.45f, Deck - 0.1f + 0.3f));
		for (const float T : { 0.45f, 0.95f })
		{
			Add(EDockKit::Cleat, FMath::Lerp(Slip.FingerA, Slip.FingerB, T), Deck - 0.02f, Out2);
		}
		Add(EDockKit::PilingCap, Slip.FingerB + Along * 0.45, 1.5f, Out2);
		const uint32 Seed = uint32(Slip.Row * 1000 + Slip.Index * 2 + (Slip.Side > 0 ? 0 : 1));
		if (MRand(Seed) < 0.35f) Add(EDockKit::Box, Slip.FingerA + Out2 * 0.6, Deck - 0.02f, Out2);
		if (Slip.Index % 2 == 0)
		{
			Add(EDockKit::Pedestal, Slip.FingerA - Out2 * 0.4, Deck, Out2);
			// A fire extinguisher cabinet by every other pedestal, at the row deck's edge.
			if (Slip.Index % 4 == 0) Add(EDockKit::Extinguisher, Slip.FingerA - Out2 * 0.4 + Along * 0.7, Deck, Out2);
		}
	}
}

void AMarinaActor::BuildGeometry(const FMarina& Marina, const FLakeTerrain* Terrain, TFunctionRef<bool(const FString&)> Generated, FKitGeometry& G,
	bool bDockKitMeshes)
{
	const float Deck = FloatingDeckHeight;
	// Club docks (#405 part 2): the floating docks' hardware, placed from the same rows and slips (the layout and the
	// physics obstacles are unchanged). A piling's white cap; a steel hoop round it from the dock's edge, on black rollers.
	auto PilingCap = [&](const FVector2D& P, float Radius, float Top)
	{
		G[EKitLook::White].Cylinder(FVector(P.X, P.Y, Top), Radius + 0.02f, 0.05f, 10);
		G[EKitLook::White].Box(FVector(P.X, P.Y, Top + 0.06f), FVector(0.6f * Radius, 0.6f * Radius, 0.02f), 45.f);
	};
	auto PilingHoop = [&](const FVector2D& P, float Radius, const FVector2D& Edge)
	{
		const float Ring = Radius + 0.07f, Z = Deck - 0.06f;
		for (int32 K = 0; K < 8; ++K)
		{
			const float Ang = 2.f * UE_PI * (K + 0.5f) / 8.f;
			const FVector2D Q = P + FVector2D(FMath::Cos(Ang), FMath::Sin(Ang)) * Ring;
			G[EKitLook::Metal].Box(FVector(Q.X, Q.Y, Z), FVector(0.025f, Ring * 0.42f, 0.03f), FMath::RadiansToDegrees(Ang));
		}
		const FVector2D Out = (P - Edge).GetSafeNormal(), Side(-Out.Y, Out.X);
		for (const double S : { -1.0, 1.0 })
		{
			const FVector2D E = Edge + Side * (S * 0.7 * Ring);
			G[EKitLook::Metal].Span(E, P + Side * (S * 0.7 * Ring), 0.04f, Z - 0.03f, Z + 0.03f);
			const FVector2D Roller = P - Out * Ring + Side * (S * 0.45 * Ring);
			G[EKitLook::Floats].Cylinder(FVector(Roller.X, Roller.Y, Z - 0.16f), 0.035f, 0.32f, 6);
		}
	};
	// Black rub strip along a floating deck's edge.
	auto RubStrips = [&](const FVector2D& A, const FVector2D& B, float Width, float Top)
	{
		const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
		for (const double S : { -1.0, 1.0 })
		{
			const FVector2D O = Left * (S * (0.5 * Width + 0.03));
			G[EKitLook::Floats].Span(A + O, B + O, 0.06f, Top - 0.16f, Top - 0.02f);
		}
	};
	// Dock rows: floating deck on black floats, pilings every 9 m alternating sides, finger piers, cleats, boxes, power.
	for (int32 RI = 0; RI < Marina.Rows.Num(); ++RI)
	{
		const FMarinaRow& R = Marina.Rows[RI];
		if (!Generated(R.Id)) continue;
		const FVector2D A = R.Points[0], B = R.Points.Last();
		const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
		const float Length = float(FVector2D::Distance(A, B));
		// The deck in 6 m float sections with a joint between them, each on its own float modules (2.4 m, gaps between).
		for (float S0 = 0.f; S0 < Length; S0 += 6.f)
		{
			const float S1 = FMath::Min(S0 + 6.f, Length);
			G[EKitLook::Decking].Span(A + Dir * (S0 + 0.015f), A + Dir * (S1 - 0.015f), R.Width, Deck - 0.12f, Deck);
		}
		for (float F0 = 0.3f; !bDockKitMeshes && F0 + 0.5f < Length - 0.3f; F0 += 2.65f)
		{
			const float F1 = FMath::Min(F0 + 2.4f, Length - 0.3f);
			G[EKitLook::Floats].Span(A + Dir * F0, A + Dir * F1, R.Width * 0.85f, -0.35f, Deck - 0.12f);
		}
		RubStrips(A, B, R.Width, Deck);
		// A hinged transition plate where the row meets the fixed walkway, with its side rails; a swim ladder at the row's end.
		G[EKitLook::Metal].Span(A - Dir * 0.9, A + Dir * 0.2, R.Width * 0.9f, Deck + 0.01f, Deck + 0.04f);
		for (const double S : { -1.0, 1.0 })
		{
			const FVector2D O = Left * (S * 0.45 * R.Width);
			G[EKitLook::Trim].Span(A - Dir * 0.9 + O, A + Dir * 0.2 + O, 0.04f, Deck + 0.85f, Deck + 0.9f);
			for (const float T : { -0.85f, 0.15f })
			{
				const FVector2D P = A + Dir * T + O;
				G[EKitLook::Trim].Box(FVector(P.X, P.Y, Deck + 0.47f), FVector(0.025f, 0.025f, 0.43f), 0.f);
			}
		}
		if (!bDockKitMeshes)
		{
			const FVector2D L0 = B - Left * 0.22, L1 = B + Left * 0.22;
			const FVector2D Off = Dir * 0.05;
			for (const FVector2D& P : { L0, L1 })
			{
				G[EKitLook::Metal].Box(FVector(P.X + Off.X, P.Y + Off.Y, Deck - 0.2f), FVector(0.02f, 0.02f, 0.85f), 0.f);
			}
			for (float Z = -0.9f; Z < Deck + 0.4f; Z += 0.3f)
			{
				G[EKitLook::Metal].Span(L0 + Off, L1 + Off, 0.03f, Z, Z + 0.03f);
			}
		}
		for (float X = 1.0f; X < Length; X += 9.f)
		{
			const FVector2D Edge = A + Dir * X + Left * ((int32(X / 9.f) % 2 ? 1.0 : -1.0) * (0.5 * R.Width));
			const FVector2D P = A + Dir * X + Left * ((int32(X / 9.f) % 2 ? 1.0 : -1.0) * (0.5 * R.Width + 0.2));
			G[EKitLook::Pilings].Cylinder(FVector(P.X, P.Y, -3.f), 0.17f, 4.9f);
			if (!bDockKitMeshes)
			{
				PilingCap(P, 0.17f, 1.9f);
				PilingHoop(P, 0.17f, Edge);
			}
		}
		for (float X = 4.0f; X < Length; X += 16.f)
		{
			const FVector2D P = A + Dir * X;
			G[EKitLook::Lamp].Box(FVector(P.X, P.Y, Deck + 0.5f), FVector(0.06f, 0.06f, 0.5f), 0.f);
			G[EKitLook::LampGlow].Box(FVector(P.X, P.Y, Deck + 1.05f), FVector(0.12f, 0.12f, 0.06f), 0.f);
			G.Lights.Add({ FVector(P.X, P.Y, Deck + 1.0f), 1 });
		}
	}
	for (const FMarinaSlip& Slip : Marina.Slips)
	{
		const FMarinaRow& R = Marina.Rows[Slip.Row];
		if (!Generated(R.Id)) continue;
		const FVector2D Out = (Slip.FingerB - Slip.FingerA).GetSafeNormal();
		const FVector2D Along(Out.Y, -Out.X);
		G[EKitLook::Decking].Span(Slip.FingerA, Slip.FingerB, 0.6f, Deck - 0.1f, Deck - 0.02f);
		if (!bDockKitMeshes) G[EKitLook::Floats].Span(Slip.FingerA + Out * 0.2, Slip.FingerB, 0.45f, -0.3f, Deck - 0.1f);
		RubStrips(Slip.FingerA + Out * 0.1, Slip.FingerB, 0.6f, Deck - 0.02f);
		// Cleats at the finger's end and middle (a cast base and two horns along the finger); a piling at its tip.
		const float FingerYaw = float(FMath::RadiansToDegrees(FMath::Atan2(Out.Y, Out.X)));
		if (!bDockKitMeshes)
		{
			for (const float T : { 0.45f, 0.95f })
			{
				const FVector2D P = FMath::Lerp(Slip.FingerA, Slip.FingerB, T);
				G[EKitLook::Metal].Box(FVector(P.X, P.Y, Deck + 0.01f), FVector(0.06f, 0.035f, 0.03f), FingerYaw);
				G[EKitLook::Metal].Box(FVector(P.X, P.Y, Deck + 0.065f), FVector(0.16f, 0.022f, 0.016f), FingerYaw);
			}
		}
		const FVector2D Tip(Slip.FingerB.X + Along.X * 0.45, Slip.FingerB.Y + Along.Y * 0.45);
		G[EKitLook::Pilings].Cylinder(FVector(Tip.X, Tip.Y, -3.f), 0.15f, 4.5f);
		if (!bDockKitMeshes) PilingCap(Tip, 0.15f, 1.5f);
		const uint32 Seed = uint32(Slip.Row * 1000 + Slip.Index * 2 + (Slip.Side > 0 ? 0 : 1));
		const FVector2D Root = Slip.FingerA + Out * 0.6;
		if (!bDockKitMeshes && MRand(Seed) < 0.35f)
		{
			// A white dock box at the finger's root.
			G[EKitLook::White].Box(FVector(Root.X, Root.Y, Deck + 0.3f), FVector(0.6f, 0.28f, 0.3f), FingerYaw);
			// its lid, proud of the box, and the hasp
			G[EKitLook::Trim].Box(FVector(Root.X, Root.Y, Deck + 0.615f), FVector(0.62f, 0.3f, 0.02f), FingerYaw);
			const FVector2D Hasp = Root + Along * 0.3;
			G[EKitLook::Metal].Box(FVector(Hasp.X, Hasp.Y, Deck + 0.55f), FVector(0.03f, 0.012f, 0.04f), FingerYaw);
		}
		if (!bDockKitMeshes && Slip.Index % 2 == 0)
		{
			// A power pedestal between two slips: the post, the meter and outlet face toward the finger, the lamp head.
			const FVector2D P = Slip.FingerA - Out * 0.4;
			G[EKitLook::White].Box(FVector(P.X, P.Y, Deck + 0.5f), FVector(0.13f, 0.13f, 0.5f), FingerYaw);
			G[EKitLook::Metal].Box(FVector(P.X, P.Y, Deck + 1.03f), FVector(0.16f, 0.16f, 0.03f), FingerYaw);
			const FVector2D Face = P + Out * 0.135;
			G[EKitLook::Floats].Box(FVector(Face.X, Face.Y, Deck + 0.62f), FVector(0.01f, 0.09f, 0.16f), FingerYaw);
			G[EKitLook::Metal].Box(FVector(Face.X, Face.Y, Deck + 0.36f), FVector(0.012f, 0.07f, 0.05f), FingerYaw);
			G[EKitLook::LampGlow].Box(FVector(P.X, P.Y, Deck + 0.93f), FVector(0.135f, 0.135f, 0.05f), FingerYaw);
		}
	}
	// Walkways and fixed piers on pilings.
	auto Fixed = [&](const FMarinaLine& L)
	{
		if (!Generated(L.Id)) return;
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D A = L.Points[I - 1], B = L.Points[I];
			G[EKitLook::Decking].Span(A, B, L.Width, L.Height - 0.15f, L.Height, true);
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
		// Floodlights at the eaves' corners.
		for (const FVector& E : { E00, E10, E11, E01 }) G.Lights.Add({ FVector(E.X, E.Y, Z0 - 0.4f), 2 });
		// Fascia under the eaves.
		G[EKitLook::Trim].Span(FVector2D(E00), FVector2D(E10), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E10), FVector2D(E11), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E11), FVector2D(E01), 0.06f, Z0 - 0.25f, Z0);
		G[EKitLook::Trim].Span(FVector2D(E01), FVector2D(E00), 0.06f, Z0 - 0.25f, Z0);
	}

}
