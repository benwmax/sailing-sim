#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "SoundCaptions.generated.h"

namespace SailingSound
{
	/** Relative bearing of a map point (+X north, +Y east) from a listener at Pos heading HeadingDeg (true): -180..180,
	 *  positive to starboard. */
	SAILINGSIM_API double RelativeBearingDeg(const FVector2D& Pos, double HeadingDeg, const FVector2D& Source);
	/** A sailor's words for a relative bearing: ahead, off the starboard bow, abeam to starboard, off the starboard
	 *  quarter, astern (and the same to port), in 45 degree sectors. */
	SAILINGSIM_API const TCHAR* RelativeDirection(double RelativeBearingDeg);
}

/**
 * Slice sound pass: sound captions (Settings > Accessibility > Sound captions). The sounds that matter (horn signals,
 * the committee's horn, thunder) add a caption saying what was heard and where from, worded from the player's boat;
 * the HUD shows the live ones (SSailHud::Refresh). Nothing is kept when the setting is off.
 */
UCLASS()
class SAILINGSIM_API USoundCaptions : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static USoundCaptions* Get(const UObject* WorldContext);

	/** A caption shown for Seconds; the same text again while it shows only extends it. */
	void Add(const FString& Text, double Seconds = 5.0);
	/** "What, <direction from the player's boat>[: Detail]" for a sound at a map point. */
	void AddFrom(const FString& What, const FVector2D& Source, const FString& Detail = FString(), double Seconds = 5.0);
	/** The captions showing now, oldest first. */
	TArray<FString> Active() const;

private:
	struct FCaption { FString Text; double Until = 0.0; };
	TArray<FCaption> Captions;
	double Now() const;
};
