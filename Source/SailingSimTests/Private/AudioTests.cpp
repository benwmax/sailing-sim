#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundWave.h"
#include "SailingAudio.h"
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
	TestEqual(TEXT("On board = master x slider"), GroupGain(EGroup::Boat), 0.4f, 1e-5f);
	TestEqual(TEXT("Lake and shore = master x slider"), GroupGain(EGroup::World), 0.2f, 1e-5f);
	TestEqual(TEXT("Weather muted"), GroupGain(EGroup::Weather), 0.f, 1e-5f);
	TestEqual(TEXT("Signals at the master"), GroupGain(EGroup::Signals), 0.5f, 1e-5f);
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
