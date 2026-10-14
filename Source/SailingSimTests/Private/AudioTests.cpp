#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundWave.h"
#include "SailingAudio.h"

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
