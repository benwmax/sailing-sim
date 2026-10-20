#include "SailingAudio.h"
#include "Components/AudioComponent.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Kismet/GameplayStatics.h"
#include "SailingGameMode.h"

const TCHAR* SailingCueName(ESailingCue Cue)
{
	static const TCHAR* Names[] = { TEXT("Wind"), TEXT("GustRumble"), TEXT("SailFlog"), TEXT("Telltales"), TEXT("BowWave"), TEXT("HullSlap"), TEXT("Winch"),
		TEXT("SheetBlock"), TEXT("HalyardSlap"), TEXT("RainDeck"), TEXT("RainWater"), TEXT("SquallHiss"), TEXT("Thunder") };
	return Names[FMath::Clamp(int32(Cue), 0, int32(ESailingCue::Count) - 1)];
}

const TCHAR* WorldSoundName(EWorldSound Kind)
{
	static const TCHAR* Names[] = { TEXT("MarinaHalyards"), TEXT("Gulls"), TEXT("Outboard"), TEXT("Diesel") };
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

		float Mix = 0.f;

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
		Mix += ClickBand.Process(WhiteN * ClickEnv, 0.38f, 0.15f) * 0.5f * MWinch;
		Mix += ZipBand.Process(WhiteN, 0.15f, 0.3f) * 0.08f * FMath::Clamp(-Tr, 0.f, 1.f) * MSheet;
		// The sheet through its block: a squeak pitched by how fast it runs.
		SheetPhase += (600.f + 900.f * FMath::Abs(Tr)) / Sr;
		SheetPhase -= FMath::FloorToFloat(SheetPhase);
		Mix += SheetBand.Process(FMath::Sin(2.f * PI * SheetPhase) * (0.5f + 0.5f * WhiteN), 0.2f, 0.2f) * 0.02f * FMath::Clamp(FMath::Abs(Tr) - 0.1f, 0.f, 1.f) * MSheet;

		// Rain: hiss on the water and drops on the deck.
		// Rain: the hiss on the water around and the drops on the deck and sails, as separate layers.
		Mix += (WhiteN - RainHigh.Low(WhiteN, 0.08f)) * 0.06f * FMath::Max(Rw, Rn * 0.0f) * MWater;
		if (Noise() > 1.f - 0.004f * Rd) DropEnv = 1.f;
		DropEnv *= 0.99f;
		Mix += DropBand.Process(WhiteN * DropEnv, 0.5f, 0.3f) * 0.2f * Rd * MDeck;
		// A squall coming across the water: a broad hiss, the rain and the wind's roar, rising as it nears.
		Mix += (SquallBand.Process(WhiteN, 2.f * PI * 3500.f / Sr, 0.9f) * 0.05f + SquallBand2.Process(PinkN, 2.f * PI * 600.f / Sr, 0.8f) * 0.08f) * Sq * Sq * MSquall;

		// Thunder: a rolling low rumble, and a crack for a close strike.
		Mix += ThunderLow.Low(BrownN, 2.f * PI * 70.f / Sr) * 2.2f * Th * MThunder;
		Mix += CrackBand.Process(WhiteN, 0.08f, 0.6f) * 0.8f * Cr * MThunder;

		// A whistle: a reedy tone (odd and even harmonics) with a little vibrato, fading in and out over 30 ms.
		const float Hn = Smooth(SHorn, THorn, Rate * 1.6f);
		if (Hn > 1e-4f)
		{
			HornVib += 5.5f / Sr;
			HornPhase += HornFreq * (1.f + 0.004f * FMath::Sin(2.f * PI * HornVib)) / Sr;
			HornPhase -= FMath::FloorToFloat(HornPhase);
			const float A = 2.f * PI * HornPhase;
			Mix += (FMath::Sin(A) + 0.5f * FMath::Sin(2.f * A) + 0.33f * FMath::Sin(3.f * A) + 0.18f * FMath::Sin(5.f * A)) * 0.35f * Hn;
		}

		const float Sample = FMath::Clamp(FMath::Tanh(Mix * Vol * 1.4f), -1.f, 1.f);
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

int32 USailingWorldSynth::OnGeneratePCMAudio(TArray<uint8>& OutAudio, int32 NumSamples)
{
	OutAudio.SetNumUninitialized(NumSamples * 2);
	int16* Out = reinterpret_cast<int16*>(OutAudio.GetData());
	const float Sr = 48000.f;
	if (Rng == 0x9E3779B9u) Rng ^= Seed * 2654435761u;
	const float TLevel = Level.load(), TRate = Rate.load();
	for (int32 I = 0; I < NumSamples; ++I)
	{
		SLevel += (TLevel - SLevel) * 0.0005f;
		SRate += (TRate - SRate) * 0.0005f;
		float Mix = 0.f;
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
		default: break;
		}
		Out[I] = bMuted.load() ? int16(0) : int16(FMath::Clamp(FMath::Tanh(Mix * SLevel * 1.5f), -1.f, 1.f) * 30000.f);
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
	A->bAllowSpatialization = true;
	A->bOverrideAttenuation = true;
	A->AttenuationOverrides.bAttenuate = true;
	A->AttenuationOverrides.bSpatialize = true;
	A->AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
	A->AttenuationOverrides.AttenuationShapeExtents = FVector(FalloffM * 0.05f * 100.f);
	A->AttenuationOverrides.FalloffDistance = FalloffM * 100.f;
	A->AttenuationOverrides.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
	A->AttenuationOverrides.bAttenuateWithLPF = true;
	A->AttenuationOverrides.LPFRadiusMin = FalloffM * 10.f;
	A->AttenuationOverrides.LPFRadiusMax = FalloffM * 100.f;
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
		A->bAllowSpatialization = true;
		A->bOverrideAttenuation = true;
		A->AttenuationOverrides.bAttenuate = true;
		A->AttenuationOverrides.bSpatialize = true;
		A->AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
		A->AttenuationOverrides.AttenuationShapeExtents = FVector(FalloffM * 0.05f * 100.f);
		A->AttenuationOverrides.FalloffDistance = FalloffM * 100.f;
		A->AttenuationOverrides.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
		A->AttenuationOverrides.bAttenuateWithLPF = true;
		A->AttenuationOverrides.LPFRadiusMin = FalloffM * 10.f;
		A->AttenuationOverrides.LPFRadiusMax = FalloffM * 100.f;
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
	const float Level = Synth->Level.load(), Rate = Synth->Rate.load();
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
