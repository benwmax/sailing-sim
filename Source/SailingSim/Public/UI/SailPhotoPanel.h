#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class APlayerController;
class ASailboatPawn;

/**
 * Photo mode's panel (docs/photo-mode/pc/): a narrow left column with the pages Camera, Focus, Exposure, Scene and
 * Frame (rows from FPhotoSettings, stepped by the pawn's photo panel commands), and the frame guides (rule-of-thirds
 * grid, crop guides). Slate over the viewport, so neither is in a photo (the shot is the scene and the canvas only);
 * H hides both with the hints, for a clean frame.
 */
class SAILINGSIM_API SSailPhotoPanel : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailPhotoPanel) {}
		SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	ASailboatPawn* Pawn() const;

private:
	TWeakObjectPtr<APlayerController> Player;
};
