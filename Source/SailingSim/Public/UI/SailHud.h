#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class APlayerController;
class ASailboatPawn;

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

	ASailboatPawn* Pawn() const;

private:
	void Refresh();
	void RefreshTraffic(const ASailboatPawn& P, const class ASailingGameMode& GM);
	void RefreshScene(const class ASailingGameMode& GM);
	TWeakObjectPtr<APlayerController> Player;
	double NextRefresh = 0.0;
	// Text refreshed at 10 Hz.
	FText TimeText, WindText, SkyText, TideText, HeadingText, SpeedText, SpeedSub, DepthText, DepthSub, AwaText, AwsText,
		PointText, SpeedUnitText, DepthUnitText, TipTitle, TipBody, ToastText, DrillTitle, DrillFooter, HintsText;
	FLinearColor ToastColor = FLinearColor::White;
	bool bShallow = false, bTidal = false, bTip = false, bDrill = false, bToast = false;
	// Prologue step 1: the captain's call (FScriptedScene's caption) and the keys that answer it.
	bool bCaptain = false;
	FText CaptainText, CaptainHint;
	double ToastSince = 0.0;
	FString LastToast, LastTip;
	double TipShownAt = 0.0;
	TArray<TTuple<FString, int32, FString>> DrillSteps;   // text, 0 upcoming 1 current 2 done, coach line
	TSharedPtr<class SVerticalBox> DrillList;
	TSharedPtr<struct FSlateBrush> MapBrush;
	// Traffic (the rules coach's callout and the signals heard), the race and the coast's navigation panel.
	bool bCoach = false, bSignals = false, bRace = false, bNav = false;
	FText CoachWho, CoachRole, CoachReason, CoachAction, CoachCpa, SignalsText, ScoreText, RaceHead, RaceTask, RaceLine, RaceResults, NavText, NextText;
	FLinearColor CoachRoleColor = FLinearColor::White, CoachCpaColor = FLinearColor::White, RaceHeadColor = FLinearColor::White, RaceTaskColor = FLinearColor::White,
		RaceLineColor = FLinearColor::White, ScoreColor = FLinearColor::White;
};
