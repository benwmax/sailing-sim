#include "SailingAudio.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Kismet/GameplayStatics.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingEnvironment.h"
#include "SailingFrame.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "AudioMixerBlueprintLibrary.h"
#include "SubmixEffects/AudioMixerSubmixEffectDynamicsProcessor.h"
#include "Sound/AudioSettings.h"
#include "Sound/SoundSubmix.h"

namespace SailingAudioLocal
{
	// Settings > Audio, copied by SailingSound::UpdateMix on the game thread for the audio thread.
	std::atomic<float> GMaster{ 0.8f * 1.585f };   // the default master with the default make-up, until UpdateMix
	std::atomic<float> GShare[int32(SailingSound::EGroup::Count)] = { { 1.f }, { 1.f }, { 1.f }, { 1.f } };
	std::atomic<bool> GMono{ false };
}

void SailingSound::UpdateMix()
{
	using namespace SailingAudioLocal;
	const USailingSettings* S = USailingSettings::Get();
	if (!S) return;
	GMaster = FMath::Clamp(S->Volume, 0.f, 1.f) * FMath::Pow(10.f, MakeupGainDb() / 20.f);
	GShare[int32(EGroup::Boat)] = FMath::Clamp(S->VolumeBoat, 0.f, 1.f);
	GShare[int32(EGroup::World)] = FMath::Clamp(S->VolumeWorld, 0.f, 1.f);
	GShare[int32(EGroup::Weather)] = FMath::Clamp(S->VolumeWeather, 0.f, 1.f);
	GShare[int32(EGroup::Signals)] = FMath::Clamp(S->VolumeSignals, 0.f, 1.f);
	GMono = S->bMonoAudio;
}

float SailingSound::GroupShare(EGroup Group)
{
	return SailingAudioLocal::GShare[FMath::Clamp(int32(Group), 0, int32(EGroup::Count) - 1)].load();
}

float SailingSound::GroupGain(EGroup Group)
{
	return SailingAudioLocal::GMaster.load() * GroupShare(Group);
}

float SailingSound::MasterGain()
{
	return SailingAudioLocal::GMaster.load();
}

float SailingSound::MakeupGainDb()
{
	// Loudness check Nov 12 (scripts/loudness-check.sh on main bc7e8801): the mix measured 4 to 9 LU under the plan's
	// -18 LUFS (breeze -20.2, storm -22.6, race -26.8, dusk -23.9) with true peaks no higher than -8.1 dBTP, so +4 dB
	// lifts it with 3 dB to spare. It is applied at the voices, not on the master submix: a gain or limiter added to the
	// master at runtime (AddMasterSubmixEffect or a chain override, +12 dB in or out) moved the recording by 0.2 LU at
	// most (the five-way check on f22849ff), so it never reached the recorded mix. The quiet scenes stay quieter than
	// the breeze on purpose. Read again when a bench list swaps the command line.
	static uint32 Gen = MAX_uint32;
	static float Db = 4.f;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		Db = 4.f;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingMakeupDb="), Db);
		Db = FMath::Clamp(Db, -24.f, 12.f);
	}
	return Db;
}

bool SailingSound::IsMono()
{
	return SailingAudioLocal::GMono.load();
}

SailingSound::EGroup SailingSound::CueGroup(ESailingCue Cue)
{
	return Cue == ESailingCue::RainDeck || Cue == ESailingCue::RainWater || Cue == ESailingCue::SquallHiss || Cue == ESailingCue::Thunder
		? EGroup::Weather : EGroup::Boat;
}

FSoundAttenuationSettings SailingSound::SpatialSettings(float FalloffM, float InnerM, float BlendStartM, float BlendEndM)
{
	FSoundAttenuationSettings S;
	S.bAttenuate = true;
	S.bSpatialize = !IsMono();
	S.AttenuationShape = EAttenuationShape::Sphere;
	S.AttenuationShapeExtents = FVector((InnerM >= 0.f ? InnerM : FalloffM * 0.05f) * 100.f);
	S.FalloffDistance = FalloffM * 100.f;
	S.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
	S.bAttenuateWithLPF = true;
	S.LPFRadiusMin = FalloffM * 10.f;
	S.LPFRadiusMax = FalloffM * 100.f;
	if (BlendStartM > 0.f)
	{
		S.NonSpatializedRadiusStart = BlendStartM * 100.f;
		S.NonSpatializedRadiusEnd = FMath::Min(BlendEndM, BlendStartM) * 100.f;
	}
	return S;
}

void SailingSound::SetSpatial(UAudioComponent* A, float FalloffM)
{
	if (!A) return;
	A->bAllowSpatialization = true;
	A->bOverrideAttenuation = true;
	A->AttenuationOverrides = SpatialSettings(FalloffM);
}

USoundAttenuation* SailingSound::MakeAttenuation(UObject* Outer, float FalloffM, float InnerM, float BlendStartM, float BlendEndM)
{
	USoundAttenuation* A = NewObject<USoundAttenuation>(Outer);
	A->Attenuation = SpatialSettings(FalloffM, InnerM, BlendStartM, BlendEndM);
	return A;
}

FVector SailingSound::AroundListener(const FVector& ListenerCm, double DirNorth, double DirEast, float DistanceM, float UpM)
{
	// The map frame and Unreal's world share their axes (+X north, +Y east): only the render origin differs, and a
	// direction does not see it.
	FVector2D D(DirNorth, DirEast);
	if (!D.Normalize()) D = FVector2D(1.0, 0.0);
	return ListenerCm + FVector(D.X, D.Y, 0.0) * DistanceM * 100.0 + FVector(0.0, 0.0, UpM * 100.0);
}

void SailingSound::TickAudioRecording(UObject* WorldContext)
{
	// Read once per command line (a bench list swaps it); one recording per run of the switch.
	static uint32 Gen = MAX_uint32;
	static float Seconds = 0.f, Warmup = 3.f;
	static int32 State = 0;   // 0 waiting, 1 recording, 2 written
	static double StartedAt = 0.0;
	static FString Shot;
	if (Gen != SailingArgs::Generation())
	{
		Gen = SailingArgs::Generation();
		Seconds = 0.f; Warmup = 3.f; State = 0;
		FParse::Value(SailingArgs::Dev(), TEXT("SailingRecordAudio="), Seconds);
		FParse::Value(SailingArgs::Dev(), TEXT("SailingBenchWarmup="), Warmup);
		if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingShot="), Shot)) Shot = TEXT("audio");
	}
	if (Seconds <= 0.f || State == 2 || !WorldContext || !WorldContext->GetWorld()) return;
	const double Now = WorldContext->GetWorld()->GetTimeSeconds();
	if (State == 0 && Now >= Warmup)
	{
		UAudioMixerBlueprintLibrary::StartRecordingOutput(WorldContext, Seconds);
		StartedAt = Now;
		State = 1;
		SAIL_LOG(Display, TEXT("Sound: recording the master mix for %.1f s"), Seconds);
	}
	else if (State == 1 && Now - StartedAt >= Seconds)
	{
		const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Bench"));
		IFileManager::Get().MakeDirectory(*Dir, true);
		UAudioMixerBlueprintLibrary::StopRecordingOutput(WorldContext, EAudioRecordingExportType::WavFile, Shot + TEXT(".audio"), Dir);
		State = 2;
		SAIL_LOG(Display, TEXT("Sound: wrote %s/%s.audio.wav"), *Dir, *Shot);
	}
}

void SailingSound::EnsureMasterLimiter(UObject* WorldContext)
{
	// Once per process: the master submix outlives the map reloads. The preset is rooted so the mixer keeps it.
	static bool bAdded = false;
	if (bAdded || !WorldContext || !GEngine || GEngine->UseSound() == false) return;
	bAdded = true;
	// Measuring (the loudness check, Nov 12: +4 dB of input gain did not show in the recording): -SailingNoMasterLimiter
	// leaves the master untouched, -SailingMasterGainDb=<dB> and -SailingMasterOutDb=<dB> replace the input and output
	// gains, -SailingMasterChain=override puts it on by a chain override, so a few runs of one scene say whether the
	// effect is in the recorded path, which way onto the master works and which gain reaches the output.
	if (FParse::Param(SailingArgs::Dev(), TEXT("SailingNoMasterLimiter")))
	{
		SAIL_LOG(Display, TEXT("Sound: master limiter off (-SailingNoMasterLimiter)"));
		return;
	}
	float InDb = 0.f, OutDb = 0.f;
	FParse::Value(SailingArgs::Dev(), TEXT("SailingMasterGainDb="), InDb);
	FParse::Value(SailingArgs::Dev(), TEXT("SailingMasterOutDb="), OutDb);
	USubmixEffectDynamicsProcessorPreset* Limiter = NewObject<USubmixEffectDynamicsProcessorPreset>(GetTransientPackage(), TEXT("SailingMasterLimiter"));
	FSubmixEffectDynamicsProcessorSettings L;
	L.DynamicsProcessorType = ESubmixEffectDynamicsProcessorType::Limiter;
	L.PeakMode = ESubmixEffectDynamicsPeakMode::Peak;
	L.LookAheadMsec = 3.f;
	L.AttackTimeMsec = 1.f;
	L.ReleaseTimeMsec = 150.f;
	L.ThresholdDb = -1.5f;   // under the -1 dBTP ceiling (docs: the sound plan's loudness target)
	L.KneeBandwidthDb = 3.f;
	// The make-up gain is at the voices (SailingSound::MakeupGainDb): the five-way check found no gain here reaching the
	// recorded mix. The limiter stays as a ceiling in case it does process on some device.
	L.InputGainDb = InDb;
	L.OutputGainDb = OutDb;
	Limiter->SetSettings(L);
	Limiter->AddToRoot();
	// Two ways onto the master (-SailingMasterChain=append|override). Append is AddMasterSubmixEffect, which adds to the
	// submix's first effect chain; UE-104414 reports effects added at runtime doing nothing, and the engine's default
	// master submix has no chain of its own. Override sets a whole chain on the main submix object, which the mixer
	// builds as a new chain of its own.
	FString Chain = TEXT("append");
	FParse::Value(SailingArgs::Dev(), TEXT("SailingMasterChain="), Chain);
	USoundSubmix* Main = nullptr;
	if (Chain == TEXT("override"))
	{
		Main = Cast<USoundSubmix>(GetDefault<UAudioSettings>()->MasterSubmix.TryLoad());
		if (Main)
		{
			Main->AddToRoot();
			TArray<USoundEffectSubmixPreset*> Presets;
			Presets.Add(Limiter);
			UAudioMixerBlueprintLibrary::SetSubmixEffectChainOverride(WorldContext, Main, Presets, 0.f);
		}
		else
		{
			SAIL_LOG(Warning, TEXT("Sound: no main submix object for the override chain; appending instead"));
		}
	}
	if (!Main) UAudioMixerBlueprintLibrary::AddMasterSubmixEffect(WorldContext, Limiter);
	SAIL_LOG(Display, TEXT("Sound: master limiter added by %s (submix %s; input %+.1f dB, output %+.1f dB, threshold %.1f dB)"),
		Main ? TEXT("override") : TEXT("append"), Main ? *Main->GetPathName() : TEXT("master"), InDb, OutDb, L.ThresholdDb);
}

const TCHAR* SailingCueName(ESailingCue Cue)
{
	static const TCHAR* Names[] = { TEXT("Wind"), TEXT("GustRumble"), TEXT("SailFlog"), TEXT("Telltales"), TEXT("BowWave"), TEXT("HullSlap"), TEXT("Winch"),
		TEXT("SheetBlock"), TEXT("HalyardSlap"), TEXT("RainDeck"), TEXT("RainWater"), TEXT("SquallHiss"), TEXT("Thunder") };
	return Names[FMath::Clamp(int32(Cue), 0, int32(ESailingCue::Count) - 1)];
}

bool SailingSound::HasSheetWinches(Sailing::EBoatType Type)
{
	using Sailing::EBoatType;
	return !(Type == EBoatType::Sunfish || Type == EBoatType::ILCA7 || Type == EBoatType::Hobie16);
}

const TCHAR* WorldSoundName(EWorldSound Kind)
{
	static const TCHAR* Names[] = { TEXT("MarinaHalyards"), TEXT("Gulls"), TEXT("Outboard"), TEXT("Diesel"), TEXT("Horn"), TEXT("Thunder"), TEXT("ShoreLife") };
	static_assert(UE_ARRAY_COUNT(Names) == int32(EWorldSound::Count), "a name for every world sound");
	return Names[FMath::Clamp(int32(Kind), 0, int32(EWorldSound::Count) - 1)];
}

USailingSynthWave::USailingSynthWave(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SetSampleRate(48000);
	NumChannels = 1;
	Duration = INDEFINITELY_LOOPING_DURATION;
	bLooping = true;
	bProcedural = true;
	SampleByteSize = 2;
}

float USailingSynthWave::Noise()
{
	Rng ^= Rng << 13; Rng ^= Rng >> 17; Rng ^= Rng << 5;
	return (Rng & 0xFFFFFF) / float(0x7FFFFF) - 1.f;
}

int32 USailingSynthWave::OnGeneratePCMAudio(TArray<uint8>& OutAudio, int32 NumSamples)
{
	OutAudio.SetNumUninitialized(NumSamples * 2);
	int16* Out = reinterpret_cast<int16*>(OutAudio.GetData());
	const float Sr = SampleRateHz;
	const float Rate = 1.f / (0.05f * Sr); // parameter smoothing, about 50 ms

	const float TWind = Params.ApparentWind.load(), TLuff = Params.Luff.load(), TTell = Params.Telltales.load();
	const float TSpeed = Params.BoatSpeed.load(), THull = Params.HullSpeedRatio.load(), TSlam = Params.BowSlam.load();
	const float TTrim = Params.TrimRate.load(), TRain = Params.Rain.load(), TThunder = Params.Thunder.load(), TCrack = Params.ThunderCrack.load();
	const float TVolume = Params.Volume.load();
	const float THorn = Params.HornLevel.load(), HornFreq = FMath::Max(Params.HornHz.load(), 40.f);
	const float TGust = Params.GustRatio.load(), TShadow = Params.WindShadow.load(), TMoored = Params.Moored.load();
	const float TRainDeck = Params.RainDeck.load(), TRainWater = Params.RainWater.load(), TSquall = Params.Squall.load();
	const float Winches = FMath::Clamp(Params.Winches.load(), 0.f, 1.f);
	const float TGainBoat = Params.GainBoat.load(), TGainWeather = Params.GainWeather.load(), TGainSignals = Params.GainSignals.load();
	const float LimiterRelease = FMath::Exp(-1.f / (0.15f * Sr));
	// A recorded sample plays instead of a muted voice (the pawn's sample layer).
	const uint32 Mask = Params.SampledMask.load();
	auto On = [Mask](ESailingCue C) { return (Mask & (1u << uint32(C))) ? 0.f : 1.f; };
	const float MWind = On(ESailingCue::Wind), MGust = On(ESailingCue::GustRumble), MFlog = On(ESailingCue::SailFlog), MTell = On(ESailingCue::Telltales);
	const float MBow = On(ESailingCue::BowWave), MSlap = On(ESailingCue::HullSlap), MWinch = On(ESailingCue::Winch), MSheet = On(ESailingCue::SheetBlock);
	const float MHalyard = On(ESailingCue::HalyardSlap), MDeck = On(ESailingCue::RainDeck), MWater = On(ESailingCue::RainWater), MSquall = On(ESailingCue::SquallHiss);
	const float MThunder = On(ESailingCue::Thunder);

	for (int32 I = 0; I < NumSamples; ++I)
	{
		const float Shadow = Smooth(SShadow, TShadow, Rate * 0.2f);
		// In the lee of a shore or a big boat the wind in the ears hushes faster than the wind on the sails drops.
		const float W = Smooth(SWind, TWind, Rate) * (1.f - 0.55f * Shadow), Lf = Smooth(SLuff, TLuff, Rate), Tl = Smooth(STell, TTell, Rate);
		const float Gr = Smooth(SGust, TGust, Rate * 0.3f), Mo = Smooth(SMoored, TMoored, Rate * 0.2f);
		const float Rd = Smooth(SRainDeck, TRainDeck, Rate), Rw = Smooth(SRainWater, TRainWater, Rate), Sq = Smooth(SSquall, TSquall, Rate * 0.2f);
		const float Sp = Smooth(SSpeed, TSpeed, Rate), Hr = Smooth(SHull, THull, Rate), Sl = Smooth(SSlam, TSlam, Rate * 4.f);
		const float Tr = Smooth(STrim, TTrim, Rate), Rn = Smooth(SRain, TRain, Rate), Th = Smooth(SThunder, TThunder, Rate), Cr = Smooth(SCrack, TCrack, Rate * 4.f);
		const float Vol = Smooth(SVolume, TVolume, Rate);

		const float WhiteN = Noise();
		// Pink noise (Paul Kellet's filter) and brown noise (leaky integrator).
		Pink[0] = 0.99886f * Pink[0] + WhiteN * 0.0555179f; Pink[1] = 0.99332f * Pink[1] + WhiteN * 0.0750759f;
		Pink[2] = 0.96900f * Pink[2] + WhiteN * 0.1538520f; Pink[3] = 0.86650f * Pink[3] + WhiteN * 0.3104856f;
		Pink[4] = 0.55000f * Pink[4] + WhiteN * 0.5329522f; Pink[5] = -0.7616f * Pink[5] - WhiteN * 0.0168980f;
		const float PinkN = (Pink[0] + Pink[1] + Pink[2] + Pink[3] + Pink[4] + Pink[5] + Pink[6] + WhiteN * 0.5362f) * 0.11f;
		Pink[6] = WhiteN * 0.115926f;
		Brown = (Brown + 0.02f * WhiteN) * 0.996f;
		const float BrownN = Brown * 3.5f;

		float Mix = 0.f, MixWeather = 0.f, MixSignals = 0.f;   // on board, weather, horns (the player's groups)

		// Wind in the rigging: a breathy band that rises in pitch and level with apparent wind, slowly gusting.
		GustPhase += 0.23f / Sr;
		const float Gust = 0.75f + 0.25f * FMath::Sin(2.f * PI * GustPhase) * FMath::Sin(2.f * PI * GustPhase * 0.37f);
		const float WindLevel = FMath::Clamp(W / 10.f, 0.f, 2.5f);
		Mix += WindBand.Process(PinkN, FMath::Min(0.9f, 2.f * PI * (220.f + 55.f * W) / Sr), 0.7f) * 0.35f * WindLevel * WindLevel * Gust * MWind;
		Mix += Whistle.Process(WhiteN, FMath::Min(0.9f, 2.f * PI * (850.f + 70.f * W) / Sr), 0.06f) * 0.012f * FMath::Pow(WindLevel, 3.f) * Gust * MWind;
		// A gust buffets the ears: a low, irregular rumble growing with how far the wind is over its mean.
		Mix += GustLow.Low(BrownN, 2.f * PI * 45.f / Sr) * 0.05f * FMath::Clamp((Gr - 1.f) * 2.5f, 0.f, 1.f) * FMath::Clamp(W / 7.f, 0.f, 1.5f) * MGust;

		// Luffing / flogging: slapping bursts at a rate that rises with the wind.
		FlapPhase += (3.5f + 0.9f * W) / Sr;
		if (FlapPhase > 1.f) FlapPhase -= 1.f;
		const float Flap = FMath::Pow(0.5f + 0.5f * FMath::Sin(2.f * PI * FlapPhase), 8.f);
		const float FlogNoise = WhiteN - FlogLow.Low(WhiteN, 0.05f);
		Mix += FlogHigh.Process(FlogNoise * Flap, 0.25f, 0.5f) * 0.9f * Lf * FMath::Clamp(W / 8.f, 0.f, 2.f) * MFlog;

		// Telltales: a light, fast rattle.
		TellPhase += 23.f / Sr;
		if (TellPhase > 1.f) TellPhase -= 1.f;
		Mix += TellBand.Process(WhiteN * (TellPhase < 0.3f ? 1.f : 0.2f), 0.45f, 0.4f) * 0.02f * Tl * FMath::Clamp(W / 8.f, 0.f, 1.5f) * MTell;

		// Water past the hull: brighter and louder with speed; a deep rumble as she nears hull speed.
		const float WaterCut = FMath::Min(0.9f, 2.f * PI * (120.f + 140.f * Sp) / Sr);
		Mix += WaterLow.Low(PinkN, WaterCut) * 0.5f * FMath::Pow(FMath::Clamp(Sp / 3.f, 0.f, 1.5f), 1.5f) * MBow;
		const float Rumble = FMath::Clamp((Hr - 0.85f) / 0.2f, 0.f, 1.f);
		Mix += RumbleLow.Low(BrownN, 2.f * PI * 90.f / Sr) * 1.2f * Rumble * MBow;
		// At rest the wavelets lap at the hull: soft, hollow knocks.
		if (Noise() > 1.f - 0.00025f * (0.4f + W / 6.f)) LapEnv = 0.6f + 0.4f * FMath::Abs(Noise());
		LapEnv *= 0.9985f;
		Mix += LapBand.Process(LapLow.Low(WhiteN, 0.2f) * LapEnv, 2.f * PI * 260.f / Sr, 0.35f) * 0.9f * Mo * MSlap;
		// ... and the halyard slaps the mast when the wind gets at it: a ringing aluminium ping.
		if (Mo > 0.2f && W > 2.f && Noise() > 1.f - 0.00006f * W * Mo)
		{
			HalyardEnv = 0.7f + 0.3f * FMath::Abs(Noise());
			HalyardF1 = 1400.f + 600.f * FMath::Abs(Noise());
			HalyardF2 = HalyardF1 * 2.76f;
		}
		HalyardEnv *= 0.99975f;
		HalyardP1 += HalyardF1 / Sr; HalyardP2 += HalyardF2 / Sr;
		HalyardP1 -= FMath::FloorToFloat(HalyardP1); HalyardP2 -= FMath::FloorToFloat(HalyardP2);
		Mix += (FMath::Sin(2.f * PI * HalyardP1) + 0.4f * FMath::Sin(2.f * PI * HalyardP2)) * 0.06f * HalyardEnv * HalyardEnv * MHalyard;

		// Bow wave slaps when the bow meets a wave.
		if (Noise() > 1.f - 0.0004f * Sl) SlapEnv = 1.f;
		SlapEnv *= 0.9993f;
		Mix += SlapBand.Process(WhiteN, 0.12f, 0.7f) * 0.35f * SlapEnv * Sl * MSlap;

		// Winch clicks while trimming in; the whir of a sheet running out while easing.
		if (Tr > 0.05f)
		{
			ClickPhase += (8.f + 14.f * Tr) / Sr;
			if (ClickPhase > 1.f) { ClickPhase -= 1.f; ClickEnv = 1.f; }
		}
		ClickEnv *= 0.992f;
		Mix += ClickBand.Process(WhiteN * ClickEnv, 0.38f, 0.15f) * 0.5f * MWinch * Winches;
		// Without winches (a dinghy) the sheet runs through its blocks both ways: trimming in sounds like easing.
		const float SheetRun = FMath::Clamp(-Tr, 0.f, 1.f) + (1.f - Winches) * FMath::Clamp(Tr, 0.f, 1.f);
		Mix += ZipBand.Process(WhiteN, 0.15f, 0.3f) * 0.08f * SheetRun * MSheet;
		// The sheet through its block: a squeak pitched by how fast it runs.
		SheetPhase += (600.f + 900.f * FMath::Abs(Tr)) / Sr;
		SheetPhase -= FMath::FloorToFloat(SheetPhase);
		Mix += SheetBand.Process(FMath::Sin(2.f * PI * SheetPhase) * (0.5f + 0.5f * WhiteN), 0.2f, 0.2f) * 0.02f * FMath::Clamp(FMath::Abs(Tr) - 0.1f, 0.f, 1.f) * MSheet;

		// Rain: hiss on the water and drops on the deck.
		// Rain: the hiss on the water around and the drops on the deck and sails, as separate layers.
		MixWeather += (WhiteN - RainHigh.Low(WhiteN, 0.08f)) * 0.06f * FMath::Max(Rw, Rn * 0.0f) * MWater;
		if (Noise() > 1.f - 0.004f * Rd) DropEnv = 1.f;
		DropEnv *= 0.99f;
		MixWeather += DropBand.Process(WhiteN * DropEnv, 0.5f, 0.3f) * 0.2f * Rd * MDeck;
		// A squall coming across the water: a broad hiss, the rain and the wind's roar, rising as it nears.
		MixWeather += (SquallBand.Process(WhiteN, 2.f * PI * 3500.f / Sr, 0.9f) * 0.05f + SquallBand2.Process(PinkN, 2.f * PI * 600.f / Sr, 0.8f) * 0.08f) * Sq * Sq * MSquall;

		// Thunder: a rolling low rumble, and a crack for a close strike.
		MixWeather += ThunderLow.Low(BrownN, 2.f * PI * 70.f / Sr) * 2.2f * Th * MThunder;
		MixWeather += CrackBand.Process(WhiteN, 0.08f, 0.6f) * 0.8f * Cr * MThunder;

		// A whistle: a reedy tone (odd and even harmonics) with a little vibrato, fading in and out over 30 ms.
		const float Hn = Smooth(SHorn, THorn, Rate * 1.6f);
		if (Hn > 1e-4f)
		{
			HornVib += 5.5f / Sr;
			HornPhase += HornFreq * (1.f + 0.004f * FMath::Sin(2.f * PI * HornVib)) / Sr;
			HornPhase -= FMath::FloorToFloat(HornPhase);
			const float A = 2.f * PI * HornPhase;
			MixSignals += (FMath::Sin(A) + 0.5f * FMath::Sin(2.f * A) + 0.33f * FMath::Sin(3.f * A) + 0.18f * FMath::Sin(5.f * A)) * 0.35f * Hn;
		}

		// The groups at the player's levels, then a peak limiter (instant attack, 150 ms release) in place of the old tanh
		// clip: a loud layer turns the whole voice down a little instead of distorting everything under it.
		const float Gb = Smooth(SGainBoat, TGainBoat, Rate), Gw = Smooth(SGainWeather, TGainWeather, Rate), Gs = Smooth(SGainSignals, TGainSignals, Rate);
		const float Pre = (Mix * Gb + MixWeather * Gw + MixSignals * Gs) * Vol * 1.4f;
		const float Peak = FMath::Abs(Pre);
		LimiterEnv = Peak > LimiterEnv ? Peak : LimiterEnv * LimiterRelease;
		const float Sample = FMath::Clamp(Pre * (LimiterEnv > 0.9f ? 0.9f / LimiterEnv : 1.f), -1.f, 1.f);
		Out[I] = int16(Sample * 32000.f);
	}
	return NumSamples;
}

USailingWorldSynth::USailingWorldSynth(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	SetSampleRate(48000);
	NumChannels = 1;
	Duration = INDEFINITELY_LOOPING_DURATION;
	bLooping = true;
	bProcedural = true;
	SampleByteSize = 2;
}

float USailingWorldSynth::Noise()
{
	Rng ^= Rng << 13; Rng ^= Rng >> 17; Rng ^= Rng << 5;
	return (Rng & 0xFFFFFF) / float(0x7FFFFF) - 1.f;
}

namespace SailingAudioLocal
{
	// Linear to 0.8, then a smooth knee that never passes 1: the master's make-up gain (up to about 1.6) would otherwise
	// hard-clip the world voices' loudest peaks (a close strike's rumble shapes to 0.95 before the gain).
	static float SoftCeiling(float X)
	{
		const float A = FMath::Abs(X);
		return A <= 0.8f ? X : FMath::Sign(X) * (0.8f + 0.2f * FMath::Tanh((A - 0.8f) / 0.2f));
	}
}

int32 USailingWorldSynth::OnGeneratePCMAudio(TArray<uint8>& OutAudio, int32 NumSamples)
{
	OutAudio.SetNumUninitialized(NumSamples * 2);
	int16* Out = reinterpret_cast<int16*>(OutAudio.GetData());
	const float Sr = 48000.f;
	if (Rng == 0x9E3779B9u) Rng ^= Seed * 2654435761u;
	const float TLevel = Level.load(), TRate = Rate.load();
	// The rate is a setting (wind, throttle, the crack), not a level: no glide from the default on the first block.
	if (!bRateSet) { SRate = TRate; bRateSet = true; }
	// The player's mix: the marina, gulls and engines are the lake and shore group; a horn is a signal, thunder weather.
	const float Gain = SailingSound::GroupGain(Kind == EWorldSound::Horn ? SailingSound::EGroup::Signals
		: Kind == EWorldSound::Thunder ? SailingSound::EGroup::Weather : SailingSound::EGroup::World);
	const float THz = FMath::Max(Hz.load(), 40.f);
	for (int32 I = 0; I < NumSamples; ++I)
	{
		SLevel += (TLevel - SLevel) * 0.0005f;
		SRate += (TRate - SRate) * 0.0005f;
		float Mix = 0.f;
		float OutLevel = SLevel;
		switch (Kind)
		{
		case EWorldSound::MarinaHalyards:
		{
			// A marina in a breeze: many halyards pinging on many masts at random, a few hollow clanks.
			if (Noise() > 1.f - 0.0004f * (0.3f + 2.f * SRate)) { Env = 0.5f + 0.5f * FMath::Abs(Noise()); F1 = 1100.f + 1900.f * FMath::Abs(Noise()); F2 = F1 * (2.4f + 0.6f * FMath::Abs(Noise())); }
			if (Noise() > 1.f - 0.00004f * (0.2f + SRate)) Env2 = 1.f;
			Env *= 0.99965f; Env2 *= 0.998f;
			P1 += F1 / Sr; P2 += F2 / Sr; P1 -= FMath::FloorToFloat(P1); P2 -= FMath::FloorToFloat(P2);
			Low += 0.02f * (Noise() - Low);
			Mix = (FMath::Sin(2.f * PI * P1) + 0.35f * FMath::Sin(2.f * PI * P2)) * 0.25f * Env * Env + Low * 3.f * Env2;
			break;
		}
		case EWorldSound::Gulls:
		{
			// Laughing gulls: a falling "kee-ow" with harmonics now and then, sometimes a run of short calls.
			if (Call <= 0.f && Noise() > 1.f - 0.00003f * (0.3f + SRate)) { Call = 0.35f + 0.25f * FMath::Abs(Noise()); Glide = 0.f; }
			if (Call > 0.f)
			{
				Glide += 1.f / Sr;
				const float T = Glide / Call;
				const float F = 1700.f - 900.f * T + 250.f * FMath::Sin(T * 6.f);
				Phase += F / Sr; Phase -= FMath::FloorToFloat(Phase);
				const float A = FMath::Sin(PI * FMath::Clamp(T, 0.f, 1.f));
				Mix = (FMath::Sin(2.f * PI * Phase) + 0.5f * FMath::Sin(4.f * PI * Phase) + 0.25f * FMath::Sin(6.f * PI * Phase) + 0.15f * Noise()) * 0.18f * A;
				if (T >= 1.f) Call = Noise() > 0.4f ? 0.f : -1.f;
			}
			else if (Call < 0.f) { Call += 0.00002f; if (Call >= 0.f) Call = 0.f; }
			break;
		}
		case EWorldSound::Outboard:
		{
			// A two-stroke outboard: a buzzing pulse train at the firing rate, prop wash under it.
			const float F = 45.f + 85.f * SRate;
			Phase += F / Sr; Phase -= FMath::FloorToFloat(Phase);
			const float Pulse = FMath::Pow(1.f - Phase, 6.f) - 0.15f;
			Low += 0.08f * (Pulse - Low);
			Low2 += 0.01f * (Noise() - Low2);
			Mix = (Pulse - Low) * 0.5f + Low2 * 1.5f * SRate;
			break;
		}
		case EWorldSound::Diesel:
		{
			// A big slow diesel: a deep throb and its harmonics, felt more than heard far off.
			const float F = 9.f + 14.f * SRate;
			Phase += F / Sr; Phase -= FMath::FloorToFloat(Phase);
			Phase2 += 3.02f * F / Sr; Phase2 -= FMath::FloorToFloat(Phase2);
			Low += 0.003f * (Noise() - Low);
			Mix = 0.35f * (FMath::Sin(2.f * PI * Phase) * 0.6f + FMath::Sin(2.f * PI * Phase2) * 0.25f + Low * 4.f) * (0.7f + 0.3f * FMath::Sin(2.f * PI * Phase * 0.5f));
			break;
		}
		case EWorldSound::Horn:
		{
			// A whistle (the boat synth's old voice, now at the vessel): a reedy tone, odd and even harmonics, a little
			// vibrato. Level fades it in and out over about 40 ms.
			Phase2 += 5.5f / Sr; Phase2 -= FMath::FloorToFloat(Phase2);
			Phase += THz * (1.f + 0.004f * FMath::Sin(2.f * PI * Phase2)) / Sr; Phase -= FMath::FloorToFloat(Phase);
			const float A = 2.f * PI * Phase;
			Mix = (FMath::Sin(A) + 0.5f * FMath::Sin(2.f * A) + 0.33f * FMath::Sin(3.f * A) + 0.18f * FMath::Sin(5.f * A)) * 0.3f;
			break;
		}
		case EWorldSound::Thunder:
		{
			// Thunder from the strike: a rolling low rumble (Level) and, for a close strike, a crack (Rate). The levels
			// come from ASailingEnvironment's thunder envelopes; the source sits toward the strike.
			Low2 += 0.02f * (Noise() - Low2);                       // brown noise
			Low += (2.f * PI * 70.f / Sr) * (Low2 * 8.f - Low);     // under 70 Hz
			const float High = Noise() - BandLow - 0.6f * Band;     // the crack's band-pass (about 600 Hz, wide)
			Band += 0.08f * High; BandLow += 0.08f * Band;
			Mix = Low * 1.2f * SLevel + Band * 0.6f * SRate;   // the crack can lead the rumble's rise
			OutLevel = 1.f;
			break;
		}
		case EWorldSound::ShoreLife:
			Mix = ShoreLifeSample(Sr);
			break;
		default: break;
		}
		Out[I] = bMuted.load() ? int16(0) : int16(SailingAudioLocal::SoftCeiling(FMath::Tanh(Mix * OutLevel * 1.5f) * Gain) * 30000.f);
	}
	return NumSamples;
}

UAudioComponent* SailingSound::MakeWorldSound(UObject* Owner, USceneComponent* Parent, EWorldSound Kind, float FalloffM, USailingWorldSynth*& OutSynth)
{
	OutSynth = NewObject<USailingWorldSynth>(Owner);
	OutSynth->Kind = Kind;
	OutSynth->Seed = uint32(Owner->GetUniqueID()) * 7919u + uint32(Kind);
	UAudioComponent* A = NewObject<UAudioComponent>(Owner);
	A->SetupAttachment(Parent);
	A->bAutoActivate = false;
	SetSpatial(A, FalloffM);
	A->SetSound(OutSynth);
	A->RegisterComponent();
	A->Play();
	// Graphics G7: the pack's recordings for this kind, when imported, play instead of the synth.
	if (AActor* Actor = Cast<AActor>(Owner))
	{
		USailingWorldSamples* Samples = NewObject<USailingWorldSamples>(Actor);
		const ASailingGameMode* GM = Actor->GetWorld() ? Actor->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
		if (Samples->Init(OutSynth, Parent, FalloffM, GM && GM->GetLake().IsCoast())) Samples->RegisterComponent();
		else Samples->MarkAsGarbage();
	}
	return A;
}

// ---------------------------------------------------------------- Graphics G7: the sample pack

void SailingSound::Crossfade(float X, const float* Centers, int32 N, float* OutWeights)
{
	for (int32 I = 0; I < N; ++I) OutWeights[I] = 0.f;
	if (N <= 0) return;
	if (X <= Centers[0]) { OutWeights[0] = 1.f; return; }
	if (X >= Centers[N - 1]) { OutWeights[N - 1] = 1.f; return; }
	for (int32 I = 0; I + 1 < N; ++I)
	{
		if (X <= Centers[I + 1])
		{
			const float T = (X - Centers[I]) / FMath::Max(Centers[I + 1] - Centers[I], 1e-4f);
			OutWeights[I] = FMath::Cos(T * HALF_PI);
			OutWeights[I + 1] = FMath::Sin(T * HALF_PI);
			return;
		}
	}
}

USoundBase* SailingSound::LoadPack(const FString& Asset)
{
	const FString Name = FPaths::GetBaseFilename(Asset);
	return LoadObject<USoundBase>(nullptr, *FString::Printf(TEXT("/Game/Audio/Pack/%s.%s"), *Asset, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
}

TConstArrayView<SailingSound::FPackLoop> SailingSound::PackLoops()
{
	// Inputs/audio/manifest.json's "Game parameter" column: which FSailingSoundParams value each loop follows.
	static const FPackLoop Loops[] = {
		{ TEXT("Wind/wind_rigging_light_loop"), ESailingCue::Wind, 0 },            // apparent wind under 5 m/s
		{ TEXT("Wind/wind_rigging_moderate_loop"), ESailingCue::Wind, 1 },         // 5 to 9
		{ TEXT("Wind/wind_rigging_strong_loop"), ESailingCue::Wind, 2 },           // over 9
		{ TEXT("Sails/sail_luff_light_loop"), ESailingCue::SailFlog, 0 },          // luff 0.1 to 0.4
		{ TEXT("Sails/sail_luff_moderate_loop"), ESailingCue::SailFlog, 1 },       // 0.4 to 0.7
		{ TEXT("Sails/sail_flog_strong_loop"), ESailingCue::SailFlog, 2 },         // over 0.7 in more than 7 m/s
		{ TEXT("Water/hull_wash_1kn_loop"), ESailingCue::BowWave, 0 },             // boat speed 0.5 m/s
		{ TEXT("Water/hull_wash_3kn_loop"), ESailingCue::BowWave, 1 },             // 1.5
		{ TEXT("Water/hull_wash_5kn_loop"), ESailingCue::BowWave, 2 },             // 2.6
		{ TEXT("Water/hull_wash_7kn_loop"), ESailingCue::BowWave, 3 },             // 3.6, raised near hull speed
		{ TEXT("Water/water_lapping_hull_calm_loop"), ESailingCue::HullSlap, 0 },  // at rest
		{ TEXT("Water/water_lapping_dock_loop"), ESailingCue::HullSlap, 1 },       // at rest in the slip
		{ TEXT("Water/water_lapping_hull_choppy_loop"), ESailingCue::HullSlap, 2 },// bow slam, or drifting in a chop
		{ TEXT("Winch/winch_ratchet_slow_loop"), ESailingCue::Winch, 0 },          // trimming slowly
		{ TEXT("Winch/winch_ratchet_tailing_loop"), ESailingCue::Winch, 1 },       // trimming fast
		{ TEXT("Rigging/sheet_running_block_loop"), ESailingCue::SheetBlock, 0 },  // easing
		{ TEXT("Weather/rain_on_roof_light_loop"), ESailingCue::RainDeck, 0 },     // rain
	};
	return Loops;
}

TArray<FString> SailingSound::PackShots(EPackShot Shot)
{
	auto Numbered = [](const TCHAR* Base, int32 N) { TArray<FString> Out; for (int32 I = 1; I <= N; ++I) Out.Add(FString::Printf(TEXT("%s_%02d"), Base, I)); return Out; };
	switch (Shot)
	{
	case EPackShot::HalyardSlap: return Numbered(TEXT("Rigging/halyard_slap"), 6);
	case EPackShot::SailFill: return Numbered(TEXT("Sails/sail_fill_snap"), 3);
	case EPackShot::WinchClick: return Numbered(TEXT("Winch/winch_click"), 4);
	case EPackShot::SheetEaseFast: return { TEXT("Rigging/sheet_ease_through_block_01") };
	case EPackShot::SheetEaseSlow: return { TEXT("Rigging/sheet_ease_through_block_02") };
	case EPackShot::DockCreak: return Numbered(TEXT("Dock/dock_creak"), 5);
	case EPackShot::FenderSqueak: return Numbered(TEXT("Dock/fender_squeak"), 3);
	default: return {};
	}
}

USailingWorldSamples::USailingWorldSamples()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.1f;
}

bool USailingWorldSamples::Init(USailingWorldSynth* InSynth, USceneComponent* Parent, float FalloffM, bool bCoast)
{
	Synth = InSynth;
	TArray<FString> LoopAssets;
	switch (InSynth->Kind)
	{
	case EWorldSound::MarinaHalyards: LoopAssets = { TEXT("Rigging/marina_halyards_distant_loop") }; Centers = { 0.f }; break;
	case EWorldSound::Outboard: LoopAssets = { TEXT("Engines/outboard_idle_loop"), TEXT("Engines/outboard_lowspeed_loop"), TEXT("Engines/outboard_running_loop") }; Centers = { 0.05f, 0.4f, 0.9f }; break;
	case EWorldSound::Gulls:
	{
		// Herring-type gulls on the lake; on the coast the laughing gull, Galveston Bay's commonest, joins them.
		TArray<FString> Names = { TEXT("Birds/gull_call_01"), TEXT("Birds/gull_call_02"), TEXT("Birds/gull_call_03") };
		if (bCoast) { Names.Add(TEXT("Birds/laughing_gull_01")); Names.Add(TEXT("Birds/laughing_gull_01")); }
		for (const FString& N : Names) if (USoundBase* S = SailingSound::LoadPack(N)) Calls.Add(S);
		break;
	}
	default: break;
	}
	auto MakeVoice = [&](USoundBase* Sound)
	{
		UAudioComponent* A = NewObject<UAudioComponent>(GetOwner());
		A->SetupAttachment(Parent);
		A->bAutoActivate = false;
		SailingSound::SetSpatial(A, FalloffM);
		A->SetSound(Sound);
		A->SetVolumeMultiplier(0.f);
		A->RegisterComponent();
		return A;
	};
	for (const FString& Asset : LoopAssets)
	{
		USoundBase* Sound = SailingSound::LoadPack(Asset);
		if (!Sound) { Loops.Reset(); return false; }
		UAudioComponent* A = MakeVoice(Sound);
		A->Play(FMath::FRand() * 5.f);   // each source from its own place in the loop
		Loops.Add(A);
	}
	if (Calls.Num()) CallVoice = MakeVoice(Calls[0]);
	if (Loops.Num() == 0 && Calls.Num() == 0) return false;
	Synth->bMuted = true;
	return true;
}

void USailingWorldSamples::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!Synth) return;
	const float Level = Synth->Level.load() * SailingSound::GroupGain(SailingSound::EGroup::World), Rate = Synth->Rate.load();
	if (Loops.Num())
	{
		float W[4] = {};
		SailingSound::Crossfade(Rate, Centers.GetData(), FMath::Min(Centers.Num(), 4), W);
		for (int32 I = 0; I < Loops.Num() && I < 4; ++I) if (Loops[I]) Loops[I]->SetVolumeMultiplier(Level * W[I] * (Synth->Kind == EWorldSound::MarinaHalyards ? 0.4f + 0.8f * Rate : 1.f));
	}
	if (CallVoice && Calls.Num() && Level > 0.02f)
	{
		const double Now = GetWorld()->GetTimeSeconds();
		if (NextCall <= 0.0) NextCall = Now + FMath::FRandRange(1.0, 8.0);
		if (Now >= NextCall)
		{
			// A call now and then, more often where there are more gulls (the owner's level and rate).
			NextCall = Now + FMath::FRandRange(2.5, 9.0) / FMath::Max(0.3f + Rate, 0.3f);
			CallVoice->SetSound(Calls[FMath::RandRange(0, Calls.Num() - 1)]);
			CallVoice->SetPitchMultiplier(FMath::FRandRange(0.95f, 1.05f));
			CallVoice->SetVolumeMultiplier(Level);
			CallVoice->Play();
		}
	}
}

// ---------------------------------------------------------------- Slice sound pass: the lake's soundscape

namespace
{
	/** 0 below A, 1 above B (or the other way round when A > B), smooth between. */
	float LifeRamp(double X, double A, double B)
	{
		const double T = FMath::Clamp((X - A) / (B - A), 0.0, 1.0);
		return float(T * T * (3.0 - 2.0 * T));
	}
	/** 1 from day Start to day End of the year, fading over Fade days either side. */
	float LifeSeason(int32 Day, int32 Start, int32 End, int32 Fade)
	{
		return LifeRamp(Day, Start - Fade, Start) * LifeRamp(Day, End + Fade, End);
	}
}

SailingSound::FShoreLife SailingSound::ShoreLifeFor(double SunElevationDeg, bool bMorning, int32 DayOfYear, float Rain, float WindMs)
{
	FShoreLife L;
	const double E = SunElevationDeg;
	// Birds: the dawn chorus from civil twilight to the sun well up, a thinner song by day, a little at dusk; none at night.
	const float Dawn = LifeRamp(E, -8.0, -4.0) * LifeRamp(E, 30.0, 15.0);
	const float Day = 0.45f * LifeRamp(E, -2.0, 4.0);
	const float Dusk = 0.6f * LifeRamp(E, -6.0, -2.0) * LifeRamp(E, 10.0, 4.0);
	L.Birds = FMath::Max(bMorning ? Dawn : Dusk, Day) * (0.65f + 0.35f * LifeSeason(DayOfYear, 60, 180, 30));
	// Cicadas: the heat of a summer's day (June to September).
	L.Cicadas = LifeRamp(E, 6.0, 18.0) * LifeSeason(DayOfYear, 160, 255, 20);
	// Crickets and katydids: from dusk through the night, April to early November.
	L.Crickets = LifeRamp(E, 3.0, -4.0) * LifeSeason(DayOfYear, 105, 300, 20);
	// Frogs: chorus frogs from February, cricket frogs and bullfrogs through the summer; at night.
	L.Frogs = LifeRamp(E, 2.0, -4.0) * LifeSeason(DayOfYear, 45, 245, 20);
	// Rain quiets the birds and the insects and wakes the frogs; a breeze thins every chorus (and covers it).
	const float R = FMath::Clamp(Rain, 0.f, 1.f);
	L.Birds *= 1.f - 0.85f * R;
	L.Cicadas *= 1.f - 0.85f * R;
	L.Crickets *= 1.f - 0.6f * R;
	L.Frogs = FMath::Min(1.f, L.Frogs * (1.f + 0.5f * R));
	const float Breeze = FMath::Clamp(1.f - (WindMs - 5.f) / 10.f, 0.25f, 1.f);
	L.Birds *= Breeze; L.Cicadas *= Breeze; L.Crickets *= Breeze; L.Frogs *= Breeze;
	return L;
}

float USailingWorldSynth::ShoreLifeSample(float Sr)
{
	FLife& L = Life;
	const float Dt = 1.f / Sr;
	if (!L.bSeeded)
	{
		// Each voice its own insects and birds: a cricket's chirp rate, where the calls start.
		L.bSeeded = true;
		L.CrkPeriod = 0.5f + 0.25f * FMath::Abs(Noise());
		L.CrkT2 = L.CrkPeriod * FMath::Abs(Noise());
		L.CicSwell = FMath::Abs(Noise());
		L.BirdWait = 0.3f + 2.f * FMath::Abs(Noise());
		L.FrogWait = 0.2f + FMath::Abs(Noise());
	}
	const float K = 0.0002f;   // the weights move over about 0.1 s
	L.SBirds += (Birds.load() - L.SBirds) * K;
	L.SCicadas += (Cicadas.load() - L.SCicadas) * K;
	L.SCrickets += (Crickets.load() - L.SCrickets) * K;
	L.SFrogs += (Frogs.load() - L.SFrogs) * K;
	float Out = 0.f;

	// Cicadas: a buzz of noise near 5 kHz pulsed at about 210 Hz, swelling and fading over nine seconds.
	if (L.SCicadas > 1e-3f)
	{
		L.CicAm += 210.f * Dt; L.CicAm -= FMath::FloorToFloat(L.CicAm);
		L.CicSwell += Dt / 9.f; L.CicSwell -= FMath::FloorToFloat(L.CicSwell);
		const float High = Noise() - L.CicLow - 0.5f * L.CicBand;   // band-pass, f = 2 sin(pi 5000 / 48000)
		L.CicBand += 0.64f * High; L.CicLow += 0.64f * L.CicBand;
		const float Am = FMath::Square(0.5f + 0.5f * FMath::Sin(2.f * PI * L.CicAm));
		const float Swell = 0.3f + 0.7f * (0.5f - 0.5f * FMath::Cos(2.f * PI * L.CicSwell));
		Out += L.CicBand * Am * Swell * 0.22f * L.SCicadas;
	}
	// Crickets: two field crickets, each a chirp of four 33 ms pulses of a 4.2-4.6 kHz tone every half second or so.
	if (L.SCrickets > 1e-3f)
	{
		auto Chirp = [](float T)
		{
			if (T >= 4.f * 0.033f) return 0.f;
			const float F = FMath::Fmod(T, 0.033f) / 0.033f;
			return F < 0.6f ? FMath::Sin(PI * F / 0.6f) : 0.f;
		};
		L.CrkT += Dt; if (L.CrkT >= L.CrkPeriod) L.CrkT -= L.CrkPeriod;
		L.CrkT2 += Dt; if (L.CrkT2 >= L.CrkPeriod * 1.17f) L.CrkT2 -= L.CrkPeriod * 1.17f;
		L.CrkPhase += 4600.f * Dt; L.CrkPhase -= FMath::FloorToFloat(L.CrkPhase);
		L.CrkPhase2 += 4200.f * Dt; L.CrkPhase2 -= FMath::FloorToFloat(L.CrkPhase2);
		Out += (FMath::Sin(2.f * PI * L.CrkPhase) * Chirp(L.CrkT) + 0.7f * FMath::Sin(2.f * PI * L.CrkPhase2) * Chirp(L.CrkT2)) * 0.12f * L.SCrickets;
	}
	// Frogs: a chorus frog's rising "crreek", like a thumb run along a comb: pulses quickening over 0.6 s, again and again.
	if (L.SFrogs > 1e-3f)
	{
		if (L.FrogT <= 0.f)
		{
			L.FrogWait -= Dt * (0.3f + L.SFrogs);
			if (L.FrogWait <= 0.f) { L.FrogT = Dt; L.FrogPulse = 0.f; }
		}
		else
		{
			const float Dur = 0.6f;
			L.FrogT += Dt;
			const float U = L.FrogT / Dur;
			L.FrogPulse += (16.f + 14.f * U) * Dt;
			L.FrogPhase += (2500.f + 500.f * U) * Dt; L.FrogPhase -= FMath::FloorToFloat(L.FrogPhase);
			const float Pulse = FMath::Pow(FMath::Max(0.f, FMath::Sin(PI * (L.FrogPulse - FMath::FloorToFloat(L.FrogPulse)))), 4.f);
			const float A = 2.f * PI * L.FrogPhase;
			Out += (FMath::Sin(A) + 0.4f * FMath::Sin(2.f * A)) * Pulse * FMath::Sin(PI * FMath::Min(U, 1.f)) * 0.12f * L.SFrogs;
			if (L.FrogT >= Dur) { L.FrogT = 0.f; L.FrogWait = 0.5f + 1.5f * FMath::Abs(Noise()); }
		}
	}
	// Songbirds: phrases of three to seven swept notes (2-6 kHz, 60-150 ms) with short gaps, a few seconds apart.
	if (L.SBirds > 1e-3f)
	{
		auto NewNote = [this, &L]()
		{
			L.BirdT = 0.f;
			L.BirdDur = 0.06f + 0.09f * FMath::Abs(Noise());
			L.BirdF0 = 2200.f + 3500.f * FMath::Abs(Noise());
			L.BirdF1 = FMath::Clamp(L.BirdF0 * (0.65f + 0.7f * FMath::Abs(Noise())), 1800.f, 7000.f);
		};
		if (L.BirdNotes == 0)
		{
			L.BirdWait -= Dt;
			if (L.BirdWait <= 0.f) { L.BirdNotes = 3 + int32(FMath::Abs(Noise()) * 4.99f); L.BirdGap = 0.f; NewNote(); }
		}
		else if (L.BirdGap > 0.f)
		{
			L.BirdGap -= Dt;
			if (L.BirdGap <= 0.f) NewNote();
		}
		else
		{
			L.BirdT += Dt;
			const float U = FMath::Min(L.BirdT / L.BirdDur, 1.f);
			L.BirdPhase += FMath::Lerp(L.BirdF0, L.BirdF1, U) * Dt; L.BirdPhase -= FMath::FloorToFloat(L.BirdPhase);
			Out += FMath::Sin(2.f * PI * L.BirdPhase) * FMath::Sin(PI * U) * 0.16f * L.SBirds;
			if (U >= 1.f)
			{
				if (--L.BirdNotes > 0) L.BirdGap = 0.03f + 0.06f * FMath::Abs(Noise());
				else L.BirdWait = (1.5f + 3.5f * FMath::Abs(Noise())) / FMath::Max(L.SBirds, 0.25f);
			}
		}
	}
	return Out;
}

USailingSoundscape::USailingSoundscape()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.25f;
}

void USailingSoundscape::BeginPlay()
{
	Super::BeginPlay();
	AActor* Owner = GetOwner();
	if (!Owner || !Owner->GetRootComponent()) return;
	for (int32 K = 0; K < 4; ++K)
	{
		USceneComponent* At = NewObject<USceneComponent>(Owner);
		At->SetupAttachment(Owner->GetRootComponent());
		At->SetUsingAbsoluteLocation(true);
		At->SetUsingAbsoluteRotation(true);
		At->RegisterComponent();
		USailingWorldSynth* Voice = nullptr;
		// Heard across a cove (natural falloff to 600 m, none inside 30 m), dulled by distance.
		SailingSound::MakeWorldSound(Owner, At, EWorldSound::ShoreLife, 600.f, Voice);
		if (Voice) Voice->Level = 0.f;
		Points.Add(At);
		Voices.Add(Voice);
	}
}

void USailingSoundscape::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	static SailingArgs::FCachedFlag NoShoreLife(TEXT("SailingNoShoreLife"));
	const ASailingGameMode* GM = GetWorld() ? GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	const bool bOn = GM && GM->GetLake().IsLoaded() && !GM->GetLake().IsCoast() && !NoShoreLife.Get();
	if (!bOn)
	{
		for (USailingWorldSynth* V : Voices) if (V) V->Level = 0.f;
		return;
	}
	const FLakeData& Lake = GM->GetLake();
	double Elevation = 0.0, Azimuth = 0.0;
	ASailingEnvironment::SunPosition(GM->GetDrawnHour(), GM->GetDayOfYear(), Lake.Latitude, Lake.Longitude, GM->GetUtcOffsetHours(), Elevation, Azimuth);
	FVector Listener = GetOwner()->GetActorLocation();
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController(); PC && PC->PlayerCameraManager) Listener = PC->PlayerCameraManager->GetCameraLocation();
	const FVector2D Here = SailingFrame::ToMap(GetWorld(), Listener);
	const float WindMs = float(GM->GetWind().MeanSpeedAtHeight(10.0));
	const SailingSound::FShoreLife Who = SailingSound::ShoreLifeFor(Elevation, Azimuth < 180.0, GM->GetDayOfYear(), float(GM->GetWeatherState().Rain), WindMs);

	// Place the four voices on the nearest shore toward the north-east, south-east, south-west and north-west: marching
	// out in 15 m steps to 900 m until the ground is half a metre above the pool, then 25 m inland, in the trees.
	// Again every 3 s once she has moved 30 m.
	const double Now = GetWorld()->GetTimeSeconds();
	const bool bPlace = Now >= NextPlace && FVector2D::Distance(Here, PlacedFrom) > 30.0;
	if (bPlace)
	{
		NextPlace = Now + 3.0;
		PlacedFrom = Here;
	}
	for (int32 K = 0; K < Voices.Num(); ++K)
	{
		USailingWorldSynth* V = Voices[K];
		if (!V || !Points[K]) continue;
		if (bPlace)
		{
			const double B = FMath::DegreesToRadians(45.0 + 90.0 * K);
			const FVector2D D(FMath::Cos(B), FMath::Sin(B));
			double Found = -1.0;
			for (double R = 15.0; R <= 900.0; R += 15.0)
			{
				const FVector2D P = Here + D * R;
				if (Lake.Terrain.HasGroundAt(P.X, P.Y) && Lake.Terrain.HeightAt(P.X, P.Y) > 0.5) { Found = R + 25.0; break; }
			}
			if (Found > 0.0)
			{
				const FVector2D P = Here + D * Found;
				Points[K]->SetWorldLocation(SailingFrame::ToWorld(GetWorld(), P.X, P.Y, Lake.Terrain.HeightAt(P.X, P.Y) + 2.0));
			}
			V->Level = Found > 0.0 ? 1.f : 0.f;   // open water that way: nothing calling from it
		}
		V->Birds = Who.Birds; V->Cicadas = Who.Cicadas; V->Crickets = Who.Crickets; V->Frogs = Who.Frogs;
	}
}
