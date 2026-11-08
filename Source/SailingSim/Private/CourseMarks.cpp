#include "CourseMarks.h"

#include "Engine/StaticMesh.h"
#include "Misc/PackageName.h"
#include "UObject/UObjectGlobals.h"

UStaticMesh* CourseMarks::Load(const TCHAR* Part)
{
	const FString Package = FString::Printf(TEXT("/Game/Boats/Kit/SM_Kit_%s"), Part);
	if (!FPackageName::DoesPackageExist(Package)) return nullptr;
	return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("%s.SM_Kit_%s"), *Package, Part));
}
