#pragma once

#include "CoreMinimal.h"
#include "VisualPipeline.h"

/**
 * Film mode (docs/film-mode/): dev-only tools for recording the demo reel from the game itself. Nothing a player sees:
 * every piece is a launch switch, read through SailingArgs::Dev() (empty in Shipping).
 *
 *   -SailingFilm                     the offline quality boost (FilmQualityCVars, FilmPostProcess) and motion blur on in
 *                                    capture mode at a 180 degree shutter
 *   -SailingMotionBlur=<amount>      capture mode keeps this much motion blur (0 = off, the reference stills' default;
 *                                    0.5 = a 180 degree shutter)
 *   -SailingEV=<EV100>               locks the exposure in capture mode and, now, outside it too
 *   -SailingCapture=Tripod -SailingTripod=<distance m>,<height m>[,<hfov deg>]
 *                                    a tripod set up where the boat will pass (bearing as for the other world cameras:
 *                                    -SailingCaptureBearing, -SailingCaptureAbsolute), panning to follow her live
 *   -SailingCapture=Path -SailingShotFile=<path to a shot .json>
 *                                    a keyframed camera move (FFilmShot): orbit, dolly, crane, pan or a locked mount
 *   -SailingCaptureHud               capture and film takes keep the HUD in the chosen UI mode (-SailingUiMode=helpful|
 *                                    natural|off or -SailingHudMode=0|1|2, else the saved setting) instead of the picture
 *                                    alone, for shots that show the instruments (the reel's helm-eye R06)
 *
 * With a fixed step (-benchmark -fps=60, or -UseFixedTimeStep), -SailingRecord=<s> -SailingRecordInterval=<s> are counted
 * in frames (FFilmFrameClock): exactly round(record / interval) frames, one every round(interval / step) frames.
 */

/** Whether the engine steps a fixed time each frame: benchmarking (-benchmark, the step from -fps) or -UseFixedTimeStep.
 *  The game mode counts the recording in frames then. (-benchmark alone leaves FApp::UseFixedTimeStep() false: PC run
 *  on #817's first head wrote 481 frames.) */
SAILINGSIM_API bool FilmUsesFrameClock();

/** Frame-counted recording under a fixed time step. Frame 0 is the bench's first tick. */
struct SAILINGSIM_API FFilmFrameClock
{
	double FrameSeconds = 1.0 / 60.0;   // game seconds per frame (the fixed step times the time dilation)
	int32 WarmupFrames = 0;             // the first frame recorded
	int32 Stride = 1;                   // frames between recorded frames
	int32 Count = 0;                    // frames recorded

	static FFilmFrameClock Make(double FrameSeconds, double WarmupSeconds, double RecordSeconds, double IntervalSeconds);

	/** The recorded frame's index (0..Count-1) at this frame, or -1 if this frame is not recorded. */
	int32 CaptureIndexAt(int64 Frame) const;
	/** The last frame recorded (WarmupFrames - 1 when there are none). */
	int64 LastFrame() const { return int64(WarmupFrames) + int64(Count - 1) * Stride; }
	/** Shot time at a frame: 0 at the first recorded frame (negative during the warm-up). */
	double ClockAt(int64 Frame) const { return double(Frame - WarmupFrames) * FrameSeconds; }
};

/** What a shot's camera is placed against. */
enum class EFilmFrame : uint8
{
	Boat,    // metres forward, right and up from the boat (up from the still water), turning with her heading but level
	World,   // metres north, east and up from the boat's start (up from the still water); angles are compass
	Mount,   // metres forward, right and up in the hull's own frame: heels and pitches with her (a locked mount)
};

enum class EFilmEase : uint8
{
	Linear,
	In,      // starts slow
	Out,     // ends slow
	InOut,   // starts and ends slow (the default: a camera operator's move)
};

SAILINGSIM_API double FilmEase(EFilmEase Ease, double U);

/** One key of a shot. Place: Pos (in the shot's frame) or an orbit about the boat. Look: at the boat, or fixed angles. */
struct SAILINGSIM_API FFilmKey
{
	double T = 0.0;                      // seconds from the first recorded frame
	bool bOrbit = false;
	FVector Pos = FVector::ZeroVector;   // m (frame axes); unused for an orbit
	double OrbitBearingDeg = 0.0;        // orbit: degrees off the bow (Boat) or compass bearing from the boat (World)
	double OrbitDistanceM = 20.0;
	double OrbitHeightM = 2.0;           // above the still water
	bool bLookAtBoat = true;
	double AimUpM = -1.0;                // look at the boat: this high on her (m); < 0 = a third of the masthead
	FRotator Look = FRotator::ZeroRotator;   // fixed look (pitch, yaw, roll deg, in the frame); look at the boat: added to the aim
	double HFovDeg = 40.0;
	EFilmEase Ease = EFilmEase::InOut;   // how the move from this key to the next is eased
};

/** The boat as the camera sees her this frame (Unreal world units, cm). */
struct SAILINGSIM_API FFilmBoatPose
{
	FVector Origin = FVector::ZeroVector;      // her drawn origin, Z at the still water
	double HeadingDeg = 0.0;                   // Unreal yaw of her bow (= compass)
	double MastheadM = 9.25;
	FVector WorldAnchor = FVector::ZeroVector; // the World frame's origin: her start, Z at the still water
};

struct SAILINGSIM_API FFilmCameraPose
{
	FVector Location = FVector::ZeroVector;    // world cm, or relative to the hull (Mount)
	FRotator Rotation = FRotator::ZeroRotator;
	double HFovDeg = 40.0;
	bool bRelativeToHull = false;
};

/**
 * A keyframed camera move, from a small JSON shot file:
 *
 *   { "frame": "boat" | "world" | "mount", "path": "linear" | "smooth", "fov": 40,
 *     "keys": [ { "t": 0, "orbit": [bearing deg, distance m, height m], "fov": 35, "ease": "inout" },
 *               { "t": 6, "pos": [x, y, z], "look": [pitch, yaw, roll] | "boat", "aim_up": 3, "ease": "linear" } ] }
 *
 * Between two keys the place and field of view move along the eased fraction of the time (keys' own "ease", in-out by
 * default); two orbits move round the boat (bearing, distance and height), anything else in a straight line in the frame
 * ("path": "smooth" goes through every key on a Catmull-Rom curve instead). The look blends from one key's to the next
 * (each key aimed at the boat from where the camera is now). Before the first key and after the last the camera holds.
 * Orbit (dolly round), pos to pos (dolly, crane), one pos with two looks (pan) and "mount" (locked on the hull) are the
 * moves the reel needs.
 */
struct SAILINGSIM_API FFilmShot
{
	EFilmFrame Frame = EFilmFrame::Boat;
	bool bSmooth = false;
	TArray<FFilmKey> Keys;

	bool Parse(const FString& Json, FString& OutError);
	bool Load(const FString& Path, FString& OutError);
	double Duration() const { return Keys.Num() > 0 ? Keys.Last().T : 0.0; }
	FFilmCameraPose Evaluate(double T, const FFilmBoatPose& Boat) const;

	/** A key's place this frame: world cm (hull cm for Mount). An orbit goes round the boat where she is now. */
	FVector KeyLocation(const FFilmKey& Key, const FFilmBoatPose& Boat) const;
	/** A key's look from a camera at Location (cm, as KeyLocation). */
	FQuat KeyRotation(const FFilmKey& Key, const FVector& Location, const FFilmBoatPose& Boat) const;
	/** A place in the shot's frame (m) in world cm (or hull cm for Mount). */
	FVector ToCm(const FVector& FramePos, const FFilmBoatPose& Boat) const;
};

/** The tripod's arguments: -SailingTripod=<distance m>,<height m>[,<hfov deg>[,<aim fraction of the masthead>]].
 *  Defaults 40 m, 1.6 m, 26 deg, 0.45: the whole J/22, waterline to masthead, in a 16:9 frame (at 20 deg and a third of
 *  the masthead the PC's first run cut her masthead off). */
struct SAILINGSIM_API FFilmTripod
{
	double DistanceM = 40.0;
	double HeightM = 1.6;
	double HFovDeg = 26.0;
	double AimFraction = 0.45;
	static FFilmTripod Parse(const FString& Arg);
};

/** The capture's motion blur: 0 (the reference stills), or -SailingMotionBlur=<a>, or 0.5 with -SailingFilm. */
SAILINGSIM_API float CaptureMotionBlurAmount(const TCHAR* CommandLine);

/** The film quality boost's console variables (applied after the tier's, -SailingFilm only): the clouds rebuilt over
 *  frames with more samples (mode 0), the water's and Lumen's reflections at full resolution, a longer TSR history. */
SAILINGSIM_API TArray<FQualityCVar> FilmQualityCVars();

/** -SailingCaptureHud on this command line: the capture mode keeps the HUD (off by default: the picture alone). */
SAILINGSIM_API bool CaptureShowsHud(const TCHAR* CommandLine);
/** -SailingCaptureHud on this run's command line (re-read on each bench-list swap). */
SAILINGSIM_API bool CaptureShowsHud();
/** Whether the HUD hides for the capture mode: in capture mode, unless the run asked for the HUD. */
SAILINGSIM_API bool CaptureHidesHud(bool bCaptureMode, bool bCaptureHud);
/** The HUD mode (SSailHud::Mode: 0 Helpful, 1 Natural, 2 Off) a run starts in: the chosen UI mode, but a measuring run
 *  keeps the full HUD (0) unless it asked for the capture HUD, which takes the chosen mode as a player would see it. */
SAILINGSIM_API int32 StartingHudMode(bool bMeasuring, bool bCaptureHud, int32 ChosenMode);

/** -SailingFilm on this run's command line (re-read on each bench-list swap). */
SAILINGSIM_API bool IsFilmMode();

/** -SailingEV=<EV100> on this run's command line: false (and Out unchanged) without it. */
SAILINGSIM_API bool FixedExposureArg(float& OutEV100);

/** The layer passes of a shot (the portfolio's layer peel): -SailingViewMode=wireframe|lightingonly|unlit|lit. */
enum class EFilmViewMode : uint8
{
	Lit,            // the game's own frames (no switch, or an unknown name)
	Wireframe,
	LightingOnly,
	Unlit,
};

/** A -SailingViewMode name (any case); Lit for anything else. */
SAILINGSIM_API EFilmViewMode ParseFilmViewMode(const FString& Name);
/** -SailingViewMode on this run's command line (re-read on each bench-list swap). */
SAILINGSIM_API EFilmViewMode FilmViewMode();

/**
 * Puts the game viewport in the -SailingViewMode pass. A cooked game has debug view modes only when it was cooked with
 * r.ForceDebugViewModes=1 (AllowDebugViewmodes()): then the engine's own view mode is used. Without them, lighting only
 * falls back to ShowFlag.LightingOnlyOverride (the normal shaders), and wireframe and unlit log why they can't and stay
 * lit. Forcing the cvar at run time in a package cooked without the shaders crashed on the first frame (PC on #828 at
 * 89ec83ed), so it is never forced here. Returns whether a pass was applied.
 */
SAILINGSIM_API bool ApplyFilmViewMode(class UGameViewportClient* Viewport, class UWorld* World);
