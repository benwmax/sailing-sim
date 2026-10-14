#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SailingHUD.generated.h"

class ASailboatPawn;
enum class ESailScreen : uint8;

/** Graphics G4: the coach's trim and safety tips (severity 0 note, 1 good, 2 caution, 3 fault). */
SAILINGSIM_API void SailingCollectTips(const ASailboatPawn& Boat, const UWorld* World, TArray<TPair<FString, int32>>& Tips);
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
	virtual void DrawHUD() override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	/** Graphics G4: the Slate front end (UI/SailFrontEnd.h) and loading screen (UI/SailLoading.h). Off for benchmarks,
	 *  captures, screenshots and tests (they start straight into the scene, as before). */
	bool UsesFrontEnd() const;
	void OpenFrontEnd(ESailScreen Screen);
	void CloseFrontEnd();
	void OpenPause();
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
	bool bPausedByMenu = false;
};
