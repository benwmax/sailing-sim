#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "SailSession.h"
#include "Learning.h"
#include "Showroom.h"
#include "Gallery.h"

class SBox;
class APlayerController;

/**
 * Graphics G4: the front end and the in-game menus (ui-spec.md section 5) as one Slate widget with a screen stack:
 * Title, then World, Launch spot, Boat, Conditions and Mode (each pushes the next; Back walks the flow back with the
 * choices kept), and in game Pause, Change conditions, Settings and Controls. Cast off hands the session to
 * USailSessionSubsystem, which reloads the map with it. Credits (from the Title and Settings) reads CREDITS.md.
 */
enum class ESailScreen : uint8 { Title, World, Launch, Boat, Conditions, Mode, Pause, ConditionsInGame, Settings, Controls, Confirm, Briefing, Quiz, Credits, Career, Gallery, Feedback };

class SAILINGSIM_API SSailFrontEnd : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailFrontEnd) : _Start(ESailScreen::Title) {}
		SLATE_ARGUMENT(ESailScreen, Start)
		SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
		/** The menus closed (Resume, or the title's Logbook and Replays): the game takes input again. */
		SLATE_EVENT(FSimpleDelegate, OnClose)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	/** The showroom behind the menus ends with them (and a front-end choice is kept for the next time they open). */
	virtual ~SSailFrontEnd() override;
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	/** Controls: a listening row takes the next key before the focused button sees it (so Enter and A can be bound). */
	virtual FReply OnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	/** Credits and the world cards: the sticks scroll the text. */
	virtual FReply OnAnalogValueChanged(const FGeometry& Geometry, const FAnalogInputEvent& Event) override;
	virtual bool SupportsKeyboardFocus() const override { return true; }
	/** The Boat screen (docs/showroom/pc/): a drag on empty space turns the showroom's camera, the wheel zooms it. */
	virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& Event) override;
	virtual FReply OnMouseWheel(const FGeometry& Geometry, const FPointerEvent& Event) override;

	void Push(ESailScreen Screen);
	/** The pause menu's Send feedback: a shot of the view without the menus, then the form (docs/sentry). */
	void OpenFeedback();
	/**
	 * docs/showroom-world/: leaving the World screen for a world other than the one loaded loads it behind the menus (a
	 * short wipe, the map reloads, the menus come back on the Launch screen with the choices kept), so the showroom and the
	 * conditions preview show the real place. Not in game.
	 */
	static bool TravelsOnPush(ESailScreen From, ESailScreen To, bool bInGame, int32 PendingWorld, int32 LoadedWorld);
	/** Back: pops a screen; on the root it does what that root's Back means (Pause: resume). */
	void Pop();
	/** Puts keyboard focus on the current screen's default target (after the widget is in the viewport). */
	void FocusCurrent();
	ESailScreen Current() const { return Stack.Num() ? Stack.Last().Screen : ESailScreen::Title; }

private:
	struct FEntry
	{
		ESailScreen Screen = ESailScreen::Title;
		TSharedPtr<SWidget> Content, Focus, Footer;
	};
	FEntry Build(ESailScreen Screen);
	FEntry BuildTitle();
	FEntry BuildWorld();
	FEntry BuildLaunch();
	FEntry BuildBoat();
	FEntry BuildConditions(bool bInGame);
	FEntry BuildMode();
	FEntry BuildPause();
	FEntry BuildSettings();
	FEntry BuildControls();
	FEntry BuildConfirm();
	/** Graphics G7: the drill's briefing (Content/Learning) and the quiz after it. */
	FEntry BuildBriefing();
	FEntry BuildQuiz();
	void StartQuiz();
	/** Career 1 (docs/career): the tiers, the chosen tier's lessons with their medals, its checkride and certificate. */
	FEntry BuildCareer();
	/** Release readiness: every credit in CREDITS.md, after the Unreal Engine notice, as scrolling text. */
	FEntry BuildCredits();
	/** The developer-only asset gallery (docs/gallery/pc/, Inputs/gallery/brief.md G2; UI/SailGallery.cpp). */
	FEntry BuildGallery();
	/** Testers' bug and idea form (docs/sentry, #410): opened from the pause menu over a shot of the view. */
	FEntry BuildFeedback();
	void SendFeedbackForm();
	void Show(const FEntry& Entry, bool bForward);
	void CastOff();
	void Close();
	void Confirm(const FString& Question, const FString& Yes, TFunction<void()> OnYes);
	/** Two answers (the gallery's "Keep these graphics settings?"): the second has focus; Esc cancels (neither). */
	void Confirm(const FString& Question, const FString& Yes, TFunction<void()> OnYes, const FString& No, TFunction<void()> OnNo);
	class ASailboatPawn* Pawn() const;

	TWeakObjectPtr<APlayerController> Player;
	FSimpleDelegate OnClose;
	TArray<FEntry> Stack;
	TSharedPtr<SBox> Body, Footer;
	FSailSessionConfig Pending;
	/** docs/showroom-wiring/: the boat and the conditions behind the screens (FSailShowroom), driven each frame. */
	FSailShowroom Showroom;
	bool bMenusInGame = false;
	/** Stills: -SailingShowroom=<boat type> shows that boat on the Boat screen (-1: the focused one). */
	int32 ShowroomArg = -1;
	EActiveTimerReturnType TickShowroom(double Time, float Delta);
	/** The wipe over the reload, then the travel (a frame later, so the wipe is drawn). */
	void TravelToWorld(ESailScreen Resume);
	bool bTravelling = false;
	class ASailingGameMode* GameMode() const;
	int32 FocusedBoat = 0;
	int32 SettingsTab = 0;
	/** Bean's UI feedback (Oct 27): a clicked tab pill, a keycap, Q/E and LB/RB all come here; the rebuilt screen focuses
	 *  the tab's first row once it is laid out (Show). */
	void SetSettingsTab(int32 Tab);
	FString ConfirmQuestion, ConfirmYes, ConfirmNo;
	// The feedback form's draft, kept while the screen is rebuilt.
	int32 FeedbackKind = 0;            // EFeedbackKind
	bool bFeedbackPlace = false;       // ideas: attach where I am
	FString FeedbackTitle, FeedbackText, FeedbackExpected, FeedbackShot, FeedbackResult;
	// The quiz: its questions, the one on screen, the option chosen (-1: not yet), the score and the debrief line.
	TArray<FQuizQuestion> Quiz;
	int32 QuizIndex = 0, QuizChosen = -1, QuizRight = 0;
	FString QuizDebrief, QuizDrillName;
	// Career 1: the tier shown on the Career screen; the checkride whose quiz is running (empty: a drill's quiz); the
	// lesson a drill's quiz closes; the career's line on the quiz's last page.
	FString CareerTierId, CheckrideTierId, QuizLessonId, QuizCareerLine;
	// Free Sail: the title was rebuilt by its Mode switch, so the switch keeps the focus.
	bool bTitleFocusMode = false;
	TFunction<void()> ConfirmAction, ConfirmNoAction;
	// Screen transitions (3.3): a 180 ms fade with a 24 px slide.
	double TransitionStart = 0.0;
	bool bTransitionForward = true;
	EActiveTimerReturnType AnimateTransition(double Time, float Delta);
	// Controls: the row being rebound, listening for the next key (a keyboard key, or a gamepad button when bListeningPad),
	// and the row that has focus (Tab or Y rebinds its gamepad button).
	int32 ListeningRow = -1;
	bool bListeningPad = false;
	int32 FocusedControlRow = 0;
	void ListenControls(int32 Row, bool bPad);
	FString ControlsMessage;
	// Credits: its scroll box. World: each card's description (the focused card's scrolls). The stick's scroll speed
	// (-1..1, held while the stick is) is applied to the active one by an active timer.
	TSharedPtr<class SScrollBox> CreditsScroll;
	TArray<TSharedPtr<class SScrollBox>> WorldScrolls;
	TArray<TSharedPtr<class SSailButton>> WorldCards;
	/** The scroll box the arrows, pages and sticks move on this screen: Credits' text, or the focused world card's. */
	TSharedPtr<class SScrollBox> ActiveScroll() const;
	float ScrollStick = 0.f;
	EActiveTimerReturnType ScrollActive(double Time, float Delta);
	// The showroom's Boat screen (Inputs/ui-showroom/brief.md section 2): the strip's cards, View mode (the panels hidden),
	// the right stick's held look and the triggers' zoom (applied by an active timer), a drag on empty space.
	TArray<TSharedPtr<class SSailButton>> BoatCards;
	TArray<int32> BoatCardTypes;
	bool bViewMode = false;
	FVector2D OrbitStick = FVector2D::ZeroVector;
	float OrbitZoomStick = 0.f, OrbitZoomCarry = 0.f;
	bool bOrbitDrag = false;
	/** The showroom's screens (the Boat screen, Conditions and Change conditions): orbit input, View mode, the clear backdrop. */
	bool IsStageScreen() const;
	// The Conditions screen's blends (Inputs/ui-showroom/brief.md section 6): what the world shows, easing toward the
	// pending choice (the wind over about 2 s, the clock as the slider moves), re-previewed five times a second.
	FSailConditions Blend;
	bool bBlendLive = false;
	double BlendAppliedAt = 0.0, BlendTickAt = 0.0;
	/** Moves along the strip (LB/RB, Q/E): the next boat is shown and focused. */
	void StepBoat(int32 Dir);
	EActiveTimerReturnType TickOrbitStick(double Time, float Delta);

	// The gallery (UI/SailGallery.cpp): its stage and index, the filters (search, category, tags), the list's rows (each
	// row's item index), the selection, the views (full screen, clean, the viewer focused, the folded cards, More, the
	// compare split), and the thumbnails rendered on the fly.
	TWeakObjectPtr<class AGalleryStage> GalleryStage;
	TArray<FGalleryItem> GalleryItems;
	FString GallerySearch, GalleryCategory = TEXT("All");
	TArray<FString> GalleryTags;
	TSharedPtr<class SScrollBox> GalleryList;
	TSharedPtr<class SWrapBox> GalleryChips, GalleryTagChips;
	TSharedPtr<class SEditableText> GallerySearchBox;
	TArray<TSharedPtr<class SSailButton>> GalleryRows;
	TArray<int32> GalleryRowItems;
	int32 GallerySelected = -1, GalleryMatches = 0;
	bool bGalleryFull = false, bGalleryClean = false, bGalleryViewer = false, bGalleryFolded = false, bGalleryMore = false;
	bool bGalleryCompareShown = false, bGalleryCompareAsked = false, bGalleryPanDrag = false;
	uint8 GalleryCompareA = 0, GalleryCompareB = 3;
	FVector2D GalleryPanStick = FVector2D::ZeroVector;
	TSharedPtr<struct FGalleryThumbs> GalleryThumbs;
	bool IsGallery() const { return Current() == ESailScreen::Gallery; }
	void OpenGallery();
	/** Leaving: the stage closes; graphics changed in the gallery are kept or restored (the caller asked). */
	void CloseGallery(bool bRestoreGraphics);
	/** The list, the chips and the counts again from the filters (focus to the first row when bFocusFirst). */
	void RefreshGallery(bool bFocusFirst);
	void SelectGalleryItem(int32 Item);
	void StepGalleryCategory(int32 Dir);
	void FocusGalleryRow();
	/** The gallery's keys and buttons (before the screen's own); Handled when it took one. */
	FReply GalleryKeyDown(const FKeyEvent& Event);
	/** Esc / B in the gallery: out of compare, clean, full screen or the viewer first; then leave (asking about graphics). */
	void GalleryBack();
	EActiveTimerReturnType TickGallery(double Time, float Delta);
};
