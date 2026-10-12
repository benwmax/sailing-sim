#include "SailingAudio.h"

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

	for (int32 I = 0; I < NumSamples; ++I)
	{
		const float W = Smooth(SWind, TWind, Rate), Lf = Smooth(SLuff, TLuff, Rate), Tl = Smooth(STell, TTell, Rate);
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
		Mix += WindBand.Process(PinkN, FMath::Min(0.9f, 2.f * PI * (220.f + 55.f * W) / Sr), 0.7f) * 0.35f * WindLevel * WindLevel * Gust;
		Mix += Whistle.Process(WhiteN, FMath::Min(0.9f, 2.f * PI * (850.f + 70.f * W) / Sr), 0.06f) * 0.012f * FMath::Pow(WindLevel, 3.f) * Gust;

		// Luffing / flogging: slapping bursts at a rate that rises with the wind.
		FlapPhase += (3.5f + 0.9f * W) / Sr;
		if (FlapPhase > 1.f) FlapPhase -= 1.f;
		const float Flap = FMath::Pow(0.5f + 0.5f * FMath::Sin(2.f * PI * FlapPhase), 8.f);
		const float FlogNoise = WhiteN - FlogLow.Low(WhiteN, 0.05f);
		Mix += FlogHigh.Process(FlogNoise * Flap, 0.25f, 0.5f) * 0.9f * Lf * FMath::Clamp(W / 8.f, 0.f, 2.f);

		// Telltales: a light, fast rattle.
		TellPhase += 23.f / Sr;
		if (TellPhase > 1.f) TellPhase -= 1.f;
		Mix += TellBand.Process(WhiteN * (TellPhase < 0.3f ? 1.f : 0.2f), 0.45f, 0.4f) * 0.02f * Tl * FMath::Clamp(W / 8.f, 0.f, 1.5f);

		// Water past the hull: brighter and louder with speed; a deep rumble as she nears hull speed.
		const float WaterCut = FMath::Min(0.9f, 2.f * PI * (120.f + 140.f * Sp) / Sr);
		Mix += WaterLow.Low(PinkN, WaterCut) * 0.5f * FMath::Pow(FMath::Clamp(Sp / 3.f, 0.f, 1.5f), 1.5f);
		const float Rumble = FMath::Clamp((Hr - 0.85f) / 0.2f, 0.f, 1.f);
		Mix += RumbleLow.Low(BrownN, 2.f * PI * 90.f / Sr) * 1.2f * Rumble;

		// Bow wave slaps when the bow meets a wave.
		if (Noise() > 1.f - 0.0004f * Sl) SlapEnv = 1.f;
		SlapEnv *= 0.9993f;
		Mix += SlapBand.Process(WhiteN, 0.12f, 0.7f) * 0.35f * SlapEnv * Sl;

		// Winch clicks while trimming in; the whir of a sheet running out while easing.
		if (Tr > 0.05f)
		{
			ClickPhase += (8.f + 14.f * Tr) / Sr;
			if (ClickPhase > 1.f) { ClickPhase -= 1.f; ClickEnv = 1.f; }
		}
		ClickEnv *= 0.992f;
		Mix += ClickBand.Process(WhiteN * ClickEnv, 0.38f, 0.15f) * 0.5f;
		Mix += ZipBand.Process(WhiteN, 0.15f, 0.3f) * 0.08f * FMath::Clamp(-Tr, 0.f, 1.f);

		// Rain: hiss on the water and drops on the deck.
		Mix += (WhiteN - RainHigh.Low(WhiteN, 0.08f)) * 0.06f * Rn;
		if (Noise() > 1.f - 0.004f * Rn) DropEnv = 1.f;
		DropEnv *= 0.99f;
		Mix += DropBand.Process(WhiteN * DropEnv, 0.5f, 0.3f) * 0.2f * Rn;

		// Thunder: a rolling low rumble, and a crack for a close strike.
		Mix += ThunderLow.Low(BrownN, 2.f * PI * 70.f / Sr) * 2.2f * Th;
		Mix += CrackBand.Process(WhiteN, 0.08f, 0.6f) * 0.8f * Cr;

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
