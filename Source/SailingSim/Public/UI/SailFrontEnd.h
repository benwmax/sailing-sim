#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "SailSession.h"
#include "Learning.h"

class SBox;
class APlayerController;

/**
 * Graphics G4: the front end and the in-game menus (ui-spec.md section 5) as one Slate widget with a screen stack:
 * Title, then World, Launch spot, Boat, Conditions and Mode (each pushes the next; Back walks the flow back with the
 * choices kept), and in game Pause, Change conditions, Settings and Controls. Cast off hands the session to
 * USailSessionSubsystem, which reloads the map with it.
 */
enum class ESailScreen : uint8 { Title, World, Launch, Boat, Conditions, Mode, Pause, ConditionsInGame, Settings, Controls, Confirm, Briefing, Quiz };

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
	virtual FReply OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
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
	int32 FocusedBoat = 0;
	int32 SettingsTab = 0;
	FString ConfirmQuestion, ConfirmYes;
	// The quiz: its questions, the one on screen, the option chosen (-1: not yet), the score and the debrief line.
	TArray<FQuizQuestion> Quiz;
	int32 QuizIndex = 0, QuizChosen = -1, QuizRight = 0;
	FString QuizDebrief, QuizDrillName;
	TFunction<void()> ConfirmAction;
	// Screen transitions (3.3): a 180 ms fade with a 24 px slide.
	double TransitionStart = 0.0;
	bool bTransitionForward = true;
	EActiveTimerReturnType AnimateTransition(double Time, float Delta);
	// Controls: the row being rebound, listening for the next key.
	int32 ListeningRow = -1;
	FString ControlsMessage;
};
