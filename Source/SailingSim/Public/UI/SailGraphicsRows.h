#pragma once

#include "CoreMinimal.h"
#include "Widgets/SWidget.h"

class ASailingGameMode;
class USailingSettings;

/**
 * Settings > Graphics' rows, shared with the gallery's Graphics & view card (Inputs/gallery/brief.md section 5) so the
 * two pages can't drift: each writes the same USailingSettings field, saves, and applies it live (ApplyQualitySettings).
 */
namespace SailGraphicsRows
{
	/** The tier: choosing one puts every row below back on Auto (the tier's own). */
	SAILINGSIM_API TSharedRef<SWidget> Quality(ASailingGameMode* GM);
	/** Anti-aliasing: Auto, Off, TAA, TSR, SMAA, and NVIDIA's DLAA and DLSS modes where available. */
	SAILINGSIM_API TSharedRef<SWidget> AntiAliasing(ASailingGameMode* GM, bool bNote = true);
	/** One feature's detail: Auto (the tier's own) or a tier. */
	SAILINGSIM_API TSharedRef<SWidget> Detail(ASailingGameMode* GM, const TCHAR* Label, int32 USailingSettings::* Field, const TCHAR* Note);
	SAILINGSIM_API TSharedRef<SWidget> MotionBlur(ASailingGameMode* GM);
	SAILINGSIM_API TSharedRef<SWidget> RenderScale(ASailingGameMode* GM, bool bNote = true);
}
