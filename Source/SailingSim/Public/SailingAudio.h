#pragma once

#include "CoreMinimal.h"
#include "Sound/SoundWaveProcedural.h"
#include <atomic>
#include "SailingAudio.generated.h"

/** Values the game thread sets each frame; the audio thread reads them (smoothed) while synthesizing. */
struct FSailingSoundParams
{
	std::atomic<float> ApparentWind{ 0.f };  // m/s at the rig
	std::atomic<float> Luff{ 0.f };          // 0..1 how much sail is luffing or flogging
	std::atomic<float> Telltales{ 0.f };     // 0..1 how much the telltales flutter
	std::atomic<float> BoatSpeed{ 0.f };     // m/s
	std::atomic<float> HullSpeedRatio{ 0.f };// boat speed / hull speed
	std::atomic<float> BowSlam{ 0.f };       // 0..1 bow meeting waves
	std::atomic<float> TrimRate{ 0.f };      // + trimming in (winch clicks), - easing (sheet running out)
	std::atomic<float> Rain{ 0.f };          // 0..1
	std::atomic<float> Thunder{ 0.f };       // 0..1 rumble level
	std::atomic<float> ThunderCrack{ 0.f };  // 0..1 sharp crack of a close strike
	std::atomic<float> HornLevel{ 0.f };     // 0..1 another vessel's whistle (or the committee's horn), by distance
	std::atomic<float> HornHz{ 400.f };      // its pitch: about 110 Hz for a ship, 400 for a small boat
	std::atomic<float> Volume{ 0.8f };
	// Visual V7 (sound and feel):
	std::atomic<float> GustRatio{ 1.f };     // wind now / mean: the low buffeting of a gust in the ears
	std::atomic<float> WindShadow{ 0.f };    // 0..1 the hush in the lee of a shore or a big boat
	std::atomic<float> Moored{ 0.f };        // 0..1 at rest: the hull's lapping and the halyard slapping on the mast
	std::atomic<float> RainDeck{ 0.f };      // 0..1 drops on the deck and the sails
	std::atomic<float> RainWater{ 0.f };     // 0..1 the hiss of rain on the water around
	std::atomic<float> Squall{ 0.f };        // 0..1 the hiss of a squall's rain and wind coming across the water
	std::atomic<uint32> SampledMask{ 0 };    // cues a recorded sample plays instead (ESailingCue bits)
};

/** The synth's voices a recorded sample can replace (Content/Audio/Samples/<Name>.wav -> /Game/Audio/Samples/S_<Name>). */
enum class ESailingCue : uint8
{
	Wind, GustRumble, SailFlog, Telltales, BowWave, HullSlap, Winch, SheetBlock, HalyardSlap, RainDeck, RainWater, SquallHiss, Thunder, Count
};
SAILINGSIM_API const TCHAR* SailingCueName(ESailingCue Cue);

/** The kinds of spatialised source in the world (each its own procedural voice at its place). */
enum class EWorldSound : uint8 { MarinaHalyards, Gulls, Outboard, Diesel, Count };
SAILINGSIM_API const TCHAR* WorldSoundName(EWorldSound Kind);

/**
 * All of the game's sound, synthesized on the audio thread from filtered noise and oscillators: wind in the
 * rigging, luffing and flogging sails, telltale flutter, water past the hull (changing near hull speed), bow
 * wave, winch clicks and running sheets, rain and thunder. No recorded samples (see CREDITS.md).
 */
UCLASS()
class SAILINGSIM_API USailingSynthWave : public USoundWaveProcedural
{
	GENERATED_BODY()

public:
	USailingSynthWave(const FObjectInitializer& ObjectInitializer);

	virtual int32 OnGeneratePCMAudio(TArray<uint8>& OutAudio, int32 NumSamples) override;

	FSailingSoundParams Params;

private:
	struct FOnePole { float Z = 0.f; float Low(float X, float A) { Z += A * (X - Z); return Z; } };
	struct FBandPass
	{
		float Low = 0.f, Band = 0.f;
		float Process(float X, float F, float Q) { const float High = X - Low - Q * Band; Band += F * High; Low += F * Band; return Band; }
	};

	float Noise();
	float Smooth(float& State, float Target, float Rate) { State += (Target - State) * Rate; return State; }

	uint32 Rng = 0x2545F491u;
	float SampleRateHz = 48000.f;
	// Smoothed parameters.
	float SHorn = 0.f, HornPhase = 0.f, HornVib = 0.f;
	float SWind = 0.f, SLuff = 0.f, STell = 0.f, SSpeed = 0.f, SHull = 0.f, SSlam = 0.f, STrim = 0.f, SRain = 0.f, SThunder = 0.f, SCrack = 0.f, SVolume = 0.8f;
	// Generators.
	float Pink[7] = {};
	float Brown = 0.f;
	float FlapPhase = 0.f, TellPhase = 0.f, ClickPhase = 0.f, GustPhase = 0.f;
	float ClickEnv = 0.f, DropEnv = 0.f, SlapEnv = 0.f;
	FBandPass WindBand, Whistle, FlogHigh, TellBand, ClickBand, ZipBand, DropBand, CrackBand, SlapBand;
	FOnePole WaterLow, RumbleLow, ThunderLow, RainHigh, FlogLow;
	// Visual V7 layers.
	float SGust = 1.f, SShadow = 0.f, SMoored = 0.f, SRainDeck = 0.f, SRainWater = 0.f, SSquall = 0.f;
	FOnePole GustLow, LapLow;
	FBandPass LapBand, SquallBand, SquallBand2, SheetBand;
	float LapEnv = 0.f, HalyardEnv = 0.f, HalyardF1 = 0.f, HalyardF2 = 0.f, HalyardP1 = 0.f, HalyardP2 = 0.f, SheetPhase = 0.f;
};

/**
 * Visual V7: a spatialised sound in the world, synthesized like the boat's: the marina's halyards clanking on their
 * masts in the breeze, gulls, an outboard's two-stroke buzz, a towboat's or a ship's diesel throb. Played by a
 * spatialised UAudioComponent at its source (SailingSound::MakeWorldSound); Level and Rate are set by the owner.
 */
UCLASS()
class SAILINGSIM_API USailingWorldSynth : public USoundWaveProcedural
{
	GENERATED_BODY()

public:
	USailingWorldSynth(const FObjectInitializer& ObjectInitializer);
	virtual int32 OnGeneratePCMAudio(TArray<uint8>& OutAudio, int32 NumSamples) override;

	EWorldSound Kind = EWorldSound::MarinaHalyards;
	std::atomic<float> Level{ 0.f };   // 0..1
	std::atomic<float> Rate{ 0.5f };   // 0..1: the wind for halyards, throttle for engines
	uint32 Seed = 1;

private:
	float Noise();
	uint32 Rng = 0x9E3779B9u;
	float SLevel = 0.f, SRate = 0.5f;
	float Phase = 0.f, Phase2 = 0.f, Env = 0.f, Env2 = 0.f, F1 = 1800.f, F2 = 2700.f, P1 = 0.f, P2 = 0.f, Glide = 0.f, Call = 0.f, Low = 0.f, Low2 = 0.f;
};

class UAudioComponent;
namespace SailingSound
{
	/** A looping spatialised voice of the given kind attached to Parent, falling off over about FalloffM. */
	SAILINGSIM_API UAudioComponent* MakeWorldSound(UObject* Owner, USceneComponent* Parent, EWorldSound Kind, float FalloffM, USailingWorldSynth*& OutSynth);
}
