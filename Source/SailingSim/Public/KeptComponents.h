#pragma once

#include "CoreMinimal.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "KeptComponents.generated.h"

/**
 * docs/tide-memory: the terrain actor's kept components (ALakeTerrainActor::KeepWithActor: the crown tiles and proxies, the
 * houses and docks, the far ring's tiles, the kit tiles) are Static, so the renderer culls them as still things. But the engine
 * treats a move of a Static (or Stationary) mesh as a reason to throw its render proxy away and build a new one
 * (UStaticMeshComponent::ShouldRecreateProxyOnUpdateTransform is `Mobility != Movable`; FScene::UpdatePrimitiveTransform then
 * runs RemovePrimitive + AddPrimitive). On a coast every 2 cm tide step moves them all, so each step rebuilt about half a
 * million instances' render state: new GPU-scene instance data, ray-tracing instances, cached draw commands. Under D3D12 the
 * memory pool kept about 75-100 MB more after each one (PC, Galveston: Inputs/bench/membisect-galveston/trace-95220b32).
 *
 * These two keep the proxy and take the move in place, as a Movable mesh's move is taken (the engine's static mesh proxy draws
 * through the GPU scene, bStaticElementsAlwaysUseProxyPrimitiveUniformBuffer, so its cached draw commands don't hold the
 * transform; the ray-tracing instances of a cached primitive read their transforms from the GPU scene too). They stay Static
 * for everything else: scene culling's still bins, the shadow cache and the instance culling are as before.
 *
 * -SailingTideRecreate puts the engine's behaviour back (compare, measure): set on each component when it is kept.
 */
UCLASS(ClassGroup = Rendering)
class SAILINGSIM_API USailingKeptMeshComponent : public UStaticMeshComponent
{
	GENERATED_BODY()
public:
	virtual bool ShouldRecreateProxyOnUpdateTransform() const override { return bRecreateOnMove && Super::ShouldRecreateProxyOnUpdateTransform(); }
	/** The engine's behaviour (a new proxy on each move): -SailingTideRecreate. */
	bool bRecreateOnMove = false;
};

UCLASS(ClassGroup = Rendering)
class SAILINGSIM_API USailingKeptInstancesComponent : public UInstancedStaticMeshComponent
{
	GENERATED_BODY()
public:
	virtual bool ShouldRecreateProxyOnUpdateTransform() const override { return bRecreateOnMove && Super::ShouldRecreateProxyOnUpdateTransform(); }
	bool bRecreateOnMove = false;
};

namespace SailingKept
{
	/** -SailingTideRecreate (game thread). */
	SAILINGSIM_API bool RecreateOnMoveArg();
	/** Sets a kept component's choice from the argument (one of the two classes above; anything else is left alone). */
	SAILINGSIM_API void ApplyRecreateOnMove(USceneComponent* Component);
	/** True when a move of the component keeps its render proxy (tests). */
	SAILINGSIM_API bool KeepsProxyOnMove(const UPrimitiveComponent* Component);
}
