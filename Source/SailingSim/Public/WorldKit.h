#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProceduralMeshComponent.h"
#include "WorldKit.generated.h"

class UStaticMesh;
class UMaterialInterface;

/**
 * Visual V6: the world kit's generated structures (the marina now; the bridge and buildings next). Generators write quads
 * into one section per look (FKitGeometry, centimetres in the map frame, UVs in metres); the editor bakes the geometry into
 * Nanite static meshes, one per 40 m tile (UWorldKitLibrary::BakeMarina, run by scripts/make-world-models.sh), and the game
 * loads those. Without a bake (or for a tile it lacks) it draws the same geometry as static procedural meshes.
 */
enum class EKitLook : uint8 { Decking, Floats, Pilings, Metal, White, Siding, Roof, Concrete, PoolWater, Trim, Lamp, Asphalt, Steel, LampGlow, Count };

struct FKitLookDesc
{
	const TCHAR* Name;     // material instance MI_World_<Name> (scripts/make_materials.py WORLD_LIBRARY)
	FLinearColor Color;
	float Roughness, Pattern, Windows, Metallic;
};
SAILINGSIM_API const FKitLookDesc& KitLook(EKitLook Look);
/** The look's material instance, MI_World_<Name>. */
SAILINGSIM_API UMaterialInterface* KitMaterial(EKitLook Look);

struct SAILINGSIM_API FKitSection
{
	TArray<FVector> V;
	TArray<int32> T;
	TArray<FVector> N;
	TArray<FVector2D> UV;
	TArray<FProcMeshTangent> Tan;

	/** Positions in metres (stored in cm); UVs as given (metres). Front face is the side the A->D x A->B normal points to. */
	void Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector2D& UA, const FVector2D& UB, const FVector2D& UC, const FVector2D& UD);
	/** A box centred at C with half extents E, turned by Yaw (deg) about Z. Top UVs run across it (U = local Y: deck boards). */
	void Box(const FVector& C, const FVector& E, float YawDeg, bool bBottom = false);
	/** A box from A to B (plan, metres), width W, from Z0 to Z1. */
	void Span(const FVector2D& A, const FVector2D& B, float W, float Z0, float Z1, bool bBottom = false);
	/** A round post (radial normals). */
	void Cylinder(const FVector& Base, float Radius, float Height, int32 Sides = 8);
};

struct SAILINGSIM_API FKitGeometry
{
	FKitSection Sections[int32(EKitLook::Count)];
	FKitSection& operator[](EKitLook L) { return Sections[int32(L)]; }
	const FKitSection& operator[](EKitLook L) const { return Sections[int32(L)]; }
	int32 NumQuads() const;
	/** Splits the quads into tiles by their centres (TileM metres). */
	void SplitTiles(double TileM, TMap<FIntPoint, FKitGeometry>& Out) const;
	/** The asset a tile bakes to: /Game/World/Baked/SM_<Prefix>_<x>_<y> (m for minus). */
	static FString TileAssetName(const FString& Prefix, const FIntPoint& Tile);
};

struct FLakeData;
struct FLakeBridge;

/** The bridges of a lake or coast from their OSM ways (FLakeBridge: kind, deck clearance): decks, girders, pier bents, barriers,
 *  lamp posts; rail and foot bridges in their own styles. The girders' underside sits where the physics stops a mast. */
SAILINGSIM_API void BuildBridgeGeometry(const FLakeData& Lake, FKitGeometry& Out);
/** Carriageway width (m) of a bridge by its OSM kind; 0 for kinds drawn without traffic. */
SAILINGSIM_API float BridgeWidth(const FLakeBridge& Bridge);
/** The top of a bridge's road surface (m above the water/datum). */
SAILINGSIM_API float BridgeRoadZ(const FLakeBridge& Bridge);

/** Adds a component per tile to Owner: the baked Nanite mesh /Game/World/Baked/<TileAssetName(Prefix)> when there is one (and
 *  !bProcedural), else a static procedural mesh with Material(look). Returns the number of baked tiles used. */
SAILINGSIM_API int32 SpawnKitTiles(AActor* Owner, const TMap<FIntPoint, FKitGeometry>& Tiles, const FString& Prefix, bool bProcedural,
	TFunctionRef<UMaterialInterface*(EKitLook)> Material, TArray<TObjectPtr<UPrimitiveComponent>>& Out);

/** Bakes generated geometry into Nanite static meshes (editor only; Python saves them). */
UCLASS()
class SAILINGSIM_API UWorldKitLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	static constexpr double TileM = 40.0;

	/** Builds the marina of a lake (Content/TerrainData/<Lake>.marina.json) and returns its tile meshes (unsaved). */
	UFUNCTION(BlueprintCallable, Category = "Sailing|World")
	static TArray<UStaticMesh*> BakeMarina(const FString& LakeName);

	/** Bridges come in 200 m tiles: SM_Bridges_<Lake>_<x>_<y>. */
	static constexpr double BridgeTileM = 200.0;
	UFUNCTION(BlueprintCallable, Category = "Sailing|World")
	static TArray<UStaticMesh*> BakeBridges(const FString& LakeName);

#if WITH_EDITOR
	static UStaticMesh* BakeMesh(const FKitGeometry& Geometry, const FString& PackagePath);
#endif
};
