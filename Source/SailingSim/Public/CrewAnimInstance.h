#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "CrewMotion.h"
#include "CrewAnimInstance.generated.h"

namespace Sailing { struct FBoatConfig; }

/**
 * Crew C1: one sailor's pose as an animation node, so it runs on the animation worker threads (it used to be posed on
 * the game thread through a UPoseableMeshComponent). The node keeps the sailor's motion state (CrewMotion.h) and
 * writes every bone of the stance, reaction layer, feet, hands and head into the pose.
 */
USTRUCT()
struct SAILINGSIM_API FAnimNode_CrewMotion : public FAnimNode_Base
{
	GENERATED_BODY()

	FCrewMotionInput Input;
	TSharedPtr<const FCrewRig> Rig;                     // null: SK_Sailor's own skeleton
	TSharedPtr<const Sailing::FBoatConfig> Config;      // what the feet stand on
	double HullDepth = 0.25;
	FCrewMotionState State;

	/** Advances the motion (the proxy's update, or Update_AnyThread in a graph). */
	void Advance(float DeltaSeconds);

	virtual void Update_AnyThread(const FAnimationUpdateContext& Context) override;
	virtual void Evaluate_AnyThread(FPoseContext& Output) override;

private:
	TArray<FTransform> CS;
};

/** The proxy runs the node on the worker threads; the game thread hands it the input in PreUpdate. */
struct SAILINGSIM_API FCrewAnimInstanceProxy : public FAnimInstanceProxy
{
	FCrewAnimInstanceProxy() = default;
	explicit FCrewAnimInstanceProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

	FAnimNode_CrewMotion Node;

	virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override;
	virtual void Update(float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;
	virtual void PostEvaluate(UAnimInstance* Instance) override;
};

UCLASS(Transient, NotBlueprintable)
class SAILINGSIM_API UCrewAnimInstance : public UAnimInstance
{
	GENERATED_BODY()
public:
	/** Once, after the mesh is set: the rig (MetaHumans), the boat the sailor is on. */
	void Setup(TSharedPtr<const FCrewRig> InRig, TSharedPtr<const Sailing::FBoatConfig> InConfig, double InHullDepth);
	/** Every frame on the game thread, before the mesh ticks. */
	void SetMotionInput(const FCrewMotionInput& In) { Input = In; }
	const FCrewMotionInput& GetMotionInput() const { return Input; }
	/** What the last pose found (bracing, head tilt). */
	const FCrewMotionReport& GetReport() const { return Report; }

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override { return new FCrewAnimInstanceProxy(this); }
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override { delete static_cast<FCrewAnimInstanceProxy*>(Proxy); }

private:
	friend struct FCrewAnimInstanceProxy;
	FCrewMotionInput Input;
	FCrewMotionReport Report;
	TSharedPtr<const FCrewRig> Rig;
	TSharedPtr<const Sailing::FBoatConfig> Config;
	double HullDepth = 0.25;
	bool bSetupDirty = false;
};
