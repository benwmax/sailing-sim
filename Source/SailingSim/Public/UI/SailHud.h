#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class APlayerController;
class ASailboatPawn;
namespace Sailing { class FScriptedScene; struct FBoatTelemetry; struct FBoatConfig; struct FSailStripState; struct FEasyAssists; }
enum class ETelltaleState : uint8;

/**
 * Graphics G4: the in-game HUD (ui-spec.md 5.8) in Slate, replacing the canvas instruments: the environment strip,
 * compass tape and heading, learning tip card, drill panel, toast line, sail trim panel, instrument cluster (speed,
 * apparent wind dial, depth), minimap and key hints. Dials, tape and map are painted every frame; text refreshes at
 * 10 Hz (a real instrument's damping, and no text rebuilt each frame). H cycles Full, Minimal and Off (Bean's UI Helpful,
 * UI Natural and UI Off: the trim panel follows them, docs/trim-panel/).
 * Layout (docs/hud-layout/, Bean Nov 15 2026): minimap top right above the drill, race and navigation panels; speed,
 * apparent wind and depth bottom left; the bottom centre left clear for the boat; messages (the captain's call, toasts,
 * rules points, signals heard, sound captions) on solid cards centre right, left of the right-hand panels when they show.
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
	/** The night palette (docs/ui-overhaul/, Phase 6): a HUD colour as it is drawn after dark. Red takes the colour's
	 *  brightness, then (bTint) green and blue are cut; Amount 0 is the day colour. Text inside the HUD's tinted panel
	 *  passes bTint false (the panel's tint does the cut). */
	static FLinearColor NightColor(const FLinearColor& C, float Amount, bool bTint = true);
	/** How far the palette is in for the environment's night amount (0 day .. 1 dark), in 1/16 steps; 0 when the player
	 *  turned it off (Settings > Display > Night colours). */
	static float NightHudAmount(float NightAmount, bool bEnabled);
	static constexpr float NightTintGreen = 0.2f;
	static constexpr float NightTintBlue = 0.14f;
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

	/** The sail trim panel's plain line in UI Helpful (Bean, Nov 15 2026, docs/trim-panel/): the coach's tips
	 *  (SailingCollectBoatTips) in one headline and a short what-to-do, the most urgent first, so the panel never says all
	 *  is well beside a tip that says otherwise. bGood when all is well; bNeutral at the dock. bHoldNoGo: the tips'
	 *  start hold on the no-go cue (SailingNoGoTipHoldSeconds). */
	struct FTrimVerdict
	{
		const TCHAR* Head = TEXT("");
		const TCHAR* Say = TEXT("");
		bool bGood = false;
		bool bNeutral = false;
	};
	static FTrimVerdict TrimVerdict(const Sailing::FBoatTelemetry& T, const Sailing::FBoatConfig& Cfg, const Sailing::FEasyAssists& Easy,
		bool bTiedUp, bool bHoldNoGo = false);
	/** Which of a sail's NumStrips strips a telltale HeightFraction up it reads (the 3D ribbons' mapping). */
	static int32 TrimStripAt(float HeightFraction, int32 NumStrips);
	/** The panel's yarns: the luff's near (windward) and far (leeward) yarns and the leech ribbons. */
	enum class ETrimYarn : uint8 { LuffWindward, LuffLeeward, Leech };
	/** What the panel's yarn on one third of a sail shows (Band 0 the bottom third, 2 the top): the 3D ribbons' rules
	 *  (JibTelltaleState, LeechTelltaleState) on every strip in that third, the worst of them, so any call the verdict
	 *  makes from two strips shows on at least one yarn. A third with no strip of its own reads the strip at its middle. */
	static ETelltaleState TrimYarnState(const Sailing::FSailStripState* Strips, int32 NumStrips, int32 Band, ETrimYarn Yarn);
	/** The learning tip card keeps a tip at least this long unless a warning replaces it; the trim panel's headline holds a
	 *  warning as long, so the two change together and a strip flickering on the edge doesn't blink either. */
	static constexpr double TipHoldSeconds = 6.0;
	/** The same headline's line changes no faster than this. */
	static constexpr double TrimSayHoldSeconds = 1.5;
	/** What the trim panel shows now (TrimVerdict held): a warning or a change at the dock shows at once; a warning stays
	 *  until it has been up TipHoldSeconds (the tip card's rule). */
	struct FTrimVerdictHold
	{
		FTrimVerdict Shown;
		double ShownAt = -1.0e9;
		double SayAt = -1.0e9;
	};
	static FTrimVerdict HoldTrimVerdict(FTrimVerdictHold& Hold, const FTrimVerdict& Fresh, double Now);

	ASailboatPawn* Pawn() const;
	/** The right-hand column's width (minimap, drill, race and navigation panels) and the gap the messages keep from it. */
	static constexpr float RightColumnWidth = 365.f;
	static constexpr float MessageGap = 20.f;
	/** The centre-right message stack's widest card: no wider than MessageMaxWidth, and kept right of the screen's centre
	 *  (the boat) where the screen allows, never narrower than MessageMinWidth. LayoutWidth is the HUD's own width (after
	 *  Settings > HUD size). */
	static constexpr float MessageMaxWidth = 460.f;
	static constexpr float MessageMinWidth = 300.f;
	static float MessageWidthFor(float LayoutWidth, bool bRightPanels);

private:
	void Refresh();
	void RefreshTraffic(const ASailboatPawn& P, const class ASailingGameMode& GM);
	void RefreshScene(const ASailboatPawn& P, const class ASailingGameMode& GM);
	TWeakObjectPtr<APlayerController> Player;
	TWeakObjectPtr<class ASailingEnvironment> Environment;
	double NextRefresh = 0.0;
	/** Whether the right-hand column shows a panel under the minimap (the messages then sit left of it). */
	bool RightPanelsShown() const;
	/** The HUD's width in its own units (Settings > HUD size applied), from the last tick. */
	float LayoutWidth = 1920.f;
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
	/** The sail trim panel's headline, judged in Refresh beside the tip card (HoldTrimVerdict). */
	FTrimVerdictHold TrimHold;
	FTrimVerdict TrimShown;
	TArray<TTuple<FString, int32, FString>> DrillSteps;   // text, 0 upcoming 1 current 2 done, coach line
	TSharedPtr<class SVerticalBox> DrillList;
	// The right-hand column's panels (drill, race, navigation) and the room they have between the minimap and the sail trim
	// panel. When they need more than that room they shed whole lines, one fit level at a time (RightFit, 0 = everything):
	// 1 the drill footer's mode, 2 the coach's lines, 3 every step but the current one, 4 the race's detail lines and the
	// navigation text, 5 the navigation panel, 6 the drill's step and the race score, 7 the race's task (its headline
	// stays). A level is undone once the room holds the height measured before it (RightFitHeights). Never a cut line.
	TSharedPtr<class SBox> RightPanels, RightPanelsRoom;
	static constexpr int32 RightFitMax = 7;
	int32 RightFit = 0;
	float RightFitHeights[RightFitMax] = {};
	uint32 RightFitKey = 0;
	double RightFitHold = 0.0;
	bool Fit(int32 Level) const { return RightFit >= Level; }
	// The left-hand column's cards (strip, tip, rules callout) and their room above the instruments: bCompactLeft drops the
	// explainer lines (the callout's reason, the tip card's footer) until the room holds FullLeftHeight again.
	TSharedPtr<class SBox> LeftPanels, LeftPanelsRoom;
	bool bCompactLeft = false;
	float FullLeftHeight = 0.f;
	TSharedPtr<struct FSlateBrush> MapBrush;
	// Traffic (the rules coach's callout and the signals heard), the race and the coast's navigation panel.
	bool bCoach = false, bSignals = false, bRace = false, bNav = false, bCoast = false;
	// Sound captions (USoundCaptions), refreshed with the rest at 10 Hz.
	bool bCaptions = false;
	FText CaptionsText;
	// The latest rules judgment as its own points card ("+20", what it was for), kept 8 s.
	bool bPoints = false;
	FText PointsValue, PointsText;
	FLinearColor PointsColor = FLinearColor::White;
	FText CoachWho, CoachRole, CoachReason, CoachAction, CoachCpa, SignalsText, ScoreText, RaceHead, RaceTask, RaceLine, RaceResults, NavText, NextText;
	FLinearColor CoachRoleColor = FLinearColor::White, CoachCpaColor = FLinearColor::White, RaceHeadColor = FLinearColor::White, RaceTaskColor = FLinearColor::White,
		RaceLineColor = FLinearColor::White, ScoreColor = FLinearColor::White;
};
