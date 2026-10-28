#pragma once

#include "CoreMinimal.h"

/**
 * Photo mode's panel (docs/photo-mode/pc/, brief Inputs/photo-mode/brief.md PR 2): the lens, focus, exposure, look,
 * scene and frame settings the panel steps through, and the maths behind them (focal length to field of view on a
 * full-frame sensor, the aperture's full stops, the crop guides' rectangles). Plain data, so the tests drive it; the
 * pawn applies it to AFreeCamera's lens and the scene. Client-only: nothing here touches a boat or the clock.
 */
enum class EPhotoFocus : uint8 { Auto, Boat, Manual };
enum class EPhotoLook : uint8 { Natural, Cinematic, Mono };
enum class EPhotoCrop : uint8 { None, Wide169, Photo32, Square, Cinema219 };

/** The panel's rows, page by page (Camera, Focus, Exposure, Scene, Frame). */
enum class EPhotoRow : uint8
{
	Focal, Roll,
	FocusMode, FocusDistance, Aperture,
	Exposure, Vignette, Grain, Look,
	HideBoat, HideOthers, HideCrew, SunHour,
	Grid, Crop, Capture,
	Count
};

struct SAILINGSIM_API FPhotoSettings
{
	EPhotoFocus Focus = EPhotoFocus::Auto;
	float ManualFocusM = 20.f;
	int32 ApertureStop = 2;          // index into PhotoMath::Apertures (f/2.8, today's lens); NumApertures = off (no depth of field)
	float ExposureEV = 0.f;          // added to the metered bias, -3..+3
	float Vignette = 0.4f, Grain = 0.f;
	EPhotoLook Look = EPhotoLook::Cinematic;
	bool bHideMyBoat = false, bHideOthers = false, bHideCrew = false;
	float SunHour = -1.f;            // visual-only time of day; < 0 follows the clock
	bool bGrid = false;
	EPhotoCrop Crop = EPhotoCrop::None;
	int32 CaptureScale = 1;          // 2: HighResShot at twice the viewport (High and Ultra)
	bool bLookTaken = false;         // vignette and grain were read from the scene's look on the first open
};

namespace PhotoMath
{
	/** Full stops, f/1.4 to f/22. */
	static constexpr int32 NumApertures = 9;
	SAILINGSIM_API float Aperture(int32 Stop);
	/** The usual primes and zoom marks, 14 to 200 mm. */
	SAILINGSIM_API const TArray<float>& FocalMarks();
	/** Horizontal field of view on a 36 mm sensor, and back. */
	SAILINGSIM_API float FovForFocal(float FocalMm);
	SAILINGSIM_API float FocalForFov(float FovDeg);
	/** The next mark up (Dir > 0) or down from where the lens is (a zoom with [ and ] can sit between marks). */
	SAILINGSIM_API float StepFocal(float FocalMm, int32 Dir);

	SAILINGSIM_API int32 PageOf(EPhotoRow Row);
	SAILINGSIM_API const TCHAR* PageName(int32 Page);
	static constexpr int32 NumPages = 5;
	SAILINGSIM_API EPhotoRow FirstRowOf(int32 Page);
	SAILINGSIM_API const TCHAR* RowLabel(EPhotoRow Row);

	/** Steps one row's value (Dir +1 or -1); FovDeg and RollDeg are the lens's, the rest is the settings. Rows that
	 *  only exist on some tiers (2x capture on High and Ultra) take bHighTier. The time of day steps by half hours from
	 *  the clock's, and passing the clock's own half hour goes back to following it. */
	SAILINGSIM_API void StepRow(FPhotoSettings& S, EPhotoRow Row, int32 Dir, float& FovDeg, float& RollDeg, bool bHighTier, float ClockHour);
	SAILINGSIM_API float StepSunHour(float SunHour, int32 Dir, float ClockHour);
	SAILINGSIM_API FString RowValue(const FPhotoSettings& S, EPhotoRow Row, float FovDeg, float RollDeg, float FocusM, bool bHighTier);
	/** A row that does nothing just now (the manual distance outside manual focus, 2x below High). */
	SAILINGSIM_API bool RowIdle(const FPhotoSettings& S, EPhotoRow Row, bool bHighTier);

	/** The crop guide's aspect (width over height), 0 for none. */
	SAILINGSIM_API float CropAspect(EPhotoCrop Crop);
	/** The largest centred rectangle of that aspect inside a W x H frame: (x, y, w, h). */
	SAILINGSIM_API FVector4f CropRect(EPhotoCrop Crop, float W, float H);
}
