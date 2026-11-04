#include "Feedback.h"
#include "SessionLog.h"
#include "CrashReports.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformOutputDevices.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Dom/JsonObject.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

void FFeedbackRecorder::Offer(const FFeedbackSample& Sample)
{
	if (Samples.Num() && Sample.T < Samples.Last().T) Samples.Reset();
	if (Samples.Num() && Sample.T - Samples.Last().T < IntervalSeconds) return;
	Samples.Add(Sample);
	int32 Drop = 0;
	while (Drop < Samples.Num() && Sample.T - Samples[Drop].T > KeepSeconds) ++Drop;
	if (Drop) Samples.RemoveAt(0, Drop);
}

FString FFeedbackRecorder::ToJson() const
{
	FString Out = FString::Printf(TEXT("{\"interval_s\": %.1f, \"samples\": ["), IntervalSeconds);
	for (int32 I = 0; I < Samples.Num(); ++I)
	{
		const FFeedbackSample& S = Samples[I];
		Out += FString::Printf(TEXT("%s\n{\"t_s\": %.1f, \"north_m\": %.1f, \"east_m\": %.1f, \"heading_deg\": %.1f, \"speed_kn\": %.2f, \"heel_deg\": %.1f, \"twa_deg\": %.1f, \"tws_kn\": %.1f, \"fps\": %.0f}"),
			I ? TEXT(",") : TEXT(""), S.T, S.North, S.East, S.HeadingDeg, S.SpeedKn, S.HeelDeg, S.TwaDeg, S.TwsKn, S.Fps);
	}
	return Out + TEXT("\n]}\n");
}

double FFeedbackRecorder::MeanFps() const
{
	double Sum = 0.0;
	for (const FFeedbackSample& S : Samples) Sum += S.Fps;
	return Samples.Num() ? Sum / Samples.Num() : 0.0;
}

const TCHAR* SailFeedback::KindId(EFeedbackKind Kind)
{
	return Kind == EFeedbackKind::Idea ? TEXT("idea") : TEXT("bug");
}

FString SailFeedback::ResultLine(bool bSent)
{
	return bSent ? FString(TEXT("Sent. Thank you!")) : FString(TEXT("Saved on this computer (this build can't send reports)."));
}

bool SailFeedback::FSentryDsn::Parse(const FString& Dsn)
{
	// scheme://publickey[:secret]@host[:port]/[path/]project
	FString Rest;
	if (!Dsn.TrimStartAndEnd().Split(TEXT("://"), &Scheme, &Rest)) return false;
	FString Key, HostPath;
	if (!Rest.Split(TEXT("@"), &Key, &HostPath)) return false;
	Key.Split(TEXT(":"), &Key, nullptr);
	PublicKey = Key;
	FString Path;
	if (!HostPath.Split(TEXT("/"), &Host, &Path)) return false;
	FString Prefix;
	ProjectId = Path;
	if (Path.Split(TEXT("/"), &Prefix, &ProjectId, ESearchCase::CaseSensitive, ESearchDir::FromEnd)) Host += TEXT("/") + Prefix;
	ProjectId.TrimEndInline();
	return !Scheme.IsEmpty() && !PublicKey.IsEmpty() && !Host.IsEmpty() && !ProjectId.IsEmpty();
}

FString SailFeedback::FSentryDsn::EnvelopeUrl() const
{
	return FString::Printf(TEXT("%s://%s/api/%s/envelope/"), *Scheme, *Host, *ProjectId);
}

FString SailFeedback::FSentryDsn::AuthHeader() const
{
	return FString::Printf(TEXT("Sentry sentry_version=7, sentry_key=%s, sentry_client=sailingsim-feedback/1.0"), *PublicKey);
}

namespace SailFeedbackEnvelopeLocal
{
	FString JsonLine(const TSharedRef<FJsonObject>& O)
	{
		FString Out;
		const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> W = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
		FJsonSerializer::Serialize(O, W);
		return Out;
	}

	void Append(TArray<uint8>& Out, const FString& Text)
	{
		const FTCHARToUTF8 Utf8(*Text);
		Out.Append((const uint8*)Utf8.Get(), Utf8.Length());
	}

	/** One item: its header line (type, length and the extra fields), then the payload and a newline. */
	void Item(TArray<uint8>& Out, TSharedRef<FJsonObject> Header, const TArray<uint8>& Payload)
	{
		Header->SetNumberField(TEXT("length"), Payload.Num());
		Append(Out, JsonLine(Header) + TEXT("\n"));
		Out.Append(Payload);
		Append(Out, TEXT("\n"));
	}
}

TArray<uint8> SailFeedback::FeedbackEnvelope(const FString& EventId, double TimestampUnix, const FString& Message, const TMap<FString, FString>& Tags,
	const FString& Release, const FString& Environment, const TArray<FEnvelopeAttachment>& Attachments)
{
	using namespace SailFeedbackEnvelopeLocal;
	TArray<uint8> Out;
	const TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>();
	Head->SetStringField(TEXT("event_id"), EventId);
	Head->SetStringField(TEXT("sent_at"), FDateTime::FromUnixTimestamp(int64(TimestampUnix)).ToIso8601());
	Append(Out, JsonLine(Head) + TEXT("\n"));

	// The feedback event: the message in the feedback context, as the SDK's own sentry_capture_feedback sends it.
	const TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
	Event->SetStringField(TEXT("event_id"), EventId);
	Event->SetNumberField(TEXT("timestamp"), TimestampUnix);
	Event->SetStringField(TEXT("platform"), TEXT("native"));
	Event->SetStringField(TEXT("level"), TEXT("info"));
	if (!Release.IsEmpty()) Event->SetStringField(TEXT("release"), Release);
	if (!Environment.IsEmpty()) Event->SetStringField(TEXT("environment"), Environment);
	const TSharedRef<FJsonObject> TagObj = MakeShared<FJsonObject>();
	for (const TPair<FString, FString>& T : Tags) TagObj->SetStringField(T.Key, T.Value);
	Event->SetObjectField(TEXT("tags"), TagObj);
	const TSharedRef<FJsonObject> Fb = MakeShared<FJsonObject>();
	Fb->SetStringField(TEXT("message"), Message);
	const TSharedRef<FJsonObject> Contexts = MakeShared<FJsonObject>();
	Contexts->SetObjectField(TEXT("feedback"), Fb);
	Event->SetObjectField(TEXT("contexts"), Contexts);
	TArray<uint8> EventBytes;
	Append(EventBytes, JsonLine(Event));
	const TSharedRef<FJsonObject> FbHead = MakeShared<FJsonObject>();
	FbHead->SetStringField(TEXT("type"), TEXT("feedback"));
	FbHead->SetStringField(TEXT("content_type"), TEXT("application/json"));
	Item(Out, FbHead, EventBytes);

	for (const FEnvelopeAttachment& A : Attachments)
	{
		if (A.Bytes.Num() == 0) continue;
		const TSharedRef<FJsonObject> AHead = MakeShared<FJsonObject>();
		AHead->SetStringField(TEXT("type"), TEXT("attachment"));
		AHead->SetStringField(TEXT("filename"), A.Name);
		AHead->SetStringField(TEXT("content_type"), A.ContentType);
		Item(Out, AHead, A.Bytes);
	}
	return Out;
}

FString SailFeedback::ReproArgs(const FString& WorldId, const FString& BoatId, const FFeedbackSample& At, double WindKn)
{
	return FString::Printf(TEXT("-SailingWorld=%s -SailingBoat=%s \"-SailingStartAt=%.0f,%.0f,%.0f\" -SailingWind=%.0f -SailingTWA=%.0f"),
		*WorldId, *BoatId, At.North, At.East, At.HeadingDeg, WindKn, At.TwaDeg);
}

FString SailFeedback::ComposeMessage(const FFeedbackReport& R)
{
	const bool bBug = R.Kind == EFeedbackKind::Bug;
	FString Out = FString::Printf(TEXT("[%s] %s\n\n"), bBug ? TEXT("Bug") : TEXT("Idea"), R.Title.IsEmpty() ? TEXT("(no title)") : *R.Title);
	if (!R.WhatHappened.IsEmpty()) Out += FString::Printf(TEXT("%s\n%s\n\n"), bBug ? TEXT("What happened:") : TEXT("Idea:"), *R.WhatHappened);
	if (bBug && !R.Expected.IsEmpty()) Out += FString::Printf(TEXT("Expected:\n%s\n\n"), *R.Expected);
	for (const TPair<FString, FString>& C : R.Context) Out += FString::Printf(TEXT("%s: %s\n"), *C.Key, *C.Value);
	if (R.CarriesPlace() && !R.Repro.IsEmpty()) Out += FString::Printf(TEXT("Repro: %s\n"), *R.Repro);
	return SailCrashReports::ScrubPaths(Out);
}

FString SailFeedback::LogTail(int32 MaxLines)
{
	// The engine's log where the build writes one (editor, Development), else the game's session log (Shipping:
	// docs/session-log/).
	FString Text;
	const FString Path = SailSessionLog::ReportLogPath();
	if (GLog) GLog->Flush();
	if (!FFileHelper::LoadFileToString(Text, *Path, FFileHelper::EHashOptions::None, FILEREAD_AllowWrite)) return FString();
	TArray<FString> Lines;
	Text.ParseIntoArrayLines(Lines, false);
	const int32 First = FMath::Max(0, Lines.Num() - MaxLines);
	FString Out;
	for (int32 I = First; I < Lines.Num(); ++I) { Out += Lines[I]; Out += TEXT("\n"); }
	return SailCrashReports::ScrubPaths(Out);
}

FString SailFeedback::WriteLocal(const FFeedbackReport& R, const FString& Dir)
{
	const FString Folder = FPaths::Combine(Dir, FString::Printf(TEXT("%s-%s"), *FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S")), KindId(R.Kind)));
	if (!IFileManager::Get().MakeDirectory(*Folder, true)) return FString();
	bool bOk = FFileHelper::SaveStringToFile(ComposeMessage(R), *FPaths::Combine(Folder, TEXT("report.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	if (R.CarriesPlace())
	{
		if (!R.TelemetryJson.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(R.TelemetryJson, *FPaths::Combine(Folder, TEXT("telemetry.json")));
		if (!R.LogTail.IsEmpty()) bOk &= FFileHelper::SaveStringToFile(SailCrashReports::ScrubPaths(R.LogTail), *FPaths::Combine(Folder, TEXT("log.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
	if (R.Tags.Num())
	{
		TArray<FString> Keys;
		R.Tags.GetKeys(Keys);
		Keys.Sort();
		FString Json = TEXT("{");
		for (int32 I = 0; I < Keys.Num(); ++I)
			Json += FString::Printf(TEXT("%s\n  \"%s\": \"%s\""), I ? TEXT(",") : TEXT(""), *Keys[I], *R.Tags[Keys[I]].ReplaceCharWithEscapedChar());
		bOk &= FFileHelper::SaveStringToFile(Json + TEXT("\n}\n"), *FPaths::Combine(Folder, TEXT("tags.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	}
	for (int32 I = 0; I < R.ShotPaths.Num(); ++I)
	{
		if (IFileManager::Get().FileExists(*R.ShotPaths[I]))
			IFileManager::Get().Copy(*FPaths::Combine(Folder, FString::Printf(TEXT("shot%d%s"), I + 1, *FPaths::GetExtension(R.ShotPaths[I], true))), *R.ShotPaths[I]);
	}
	return bOk ? Folder : FString();
}

FString SailFeedback::LocalDir()
{
	return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Feedback"));
}

bool SailFeedback::ShotToJpeg(const FString& PngPath, const FString& JpegPath, int64 MaxBytes)
{
	TArray<uint8> Png;
	if (!FFileHelper::LoadFileToArray(Png, *PngPath)) return false;
	IImageWrapperModule& Images = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> In = Images.CreateImageWrapper(EImageFormat::PNG);
	TArray<uint8> Raw;
	if (!In.IsValid() || !In->SetCompressed(Png.GetData(), Png.Num()) || !In->GetRaw(ERGBFormat::BGRA, 8, Raw)) return false;
	int32 W = In->GetWidth(), H = In->GetHeight();
	for (int32 Pass = 0; Pass < 4; ++Pass)
	{
		for (const int32 Quality : { 85, 70, 55 })
		{
			TSharedPtr<IImageWrapper> Out = Images.CreateImageWrapper(EImageFormat::JPEG);
			if (!Out.IsValid() || !Out->SetRaw(Raw.GetData(), Raw.Num(), W, H, ERGBFormat::BGRA, 8)) return false;
			const TArray64<uint8>& Jpeg = Out->GetCompressed(Quality);
			if (Jpeg.Num() > 0 && Jpeg.Num() <= MaxBytes) return FFileHelper::SaveArrayToFile(Jpeg, *JpegPath);
		}
		// Still too big: half the size (box filter).
		const int32 W2 = FMath::Max(1, W / 2), H2 = FMath::Max(1, H / 2);
		TArray<uint8> Half;
		Half.SetNumUninitialized(W2 * H2 * 4);
		for (int32 Y = 0; Y < H2; ++Y)
			for (int32 X = 0; X < W2; ++X)
				for (int32 C = 0; C < 4; ++C)
				{
					const int32 Sx = FMath::Min(2 * X + 1, W - 1), Sy = FMath::Min(2 * Y + 1, H - 1);
					const int32 Sum = Raw[(2 * Y * W + 2 * X) * 4 + C] + Raw[(2 * Y * W + Sx) * 4 + C] + Raw[(Sy * W + 2 * X) * 4 + C] + Raw[(Sy * W + Sx) * 4 + C];
					Half[(Y * W2 + X) * 4 + C] = uint8(Sum / 4);
				}
		Raw = MoveTemp(Half);
		W = W2; H = H2;
	}
	return false;
}
