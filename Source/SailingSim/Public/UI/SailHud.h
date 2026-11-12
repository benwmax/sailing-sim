#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class APlayerController;
class ASailboatPawn;
namespace Sailing { class FScriptedScene; }

/**
 * Graphics G4: the in-game HUD (ui-spec.md 5.8) in Slate, replacing the canvas instruments: the environment strip,
 * compass tape and heading, learning tip card, drill panel, toast line, sail trim panel, instrument cluster (speed,
 * apparent wind dial, depth), minimap and key hints. Dials, tape and map are painted every frame; text refreshes at
 * 10 Hz (a real instrument's damping, and no text rebuilt each frame). H cycles Full, Minimal and Off.
 */
class SAILINGSIM_API SSailHud : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailHud) {}
		SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual void Tick(const FGeometry& Geometry, const double CurrentTime, const float DeltaTime) override;
	/** 0 full, 1 minimal (cluster, compass, drill panel, toasts), 2 off (toasts only). */
	static int32 Mode;
	/** #596: the learning tip card stays down while a scripted scene runs (the first job's instructor is the coach there;
	 *  the two had talked at once with different instructions), and through a finished scene's handover to its lesson
	 *  (bHandoverPending: the instructor's last line is still up). */
	static bool TipsMutedByScene(const Sailing::FScriptedScene* Scene, bool bHandoverPending = false);
	/** #602: where a map point (north, east m) falls on the minimap (north up, the boat at the centre, SpanM across the
	 *  drawn square of Size px at Origin). One beyond the square's edge is pulled in onto it (bClamped), so its direction
	 *  still shows. */
	static FVector2f MiniMapPoint(const FVector2D& BoatMap, const FVector2D& TargetMap, double SpanM, const FVector2f& Origin, const FVector2f& Size, bool& bClamped);
	/** #602 polish: an edge-clamped dot moved along its edge out of the Keep boxes (the N label, the wind arrow), Radius clear. */
	static FVector2f MiniMapClearOf(const FVector2f& Q, float Radius, TArrayView<const FBox2f> Keep, const FVector2f& Origin, const FVector2f& Size);

	ASailboatPawn* Pawn() const;

private:
	void Refresh();
	void RefreshTraffic(const ASailboatPawn& P, const class ASailingGameMode& GM);
	void RefreshScene(const ASailboatPawn& P, const class ASailingGameMode& GM);
	TWeakObjectPtr<APlayerController> Player;
	double NextRefresh = 0.0;
	// Text refreshed at 10 Hz.
	FText TimeText, WindText, SkyText, TideText, HeadingText, SpeedText, SpeedSub, DepthText, DepthSub, AwaText, AwsText,
		PointText, SpeedUnitText, DepthUnitText, TipTitle, TipBody, ToastText, DrillTitle, DrillFooter, HintsText;
	FLinearColor ToastColor = FLinearColor::White;
	bool bShallow = false, bTidal = false, bTip = false, bDrill = false, bToast = false;
	// Prologue step 1: the captain's call (FScriptedScene's caption) and the keys that answer it.
	bool bCaptain = false;
	FText CaptainWho = FText::FromString(TEXT("Captain")); // #402: who speaks: "Instructor" in the first job (its calls are instructor.*)
	FText CaptainText, CaptainHint, CaptainStation; // step 2: the station the player is at ("You: jib trimmer")
	double ToastSince = 0.0;
	FString LastToast, LastTip;
	double TipShownAt = 0.0;
	TArray<TTuple<FString, int32, FString>> DrillSteps;   // text, 0 upcoming 1 current 2 done, coach line
	TSharedPtr<class SVerticalBox> DrillList;
	TSharedPtr<struct FSlateBrush> MapBrush;
	// Traffic (the rules coach's callout and the signals heard), the race and the coast's navigation panel.
	bool bCoach = false, bSignals = false, bRace = false, bNav = false, bCoast = false;
	// Sound captions (USoundCaptions), refreshed with the rest at 10 Hz.
	bool bCaptions = false;
	FText CaptionsText;
	FText CoachWho, CoachRole, CoachReason, CoachAction, CoachCpa, SignalsText, ScoreText, RaceHead, RaceTask, RaceLine, RaceResults, NavText, NextText;
	FLinearColor CoachRoleColor = FLinearColor::White, CoachCpaColor = FLinearColor::White, RaceHeadColor = FLinearColor::White, RaceTaskColor = FLinearColor::White,
		RaceLineColor = FLinearColor::White, ScoreColor = FLinearColor::White;
};
