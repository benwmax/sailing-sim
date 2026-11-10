#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SailingHUD.generated.h"

class ASailboatPawn;
enum class ESailScreen : uint8;
namespace Sailing { struct FBoatTelemetry; struct FBoatControls; struct FEasyAssists; }

/** Graphics G4: the coach's trim and safety tips (severity 0 note, 1 good, 2 caution, 3 fault). */
SAILINGSIM_API void SailingCollectTips(const ASailboatPawn& Boat, const UWorld* World, TArray<TPair<FString, int32>>& Tips);
/** The boat's own tips (no weather), for the tests. Tied up, there is only the first line: no trim, irons or heel
 *  tips while the lines hold her (feedback #488). */
SAILINGSIM_API void SailingCollectBoatTips(const Sailing::FBoatTelemetry& T, double WindwardSide, const Sailing::FBoatControls& C,
	const Sailing::FEasyAssists& Easy, bool bEasyRecovering, bool bTiedUp, TArray<TPair<FString, int32>>& Tips, bool bHoldNoGo = false);
/** #598: the no-go tips ("Too close to the wind", "Close to the no-go zone") wait this long after she is put at her start:
 *  nobody on the helm, a boat's weather helm rounds her up toward the wind, and the first tip shouldn't blame the player
 *  for the game's own start. In irons and the Easy crew's recovery still show at once. */
constexpr double SailingNoGoTipHoldSeconds = 10.0;
/** #598: the seconds since she was put at her start, on the boat clock, not counting time the UI held her (the loading
 *  screen and the briefing run the clock while the boat waits). ASailboatPawn::GetSecondsSinceStart reads it. */
struct FSailStartClock
{
	void Reset(double Now) { Start = Now; if (HeldAt >= 0.0) HeldAt = Now; }
	void Hold(bool bHeld, double Now)
	{
		if (bHeld && HeldAt < 0.0) HeldAt = Now;
		else if (!bHeld && HeldAt >= 0.0) { Start += Now - HeldAt; HeldAt = -1.0; }
	}
	double Seconds(double Now) const { return (HeldAt >= 0.0 ? HeldAt : Now) - Start; }
private:
	double Start = 0.0;
	double HeldAt = -1.0;
};
SAILINGSIM_API FString SailingPointOfSail(double TwaDeg, bool bInIrons);

/**
 * Cockpit instruments drawn on the canvas: boat speed, heading, apparent and true wind, heel, VMG, helm load
 * and sail controls. Learning mode adds a wind diagram, the point of sail and trim tips.
 */
UCLASS()
class SAILINGSIM_API ASailingHUD : public AHUD
{
	GENERATED_BODY()

public:
	ASailingHUD();
	virtual void DrawHUD() override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	/** Graphics G4: the Slate front end (UI/SailFrontEnd.h) and loading screen (UI/SailLoading.h). Off for benchmarks,
	 *  captures, screenshots and tests (they start straight into the scene, as before). */
	bool UsesFrontEnd() const;
	void OpenFrontEnd(ESailScreen Screen);
	void CloseFrontEnd();
	void OpenPause();
	/** Graphics G7: the drill briefing or the quiz after it (paused, like the pause menu). */
	void OpenLearning(ESailScreen Screen);
	bool IsFrontEndOpen() const { return FrontEnd.IsValid() || Loading.IsValid(); }

private:
	void DrawInstruments(const ASailboatPawn& Boat);
	void DrawControls(const ASailboatPawn& Boat);
	void DrawWindDiagram(const ASailboatPawn& Boat, const FVector2D& Center, float Radius);
	void DrawTips(const ASailboatPawn& Boat);
	void DrawWeather(const ASailboatPawn& Boat);
	void DrawDrillAndStatus(const ASailboatPawn& Boat);
	void DrawMenu(const ASailboatPawn& Boat);
	void DrawControlsCard(const ASailboatPawn& Boat);
	/** Coast instruments: compass (magnetic), depth sounder, log, GPS speed and course, tide and current. */
	void DrawNavigation(const ASailboatPawn& Boat, float Top);
	/** The chart view: the NOAA chart of the area with the aids, soundings, compass rose and the navigator's plot. */
	void DrawChart(const ASailboatPawn& Boat);
	/** Traffic: the rules callout (learning) or the rules score (game), signals heard, and the race panel. */
	void DrawTraffic(const ASailboatPawn& Boat);
	/** The ship's log page (Y). */
	void DrawLogbook(const ASailboatPawn& Boat);
	/** The keys screen. */
	void DrawKeys(const ASailboatPawn& Boat);
	void Text(const FString& Str, float X, float Y, const FLinearColor& Color = FLinearColor::White, float Scale = 1.f, bool bBig = false);
	void Bar(const FString& Label, float Value, float Lo, float Hi, float X, float Y, float Width, const FLinearColor& Color);
	float UIScale = 1.f;
	void ShowWidget(TSharedRef<class SWidget> Widget, TSharedPtr<class SWidget> Focus);
	void RemoveWidgets();
	void StartSailing();
	TSharedPtr<class SSailFrontEnd> FrontEnd;
	TSharedPtr<class SSailLoading> Loading;
	TSharedPtr<class SWidget> ShownWidget;
	TSharedPtr<class SSailHud> SlateHud;   // the in-game HUD (Graphics G4): replaces the canvas instruments
	TSharedPtr<class SSailPhotoPanel> PhotoPanel;   // photo mode's panel and frame guides (docs/photo-mode/pc/)
	bool bPausedByMenu = false;
	/** -SailingUIScript=Enter,Down,Wait,... : keys sent to the menus every 0.6 s (the front end's end-to-end check). */
	virtual void Tick(float DeltaSeconds) override;
	double NextScriptKey = 0.0;
	double ScriptWaitStart = -1.0;   // the UI script's WaitFor: (playthrough)
	/** The drill each briefing and quiz was shown for (ASailboatPawn::GetDrillSerial). */
	int32 BriefedSerial = 0, QuizzedSerial = 0;
	double DrillDoneAt = -1.0;
	bool bLearningScreensAuto = true;
	void WatchDrill();
};
