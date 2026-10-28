#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/WorldSettings.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Gallery.h"
#include "GalleryStage.h"
#include "SailingSettings.h"
#include "UI/SailCatalog.h"

#if WITH_DEV_AUTOMATION_TESTS

// The developer asset gallery (docs/gallery-core/, Inputs/gallery/brief.md G1).
namespace
{
	constexpr EAutomationTestFlags GalleryFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	const FGalleryItem* ByName(const TArray<FGalleryItem>& Items, const TCHAR* Name)
	{
		return Items.FindByPredicate([Name](const FGalleryItem& I) { return I.Name == Name; });
	}
}

// The list from a set of meshes: the folder table's categories and tags, an unknown folder in Other, twins grouped under
// their base, excluded folders left out, names split and numbered from 1, the eight boats added, the search.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGalleryIndexTest, "SailingSim.UI.Gallery.Index", GalleryFlags)
bool FSailingGalleryIndexTest::RunTest(const FString&)
{
	using namespace SailGallery;
	const TArray<FAssetRef> Meshes = {
		{ TEXT("/Game/Boats/Kit"), TEXT("SM_Kit_HornCleat") }, { TEXT("/Game/Boats/Kit"), TEXT("SM_Kit_HornCleat_Light") },
		{ TEXT("/Game/World/Trees"), TEXT("SM_LiveOak_0") }, { TEXT("/Game/World/Trees"), TEXT("SM_LiveOak_0_Far") }, { TEXT("/Game/World/Trees"), TEXT("SM_LiveOak_1") },
		{ TEXT("/Game/World/Houses"), TEXT("SM_HouseNear_Cottage") }, { TEXT("/Game/World/Houses"), TEXT("SM_House_Ranch") },
		{ TEXT("/Game/World/Landmarks"), TEXT("SM_Landmark_NotreDameGarde") },
		{ TEXT("/Game/World/Baked"), TEXT("SM_Marina_Tile_3") }, { TEXT("/Game/World/Far"), TEXT("SM_Far_12") },
		{ TEXT("/Game/Boats/J22Hero"), TEXT("SM_J22H_Hull") }, { TEXT("/Game/Boats/Lagoon42"), TEXT("SM_Lagoon42_Hull") },
		{ TEXT("/Game/World/Seabed"), TEXT("SM_Wreck") },
		{ TEXT("/Game/World/Trees"), TEXT("SM_Orphan_Far") },
	};
	int32 Other = 0;
	const TArray<FGalleryItem> Items = BuildIndex(Meshes, &Other);
	const int32 Boats = SailCatalog::Boats().Num();
	TestEqual(TEXT("Eight assets of these and the fleet: twins grouped, baked tiles and boat parts left out"), Items.Num(), 8 + Boats);
	TestEqual(TEXT("One in Other"), Other, 1);
	const FGalleryItem* Cleat = ByName(Items, TEXT("Horn cleat"));
	TestTrue(TEXT("Kit: deck hardware, named, its light twin grouped"), Cleat && Cleat->Category == TEXT("Deck hardware") && Cleat->Light.IsValid()
		&& Cleat->Tags.Contains(TEXT("Has light version")) && Cleat->Tags.Contains(TEXT("Hero detail")) && Cleat->bHero);
	TestEqual(TEXT("Its key is the base mesh"), Cleat ? Cleat->Key : FString(), FString(TEXT("/Game/Boats/Kit/SM_Kit_HornCleat.SM_Kit_HornCleat")));
	const FGalleryItem* Oak1 = ByName(Items, TEXT("Live oak 1"));
	const FGalleryItem* Oak2 = ByName(Items, TEXT("Live oak 2"));
	TestTrue(TEXT("Numbered shapes are separate, counted from 1; the far twin under the first"), Oak1 && Oak2 && Oak1->Far.IsValid() && !Oak2->Far.IsValid()
		&& Oak1->Category == TEXT("Trees") && Oak1->Tags.Contains(TEXT("Has far version")));
	const FGalleryItem* Cottage = ByName(Items, TEXT("Cottage"));
	const FGalleryItem* Ranch = ByName(Items, TEXT("Ranch"));
	TestTrue(TEXT("Houses: near and far shore"), Cottage && Ranch && Cottage->Tags.Contains(TEXT("Near shore")) && Ranch->Tags.Contains(TEXT("Far shore"))
		&& Cottage->Category == TEXT("Houses & docks"));
	TestNotNull(TEXT("The names table: Notre-Dame de la Garde"), ByName(Items, TEXT("Notre-Dame de la Garde")));
	const FGalleryItem* Wreck = ByName(Items, TEXT("Wreck"));
	TestTrue(TEXT("A folder the table doesn't name: Other"), Wreck && Wreck->Category == TEXT("Other"));
	TestTrue(TEXT("A twin without its base stands alone"), ByName(Items, TEXT("Orphan far")) != nullptr);
	TestNull(TEXT("Baked tiles are not listed"), Find(Items, TEXT("/Game/World/Baked/SM_Marina_Tile_3")));
	TestNull(TEXT("Nor the boats' parts"), Find(Items, TEXT("/Game/Boats/J22Hero/SM_J22H_Hull")));
	const FGalleryItem* J22 = Find(Items, TEXT("Boat:0"));
	TestTrue(TEXT("The boats come whole, from the fleet"), J22 && J22->BoatType == 0 && J22->Category == TEXT("Boats") && J22->Tags.Contains(TEXT("ASA 101")));
	TestTrue(TEXT("Sorted: boats first, Other last"), Items.Num() > 1 && Items[0].Category == TEXT("Boats") && Items.Last().Category == TEXT("Other"));

	// The search: every word, any case, against name, folder, category and tags; category and tags must match too.
	TestTrue(TEXT("'live oak' finds the oak"), Oak1 && Matches(*Oak1, TEXT("live OAK"), TEXT("All"), {}));
	TestTrue(TEXT("'kit cleat' finds the cleat by its folder"), Cleat && Matches(*Cleat, TEXT("kit cleat"), TEXT(""), {}));
	TestFalse(TEXT("'kit oak' finds nothing in the trees"), Oak1 && Matches(*Oak1, TEXT("kit oak"), TEXT(""), {}));
	TestFalse(TEXT("The category must match"), Oak1 && Matches(*Oak1, TEXT(""), TEXT("Deck hardware"), {}));
	TestTrue(TEXT("Tags AND together"), Cottage && Matches(*Cottage, TEXT(""), TEXT("Houses & docks"), { TEXT("Near shore") })
		&& !Matches(*Cottage, TEXT(""), TEXT(""), { TEXT("Near shore"), TEXT("Far shore") }));

	TestEqual(TEXT("Names: CamelCase split"), DisplayName(TEXT("SM_Kit_Block29")), FString(TEXT("Block 29")));
	TestEqual(TEXT("Names: underscores"), DisplayName(TEXT("SM_Buoy_Can")), FString(TEXT("Buoy can")));
	TestEqual(TEXT("Names: a prefix dropped"), DisplayName(TEXT("SM_Vessel_Committee")), FString(TEXT("Committee")));
	return true;
}

// The real registry: every static mesh under the gallery's folders is listed (as an entry or a twin of one), except the
// excluded folders; the kit's light twins and the trees' far twins are grouped.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGalleryRegistryTest, "SailingSim.UI.Gallery.Registry", GalleryFlags)
bool FSailingGalleryRegistryTest::RunTest(const FString&)
{
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	FARFilter Filter;
	Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
	for (const FString& F : SailGallery::RootFolders()) Filter.PackagePaths.Add(FName(*F));
	Filter.bRecursivePaths = true;
	TArray<FAssetData> Found;
	Registry.GetAssets(Filter, Found);
	const TArray<FGalleryItem> Items = SailGallery::ScanRegistry();
	TSet<FString> Listed;
	for (const FGalleryItem& I : Items)
	{
		for (const FSoftObjectPath& P : { I.Mesh, I.Light, I.Far }) if (P.IsValid()) Listed.Add(P.ToString());
	}
	int32 Expected = 0, Missing = 0;
	for (const FAssetData& D : Found)
	{
		if (SailGallery::IsExcluded(D.PackagePath.ToString())) continue;
		++Expected;
		if (!Listed.Contains(D.GetSoftObjectPath().ToString())) { ++Missing; if (Missing <= 5) AddInfo(FString::Printf(TEXT("Not listed: %s"), *D.GetObjectPathString())); }
	}
	AddInfo(FString::Printf(TEXT("%d meshes under the gallery's folders, %d to list, %d entries"), Found.Num(), Expected, Items.Num()));
	TestTrue(TEXT("Some meshes found"), Expected > 50);
	TestEqual(TEXT("Every one listed"), Missing, 0);
	const int32 WithLight = Items.FilterByPredicate([](const FGalleryItem& I) { return I.Light.IsValid(); }).Num();
	const int32 WithFar = Items.FilterByPredicate([](const FGalleryItem& I) { return I.Far.IsValid(); }).Num();
	TestTrue(FString::Printf(TEXT("Kit parts carry their light twins (%d)"), WithLight), WithLight > 10);
	TestTrue(FString::Printf(TEXT("Trees carry their far twins (%d)"), WithFar), WithFar > 5);
	return true;
}

// The stage without a screen: a mesh shown (loaded, standing on the floor, framed), its stats, a forced LOD, the
// wireframe override and the overlay; the graphics snapshot round trip; the framing distance; the compare split.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingGalleryStageTest, "SailingSim.Smoke.GalleryStage", GalleryFlags)
bool FSailingGalleryStageTest::RunTest(const FString&)
{
	TestEqual(TEXT("A 1 m sphere fills 70% of a 46.8 deg view from about 3.1 m"), AGalleryStage::FramingDistanceCm(100.f, 46.8f, 0.7f), 100.f / FMath::Sin(FMath::DegreesToRadians(46.8f * 0.35f)), 0.01f);
	TestEqual(TEXT("Tiers by name"), AGalleryStage::TierFromName(TEXT("ultra")), 3);
	TestEqual(TEXT("And an unknown one"), AGalleryStage::TierFromName(TEXT("Epic")), -1);
	const FIntPoint Size(4, 2);
	TArray<FColor> A, B;
	A.Init(FColor::Red, 8);
	B.Init(FColor::Blue, 8);
	const TArray<FColor> Split = AGalleryStage::CompareSplit(A, B, Size);
	TestTrue(TEXT("Compare: A left, the split white, B right"), Split.Num() == 8 && Split[0] == FColor::Red && Split[2] == FColor::White && Split[7] == FColor::Blue);

	SailGallery::FGraphicsSnapshot Was = SailGallery::FGraphicsSnapshot::Capture();
	USailingSettings* S = USailingSettings::Get();
	const ESailingQuality Q = S->Quality;
	S->Quality = Q == ESailingQuality::Ultra ? ESailingQuality::Low : ESailingQuality::Ultra;
	S->ShadowQuality = 2;
	TestTrue(TEXT("A change shows"), SailGallery::FGraphicsSnapshot::Capture() != Was);
	Was.Restore(nullptr, false);
	TestTrue(TEXT("Restore puts it back"), SailGallery::FGraphicsSnapshot::Capture() == Was && S->Quality == Q);

	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("SailingGalleryWorld"));
	FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	AGalleryStage* Stage = World->SpawnActor<AGalleryStage>();
	if (TestNotNull(TEXT("A stage"), Stage))
	{
		FGalleryItem Cube;
		Cube.Name = TEXT("Cube");
		Cube.Mesh = FSoftObjectPath(TEXT("/Engine/BasicShapes/Cube.Cube"));
		Cube.Key = Cube.Mesh.ToString();
		Stage->Show(Cube);
		for (int32 I = 0; I < 300 && Stage->IsLoading(); ++I) { FlushAsyncLoading(); ++GFrameCounter; World->Tick(LEVELTICK_All, 1.f / 60.f); }
		const FGalleryStats St = Stage->GetStats();
		// The engine's cube is subdivided (48 triangles on this engine): the count is its LOD 0's.
		const UStaticMesh* CubeMesh = Cast<UStaticMesh>(Cube.Mesh.ResolveObject());
		const int32 Lod0 = CubeMesh && CubeMesh->GetRenderData() ? CubeMesh->GetRenderData()->LODResources[0].GetNumTriangles() : -1;
		TestTrue(FString::Printf(TEXT("Shown: the cube's LOD 0 triangles (%d)"), St.Triangles), St.Triangles >= 12 && St.Triangles == Lod0);
		TestTrue(TEXT("A metre across"), St.SizeM.Equals(FVector(1.0), 0.01));
		TestTrue(TEXT("Its path"), St.Path.Contains(TEXT("/Engine/BasicShapes/Cube")));
		const UStaticMeshComponent* D = Stage->FindComponentByClass<UStaticMeshComponent>();
		TestTrue(TEXT("Standing on the floor: its lowest point at the turntable"), D && FMath::IsNearlyEqual(float(D->Bounds.Origin.Z - D->Bounds.BoxExtent.Z), float(Stage->GetActorLocation().Z), 0.5f));
		Stage->SetDetail(EGalleryDetail::Lod, 0);
		TestEqual(TEXT("LOD 0 forced"), D ? D->ForcedLodModel : -1, 1);
		Stage->SetDetail(EGalleryDetail::Auto);
		TestEqual(TEXT("Auto again"), D ? D->ForcedLodModel : -1, 0);
		Stage->SetView(EGalleryView::Wireframe);
		const bool bWireMat = D && D->GetMaterial(0) && D->GetMaterial(0)->GetName() == TEXT("M_GalleryWire");
		TestTrue(TEXT("Wireframe: the wire material on every slot"), bWireMat);
		Stage->SetView(EGalleryView::LitWire);
		TestTrue(TEXT("Lit + wire: its own material with the wire over it"), D && D->GetMaterial(0) && D->GetMaterial(0)->GetName() != TEXT("M_GalleryWire")
			&& D->GetOverlayMaterial() && D->GetOverlayMaterial()->GetName() == TEXT("M_GalleryWire"));
		Stage->SetView(EGalleryView::Lit);
		TestTrue(TEXT("Lit: no overlay"), D && !D->GetOverlayMaterial());
	}
	World->EndPlay(EEndPlayReason::Quit);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

#endif
