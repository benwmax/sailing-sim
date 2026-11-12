#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundWave.h"
#include "SailingAudio.h"
#include "BenchRunner.h"
#include "SailingSettings.h"
#include "SoundCaptions.h"

namespace
{
	constexpr EAutomationTestFlags AudioFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
}

/**
 * Graphics G7: the sample pack (Inputs/audio) is imported and every file has a layer: each manifest entry is one of the
 * boat's loops or one-shots or a world source's recording, loads from /Game/Audio/Pack, and loops exactly when the
 * manifest says so. The crossfade keeps equal power between neighbouring bands.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSamplePackTest, "SailingSim.Audio.SamplePack", AudioFlags)
bool FSailingSamplePackTest::RunTest(const FString& Parameters)
{
	using namespace SailingSound;
	TSet<FString> Mapped;
	for (const FPackLoop& L : PackLoops()) Mapped.Add(L.Asset);
	for (uint8 K = 0; K < uint8(EPackShot::Count); ++K) for (const FString& A : PackShots(EPackShot(K))) Mapped.Add(A);
	// The world sources (USailingWorldSamples::Init).
	for (const TCHAR* A : { TEXT("Rigging/marina_halyards_distant_loop"), TEXT("Engines/outboard_idle_loop"), TEXT("Engines/outboard_lowspeed_loop"),
		TEXT("Engines/outboard_running_loop"), TEXT("Birds/gull_call_01"), TEXT("Birds/gull_call_02"), TEXT("Birds/gull_call_03"), TEXT("Birds/laughing_gull_01") }) Mapped.Add(A);

	FString Text;
	const FString Manifest = FPaths::ProjectDir() / TEXT("Inputs/audio/manifest.json");
	if (!TestTrue(TEXT("Reads the manifest"), FFileHelper::LoadFileToString(Text, *Manifest))) return false;
	TArray<TSharedPtr<FJsonValue>> Entries;
	if (!TestTrue(TEXT("Parses the manifest"), FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Entries))) return false;
	for (const TSharedPtr<FJsonValue>& V : Entries)
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		const FString File = FPaths::ChangeExtension(O->GetStringField(TEXT("file")), TEXT(""));
		TestTrue(FString::Printf(TEXT("%s has a layer in the game"), *File), Mapped.Contains(File));
		USoundWave* Wave = Cast<USoundWave>(LoadPack(File));
		if (TestNotNull(FString::Printf(TEXT("%s is imported"), *File), Wave))
		{
			TestEqual(FString::Printf(TEXT("%s loops as the manifest says"), *File), Wave->bLooping, O->GetBoolField(TEXT("loop")));
		}
	}
	TestEqual(TEXT("Every mapped file is in the manifest"), Mapped.Num(), Entries.Num());

	const float C[] = { 3.f, 7.f, 11.f };
	for (float X = 0.f; X <= 14.f; X += 0.5f)
	{
		float W[3];
		Crossfade(X, C, 3, W);
		TestTrue(FString::Printf(TEXT("Equal power at %.1f"), X), FMath::IsNearlyEqual(W[0] * W[0] + W[1] * W[1] + W[2] * W[2], 1.f, 1e-3f));
	}
	return true;
}

/** Slice sound pass: a dinghy trims by hand through blocks, so the Sunfish, the ILCA and the Hobie never click a winch. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSheetWinchesTest, "SailingSim.Audio.SheetWinches", AudioFlags)
bool FSailingSheetWinchesTest::RunTest(const FString& Parameters)
{
	using Sailing::EBoatType;
	TestFalse(TEXT("Sunfish has no winches"), SailingSound::HasSheetWinches(EBoatType::Sunfish));
	TestFalse(TEXT("ILCA has no winches"), SailingSound::HasSheetWinches(EBoatType::ILCA7));
	TestFalse(TEXT("Hobie has no winches"), SailingSound::HasSheetWinches(EBoatType::Hobie16));
	TestTrue(TEXT("J/22 has winches"), SailingSound::HasSheetWinches(EBoatType::J22));
	TestTrue(TEXT("Catalina 22 has winches"), SailingSound::HasSheetWinches(EBoatType::Catalina22));
	return true;
}

/** Slice sound pass: Settings > Audio's groups. Each group's gain is the master times its own slider; rain, the squall and
 *  thunder are weather, every other boat cue is on board. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingAudioMixTest, "SailingSim.Audio.Mix", AudioFlags)
bool FSailingAudioMixTest::RunTest(const FString& Parameters)
{
	using namespace SailingSound;
	USailingSettings* S = USailingSettings::Get();
	const float Keep[] = { S->Volume, S->VolumeBoat, S->VolumeWorld, S->VolumeWeather, S->VolumeSignals };
	const bool bKeepMono = S->bMonoAudio;
	S->Volume = 0.5f; S->VolumeBoat = 0.8f; S->VolumeWorld = 0.4f; S->VolumeWeather = 0.f; S->VolumeSignals = 1.f; S->bMonoAudio = true;
	UpdateMix();
	// Every voice carries the make-up gain (4 dB unless -SailingMakeupDb= says otherwise).
	const float Up = FMath::Pow(10.f, MakeupGainDb() / 20.f);
	FString Given;
	if (!FParse::Value(SailingArgs::Dev(), TEXT("SailingMakeupDb="), Given)) TestEqual(TEXT("Make-up gain is 4 dB by default"), MakeupGainDb(), 4.f, 1e-5f);
	TestEqual(TEXT("Master carries the make-up"), MasterGain(), 0.5f * Up, 1e-5f);
	TestEqual(TEXT("On board = master x slider"), GroupGain(EGroup::Boat), 0.4f * Up, 1e-5f);
	TestEqual(TEXT("Lake and shore = master x slider"), GroupGain(EGroup::World), 0.2f * Up, 1e-5f);
	TestEqual(TEXT("Weather muted"), GroupGain(EGroup::Weather), 0.f, 1e-5f);
	TestEqual(TEXT("Signals at the master"), GroupGain(EGroup::Signals), 0.5f * Up, 1e-5f);
	TestEqual(TEXT("Share leaves the master out"), GroupShare(EGroup::Boat), 0.8f, 1e-5f);
	TestTrue(TEXT("Mono read"), IsMono());
	TestTrue(TEXT("Thunder is weather"), CueGroup(ESailingCue::Thunder) == EGroup::Weather);
	TestTrue(TEXT("Rain on deck is weather"), CueGroup(ESailingCue::RainDeck) == EGroup::Weather);
	TestTrue(TEXT("The winch is on board"), CueGroup(ESailingCue::Winch) == EGroup::Boat);
	TestTrue(TEXT("Wind is on board"), CueGroup(ESailingCue::Wind) == EGroup::Boat);
	S->Volume = Keep[0]; S->VolumeBoat = Keep[1]; S->VolumeWorld = Keep[2]; S->VolumeWeather = Keep[3]; S->VolumeSignals = Keep[4]; S->bMonoAudio = bKeepMono;
	UpdateMix();
	return true;
}

/** Slice sound pass: sound captions name where a sound came from in a sailor's words, from the boat's heading. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingCaptionDirectionTest, "SailingSim.Audio.CaptionDirection", AudioFlags)
bool FSailingCaptionDirectionTest::RunTest(const FString& Parameters)
{
	using namespace SailingSound;
	const FVector2D Here(0.0, 0.0);
	// Heading north (0 deg): a source to the east (+Y) is abeam to starboard, one to the north-west off the port bow.
	TestEqual(TEXT("East of a north heading"), FString(RelativeDirection(RelativeBearingDeg(Here, 0.0, FVector2D(0.0, 100.0)))), FString(TEXT("abeam to starboard")));
	TestEqual(TEXT("North-west of a north heading"), FString(RelativeDirection(RelativeBearingDeg(Here, 0.0, FVector2D(100.0, -100.0)))), FString(TEXT("off the port bow")));
	TestEqual(TEXT("Dead ahead"), FString(RelativeDirection(RelativeBearingDeg(Here, 90.0, FVector2D(0.0, 500.0)))), FString(TEXT("ahead")));
	TestEqual(TEXT("Astern of an east heading"), FString(RelativeDirection(RelativeBearingDeg(Here, 90.0, FVector2D(0.0, -500.0)))), FString(TEXT("astern")));
	TestEqual(TEXT("South-east of a north heading"), FString(RelativeDirection(RelativeBearingDeg(Here, 0.0, FVector2D(-100.0, 100.0)))), FString(TEXT("off the starboard quarter")));
	TestEqual(TEXT("Wraps past 180"), FString(RelativeDirection(-230.0)), FString(TEXT("off the starboard quarter")));
	return true;
}

/**
 * Slice sound pass: placed sounds. A direction-only source (wind, thunder) sits at the given distance toward its bearing
 * in the map frame; the settings carry the inner radius and the blend toward both ears; the horn and thunder voices
 * are silent at rest, the horn sounds when blown, and a close strike's crack is heard before its rumble rises.
 */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingPlacedSoundsTest, "SailingSim.Audio.PlacedSounds", AudioFlags)
bool FSailingPlacedSoundsTest::RunTest(const FString& Parameters)
{
	using namespace SailingSound;
	const FVector North = AroundListener(FVector(100.0, 200.0, 300.0), 10.0, 0.0, 50.f, 1.f);
	TestTrue(TEXT("50 m north, 1 m up"), North.Equals(FVector(5100.0, 200.0, 400.0), 0.01));
	const FVector East = AroundListener(FVector::ZeroVector, 0.0, 3.0, 5.f, 0.f);
	TestTrue(TEXT("5 m east"), East.Equals(FVector(0.0, 500.0, 0.0), 0.01));
	TestTrue(TEXT("No direction: north"), AroundListener(FVector::ZeroVector, 0.0, 0.0, 1.f, 0.f).Equals(FVector(100.0, 0.0, 0.0), 0.01));

	const FSoundAttenuationSettings Wind = SpatialSettings(100.f, 40.f, 10.f, 1.f);
	TestEqual(TEXT("Inner radius"), double(Wind.AttenuationShapeExtents.X), 4000.0, 0.01);
	TestEqual(TEXT("Falloff"), double(Wind.FalloffDistance), 10000.0, 0.01);
	TestEqual(TEXT("Blend from 10 m"), double(Wind.NonSpatializedRadiusStart), 1000.0, 0.01);
	TestEqual(TEXT("Both ears at 1 m"), double(Wind.NonSpatializedRadiusEnd), 100.0, 0.01);
	TestEqual(TEXT("Placed unless mono"), bool(Wind.bSpatialize), !IsMono());
	TestEqual(TEXT("Default inner radius: a twentieth"), double(SpatialSettings(3000.f).AttenuationShapeExtents.X), 15000.0, 0.01);

	auto Rms = [](USoundWaveProcedural* W, int32 N)
	{
		TArray<uint8> Buf;
		double Sum = 0.0;
		for (int32 Block = 0; Block < 4; ++Block)
		{
			W->OnGeneratePCMAudio(Buf, N);
			const int16* S = reinterpret_cast<const int16*>(Buf.GetData());
			for (int32 I = 0; I < N; ++I) Sum += double(S[I]) * S[I];
		}
		return FMath::Sqrt(Sum / (4.0 * N)) / 32768.0;
	};
	auto Voice = [](EWorldSound Kind, float Level, float Rate)
	{
		USailingWorldSynth* W = NewObject<USailingWorldSynth>();
		W->Kind = Kind; W->Level = Level; W->Rate = Rate; W->Hz = 110.f;
		return W;
	};
	// The mix's groups at full for the duration (restored after).
	USailingSettings* S = USailingSettings::Get();
	const float Keep[] = { S->Volume, S->VolumeWeather, S->VolumeSignals };
	S->Volume = 1.f; S->VolumeWeather = 1.f; S->VolumeSignals = 1.f;
	UpdateMix();
	TestTrue(TEXT("A horn at rest is silent"), Rms(Voice(EWorldSound::Horn, 0.f, 0.f), 12000) < 1e-4);
	TestTrue(TEXT("A ship's whistle sounds"), Rms(Voice(EWorldSound::Horn, 1.f, 0.f), 12000) > 0.01);
	TestTrue(TEXT("No thunder, no sound"), Rms(Voice(EWorldSound::Thunder, 0.f, 0.f), 12000) < 1e-4);
	TestTrue(TEXT("A close strike's crack leads its rumble"), Rms(Voice(EWorldSound::Thunder, 0.f, 1.f), 12000) > 0.01);
	TestTrue(TEXT("The rumble"), Rms(Voice(EWorldSound::Thunder, 1.f, 0.f), 24000) > 0.003);
	S->VolumeSignals = 0.f;
	UpdateMix();
	TestTrue(TEXT("Horns and voices at 0: the whistle is silent"), Rms(Voice(EWorldSound::Horn, 1.f, 0.f), 12000) < 1e-4);
	S->Volume = Keep[0]; S->VolumeWeather = Keep[1]; S->VolumeSignals = Keep[2];
	UpdateMix();
	return true;
}

/** Slice sound pass: the lake's shore life follows the sun and the season, the rain and the wind. */
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingShoreLifeTest, "SailingSim.Audio.ShoreLife", AudioFlags)
bool FSailingShoreLifeTest::RunTest(const FString& Parameters)
{
	using namespace SailingSound;
	const FShoreLife MayDawn = ShoreLifeFor(2.0, true, 130, 0.f, 2.f);
	TestTrue(TEXT("May dawn: the birds' chorus"), MayDawn.Birds > 0.8f);
	TestEqual(TEXT("May dawn: no cicadas"), MayDawn.Cicadas, 0.f);
	const FShoreLife JulyNoon = ShoreLifeFor(70.0, false, 200, 0.f, 2.f);
	TestEqual(TEXT("July noon: cicadas"), JulyNoon.Cicadas, 1.f);
	TestTrue(TEXT("July noon: a thinner birdsong than dawn"), JulyNoon.Birds > 0.2f && JulyNoon.Birds < MayDawn.Birds);
	TestEqual(TEXT("July noon: no crickets"), JulyNoon.Crickets, 0.f);
	TestEqual(TEXT("July noon: no frogs"), JulyNoon.Frogs, 0.f);
	const FShoreLife JulyNight = ShoreLifeFor(-20.0, false, 200, 0.f, 2.f);
	TestEqual(TEXT("July night: crickets"), JulyNight.Crickets, 1.f);
	TestEqual(TEXT("July night: frogs"), JulyNight.Frogs, 1.f);
	TestEqual(TEXT("July night: no birds"), JulyNight.Birds, 0.f);
	TestEqual(TEXT("July night: no cicadas"), JulyNight.Cicadas, 0.f);
	const FShoreLife JanNight = ShoreLifeFor(-20.0, false, 15, 0.f, 2.f);
	TestEqual(TEXT("January night: no crickets"), JanNight.Crickets, 0.f);
	TestEqual(TEXT("January night: no frogs"), JanNight.Frogs, 0.f);
	const FShoreLife WetNight = ShoreLifeFor(-20.0, false, 120, 1.f, 2.f);
	const FShoreLife DryNight = ShoreLifeFor(-20.0, false, 120, 0.f, 2.f);
	TestTrue(TEXT("Rain: the frogs at least as loud"), WetNight.Frogs >= DryNight.Frogs && DryNight.Frogs > 0.f);
	TestTrue(TEXT("Rain: fewer crickets"), WetNight.Crickets < DryNight.Crickets);
	const FShoreLife Windy = ShoreLifeFor(-20.0, false, 200, 0.f, 15.f);
	TestEqual(TEXT("A strong breeze thins the chorus"), Windy.Crickets, 0.25f, 1e-4f);

	auto Rms = [](USoundWaveProcedural* W, int32 N)
	{
		TArray<uint8> Buf;
		double Sum = 0.0;
		for (int32 Block = 0; Block < 8; ++Block)
		{
			W->OnGeneratePCMAudio(Buf, N);
			const int16* S = reinterpret_cast<const int16*>(Buf.GetData());
			for (int32 I = 0; I < N; ++I) Sum += double(S[I]) * S[I];
		}
		return FMath::Sqrt(Sum / (8.0 * N)) / 32768.0;
	};
	USailingSettings* S = USailingSettings::Get();
	const float Keep[] = { S->Volume, S->VolumeWorld };
	S->Volume = 1.f; S->VolumeWorld = 1.f;
	UpdateMix();
	for (int32 K = 0; K < 5; ++K)
	{
		USailingWorldSynth* W = NewObject<USailingWorldSynth>();
		W->Kind = EWorldSound::ShoreLife;
		W->Level = K == 4 ? 0.f : 1.f;
		W->Birds = K == 0 ? 1.f : 0.f; W->Cicadas = K == 1 ? 1.f : 0.f; W->Crickets = K == 2 ? 1.f : 0.f; W->Frogs = K == 3 ? 1.f : 0.f;
		const double R = Rms(W, 48000);
		static const TCHAR* Who[] = { TEXT("Birds"), TEXT("Cicadas"), TEXT("Crickets"), TEXT("Frogs"), TEXT("Nothing at level 0") };
		AddInfo(FString::Printf(TEXT("%s: %.4f"), Who[K], R));
		if (K < 4) TestTrue(FString::Printf(TEXT("%s are heard"), Who[K]), R > 0.002);
		else TestTrue(Who[K], R < 1e-4);
	}
	S->Volume = Keep[0]; S->VolumeWorld = Keep[1];
	UpdateMix();
	return true;
}
