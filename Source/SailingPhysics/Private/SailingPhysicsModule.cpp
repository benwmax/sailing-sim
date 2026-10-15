#include "SailingPhysicsModule.h"
#include "Modules/ModuleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Wind.h"

IMPLEMENT_MODULE(FSailingPhysicsModule, SailingPhysics);

void FSailingPhysicsModule::StartupModule()
{
	const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Wind.mann");
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent) || !Sailing::FTurbulenceTile::LoadSharedFromMemory(Bytes.GetData(), size_t(Bytes.Num())))
	{
		UE_LOG(LogTemp, Warning, TEXT("Wind: no turbulence tile at %s (Tools/wind/make_mann_slice.py); the fine turbulence uses its stand-in"), *Path);
	}
}
