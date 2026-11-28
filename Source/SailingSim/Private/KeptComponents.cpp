#include "KeptComponents.h"
#include "BenchRunner.h"

namespace SailingKept
{
	bool RecreateOnMoveArg()
	{
		static SailingArgs::FCachedFlag Arg(TEXT("SailingTideRecreate"));
		return Arg.Get();
	}

	void ApplyRecreateOnMove(USceneComponent* Component)
	{
		const bool bRecreate = RecreateOnMoveArg();
		if (USailingKeptMeshComponent* M = Cast<USailingKeptMeshComponent>(Component)) M->bRecreateOnMove = bRecreate;
		else if (USailingKeptInstancesComponent* I = Cast<USailingKeptInstancesComponent>(Component)) I->bRecreateOnMove = bRecreate;
	}

	bool KeepsProxyOnMove(const UPrimitiveComponent* Component)
	{
		return Component && !Component->ShouldRecreateProxyOnUpdateTransform();
	}
}
