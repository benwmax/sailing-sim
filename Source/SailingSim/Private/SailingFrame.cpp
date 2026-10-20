#include "SailingFrame.h"
#include "Engine/World.h"

namespace SailingFrame
{
	FVector OriginCm(const UWorld* World)
	{
		return World ? FVector(World->OriginLocation) : FVector::ZeroVector;
	}
}
