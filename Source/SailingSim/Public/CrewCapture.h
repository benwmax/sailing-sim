#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CrewCapture.generated.h"

class UAnimSequence;
class USkeletalMesh;

/**
 * Crew C2: motion capture for the crew. Bean films himself on a mock cockpit; MetaHuman Animator's markerless body solve
 * (a Fab plugin, Windows only) turns each clip into an animation on the MetaHuman body skeleton. These carry it to the
 * crew's skeletons (SK_Sailor's, and each MetaHuman's) and trim it by the clip list (Tools/capture/clips.csv, run by
 * Tools/capture/capture_clips.py). Editor only; the script saves what they return.
 *
 * The retarget is the one FCrewRig already defines between the two skeletons: a pose is each bone's component-space
 * turn from a T-posed rest (CrewSolver), and the MetaHuman's rest is turned into SK_Sailor's T-pose in SK_Sailor's frame
 * (BuildCrewRig). So a source frame's turns, carried into the target's frame and onto the matching bones (SK_Sailor's
 * spine from the MetaHuman's spine_02, chest from spine_05, neck from neck_02, forearm from lowerarm), pose the target;
 * the pelvis moves as the source's does, scaled by the pelvis heights. Bones without a match follow their parent.
 */
UCLASS()
class SAILINGSIM_API UCrewCaptureLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Retargets Source (an animation for SourceMesh's skeleton) to TargetMesh's skeleton, from StartSeconds to EndSeconds
	 *  (EndSeconds <= 0: to the end), resampled at Fps. AssetPath "/Game/..." creates the asset there (unsaved); empty
	 *  makes a transient one. Same skeleton: a trimmed copy. bLevelHeading turns the whole clip about the vertical so the
	 *  hips face as the rest pose's do at the source's first frame, and slides it so the pelvis starts over the rest
	 *  pose's: a body solve gives the heading and place in the camera's frame (the README films from 30-45 deg off
	 *  square), and every clip starts sitting still on the seat, facing forward. */
	UFUNCTION(BlueprintCallable, Category = "Sailing|Crew")
	static UAnimSequence* RetargetClip(UAnimSequence* Source, USkeletalMesh* SourceMesh, USkeletalMesh* TargetMesh, float StartSeconds,
		float EndSeconds, int32 Fps, const FString& AssetPath, bool bLevelHeading = false);

	/** The turn about the vertical (component Z) that brings Mesh's hip axis (thigh_l to thigh_r) at Seq's Seconds onto
	 *  its rest pose's; identity without both thighs. */
	static FQuat HeadingToRest(const UAnimSequence* Seq, const USkeletalMesh* Mesh, double Seconds);

	/** A synthetic clip on Mesh's skeleton from the crew's own stances (CrewJointRotations), to test the pipeline before
	 *  any filmed clip exists: Spec is "Stance[:hike]=seconds,..." (e.g. "Helm=3,Crossing=2,Helm:1=3"), each stance
	 *  blended in over the first 40% of its time. */
	UFUNCTION(BlueprintCallable, Category = "Sailing|Crew")
	static UAnimSequence* MakeStanceClip(USkeletalMesh* Mesh, const FString& Spec, int32 Fps, const FString& AssetPath);

	/** Component-space bone transforms of Mesh posed by Seq at Seconds (the reference pose where a bone has no track). */
	static void EvaluateClip(const UAnimSequence* Seq, const USkeletalMesh* Mesh, double Seconds, TArray<FTransform>& OutCS);
	/** The clip's length in seconds. */
	static double ClipSeconds(const UAnimSequence* Seq);
};
