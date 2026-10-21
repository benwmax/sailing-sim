#include "Misc/AutomationTest.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/Texture2D.h"

namespace
{
	constexpr EAutomationTestFlags BoatTexFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
}

// Boat texture budget (docs/boat-tex-medium): the hero J/22's baked maps and the boats' close-up detail maps are in the
// Vehicle texture groups, which ASailingGameMode drops a mip on Medium and Low (24 MB for the hero boat there). A texture
// left in a World group would keep its full size on Medium.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualBoatTextureBudgetTest, "SailingSim.Visual.BoatTextureBudget", BoatTexFlags)
bool FVisualBoatTextureBudgetTest::RunTest(const FString& Parameters)
{
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	int32 Count = 0;
	for (const TCHAR* Folder : { TEXT("/Game/Boats/J22Hero/Textures"), TEXT("/Game/Boats/Detail") })
	{
		TArray<FAssetData> Assets;
		Registry.GetAssetsByPath(FName(Folder), Assets, true);
		for (const FAssetData& A : Assets)
		{
			const UTexture2D* Tex = Cast<UTexture2D>(A.GetAsset());
			if (!Tex) continue;
			++Count;
			const bool bVehicle = Tex->LODGroup == TEXTUREGROUP_Vehicle || Tex->LODGroup == TEXTUREGROUP_VehicleNormalMap;
			TestTrue(FString::Printf(TEXT("%s is in a Vehicle texture group"), *A.AssetName.ToString()), bVehicle);
			if (Tex->CompressionSettings == TC_Normalmap) TestEqual(FString::Printf(TEXT("%s: normal map group"), *A.AssetName.ToString()), int32(Tex->LODGroup), int32(TEXTUREGROUP_VehicleNormalMap));
		}
	}
	if (Count == 0) AddWarning(TEXT("No boat textures found (hero not imported?)"));
	else TestTrue(FString::Printf(TEXT("Boat textures checked: %d"), Count), Count >= 20);
	return true;
}
