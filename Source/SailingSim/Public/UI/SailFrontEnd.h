#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "SailSession.h"
#include "Learning.h"
#include "Showroom.h"

class SBox;
class APlayerController;

/**
 * Graphics G4: the front end and the in-game menus (ui-spec.md section 5) as one Slate widget with a screen stack:
 * Title, then World, Launch spot, Boat, Conditions and Mode (each pushes the next; Back walks the flow back with the
 * choices kept), and in game Pause, Change conditions, Settings and Controls. Cast off hands the session to
 * USailSessionSubsystem, which reloads the map with it. Credits (from the Title and Settings) reads CREDITS.md.
 */
enum class ESailScreen : uint8 { Title, World, Launch, Boat, Conditions, Mode, Pause, ConditionsInGame, Settings, Controls, Confirm, Briefing, Quiz, Credits, Career };

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

	void Push(ESailScreen Screen);
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
	void Show(const FEntry& Entry, bool bForward);
	void CastOff();
	void Close();
	void Confirm(const FString& Question, const FString& Yes, TFunction<void()> OnYes);
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
	class ASailingGameMode* GameMode() const;
	int32 FocusedBoat = 0;
	int32 SettingsTab = 0;
	/** Bean's UI feedback (Oct 27): a clicked tab pill, a keycap, Q/E and LB/RB all come here; the rebuilt screen focuses
	 *  the tab's first row once it is laid out (Show). */
	void SetSettingsTab(int32 Tab);
	FString ConfirmQuestion, ConfirmYes;
	// The quiz: its questions, the one on screen, the option chosen (-1: not yet), the score and the debrief line.
	TArray<FQuizQuestion> Quiz;
	int32 QuizIndex = 0, QuizChosen = -1, QuizRight = 0;
	FString QuizDebrief, QuizDrillName;
	// Career 1: the tier shown on the Career screen; the checkride whose quiz is running (empty: a drill's quiz); the
	// lesson a drill's quiz closes; the career's line on the quiz's last page.
	FString CareerTierId, CheckrideTierId, QuizLessonId, QuizCareerLine;
	// Free Sail: the title was rebuilt by its Mode switch, so the switch keeps the focus.
	bool bTitleFocusMode = false;
	TFunction<void()> ConfirmAction;
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
};
