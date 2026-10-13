#include "WorldKit.h"
#include "SailingSim.h"
#include "LakeData.h"
#include "Marina.h"
#include "MarinaActor.h"
#include "Engine/StaticMesh.h"
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
	};
	return Looks[int32(Look)];
}

void FKitSection::Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector2D& UA, const FVector2D& UB, const FVector2D& UC, const FVector2D& UD)
{
	const int32 I = V.Num();
	const FVector Nrm = FVector::CrossProduct(D - A, B - A).GetSafeNormal();
	const FProcMeshTangent Tg((B - A).GetSafeNormal(), false);
	for (const FVector& P : { A, B, C, D }) { V.Add(P * 100.0); N.Add(Nrm); Tan.Add(Tg); }
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
			for (int32 J = 0; J < 4; ++J) { D.V.Add(Src.V[Q + J]); D.N.Add(Src.N[Q + J]); D.UV.Add(Src.UV[Q + J]); D.Tan.Add(Src.Tan[Q + J]); }
			D.T.Append({ I, I + 1, I + 2, I, I + 2, I + 3 });
		}
	}
}

FString FKitGeometry::TileAssetName(const FString& Prefix, const FIntPoint& Tile)
{
	auto Num = [](int32 X) { return X < 0 ? FString::Printf(TEXT("m%d"), -X) : FString::FromInt(X); };
	return FString::Printf(TEXT("SM_%s_%s_%s"), *Prefix, *Num(Tile.X), *Num(Tile.Y));
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
	UVs.SetNumChannels(1);
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
