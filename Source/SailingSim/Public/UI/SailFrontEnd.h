#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "SailSession.h"
#include "SailSave.h"
#include "Learning.h"
#include "Showroom.h"
#include "Gallery.h"
#include "SkinEditor.h"
namespace Sailing { class FScriptedScene; }

class SBox;
class APlayerController;

/**
 * Graphics G4: the front end and the in-game menus (ui-spec.md section 5) as one Slate widget with a screen stack:
 * Title, then World, Launch spot, Boat, Conditions and Mode (each pushes the next; Back walks the flow back with the
 * choices kept), and in game Pause, Change conditions, Settings and Controls. Cast off hands the session to
 * USailSessionSubsystem, which reloads the map with it. Credits (from the Title and Settings) reads CREDITS.md.
 */
enum class ESailScreen : uint8 { Title, World, Launch, Boat, Conditions, Mode, Pause, ConditionsInGame, Settings, Controls, Confirm, Briefing, Quiz, Credits, Career, Gallery, Feedback, FirstLaunch, Customize };

struct FCareerLesson;

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
	/** Where the Career screen's focus starts (#439, #438): the First job card while the first job waits (its card shows:
	 *  first launch seen, the first-job scene not done), else the next lesson until a tier is picked, else the tier card. */
	enum class ECareerFocus : uint8 { FirstJob, NextLesson, TierCard };
	static bool ShowsFirstJob(const FSailSave::FProgress& Progress);
	static ECareerFocus CareerFocus(const FSailSave::FProgress& Progress, bool bTierPicked);
	/** #599: the title's Continue goes back to the first job: the last session was the first job and it isn't done. */
	static bool ResumesFirstJob(const struct FSailSessionConfig& Last, const FSailSave::FProgress& Progress);
	/** #601: the tiers a certificate opens that have lessons to sail (the names for its "Open now" line). */
	static TArray<FString> TiersOpenedBy(const struct FCareerTier& Tier);
	/** #599: the pause menu's title and restart item. A scripted scene running (the first job) gives its own title and
	 *  "Restart from checkpoint" (true). Otherwise the restart is the mode's (drill, race, or the launch spot), and the title
	 *  (#605, #636) is the session's career lesson (LessonId), else with a drill set (running or finished) the drill's own
	 *  name, else the mode's name. */
	static bool PauseHeading(const Sailing::FScriptedScene* Scene, ESailMode Mode, FString& OutTitle, FString& OutRestart,
		ESailingDrill Drill = ESailingDrill::None, const FString& LessonId = FString());
	/** Boat skins (docs/skins): the Customize screen for a class's boat, over the showroom (from the Boat screen). */
	void OpenCustomize(int32 BoatType);
	/** Whether the Boat screen offers Customize (-SailingNoCustomize takes it away: the one switch if it must wait). */
	static bool CustomizeEnabled();
	const FSkinEditor& GetSkinEditor() const { return SkinEdit; }
	/** Back: pops a screen; on the root it does what that root's Back means (Pause: resume). */
	void Pop();
	/** Puts keyboard focus on the current screen's default target (after the widget is in the viewport); true when it has
	 *  it (or the screen has none and the menus took it). */
	bool FocusCurrent();
	ESailScreen Current() const { return Stack.Num() ? Stack.Last().Screen : ESailScreen::Title; }
	/** What FocusCurrent focuses on the current screen (tests). */
	TSharedPtr<SWidget> FocusTarget() const { return Stack.Num() ? Stack.Last().Focus : TSharedPtr<SWidget>(); }
	/** #404's nightly playthrough (the UI script's Answer:all): answers the open quiz right through its own answer and
	 *  Next buttons' handlers, question by question, until the score shows (so the lesson's or checkride's quiz is
	 *  recorded as a player's is). Returns how many questions it answered. */
	int32 DevAnswerQuiz();

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
	/** #402 (docs/first-launch/): a new save's two questions, then the first job (or the title). */
	FEntry BuildFirstLaunch();
	/** #402: a lesson's quiz taken from its Career row or retaken from the finish panel (no drill sailed this time). */
	FString QuizRetakeLessonId;
	/** #402: the finish panel's way on: a lesson's session cast off at once (Next lesson, Sail it again). */
	void StartLesson(const FCareerLesson& Lesson);
	/** #439: casts off on the first job (the J/22 off Rush Creek, the lesson day, no traffic), from the first-launch screen
	 *  or the Career screen's First job card after a skip. */
	void StartFirstJob(bool bEasy);
	/** The first-launch screen's answers (quality tier, Easy) while it is open. */
	int32 FirstQuality = -1;
	bool bFirstEasy = true;
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
	/** Keeps keyboard focus in the menus while they are up: when the game's viewport takes it (the window activating
	 *  after the screen was built), it goes back to the screen's default. */
	void KeepFocusInMenus();
	double FocusReclaimAt = 0.0;
	/** The wipe over the reload, then the travel (a frame later, so the wipe is drawn). */
	void TravelToWorld(ESailScreen Resume);
	bool bTravelling = false;
	class ASailingGameMode* GameMode() const;
	int32 FocusedBoat = 0;
	int32 SettingsTab = 0;
	/** A choice that rebuilds its screen (the Mode screen's Mode, Settings' Text size) names itself here and rebuilds; its
	 *  builder makes it the new screen's focus (KeepFocus), which Show sets once the screen is laid out. Without it the
	 *  rebuilt screen focused its default and the next key went elsewhere, or nowhere. */
	FName RefocusChoice;
	void RebuildKeeping(FName Choice);
	void KeepFocus(FEntry& E, FName Choice, const TSharedRef<SWidget>& Widget) const;
	/** Bean's UI feedback (Oct 27): a clicked tab pill, a keycap, Q/E and LB/RB all come here; the rebuilt screen focuses
	 *  the tab's first row once it is laid out (Show). */
	void SetSettingsTab(int32 Tab);
	FString ConfirmQuestion, ConfirmYes, ConfirmNo;
	// The feedback form's draft, kept while the screen is rebuilt.
	int32 FeedbackKind = 0;            // EFeedbackKind
	bool bFeedbackPlace = false;       // ideas: attach where I am
	bool bFeedbackPhotos = false;      // add photo mode's latest two shots
	FString FeedbackTitle, FeedbackText, FeedbackExpected, FeedbackShot, FeedbackResult;
	// The quiz: its questions, the one on screen, the option chosen (-1: not yet), the score and the debrief line.
	TArray<FQuizQuestion> Quiz;
	int32 QuizIndex = 0, QuizChosen = -1, QuizRight = 0;
	TArray<TSharedPtr<SWidget>> QuizOptions;   // the open question's answer buttons, in order
	TArray<FSimpleDelegate> QuizOptionClicks;   // their click handlers, and Next's (DevAnswerQuiz)
	FSimpleDelegate QuizNextClick;
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
	// Boat skins (UI/SailCustomize.cpp, docs/skins): the Customize screen. The draft and its undo are FSkinEditor's; here
	// are the tab, the part and the colour the sliders hold (hue, strength, lightness: a grey has no hue of its own), the
	// before/after switch, the revision last shown on the boat (a dragged slider is shown at most eight times a second), the
	// two-press guards (leaving with changes, deleting) and the text boxes (typing must not reach the screen's keys).
	FSkinEditor SkinEdit;
	int32 CustomTab = 0, CustomPart = 0;
	FVector CustomHsv = FVector(210.0, 0.5, 0.5);
	bool bCustomBefore = false, bCustomBeforeShown = false, bCustomLeaveArmed = false, bCustomDeleteArmed = false;
	uint32 CustomShownRevision = 0;
	uint32 CustomLeaveRevision = 0;   // the draft's revision when Back was first pressed: a change since asks again
	double CustomPreviewAt = 0.0;
	FString CustomMessage;
	TArray<TSharedPtr<SWidget>> CustomTextBoxes;
	FEntry BuildCustomize();
	void SetCustomTab(int32 Tab);
	/** The screen's own keys (tabs, undo and redo, before/after, Surprise me, the guarded Back); Handled when it took one. */
	FReply CustomizeKeyDown(const FKeyEvent& Event);
	/** Each frame on the screen: the draft on the showroom's boat when it changed (or her saved look for Before). */
	void TickCustomize(double Time);
	/** Leaving the screen (Back, or the menus closing): the boat wears her saved look again. */
	void EndCustomize();
	void CustomUse();
	/** The sliders' colour from the part's (or the cloth's) own, when the part changes. */
	void CustomSyncHsv();
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
