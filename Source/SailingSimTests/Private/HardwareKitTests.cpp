#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "Materials/MaterialInterface.h"

namespace
{
	constexpr EAutomationTestFlags HardwareKitFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	// Phase 0's budget for a non-Nanite boat part (docs/boat-fidelity-0): the light versions stay inside it.
	constexpr int32 LightMaxTris = 40000;
	constexpr int32 LightMaxSlots = 8;
}

// Boat fidelity 2 (docs/boat-fidelity-2): the deck hardware kit. Every part in Inputs/boat-kit/kit.json (written by
// scripts/import_hardware_kit.py) is imported to /Game/Boats/Kit twice: the hero as Nanite and the light version without,
// inside phase 0's budget; both carry every socket the kit names, where the kit put it (Blender's +Y is Unreal's -Y), and
// every slot has its MI_Kit_ instance. Skipped (with a warning) before the kit is imported.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualHardwareKitTest, "SailingSim.Visual.HardwareKit", HardwareKitFlags)
bool FVisualHardwareKitTest::RunTest(const FString& Parameters)
{
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectDir(), TEXT("Inputs/boat-kit/kit.json"))))
	{
		AddWarning(TEXT("No Inputs/boat-kit/kit.json: run make-boatkit and import_hardware_kit.py"));
		return true;
	}
	TSharedPtr<FJsonObject> Kit;
	if (!TestTrue(TEXT("kit.json parses"), FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Kit) && Kit.IsValid()))
	{
		return false;
	}
	TestTrue(FString::Printf(TEXT("At least 25 parts (%d)"), Kit->Values.Num()), Kit->Values.Num() >= 25);
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Part : Kit->Values)
	{
		const TSharedPtr<FJsonObject> Info = Part.Value->AsObject();
		const TSharedPtr<FJsonObject>* Sockets = nullptr;
		Info->TryGetObjectField(TEXT("sockets"), Sockets);
		for (const bool bLight : { false, true })
		{
			const FString Name = FString::Printf(TEXT("SM_Kit_%s%s"), *Part.Key, bLight ? TEXT("_Light") : TEXT(""));
			const FString Path = FString::Printf(TEXT("/Game/Boats/Kit/%s.%s"), *Name, *Name);
			UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
			if (!TestNotNull(Name, Mesh))
			{
				continue;
			}
			TestEqual(FString::Printf(TEXT("%s Nanite"), *Name), Mesh->IsNaniteEnabled(), !bLight);
			if (bLight)
			{
				const int32 Tris = Mesh->GetNumTriangles(0);
				TestTrue(FString::Printf(TEXT("%s: %d triangles within %d"), *Name, Tris, LightMaxTris), Tris > 0 && Tris <= LightMaxTris);
				TestTrue(FString::Printf(TEXT("%s: %d slots within %d"), *Name, Mesh->GetStaticMaterials().Num(), LightMaxSlots), Mesh->GetStaticMaterials().Num() <= LightMaxSlots);
			}
			for (const FStaticMaterial& M : Mesh->GetStaticMaterials())
			{
				TestTrue(FString::Printf(TEXT("%s: slot %s has its kit material"), *Name, *M.MaterialSlotName.ToString()),
					M.MaterialInterface && M.MaterialInterface->GetName() == FString::Printf(TEXT("MI_Kit_%s"), *M.MaterialSlotName.ToString()));
			}
			if (!Sockets)
			{
				continue;
			}
			for (const TPair<FString, TSharedPtr<FJsonValue>>& S : (*Sockets)->Values)
			{
				const UStaticMeshSocket* Socket = Mesh->FindSocket(FName(*S.Key));
				if (!TestNotNull(FString::Printf(TEXT("%s socket %s"), *Name, *S.Key), Socket))
				{
					continue;
				}
				const TArray<TSharedPtr<FJsonValue>>& P = S.Value->AsArray();
				const FVector Want(P[0]->AsNumber() * 100.0, -P[1]->AsNumber() * 100.0, P[2]->AsNumber() * 100.0);
				TestTrue(FString::Printf(TEXT("%s socket %s at (%.2f, %.2f, %.2f) cm, the kit's (%.2f, %.2f, %.2f)"), *Name, *S.Key,
					Socket->RelativeLocation.X, Socket->RelativeLocation.Y, Socket->RelativeLocation.Z, Want.X, Want.Y, Want.Z),
					FVector::Dist(Socket->RelativeLocation, Want) < 0.1);
			}
		}
	}
	return true;
}
