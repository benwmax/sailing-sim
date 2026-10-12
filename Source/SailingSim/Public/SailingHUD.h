#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SailingHUD.generated.h"

class ASailboatPawn;

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
	void Text(const FString& Str, float X, float Y, const FLinearColor& Color = FLinearColor::White, float Scale = 1.f, bool bBig = false);
	void Bar(const FString& Label, float Value, float Lo, float Hi, float X, float Y, float Width, const FLinearColor& Color);
	float UIScale = 1.f;
};
