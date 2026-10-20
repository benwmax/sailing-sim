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
enum class EKitLook : uint8 { Decking, Floats, Pilings, Metal, White, Siding, Roof, Concrete, PoolWater, Trim, Lamp, Asphalt, Steel, LampGlow, Riprap,
	HouseWall, HouseRoof, Count };   // Graphics G6: the houses' walls and roofs, coloured per vertex (FKitSection::Paint)

struct FKitLookDesc
{
	const TCHAR* Name;     // material instance MI_World_<Name> (scripts/make_materials.py WORLD_LIBRARY)
	FLinearColor Color;
	float Roughness, Pattern, Windows, Metallic;
};
SAILINGSIM_API const FKitLookDesc& KitLook(EKitLook Look);
/** How far (m) the earth's curvature, with standard refraction (R = 7/6 of 6371 km), sinks a point Distance metres away
 *  below the camera's horizontal (the materials' curvature offset; CPU-placed things use this). */
inline double CurvatureDrop(double DistanceM) { return DistanceM * DistanceM / (2.0 * 7.433e6); }
/** The look's material instance, MI_World_<Name>. */
SAILINGSIM_API UMaterialInterface* KitMaterial(EKitLook Look);

struct SAILINGSIM_API FKitSection
{
	TArray<FVector> V;
	TArray<int32> T;
	TArray<FVector> N;
	TArray<FVector2D> UV;
	TArray<FProcMeshTangent> Tan;
	/** Graphics G6: per-vertex colour and a second UV channel, for looks that vary per building (HouseWall, HouseRoof). Every
	 *  vertex added takes the current Paint and Tag. */
	TArray<FColor> Col;
	TArray<FVector2D> UV1;
	FColor Paint = FColor::White;
	FVector2D Tag = FVector2D::ZeroVector;

	/** Positions in metres (stored in cm); UVs as given (metres). Front face is the side the A->D x A->B normal points to. */
	void Quad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector2D& UA, const FVector2D& UB, const FVector2D& UC, const FVector2D& UD);
	/** Graphics G7: a triangle facing up (the deck of a lidar pier). */
	void Tri(const FVector& A, const FVector& B, const FVector& C, const FVector2D& UA, const FVector2D& UB, const FVector2D& UC);
	/** A box centred at C with half extents E, turned by Yaw (deg) about Z. Top UVs run across it (U = local Y: deck boards). */
	void Box(const FVector& C, const FVector& E, float YawDeg, bool bBottom = false);
	/** A box from A to B (plan, metres), width W, from Z0 to Z1. */
	void Span(const FVector2D& A, const FVector2D& B, float W, float Z0, float Z1, bool bBottom = false);
	/** A round post (radial normals). */
	void Cylinder(const FVector& Base, float Radius, float Height, int32 Sides = 8);
};

/** A light the generators put on a fixture (for ANightLightsActor): position (m), kind (0 street lamp, 1 dock lamp,
 *  2 building floodlight, 3 waterfront business). */
struct FKitLight
{
	FVector Position;
	int32 Kind = 0;
};

struct SAILINGSIM_API FKitGeometry
{
	FKitSection Sections[int32(EKitLook::Count)];
	TArray<FKitLight> Lights;
	FKitSection& operator[](EKitLook L) { return Sections[int32(L)]; }
	const FKitSection& operator[](EKitLook L) const { return Sections[int32(L)]; }
	int32 NumQuads() const;
	/** Splits the quads into tiles by their centres (TileM metres). */
	void SplitTiles(double TileM, TMap<FIntPoint, FKitGeometry>& Out) const;
	/** The asset a tile bakes to: /Game/World/Baked/SM_<Prefix>_<x>_<y> (m for minus). */
	static FString TileAssetName(const FString& Prefix, const FIntPoint& Tile);
};

struct FLakeData;

/** Environment E1 (docs/environment-1): what every placed structure carries so the materials can age it, the same on the
 *  Mac and the PC: drawn from a hash of the structure's id, never from a random stream (adding a slip or a house elsewhere
 *  changes nothing here). Written to per-instance custom data from Slot on the marina's berthed boats (club and coast),
 *  the houses and their private docks; the slots below Slot stay each instance's own (the boats' livery 0-6, the houses'
 *  paint 0-9). */
enum class EWearSite : uint8 { Lake, Bay, Gulf };
/** Where a structure meets the water: not at all (houses), riding it (floats, boats), or fixed while it rises and falls. */
enum class EWearWater : uint8 { Dry, Floating, Fixed };
struct SAILINGSIM_API FWearSeed
{
	static constexpr int32 Slot = 10;
	static constexpr int32 NumFloats = 6;
	static constexpr int32 TotalFloats = Slot + NumFloats;

	float Age = 0.f;       // years, 0-25: silvering, fade, rust, replaced boards
	float Care = 1.f;      // 0 neglected .. 1 kept
	float Sun = 0.5f;      // 0 shaded north face .. 1 bleached south-west face
	float Wet = 0.f;       // metres of stain band above the waterline (0 dry)
	EWearSite Site = EWearSite::Lake;
	int32 Variant = 0;     // which set: a slip's cover, a house's or dock's look; Variants values

	static constexpr int32 Variants = 8;
	/** FacingDeg: the map-frame yaw the structure's main face looks along (0 north, 90 east). Variant < 0 hashes one. */
	static FWearSeed Make(uint32 Id, EWearSite Site, EWearWater Water, float FacingDeg, int32 Variant = -1);
	/** A structure's id: its name (slips, rows) or, for unnamed ones, its plan position rounded to 0.25 m. */
	static uint32 IdOf(const FString& Name);
	static uint32 IdAt(const FVector2D& PlanM);
	/** The NumFloats values in slot order: age, care, sun, wet, site, variant. */
	void Write(float* Dst) const;
};
SAILINGSIM_API EWearSite WearSiteFor(const FLakeData& Lake);

struct FLakeBridge;
struct FLakeDock;

/** Ear-clipping triangulation of a simple polygon (no holes): triangle indices into Points. */
SAILINGSIM_API TArray<int32> KitTriangulate(const TArray<FVector2D>& Points);

/** Graphics G7: a band of riprap along a line: a breakwater or jetty is one, the Texas City Dike one along each edge. */
struct FRiprapBand
{
	TArray<FVector2D> Points;
	float HalfWidth = 3.2f;   // at the waterline
	float Crest = 0.8f;       // above the datum
};
/** The riprap bands of a dock line (breakwater, groin, dike); none for other kinds. */
SAILINGSIM_API void RiprapBands(const FLakeDock& Dock, TArray<FRiprapBand>& Out);

/** The bridges of a lake or coast from their OSM ways (FLakeBridge: kind, deck clearance): decks, girders, pier bents, barriers,
 *  lamp posts; rail and foot bridges in their own styles. The girders' underside sits where the physics stops a mast. */
SAILINGSIM_API void BuildBridgeGeometry(const FLakeData& Lake, FKitGeometry& Out);
/** The shore's charted constructions: breakwaters, jetties and revetments as a riprap band (jittered rock cross-sections);
 *  on a lake also its private piers (decking on pilings). Coasts keep their thousands of piers as ALakeTerrainActor draws them. */
SAILINGSIM_API void BuildShoreGeometry(const FLakeData& Lake, FKitGeometry& Out);
/** Whether BuildShoreGeometry draws a lake's piers (and ALakeTerrainActor leaves them out). */
SAILINGSIM_API bool KitDrawsPiers(const FLakeData& Lake);
/** Carriageway width (m) of a bridge by its OSM kind; 0 for kinds drawn without traffic. */
SAILINGSIM_API float BridgeWidth(const FLakeBridge& Bridge);
/** The top of a bridge's road surface (m above the water/datum). */
SAILINGSIM_API float BridgeRoadZ(const FLakeBridge& Bridge);

/** Graphics G6: the G2 houses (FLakeData::Houses) by HouseTileM tile of their centre, leaving out the marina's own buildings. */
SAILINGSIM_API void HouseTiles(const FLakeData& Lake, TMap<FIntPoint, TArray<int32>>& Out);
/** The houses' walls, roofs, eaves and (full detail) windows, doors and chimneys (HouseKit.cpp). */
SAILINGSIM_API void BuildHouseGeometry(const FLakeData& Lake, TConstArrayView<int32> Houses, FKitGeometry& Out);

/** Adds a component per tile to Owner: the baked Nanite mesh /Game/World/Baked/<TileAssetName(Prefix)> when there is one (and
 *  !bProcedural), else a static procedural mesh with Material(look). Returns the number of baked tiles used. */
SAILINGSIM_API int32 SpawnKitTiles(AActor* Owner, const TMap<FIntPoint, FKitGeometry>& Tiles, const FString& Prefix, bool bProcedural,
	TFunctionRef<UMaterialInterface*(EKitLook)> Material, TArray<TObjectPtr<UPrimitiveComponent>>& Out,
	EComponentMobility::Type Mobility = EComponentMobility::Static);

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
	/** The shore kit, in 1 km tiles (it runs along whole coastlines): SM_Shore_<Lake>_<x>_<y>. */
	static constexpr double ShoreTileM = 1000.0;
	UFUNCTION(BlueprintCallable, Category = "Sailing|World")
	static TArray<UStaticMesh*> BakeShore(const FString& LakeName);

	/** Graphics G6: the G2 houses in 500 m tiles (by house centre): SM_Houses_<Lake>_<x>_<y>. */
	static constexpr double HouseTileM = 500.0;
	UFUNCTION(BlueprintCallable, Category = "Sailing|World")
	static TArray<UStaticMesh*> BakeHouses(const FString& LakeName);

	/** Wide World Rendering PR 1 (docs/world-far): the far coast ring (<World>.far, Tools/terrain/build_far_ring.py), one
	 *  Nanite mesh per tile, /Game/World/Far/SM_Far_<World>_<row>_<col> with M_FarLand, its pivot at the tile's corner; no
	 *  distance field or ray-tracing structure. */
	UFUNCTION(BlueprintCallable, Category = "Sailing|World")
	static TArray<UStaticMesh*> BakeFarRing(const FString& WorldName, const FString& Variant = TEXT(""));

#if WITH_EDITOR
	static UStaticMesh* BakeMesh(const FKitGeometry& Geometry, const FString& PackagePath);
#endif
};
