#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/DeclarativeSyntaxSupport.h"

class APlayerController;
class ASailboatPawn;

/**
 * Photo mode's panel (docs/photo-mode/pc/, redesigned in camera views slice 3, docs/camera-views/): a glass card with
 * the tabs Lens, Focus, Light, Scene and Frame on the bumpers, rows on the D-pad, drawn controller glyphs, and the frame
 * guides (rule-of-thirds grid, crop guides). It follows the UI modes: Helpful shows every row on the tab with a line on
 * what the current one does; Natural only the tab and the row you are on; Off opens with the panel closed (a tap of View
 * or H opens it, as Natural). It slides to the other side when the boat comes behind it, and takes clicks while Alt
 * shows the pointer. Slate over the viewport, so none of it is in a photo (the shot is the scene and the canvas only).
 */
class SAILINGSIM_API SSailPhotoPanel : public SCompoundWidget
{
public:
	SLATE_BEGIN_ARGS(SSailPhotoPanel) {}
		SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs);
	virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;
	/** Whether the guides (and the panel, when it is open) show: in photo mode with its camera, not hidden with H, no menu
	 *  open, and never in a clean still (-SailingNoHud, which also hides the HUD and its hints). */
	static bool ShouldShow(bool bPhotoMode, bool bHasFreeCamera, bool bHintsHidden, bool bFrontEndOpen, bool bNoHudArg)
	{
		return bPhotoMode && bHasFreeCamera && !bHintsHidden && !bFrontEndOpen && !bNoHudArg;
	}
	/** A controller button's name as the glyph parser reads it ("D-pad up" to an arrow, "Right stick press" to R3). */
	static FString GlyphText(const FString& PadLabel);
	ASailboatPawn* Pawn() const;

private:
	TSharedRef<SWidget> BuildCard();
	FString Signature() const;
	TWeakObjectPtr<APlayerController> Player;
	TSharedPtr<class SBox> CardHolder;
	FString BuiltFor;
	bool bOnRight = false;
	float SideT = 0.f;   // 0 on the left, 1 on the right, eased between
};
