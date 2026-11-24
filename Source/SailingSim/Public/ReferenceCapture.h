#pragma once

#include "CoreMinimal.h"
#include "BoatModel.h"

/**
 * Reference capture (Phase 8): reproduce a real photo or clip so the game shot can be compared with it. A preset
 * places a camera where real reference cameras sit, with their lens; exposure is locked, motion blur and depth of
 * field are off, the HUD is hidden, and every frame's boat state goes to a telemetry CSV. See docs/phase-8/README.md.
 *
 *   -SailingCapture=HelmEye|ActionCam|Chase|Drone|ShoreTele   -SailingCaptureBearing=<deg off the bow, + starboard>
 *   -SailingEV=<EV100>   (otherwise auto exposure is frozen once it has settled)
 */
enum class ECapturePreset : uint8
{
	None,
	HelmEye,    // 1.0 m above the cockpit sole at the tiller, looking forward; 70 deg (phone main camera)
	ActionCam,  // stern pulpit or transom mount looking forward; 118 deg with barrel distortion (GoPro wide)
	Chase,      // 15 m off, 2 m above the water; 50 deg
	Drone,      // 30 m up, 30 m off (45 deg down); 80 deg
	ShoreTele,  // a tripod 200 m off, 3 m above the water, panning to follow; 15 deg
	Tripod,     // film mode: a tripod at -SailingTripod's distance and height, panning to follow (FilmMode.h)
	Path,       // film mode: a keyframed camera move from -SailingShotFile (FFilmShot)
	Count
};

struct SAILINGSIM_API FCapturePresetInfo
{
	const TCHAR* Name;
	float HFovDeg;       // horizontal field of view as seen in the final image
	bool bOnboard;       // rigidly mounted: rolls and pitches with the boat
	bool bBarrel;        // action-cam lens distortion
	float DefaultBearingDeg; // world presets: where the camera stands, degrees off the bow (+ = starboard); NAN = to leeward
};

SAILINGSIM_API const FCapturePresetInfo& CapturePresetInfo(ECapturePreset Preset);
SAILINGSIM_API ECapturePreset ParseCapturePreset(const FString& Name);

/** An onboard camera's mount in the boat frame (cm, Unreal axes: X forward, Y starboard, Z up from the waterline).
 *  Side: +1 starboard, -1 port; the helm eye sits on the windward side, where the helmsman does. */
SAILINGSIM_API void OnboardCameraMount(ECapturePreset Preset, const Sailing::FBoatConfig& Config, float Side, FVector& OutLocation, FRotator& OutRotation);

/**
 * A world camera's place and aim (cm). Bearing is degrees off the bow (+ = starboard); the camera stays level and
 * looks at a point a third of the way up the mast. Shore cameras are fixed: pass their stand once, then only aim.
 */
SAILINGSIM_API void WorldCameraPose(ECapturePreset Preset, const FVector& BoatOrigin, float HeadingDeg, float BearingDeg,
	float MastheadMeters, float WaterZ, FVector& OutLocation, FRotator& OutRotation);
/** The same at a chosen range and height (m) off the boat, looking at AimFraction of the masthead (film mode's tripod). */
SAILINGSIM_API void WorldCameraPoseAt(const FVector& BoatOrigin, float HeadingDeg, float BearingDeg, float RangeMeters, float HeightMeters,
	float AimFraction, float MastheadMeters, float WaterZ, FVector& OutLocation, FRotator& OutRotation);

/** One frame of the boat for the telemetry CSV (knots and degrees, as a sailor reads them). */
struct SAILINGSIM_API FCaptureTelemetryRow
{
	double Time = 0.0;                     // s since the capture began
	double SpeedThroughWaterKn = 0.0, SpeedOverGroundKn = 0.0;
	double HeadingDeg = 0.0, CourseOverGroundDeg = 0.0;
	double HeelDeg = 0.0, PitchDeg = 0.0, RollRateDegS = 0.0;
	double RudderDeg = 0.0, Tiller = 0.0, MainSheet = 0.0, JibSheet = 0.0, Hike = 0.0;
	double TrueWindKn = 0.0, TrueWindFromDeg = 0.0, TrueWindAngleDeg = 0.0;
	double ApparentWindKn = 0.0, ApparentWindAngleDeg = 0.0;
	double WaveHeightM = 0.0;              // water surface under the boat's origin, relative to the still level
	double HelmForceN = 0.0;
	bool bCapsized = false;

	static FCaptureTelemetryRow FromBoat(double Time, const Sailing::FBoatModel& Boat, const Sailing::FBoatControls& Controls, double WaveHeight);
};

/** Collects the telemetry CSV in memory and writes it once, at Close (the pawn's EndPlay, or the destructor). Nothing
 *  touches the disk while the capture runs: a flush on the game thread every 120 rows stalled frames 30-140 ms
 *  (docs: Inputs/bench/helm-eye-hitch on the inputs branch). A crash loses the rows. */
class SAILINGSIM_API FCaptureTelemetry
{
public:
	~FCaptureTelemetry() { Close(); }
	bool Open(const FString& Path);
	void Add(const FCaptureTelemetryRow& Row);
	/** Writes the file (header and every row) and forgets it; false if the write failed. Safe to call twice. */
	bool Close();
	bool IsOpen() const { return !OutPath.IsEmpty(); }
	int32 NumRows() const { return Count; }

	static FString Header();
	static FString Format(const FCaptureTelemetryRow& Row);

private:
	void Append(const FString& Line);

	FString OutPath;
	TArray<uint8> Pending;
	int32 Count = 0;
};
