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
	std::atomic<float> Volume{ 0.8f };
};

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
	float SWind = 0.f, SLuff = 0.f, STell = 0.f, SSpeed = 0.f, SHull = 0.f, SSlam = 0.f, STrim = 0.f, SRain = 0.f, SThunder = 0.f, SCrack = 0.f, SVolume = 0.8f;
	// Generators.
	float Pink[7] = {};
	float Brown = 0.f;
	float FlapPhase = 0.f, TellPhase = 0.f, ClickPhase = 0.f, GustPhase = 0.f;
	float ClickEnv = 0.f, DropEnv = 0.f, SlapEnv = 0.f;
	FBandPass WindBand, Whistle, FlogHigh, TellBand, ClickBand, ZipBand, DropBand, CrackBand, SlapBand;
	FOnePole WaterLow, RumbleLow, ThunderLow, RainHigh, FlogLow;
};
